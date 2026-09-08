from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import select

from wisetodo.database import Database, initialize_database
from wisetodo.sessions.models import SessionStatus
from wisetodo.sessions.service import SessionReadOnlyError, SessionService
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


def test_completed_history_rejects_writes_using_database_state(database: Database) -> None:
    service = SessionService(database.sessions)
    stale = service.create("Original")
    with database.sessions.begin() as session:
        record = session.get_one(SessionRecord, stale.id)
        record.messages = [MessageRecord(position=0, role="user", content="Keep")]
        record.tool_events = [
            ToolEventRecord(
                position=0, run_id="run", call_id="call", tool_name="read", event_type="completed"
            )
        ]
        record.status = "completed"
    before = service.get(stale.id)
    assert stale.status == "ready"  # A caller's old snapshot cannot authorize writing.
    with pytest.raises(SessionReadOnlyError) as failure, service.write_history(stale.id):
        pytest.fail("The protected write body must never be entered")
    assert failure.value.session_id == stale.id
    assert service.get(stale.id) == before
    assert service.list()[0].status == "completed"
    new = service.create("Next")
    assert new.id != stale.id and new.status == "ready"
    assert service.delete(stale.id)
    assert service.get(new.id) == new


@pytest.mark.parametrize(
    "status", [state for state in SessionStatus if state != SessionStatus.COMPLETED]
)
def test_non_completed_history_accepts_transactional_writes(
    database: Database, status: SessionStatus
) -> None:
    service = SessionService(database.sessions)
    created = service.create()
    with database.sessions.begin() as session:
        session.get_one(SessionRecord, created.id).status = status
    with service.write_history(created.id) as record:
        record.messages.append(MessageRecord(position=0, role="system", content="Saved"))
    stored = service.get(created.id)
    assert stored is not None and stored.status == status
    assert stored.messages[0].content == "Saved"


def test_write_history_rolls_back_and_noop_preserves_timestamp(database: Database) -> None:
    service = SessionService(database.sessions)
    original = service.create("Keep")
    with service.write_history(original.id):
        pass
    assert service.get(original.id) == original
    with pytest.raises(RuntimeError), service.write_history(original.id) as record:
        record.label = "Must roll back"
        record.messages.append(MessageRecord(position=0, role="user", content="Must roll back"))
        record.status = "completed"
        raise RuntimeError("Save failed")
    assert service.get(original.id) == original
    with pytest.raises(LookupError), service.write_history("missing"):
        pytest.fail("Missing Session must not enter write body")


def test_completion_and_final_notification_can_commit_together(database: Database) -> None:
    service = SessionService(database.sessions)
    original = service.create()
    with database.sessions.begin() as session:
        session.get_one(SessionRecord, original.id).status = "running"
    with service.write_history(original.id) as record:
        record.messages.append(MessageRecord(position=0, role="assistant", content="已创建"))
        record.status = "completed"
    stored = service.get(original.id)
    assert stored is not None and stored.status == "completed"
    assert stored.messages[0].content == "已创建"
    with pytest.raises(SessionReadOnlyError), service.write_history(original.id):
        pytest.fail("No writes after completion")
