import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError

from wisetodo.agent.runtime import AgentRuntime
from wisetodo.database import initialize_database
from wisetodo.model.contracts import ModelResponse
from wisetodo.sessions.models import ChatInput
from wisetodo.sessions.retry import RetryExecutionError
from wisetodo.sessions.service import SessionService
from wisetodo.sessions.tables import SessionRecord
from wisetodo.todos import TodoChanges, TodoInput, TodoService


def create_output(topic="阅读"):
    return {
        "type": "todo_operation",
        "operation": {
            "action": "create",
            "todo": {
                "topic": topic,
                "items": ["第一章", "第二章"],
            },
        },
    }


class Scope:
    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.requests = []
        self.opens = 0
        self.closes = 0
        self.hook = None

    @asynccontextmanager
    async def open(self):
        self.opens += 1
        try:
            yield self
        finally:
            self.closes += 1

    async def complete(self, request):
        self.requests.append(request)
        if self.hook:
            await self.hook()
        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        return ModelResponse(content=json.dumps(output), finish_reason="stop")


def services(db, scope):
    sessions = SessionService(db.sessions)
    todos = TodoService(db.sessions)
    sessions.agent_executor = AgentRuntime(sessions, todos, scope)
    return sessions, todos


@pytest.fixture
def database(tmp_path):
    db = initialize_database(tmp_path / "runtime.db")
    yield db
    db.dispose()


def message(text="读书", todo_id=None):
    return ChatInput(message_id=uuid4(), content=text, todo_id=todo_id)


async def test_submit_create_complete_readonly_and_deduplicate(database):
    scope = Scope(create_output())
    sessions, todos = services(database, scope)
    session = sessions.create()
    incoming = message()
    result = await sessions.submit(session.id, incoming)
    assert result.status == "completed"
    assert result.messages[-1].content == "已创建：阅读"
    assert len(todos.list()) == 1
    assert scope.opens == scope.closes == 1
    assert await sessions.submit(session.id, incoming) == result
    assert len(scope.requests) == 1
    with pytest.raises(PermissionError):
        await sessions.submit(session.id, message("new"))
    with database.sessions() as tx:
        record = tx.get(SessionRecord, session.id)
        assert record.pending_operation is None and record.active_run_id is None


async def test_clarification_then_completion_uses_only_this_session(database):
    scope = Scope({"type": "clarification", "question": "哪本书？"}, create_output())
    sessions, todos = services(database, scope)
    other = sessions.create()
    sessions.send_message(other.id, message("secret other session"))
    session = sessions.create()
    result = await sessions.submit(session.id, message())
    assert result.status == "waiting_input" and todos.list() == []
    result = await sessions.submit(session.id, message("Python书"))
    assert result.status == "completed" and len(result.messages) == 4
    content = "\n".join(m.content for m in scope.requests[-1].messages)
    assert "哪本书？" in content and "secret other session" not in content


async def test_update_selected_target_preserves_unmodified_fields(database):
    scope = Scope()
    sessions, todos = services(database, scope)
    original = todos.create(TodoInput(topic="old", priority=1, items=["a", "b"]))
    scope.outputs.append(
        {
            "type": "todo_operation",
            "operation": {
                "action": "update",
                "todoId": original.id,
                "changes": {"topic": "new"},
            },
        }
    )
    result = await sessions.submit(sessions.create().id, message(todo_id=original.id))
    assert result.status == "completed"
    assert todos.get(original.id).topic == "new"
    assert todos.get(original.id).priority == 1
    assert len(todos.list()) == 1


async def test_commit_failure_is_atomic_and_restart_retry_never_opens_model(database):
    scope = Scope(create_output())
    sessions, todos = services(database, scope)
    session = sessions.create()

    def fail_commit(tx):
        if any(
            isinstance(row, SessionRecord) and row.status == "completed"
            for row in tx.identity_map.values()
        ):
            raise SQLAlchemyError("simulated commit failure")

    event.listen(database.sessions, "before_commit", fail_commit)
    try:
        with pytest.raises(RetryExecutionError):
            await sessions.submit(session.id, message())
    finally:
        event.remove(database.sessions, "before_commit", fail_commit)
    assert todos.list() == []
    failed = sessions.get(session.id)
    assert failed.status == "failed" and len(failed.messages) == 1
    with database.sessions() as tx:
        assert tx.get(SessionRecord, session.id).pending_operation is not None
    reopened = initialize_database(Path(database.engine.url.database))
    try:
        no_model = Scope()
        restarted, saved = services(reopened, no_model)
        result = await restarted.retry(session.id)
        assert result.status == "completed" and len(saved.list()) == 1
        assert no_model.opens == 0
        with pytest.raises(PermissionError):
            await restarted.retry(session.id)
        assert len(saved.list()) == 1
    finally:
        reopened.dispose()


async def test_cancel_pending_model_and_reject_concurrent_run(database):
    scope = Scope(create_output())
    sessions, todos = services(database, scope)
    session = sessions.create()
    started = asyncio.Event()

    async def wait():
        started.set()
        await asyncio.Event().wait()

    scope.hook = wait
    task = asyncio.create_task(sessions.submit(session.id, message()))
    await asyncio.wait_for(started.wait(), 2)
    with pytest.raises(ValueError):
        await sessions.submit(session.id, message("another"))
    with database.sessions() as tx:
        run_id = tx.get(SessionRecord, session.id).active_run_id
    assert not sessions.cancel(session.id, "stale")
    assert sessions.cancel(session.id, run_id)
    with pytest.raises(asyncio.CancelledError):
        await task
    assert sessions.get(session.id).status == "cancelled" and todos.list() == []
    assert scope.closes == 1


async def test_manual_change_during_generation_never_overwritten(database):
    scope = Scope()
    sessions, todos = services(database, scope)
    original = todos.create(TodoInput(topic="old", items=["a", "b"]))
    scope.outputs.append(
        {
            "type": "todo_operation",
            "operation": {
                "action": "update",
                "todoId": original.id,
                "changes": {"topic": "model"},
            },
        }
    )

    async def edit():
        todos.update(original.id, TodoChanges(topic="manual"))

    scope.hook = edit
    with pytest.raises(RetryExecutionError):
        await sessions.submit(sessions.create().id, message(todo_id=original.id))
    assert todos.get(original.id).topic == "manual"


async def test_model_failure_retry_uses_model_again(database):
    scope = Scope(RuntimeError("failed"), create_output())
    sessions, todos = services(database, scope)
    session = sessions.create()
    with pytest.raises(RetryExecutionError):
        await sessions.submit(session.id, message())
    assert todos.list() == []
    assert (await sessions.retry(session.id)).status == "completed"
    assert scope.opens == 2


async def test_recovered_pending_run_commits_without_model(database):
    scope = Scope()
    sessions, todos = services(database, scope)
    session = sessions.create()
    sessions.send_message(session.id, message())
    with database.sessions.begin() as tx:
        record = tx.get(SessionRecord, session.id)
        record.status = "running"
        record.active_run_id = str(uuid4())
        record.pending_operation = {"result": create_output(), "target": None}
    assert sessions.recover_interrupted() == 1
    assert (await sessions.retry(session.id)).status == "completed"
    assert len(todos.list()) == 1 and scope.opens == 0


async def test_new_input_discards_old_pending_result(database):
    scope = Scope(create_output("新需求"))
    sessions, todos = services(database, scope)
    session = sessions.create()
    sessions.send_message(session.id, message())
    with database.sessions.begin() as tx:
        record = tx.get(SessionRecord, session.id)
        record.status = "failed"
        record.pending_operation = {"result": create_output("旧需求"), "target": None}
    await sessions.submit(session.id, message("换个任务"))
    assert [todo.topic for todo in todos.list()] == ["新需求"]
    assert scope.opens == 1


async def test_stale_run_cannot_commit(database):
    scope = Scope()
    sessions, todos = services(database, scope)
    session = sessions.create()
    sessions.send_message(session.id, message())
    with database.sessions.begin() as tx:
        record = tx.get(SessionRecord, session.id)
        record.status = "running"
        record.active_run_id = "new-run"
        record.pending_operation = {"result": create_output(), "target": None}
    with pytest.raises(ValueError):
        sessions.agent_executor._commit(
            session.id, "stale-run", {"result": create_output(), "target": None}
        )
    assert todos.list() == []
    assert sessions.get(session.id).status == "running"


async def test_cancel_after_generation_retains_pending_but_does_not_commit(database):
    class CancelOnClose(Scope):
        @asynccontextmanager
        async def open(self):
            self.opens += 1
            yield self
            self.closes += 1
            asyncio.current_task().cancel()

    scope = CancelOnClose(create_output())
    sessions, todos = services(database, scope)
    session = sessions.create()
    task = asyncio.create_task(sessions.submit(session.id, message()))
    with pytest.raises(asyncio.CancelledError):
        await task
    assert todos.list() == [] and sessions.get(session.id).status == "cancelled"
    with database.sessions() as tx:
        assert tx.get(SessionRecord, session.id).pending_operation is not None
    restarted, _ = services(database, Scope())
    assert (await restarted.retry(session.id)).status == "completed"


@pytest.mark.parametrize("selected", [False, True])
async def test_model_cannot_choose_unselected_update_target(database, selected):
    scope = Scope()
    sessions, todos = services(database, scope)
    target = todos.create(TodoInput(topic="keep", items=["a", "b"]))
    other = todos.create(TodoInput(topic="other", items=["a", "b"]))
    scope.outputs.append(
        {
            "type": "todo_operation",
            "operation": {
                "action": "update",
                "todoId": other.id,
                "changes": {"topic": "bad"},
            },
        }
    )
    with pytest.raises(RetryExecutionError):
        await sessions.submit(
            sessions.create().id, message(todo_id=target.id if selected else None)
        )
    assert todos.get(other.id).topic == "other"


async def test_deleted_target_is_not_recreated_by_pending_retry(database):
    from wisetodo.todos import TodoCaller

    scope = Scope()
    sessions, todos = services(database, scope)
    target = todos.create(TodoInput(topic="old", items=["a", "b"]))
    session = sessions.create()
    sessions.send_message(session.id, message(todo_id=target.id))
    with database.sessions.begin() as tx:
        record = tx.get(SessionRecord, session.id)
        record.status = "failed"
        record.pending_operation = {
            "target": target.model_dump(mode="json"),
            "result": {
                "type": "todo_operation",
                "operation": {"action": "update", "todoId": target.id, "changes": {"topic": "new"}},
            },
        }
    todos.delete(target.id, caller=TodoCaller.USER)
    with pytest.raises(RetryExecutionError):
        await sessions.retry(session.id)
    assert todos.list() == [] and scope.opens == 0


async def test_real_provider_stream_through_graph_and_commit(database):
    import httpx2

    from wisetodo.model.openai_provider import OpenAIProvider
    from wisetodo.model.runtime import RunProviderScope
    from wisetodo.settings import ResolvedSettings

    settings = ResolvedSettings(base_url="http://local.invalid/v1", model="mock")

    class Settings:
        def resolve(self):
            return settings

    class Stream(httpx2.AsyncByteStream):
        async def __aiter__(self):
            payload = {
                "id": "test",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": "mock",
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": json.dumps(create_output())},
                        "finish_reason": "stop",
                    }
                ],
            }
            yield ("data: " + json.dumps(payload) + "\n\ndata: [DONE]\n\n").encode()

    calls = []

    def transport(request):
        calls.append(json.loads(request.content))
        return httpx2.Response(200, headers={"content-type": "text/event-stream"}, stream=Stream())

    scope = RunProviderScope(
        Settings(),
        lambda config: OpenAIProvider(
            config,
            transport=httpx2.MockTransport(transport),
        ),
    )
    sessions, todos = services(database, scope)
    result = await sessions.submit(sessions.create().id, message())
    assert result.status == "completed" and len(todos.list()) == 1
    assert len(calls) == 1 and calls[0]["stream"] is True
