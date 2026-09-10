import pytest
from test_agent_runtime import Scope, create_output, message

from wisetodo.agent.history import (
    CLIPPED,
    HISTORY_MAX_CHARS,
    HISTORY_MAX_MESSAGES,
    MESSAGE_MAX_CHARS,
    OMITTED,
    bounded_history,
)
from wisetodo.agent.runtime import AgentRuntime
from wisetodo.database import initialize_database
from wisetodo.model.contracts import ModelMessage
from wisetodo.sessions.service import SessionService
from wisetodo.sessions.tables import MessageRecord
from wisetodo.todos import TodoService


@pytest.mark.parametrize("size", [0, 1, 64, 65, 1000])
def test_count_limit_order_and_no_mutation(size):
    messages = [ModelMessage(role="user", content=f"message-{i}") for i in range(size)]
    before = [row.model_dump() for row in messages]
    result = bounded_history(messages)
    assert len(result) <= HISTORY_MAX_MESSAGES
    assert sum(len(row.content) for row in result) <= HISTORY_MAX_CHARS
    assert [row.model_dump() for row in messages] == before
    if size <= 64:
        assert result == messages
    else:
        assert result[0].content == OMITTED + "message-0"
        assert result[1:] == messages[-63:]


@pytest.mark.parametrize("size", [MESSAGE_MAX_CHARS, MESSAGE_MAX_CHARS + 1, 100_000])
def test_single_unicode_message_boundary(size):
    content = "开始" + "🙂章" * ((size - 4) // 2) + "结尾"
    content += "末" * (size - len(content))
    result = bounded_history([ModelMessage(role="user", content=content)])[0].content
    if size <= MESSAGE_MAX_CHARS:
        assert result == content
    else:
        assert result.startswith(OMITTED + "开始")
        assert result.endswith(content[-10:])
        assert CLIPPED in result
        assert len(result) == MESSAGE_MAX_CHARS + len(OMITTED)


def test_character_budget_preserves_goal_and_latest_contiguous_suffix():
    messages = [
        ModelMessage(role="user" if i % 2 == 0 else "assistant", content=f"{i}:" + "文" * 7000)
        for i in range(100)
    ]
    result = bounded_history(messages)
    assert sum(len(row.content) for row in result) <= HISTORY_MAX_CHARS
    assert result[0].content == OMITTED + messages[0].content
    assert result[1:] == messages[-(len(result) - 1) :]
    assert result[-1] == messages[-1]


def test_system_instructions_cannot_be_trimmed_as_history():
    with pytest.raises(ValueError):
        bounded_history([ModelMessage(role="system", content="rules")])


@pytest.mark.parametrize("mode", ["native", "prompt_compat"])
async def test_runtime_limits_only_model_history_and_keeps_database(tmp_path, mode):
    database = initialize_database(tmp_path / "history.db")
    try:
        sessions = SessionService(database.sessions)
        todos = TodoService(database.sessions)
        scope = Scope(create_output())
        sessions.agent_executor = AgentRuntime(sessions, todos, scope, mode=mode)
        other = sessions.create()
        sessions.send_message(other.id, message("OTHER_SESSION_SECRET"))
        session = sessions.create()
        with sessions.write_history(session.id) as record:
            record.messages.extend(
                MessageRecord(
                    position=i,
                    role="user" if i % 2 == 0 else "assistant",
                    content=f"history-{i}:" + "文" * 3000,
                )
                for i in range(100)
            )
        before = sessions.get(session.id).messages
        await sessions.submit(session.id, message("LATEST_GOAL"))
        request = scope.requests[0]
        chat = request.messages[1:-1]  # system rules and target snapshot are separate
        assert sum(len(row.content) for row in chat) <= HISTORY_MAX_CHARS
        assert len(chat) <= HISTORY_MAX_MESSAGES
        assert "history-0:" in chat[0].content and OMITTED in chat[0].content
        assert chat[-1].content == "LATEST_GOAL"
        assert "应用提供的本次编辑目标资料" in request.messages[-1].content
        assert "OTHER_SESSION_SECRET" not in str(request)
        assert sessions.get(session.id).messages[:100] == before
        assert len(scope.requests) == 1  # no model-based summarization
    finally:
        database.dispose()
