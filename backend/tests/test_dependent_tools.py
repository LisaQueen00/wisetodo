import json

import pytest
from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError
from test_agent_runtime import Scope, create_output, message
from test_github_tools import github_api  # noqa: F401

from wisetodo.agent.runtime import AgentRuntime
from wisetodo.database import initialize_database
from wisetodo.model.contracts import ModelResponse, ToolCall
from wisetodo.sessions.retry import RetryExecutionError
from wisetodo.sessions.service import SessionService
from wisetodo.sessions.tables import SessionRecord
from wisetodo.todos import TodoService


@pytest.mark.parametrize("mode", ["native", "prompt_compat"])
async def test_search_rounds_are_bounded(tmp_path, mode, request):
    request.getfixturevalue("github_api")

    class Provider(Scope):
        async def complete(self, model_request):
            self.requests.append(model_request)
            step = len(self.requests)
            if step == 4:
                assert not model_request.tools
                return ModelResponse(
                    finish_reason="stop",
                    content=json.dumps(
                        {"type": "clarification", "question": "请选择一个候选项目。"}
                    ),
                )
            args = {"query": f"cli {step}"}
            if mode == "native":
                return ModelResponse(
                    finish_reason="tool_calls",
                    tool_calls=(
                        ToolCall(id=str(step), name="search_projects", arguments=json.dumps(args)),
                    ),
                )
            return ModelResponse(
                finish_reason="stop",
                content=json.dumps(
                    {
                        "type": "tool_calls",
                        "calls": [
                            {"callId": str(step), "tool": "search_projects", "arguments": args}
                        ],
                    }
                ),
            )

    db = initialize_database(tmp_path / "bounded.db")
    try:
        sessions, todos, provider = (
            SessionService(db.sessions),
            TodoService(db.sessions),
            Provider(),
        )
        sessions.agent_executor = AgentRuntime(
            sessions,
            todos,
            provider,
            mode=mode,
            tool_config=tmp_path / "tools.json",
            optional_tool_config=True,
        )
        result = await sessions.submit(sessions.create().id, message("推荐项目"))
        assert result.status == "waiting_input" and not todos.list()
        assert len(result.tool_events) == 6 and len(provider.requests) == 4
    finally:
        db.dispose()


@pytest.mark.parametrize("mode", ["native", "prompt_compat"])
@pytest.mark.parametrize("commit_failure", [False, True])
async def test_search_then_read_then_commit_in_one_run(tmp_path, mode, request, commit_failure):
    github_requests = request.getfixturevalue("github_api")

    class Provider(Scope):
        async def complete(self, request):
            self.requests.append(request)
            step = len(self.requests)
            if step == 3:
                assert request.tools  # Repository details can now be requested before committing.
                assert "src/cli.py" in request.messages[-1].content
                return ModelResponse(content=json.dumps(create_output()), finish_reason="stop")
            if step == 2:
                assert "sample/cli" in request.messages[-1].content
            name = "search_projects" if step == 1 else "read_github_project"
            args = (
                {"query": "sample cli"} if step == 1 else {"url": "https://github.com/sample/cli"}
            )
            if mode == "native":
                return ModelResponse(
                    finish_reason="tool_calls",
                    tool_calls=(
                        ToolCall(id=f"step-{step}", name=name, arguments=json.dumps(args)),
                    ),
                )
            return ModelResponse(
                finish_reason="stop",
                content=json.dumps(
                    {
                        "type": "tool_calls",
                        "calls": [{"callId": f"step-{step}", "tool": name, "arguments": args}],
                    }
                ),
            )

    database = initialize_database(tmp_path / "db.sqlite")
    try:
        sessions, todos, provider = (
            SessionService(database.sessions),
            TodoService(database.sessions),
            Provider(),
        )
        sessions.agent_executor = AgentRuntime(
            sessions,
            todos,
            provider,
            mode=mode,
            tool_config=tmp_path / "tools.json",
            optional_tool_config=True,
        )
        session = sessions.create()

        def fail_commit(tx):
            if any(
                isinstance(row, SessionRecord) and row.status == "completed"
                for row in tx.identity_map.values()
            ):
                raise SQLAlchemyError("simulated failure")

        if commit_failure:
            event.listen(database.sessions, "before_commit", fail_commit)
            try:
                with pytest.raises(RetryExecutionError):
                    await sessions.submit(session.id, message("学习 sample CLI 项目"))
            finally:
                event.remove(database.sessions, "before_commit", fail_commit)
            assert not todos.list()
            result = await sessions.retry(session.id)
        else:
            result = await sessions.submit(session.id, message("学习 sample CLI 项目"))
        assert result.status == "completed"
        assert len(todos.list()) == 1
        assert [e.event_type for e in result.tool_events] == ["started", "completed"] * 2
        assert len(provider.requests) == 3
        assert provider.opens == provider.closes == 1
        assert github_requests[0].url.path == "/search/repositories"
    finally:
        database.dispose()
