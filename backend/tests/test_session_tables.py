from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import delete, inspect, select
from sqlalchemy.exc import IntegrityError

from alembic import command
from wisetodo.database import Base, Database, create_database, initialize_database
from wisetodo.sessions.models import MessageRole, SessionStatus, ToolEventType
from wisetodo.sessions.tables import MessageRecord, SessionRecord, ToolEventRecord
from wisetodo.todos import TodoInput, TodoService


@pytest.fixture
def database(tmp_path: Path) -> Iterator[Database]:
    database = initialize_database(tmp_path / "history.db")
    try:
        yield database
    finally:
        database.dispose()


def event(position: int, **changes: object) -> ToolEventRecord:
    return ToolEventRecord(
        **{
            "position": position,
            "run_id": "run-1",
            "call_id": "call-1",
            "tool_name": "parse_pdf",
            "event_type": ToolEventType.STARTED,
            **changes,
        }
    )


def test_schema_matches_metadata_and_has_no_todo_foreign_key(database: Database) -> None:
    with database.engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    inspector = inspect(database.engine)
    assert inspector.get_foreign_keys("sessions") == []
    for name in ["messages", "tool_events"]:
        fk = inspector.get_foreign_keys(name)
        assert len(fk) == 1
        assert fk[0]["referred_table"] == "sessions"
        assert fk[0]["options"]["ondelete"] == "CASCADE"


def test_ordered_history_and_json_survive_reopen(database: Database, tmp_path: Path) -> None:
    with database.sessions.begin() as session:
        record = SessionRecord(label="阅读 📖")
        record.messages = [
            MessageRecord(position=1, role=MessageRole.ASSISTANT, content="请问是哪本书？"),
            MessageRecord(
                position=0,
                role=MessageRole.USER,
                content="阅读计划\n保留原文",
                attachments=["D:/书籍/示例.pdf"],
            ),
        ]
        record.tool_events = [
            event(1, event_type=ToolEventType.COMPLETED, payload={"result": ["第一章", "第二章"]}),
            event(0, payload={"arguments": {"file_ref": "D:/书籍/示例.pdf"}}),
        ]
        session.add(record)
        session.flush()
        record_id = record.id
        assert record.status == SessionStatus.READY
        assert record.created_at is not None and record.updated_at is not None
    reopened = initialize_database(tmp_path / "history.db")
    try:
        with reopened.sessions() as session:
            stored = session.get_one(SessionRecord, record_id)
            assert stored.label == "阅读 📖"
            assert [message.position for message in stored.messages] == [0, 1]
            assert stored.messages[0].content == "阅读计划\n保留原文"
            assert stored.messages[0].attachments == ["D:/书籍/示例.pdf"]
            assert stored.messages[1].attachments == []
            assert [item.event_type for item in stored.tool_events] == ["started", "completed"]
            assert stored.tool_events[1].payload == {"result": ["第一章", "第二章"]}
    finally:
        reopened.dispose()


@pytest.mark.parametrize("use_orm", [True, False])
def test_deleting_history_cascades_without_deleting_todos(
    database: Database, use_orm: bool
) -> None:
    todos = TodoService(database.sessions)
    todo = todos.create(TodoInput(topic="Keep me", items=["One", "Two"]))
    with database.sessions.begin() as session:
        first = SessionRecord(
            messages=[MessageRecord(position=0, role="user", content="Hi")], tool_events=[event(0)]
        )
        other = SessionRecord(messages=[MessageRecord(position=0, role="user", content="Keep")])
        session.add_all([first, other])
        session.flush()
        first_id, other_id = first.id, other.id
    with database.sessions.begin() as session:
        if use_orm:
            record = session.get_one(SessionRecord, first_id)
            assert record.messages and record.tool_events  # Also exercise loaded relationships.
            session.delete(record)
        else:
            session.execute(delete(SessionRecord).where(SessionRecord.id == first_id))
    with database.sessions() as session:
        assert session.get(SessionRecord, first_id) is None
        assert list(session.scalars(select(ToolEventRecord))) == []
        assert [message.session_id for message in session.scalars(select(MessageRecord))] == [
            other_id
        ]
    assert todos.get(todo.id) == todo


@pytest.mark.parametrize(
    "invalid",
    [
        "status",
        "role",
        "event_type",
        "message_position",
        "event_position",
        "duplicate_message",
        "duplicate_event",
        "orphan_message",
        "orphan_event",
    ],
)
def test_database_rejects_invalid_history(database: Database, invalid: str) -> None:
    with pytest.raises(IntegrityError), database.sessions.begin() as session:
        record = SessionRecord()
        message = MessageRecord(position=0, role="user", content="Hello")
        tool = event(0)
        record.messages = [message]
        record.tool_events = [tool]
        if invalid == "status":
            record.status = "unknown"
        elif invalid == "role":
            message.role = "unknown"
        elif invalid == "event_type":
            tool.event_type = "unknown"
        elif invalid == "message_position":
            message.position = -1
        elif invalid == "event_position":
            tool.position = -1
        elif invalid == "duplicate_message":
            record.messages.append(MessageRecord(position=0, role="assistant", content="Duplicate"))
        elif invalid == "duplicate_event":
            record.tool_events.append(event(0))
        elif invalid == "orphan_message":
            session.add(
                MessageRecord(session_id="missing", position=0, role="user", content="Orphan")
            )
        elif invalid == "orphan_event":
            session.add(event(0, session_id="missing"))
        session.add(record)


@pytest.mark.parametrize("status", list(SessionStatus))
def test_all_session_states_can_be_stored(database: Database, status: SessionStatus) -> None:
    with database.sessions.begin() as session:
        session.add(SessionRecord(status=status))


def test_upgrade_and_downgrade_preserve_existing_todos(tmp_path: Path) -> None:
    config = Config(Path(__file__).resolve().parents[1] / "alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{(tmp_path / 'upgrade.db').as_posix()}")
    command.upgrade(config, "0002_create_todo_tables")
    database = create_database(config.get_main_option("sqlalchemy.url"))
    try:
        todos = TodoService(database.sessions)
        original = todos.create(TodoInput(topic="Existing", priority=1, items=["One", "Two"]))
        original = todos.set_item_completed(original.id, original.items[0].id, True)
        assert original is not None
        command.upgrade(config, "head")
        command.upgrade(config, "head")
        assert todos.get(original.id) == original
        with database.sessions.begin() as session:
            session.add(
                SessionRecord(
                    messages=[MessageRecord(position=0, role="user", content="Hi")],
                    tool_events=[event(0)],
                )
            )
        with database.engine.begin() as connection:
            config.attributes["connection"] = connection
            command.downgrade(config, "0002_create_todo_tables")
        config.attributes.pop("connection")
        assert set(inspect(database.engine).get_table_names()) == {
            "alembic_version",
            "todos",
            "todo_items",
        }
        assert todos.get(original.id) == original
        command.upgrade(config, "head")
        assert todos.get(original.id) == original
    finally:
        database.dispose()
