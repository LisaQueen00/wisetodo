import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import event

from alembic import command
from wisetodo.agent.handler import AgentResultHandler, ClarificationRequested, TodoCommitted
from wisetodo.agent.results import AGENT_RESULT_ADAPTER, AgentResult, TodoOperationResult
from wisetodo.database import Database, create_database
from wisetodo.sessions.models import SessionStatus
from wisetodo.sessions.state_machine import SessionEvent, next_status
from wisetodo.todos import TodoInput, TodoService


@pytest.fixture
def storage(tmp_path: Path) -> Iterator[tuple[Database, TodoService]]:
    url = f"sqlite:///{(tmp_path / 'handler.db').as_posix()}"
    config = Config(Path(__file__).resolve().parents[1] / "alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    database = create_database(url)
    try:
        yield database, TodoService(database.sessions)
    finally:
        database.dispose()


def create_result() -> AgentResult:
    return AGENT_RESULT_ADAPTER.validate_python(
        {
            "type": "todo_operation",
            "operation": {
                "action": "create",
                "todo": {"topic": "阅读", "items": ["第一章", "第二章"]},
            },
        }
    )


async def test_create_commits_one_todo_before_reporting_success(storage) -> None:
    database, service = storage
    outcome = await AgentResultHandler(service).handle(create_result())
    assert isinstance(outcome, TodoCommitted)
    assert outcome.message == "已创建：阅读"
    assert outcome.action == "create"
    assert next_status(SessionStatus.RUNNING, outcome.event) == SessionStatus.COMPLETED
    assert service.list() == [outcome.todo]
    assert all(not item.completed for item in outcome.todo.items)
    # Read through a fresh connection, not a cached identity map.
    reopened = create_database(str(database.engine.url))
    try:
        assert TodoService(reopened.sessions).get(outcome.todo.id) == outcome.todo
    finally:
        reopened.dispose()


@pytest.mark.parametrize(
    "changes",
    [
        {"topic": "新主题"},
        {"priority": 1},
        {"items": ["修改的第一章", "第二章"]},
    ],
)
async def test_update_reuses_service_semantics(storage, changes: dict) -> None:
    _, service = storage
    original = service.create(TodoInput(topic="阅读", items=["第一章", "第二章"]))
    service.set_item_completed(original.id, original.items[0].id, True)
    result = AGENT_RESULT_ADAPTER.validate_python(
        {
            "type": "todo_operation",
            "operation": {"action": "update", "todoId": original.id, "changes": changes},
        }
    )
    outcome = await AgentResultHandler(service).handle(result)
    assert isinstance(outcome, TodoCommitted)
    assert outcome.action == "update"
    assert outcome.todo.id == original.id
    assert outcome.todo.topic == changes.get("topic", original.topic)
    assert outcome.todo.priority == changes.get("priority", original.priority)
    assert outcome.todo.items[0].completed == ("items" not in changes)
    assert outcome.message == f"已修改：{outcome.todo.topic}"
    assert service.list() == [outcome.todo]


async def test_clarification_does_not_touch_todos(storage) -> None:
    _, service = storage
    original = service.create(TodoInput(topic="保留", items=["a", "b"]))
    result = AGENT_RESULT_ADAPTER.validate_python(
        {
            "type": "clarification",
            "question": " 请先选择一本书？ ",
        }
    )
    outcome = await AgentResultHandler(service).handle(result)
    assert isinstance(outcome, ClarificationRequested)
    assert outcome.message == "请先选择一本书？"
    assert outcome.event == SessionEvent.REQUEST_INPUT
    assert next_status(SessionStatus.RUNNING, outcome.event) == SessionStatus.WAITING_INPUT
    assert service.list() == [original]


async def test_missing_update_never_creates(storage) -> None:
    _, service = storage
    result = AGENT_RESULT_ADAPTER.validate_python(
        {
            "type": "todo_operation",
            "operation": {"action": "update", "todoId": "missing", "changes": {"priority": 1}},
        }
    )
    with pytest.raises(LookupError, match="Todo not found"):
        await AgentResultHandler(service).handle(result)
    assert service.list() == []


async def test_mutated_result_revalidated_before_write(storage) -> None:
    _, service = storage
    result = create_result()
    assert isinstance(result, TodoOperationResult)
    result.operation.todo.items.clear()
    with pytest.raises(ValidationError):
        await AgentResultHandler(service).handle(result)
    assert service.list() == []


async def test_tool_calls_are_not_final_results(storage) -> None:
    _, service = storage
    result = AGENT_RESULT_ADAPTER.validate_python(
        {
            "type": "tool_calls",
            "calls": [{"callId": "1", "tool": "read", "arguments": {}}],
        }
    )
    with pytest.raises(ValueError, match="tool executor"):
        await AgentResultHandler(service).handle(result)
    assert service.list() == []


async def test_cancellation_checkpoint_prevents_write(storage) -> None:
    _, service = storage
    task = asyncio.create_task(AgentResultHandler(service).handle(create_result()))
    await asyncio.sleep(0)  # Handler has entered and yielded at its checkpoint.
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert service.list() == []


@pytest.mark.parametrize("action", ["create", "update"])
async def test_commit_failure_rolls_back_without_success(storage, action: str) -> None:
    database, service = storage
    original = service.create(TodoInput(topic="保留", items=["a", "b"]))
    result = (
        create_result()
        if action == "create"
        else AGENT_RESULT_ADAPTER.validate_python(
            {
                "type": "todo_operation",
                "operation": {
                    "action": "update",
                    "todoId": original.id,
                    "changes": {"topic": "失败"},
                },
            }
        )
    )

    def fail_commit(session) -> None:
        raise RuntimeError("simulated commit failure")

    event.listen(database.sessions, "before_commit", fail_commit)
    try:
        with pytest.raises(RuntimeError, match="simulated commit failure"):
            await AgentResultHandler(service).handle(result)
    finally:
        event.remove(database.sessions, "before_commit", fail_commit)
    assert service.list() == [original]
