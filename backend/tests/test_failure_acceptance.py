"""Offline fault acceptance across Session, Runtime, persistence and safe errors."""

import asyncio

import pytest
from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError
from test_agent_runtime import Scope, create_output, message

from wisetodo.agent.runtime import AgentRuntime
from wisetodo.database import initialize_database
from wisetodo.ipc.messages import IpcRequest
from wisetodo.ipc.server import dispatch
from wisetodo.ipc.sessions import SessionRequestError
from wisetodo.model.provider import ModelRequestError
from wisetodo.sessions.service import SessionService
from wisetodo.sessions.tables import SessionRecord
from wisetodo.todos import TodoInput, TodoService


@pytest.fixture
def db(tmp_path):
    database = initialize_database(tmp_path / "acceptance.db")
    yield database
    database.dispose()


def setup(db, provider, mode):
    sessions, todos = SessionService(db.sessions), TodoService(db.sessions)
    sessions.agent_executor = AgentRuntime(sessions, todos, provider, mode=mode)
    return sessions, todos


@pytest.mark.parametrize("mode", ["native", "prompt_compat"])
@pytest.mark.parametrize("fault", ["model", "invalid", "repair_success"])
async def test_model_fault_safe_ipc_and_explicit_retry(db, mode, fault):
    invalid = {
        "type": "todo_operation",
        "operation": {
            "action": "create",
            "todo": {"topic": "PRIVATE_OUTPUT", "items": ["only one"]},
        },
    }
    outputs = (
        [ModelRequestError()]
        if fault == "model"
        else [invalid, invalid]
        if fault == "invalid"
        else [invalid, create_output()]
    )
    provider = Scope(*outputs)
    sessions, todos = setup(db, provider, mode)
    session = sessions.create()
    incoming = message()
    request = IpcRequest(
        requestId="test",
        method="user.sessions.send",
        params={
            "session_id": session.id,
            "message": incoming.model_dump(mode="json"),
        },
    )
    if fault == "repair_success":
        await dispatch(request, todos, sessions)
        assert sessions.get(session.id).status == "completed"
        assert len(todos.list()) == 1
    else:
        with pytest.raises(SessionRequestError) as caught:
            await dispatch(request, todos, sessions)
        assert caught.value.error.code == (
            "MODEL_REQUEST_FAILED" if fault == "model" else "INVALID_AGENT_OUTPUT"
        )
        assert "PRIVATE" not in caught.value.error.model_dump_json()
        assert sessions.get(session.id).status == "failed"
        assert todos.list() == []
        with db.sessions() as tx:
            row = tx.get(SessionRecord, session.id)
            assert row.pending_operation is None and row.active_run_id is None
        # No automatic retry of request failure; invalid output has only one repair.
        assert len(provider.requests) == (1 if fault == "model" else 2)
        assert provider.opens == provider.closes == 1
        provider.outputs.append(create_output())
        assert (await sessions.retry(session.id)).status == "completed"
        assert provider.opens == provider.closes == 2
        assert len(todos.list()) == 1
        # Replayed submission ID returns history; it must not re-run the model.
        calls = len(provider.requests)
        assert (await sessions.submit(session.id, incoming)).status == "completed"
        assert len(provider.requests) == calls
    if fault != "model":
        assert "唯一一次修复机会" in provider.requests[1].messages[-1].content


@pytest.mark.parametrize("mode", ["native", "prompt_compat"])
async def test_cancel_during_output_repair_releases_provider_and_preserves_history(db, mode):
    entered = asyncio.Event()
    provider = Scope({"type": "invalid"}, create_output())

    async def block_second_call():
        if len(provider.requests) == 2:
            entered.set()
            await asyncio.Future()

    provider.hook = block_second_call
    sessions, todos = setup(db, provider, mode)
    session = sessions.create()
    task = asyncio.create_task(sessions.submit(session.id, message()))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        with db.sessions() as tx:
            run_id = tx.get(SessionRecord, session.id).active_run_id
        assert sessions.cancel(session.id, run_id)
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 5)
        history = sessions.get(session.id)
        assert history.status == "cancelled" and len(history.messages) == 1
        assert todos.list() == []
        assert provider.opens == provider.closes == 1
        with db.sessions() as tx:
            assert tx.get(SessionRecord, session.id).pending_operation is None
        provider.hook = None
        assert (await sessions.retry(session.id)).status == "completed"
        assert len(todos.list()) == 1
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("mode", ["native", "prompt_compat"])
async def test_failed_update_rolls_back_children_then_retries_without_model(db, mode):
    provider = Scope()
    sessions, todos = setup(db, provider, mode)
    original = todos.create(TodoInput(topic="原始任务", priority=1, items=["甲", "乙"]))
    original = todos.set_item_completed(original.id, original.items[0].id, True)
    provider.outputs.append(
        {
            "type": "todo_operation",
            "operation": {
                "action": "update",
                "todoId": original.id,
                "changes": {"topic": "更新任务", "items": ["甲", "丙"]},
            },
        }
    )
    session = sessions.create()

    def fail_commit(tx):
        if any(
            isinstance(row, SessionRecord) and row.status == "completed"
            for row in tx.identity_map.values()
        ):
            raise SQLAlchemyError("PRIVATE_DATABASE_EXCEPTION")

    event.listen(db.sessions, "before_commit", fail_commit)
    try:
        request = IpcRequest(
            requestId="update",
            method="user.sessions.send",
            params={
                "session_id": session.id,
                "message": message(todo_id=original.id).model_dump(mode="json"),
            },
        )
        with pytest.raises(SessionRequestError) as caught:
            await dispatch(request, todos, sessions)
        assert caught.value.error.code == "TODO_SAVE_FAILED"
        assert "PRIVATE" not in caught.value.error.model_dump_json()
    finally:
        event.remove(db.sessions, "before_commit", fail_commit)
    assert todos.get(original.id) == original
    assert len(sessions.get(session.id).messages) == 1
    with db.sessions() as tx:
        assert tx.get(SessionRecord, session.id).pending_operation is not None
    no_model = Scope()
    restarted, saved = setup(db, no_model, mode)
    assert (await restarted.retry(session.id)).status == "completed"
    assert no_model.opens == 0
    updated = saved.get(original.id)
    assert updated.topic == "更新任务" and updated.priority == 1
    assert [item.topic for item in updated.items] == ["甲", "丙"]
    assert updated.items[0].id == original.items[0].id and updated.items[0].completed
    assert not updated.items[1].completed
    assert len(saved.list()) == 1
    with pytest.raises(PermissionError):
        await restarted.retry(session.id)
