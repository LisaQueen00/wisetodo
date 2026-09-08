from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import select

from wisetodo.database import Database, initialize_database
from wisetodo.sessions.service import SessionService
from wisetodo.sessions.tables import MessageRecord, SessionRecord, ToolEventRecord
from wisetodo.todos import TodoInput, TodoService


@pytest.fixture
def database(tmp_path: Path) -> Iterator[Database]:
    database = initialize_database(tmp_path / "sessions.db")
    try:
        yield database
    finally:
        database.dispose()


def test_create_list_get_and_reopen(database: Database, tmp_path: Path) -> None:
    service = SessionService(database.sessions)
    assert service.list() == []
    first = service.create("  学习 📖  ")
    second = service.create()
    assert first.label == "学习 📖" and first.status == "ready"
    assert first.messages == [] and first.tool_events == []
    assert second.label == "" and first.id != second.id
    summaries = service.list()
    assert {row.id for row in summaries} == {first.id, second.id}
    assert "messages" not in summaries[0].model_dump()
    assert service.get(first.id) == first
    assert service.get("missing") is None
    reopened = initialize_database(tmp_path / "sessions.db")
    try:
        assert SessionService(reopened.sessions).get(first.id) == first
    finally:
        reopened.dispose()


def test_history_read_is_ordered_and_does_not_change_state(database: Database) -> None:
    service = SessionService(database.sessions)
    created = service.create()
    with database.sessions.begin() as session:
        record = session.get_one(SessionRecord, created.id)
        record.status = "completed"
        record.messages = [
            MessageRecord(position=1, role="assistant", content="已创建"),
            MessageRecord(position=0, role="user", content="Read", attachments=["D:/book.pdf"]),
        ]
        record.tool_events = [
            ToolEventRecord(
                position=0,
                run_id="run",
                call_id="call",
                tool_name="reader",
                event_type="completed",
                payload={"result": "章节"},
            )
        ]
    history = service.get(created.id)
    assert history is not None and history.status == "completed"
    assert [message.content for message in history.messages] == ["Read", "已创建"]
    assert history.messages[0].attachments == ["D:/book.pdf"]
    assert history.tool_events[0].payload == {"result": "章节"}
    assert service.get(created.id) == history


def test_delete_cascades_but_preserves_todos_and_other_sessions(database: Database) -> None:
    service = SessionService(database.sessions)
    todos = TodoService(database.sessions)
    todo = todos.create(TodoInput(topic="Keep", items=["One", "Two"]))
    first, other = service.create(), service.create()
    with database.sessions.begin() as session:
        session.add(MessageRecord(session_id=first.id, position=0, role="user", content="Delete"))
        session.add(
            ToolEventRecord(
                session_id=first.id,
                position=0,
                run_id="run",
                call_id="call",
                tool_name="read",
                event_type="started",
            )
        )
    assert service.delete(first.id)
    assert not service.delete(first.id)
    assert service.get(first.id) is None
    assert service.get(other.id) == other
    assert todos.get(todo.id) == todo
    with database.sessions() as session:
        assert list(session.scalars(select(MessageRecord))) == []
        assert list(session.scalars(select(ToolEventRecord))) == []


def test_running_session_cannot_be_deleted(database: Database) -> None:
    service = SessionService(database.sessions)
    created = service.create()
    with database.sessions.begin() as session:
        session.get_one(SessionRecord, created.id).status = "running"
    before = service.get(created.id)
    with pytest.raises(ValueError, match="Stop"):
        service.delete(created.id)
    assert service.get(created.id) == before
