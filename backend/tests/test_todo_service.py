from datetime import datetime
from pathlib import Path

import pytest
from alembic.config import Config
from pydantic import ValidationError

from alembic import command
from wisetodo.database import Database, create_database
from wisetodo.todos import TodoCaller, TodoChanges, TodoInput, TodoService
from wisetodo.todos.tables import TodoItemRecord, TodoRecord

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("items", [[], ["One"], ["One", "  "]])
def test_invalid_update_leaves_saved_todo_unchanged(tmp_path: Path, items: list[str]) -> None:
    database, service = create_service(tmp_path)
    try:
        created = service.create(TodoInput(topic="Keep", items=["One", "Two"]))
        with pytest.raises(ValidationError):
            service.update(created.id, TodoChanges(topic="Changed", items=items))
        assert service.get(created.id) == created
    finally:
        database.dispose()


def test_duplicate_items_match_once_in_order_and_survive_reload(tmp_path: Path) -> None:
    database, service = create_service(tmp_path)
    try:
        created = service.create(TodoInput(topic="Task", items=["Same", "Same"]))
        with database.sessions.begin() as session:
            session.get_one(TodoItemRecord, created.items[0].id).completed = True
        updated = service.update(created.id, TodoChanges(items=[" Same ", "Same", "Same"]))
        assert updated is not None
        assert [item.id for item in updated.items[:2]] == [i.id for i in created.items]
        assert len({item.id for item in updated.items}) == 3
        assert [item.completed for item in updated.items] == [True, False, False]
        assert [item.position for item in updated.items] == [0, 1, 2]
        assert service.get(created.id) == updated
        reduced = service.update(created.id, TodoChanges(items=["Same", "Same"]))
        assert reduced is not None
        assert reduced.items == updated.items[:2]
        with database.sessions() as session:
            assert session.get(TodoItemRecord, updated.items[2].id) is None
    finally:
        database.dispose()


def test_renaming_completed_item_resets_progress(tmp_path: Path) -> None:
    database, service = create_service(tmp_path)
    try:
        created = service.create(TodoInput(topic="Task", items=["One", "Two"]))
        with database.sessions.begin() as session:
            for item in session.get_one(TodoRecord, created.id).items:
                item.completed = True
        updated = service.update(created.id, TodoChanges(items=["Renamed", "Two"]))
        assert updated is not None
        assert updated.items[0].id != created.items[0].id
        assert not updated.items[0].completed
        assert updated.items[1].id == created.items[1].id
        assert updated.items[1].completed
        assert updated.progress == 0.5
        assert not updated.completed
        assert service.get(created.id) == updated
    finally:
        database.dispose()


@pytest.mark.parametrize("completed", [False, True])
def test_sort_ties_use_creation_time_then_id(tmp_path: Path, completed: bool) -> None:
    database, service = create_service(tmp_path)
    try:
        with database.sessions.begin() as session:
            for todo_id, day in [("c", 2), ("b", 1), ("a", 1)]:
                session.add(
                    TodoRecord(
                        id=todo_id,
                        topic=todo_id,
                        priority=0,
                        position=0,
                        created_at=datetime(2026, 1, day),
                        items=[
                            TodoItemRecord(topic=str(i), position=i, completed=completed)
                            for i in range(2)
                        ],
                    )
                )
        assert [todo.id for todo in service.list()] == ["a", "b", "c"]
        assert [todo.id for todo in service.list()] == ["a", "b", "c"]
    finally:
        database.dispose()


def create_service(tmp_path: Path) -> tuple[Database, TodoService]:
    database_url = f"sqlite:///{(tmp_path / 'service.db').as_posix()}"
    config = Config(BACKEND_DIR / "alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    database = create_database(database_url)
    return database, TodoService(database.sessions)


def test_create_get_and_list_todos(tmp_path: Path) -> None:
    database, service = create_service(tmp_path)
    try:
        created = service.create(
            TodoInput(topic="Read a book", priority=1, items=["Chapter 1", "Chapter 2"])
        )

        fetched = service.get(created.id)
        listed = service.list()

        assert fetched == created
        assert listed == [created]
        assert [item.position for item in created.items] == [0, 1]
        assert all(item.todo_id == created.id for item in created.items)
        assert created.progress == 0.0
        assert not created.completed
    finally:
        database.dispose()


def test_update_replaces_changed_fields_and_items(tmp_path: Path) -> None:
    database, service = create_service(tmp_path)
    try:
        created = service.create(TodoInput(topic="Old topic", items=["Old item 1", "Old item 2"]))

        updated = service.update(
            created.id,
            TodoChanges(topic="New topic", priority=1, items=["New item 1", "New item 2"]),
        )

        assert updated is not None
        assert updated.topic == "New topic"
        assert updated.priority == 1
        assert [item.topic for item in updated.items] == ["New item 1", "New item 2"]
        assert {item.id for item in updated.items}.isdisjoint(item.id for item in created.items)
    finally:
        database.dispose()


def test_update_items_preserves_matches_and_removes_missing_items(tmp_path: Path) -> None:
    database, service = create_service(tmp_path)
    try:
        created = service.create(
            TodoInput(topic="Learn project", items=["Keep", "Remove", "Completed"])
        )
        original_by_topic = {item.topic: item for item in created.items}

        with database.sessions.begin() as session:
            session.get_one(TodoItemRecord, original_by_topic["Completed"].id).completed = True

        updated = service.update(
            created.id,
            TodoChanges(items=["Completed", "Keep", "New item"]),
        )

        assert updated is not None
        updated_by_topic = {item.topic: item for item in updated.items}
        assert [item.topic for item in updated.items] == ["Completed", "Keep", "New item"]
        assert updated_by_topic["Completed"].id == original_by_topic["Completed"].id
        assert updated_by_topic["Completed"].completed
        assert updated_by_topic["Keep"].id == original_by_topic["Keep"].id
        assert not updated_by_topic["New item"].completed
        assert updated_by_topic["New item"].id not in {item.id for item in created.items}

        with database.sessions() as session:
            assert session.get(TodoItemRecord, original_by_topic["Remove"].id) is None
    finally:
        database.dispose()


def test_delete_removes_todo_and_its_items(tmp_path: Path) -> None:
    database, service = create_service(tmp_path)
    try:
        created = service.create(TodoInput(topic="Delete me", items=["One", "Two"]))

        assert service.delete(created.id, caller=TodoCaller.USER)
        assert service.get(created.id) is None
        assert service.list() == []
        assert not service.delete(created.id, caller=TodoCaller.USER)
    finally:
        database.dispose()


def test_agent_cannot_delete_top_level_todo(tmp_path: Path) -> None:
    database, service = create_service(tmp_path)
    try:
        created = service.create(TodoInput(topic="Keep me", items=["One", "Two"]))

        with pytest.raises(PermissionError, match="Only user callers can delete"):
            service.delete(created.id, caller=TodoCaller.AGENT)

        assert service.get(created.id) == created
    finally:
        database.dispose()


def test_get_and_update_return_none_when_todo_is_missing(tmp_path: Path) -> None:
    database, service = create_service(tmp_path)
    try:
        assert service.get("missing") is None
        assert service.update("missing", TodoChanges(topic="New topic")) is None
    finally:
        database.dispose()


def test_list_sorts_by_completion_priority_and_position(tmp_path: Path) -> None:
    database, service = create_service(tmp_path)
    try:
        low_priority = service.create(
            TodoInput(topic="Low priority", priority=0, items=["One", "Two"])
        )
        high_later = service.create(TodoInput(topic="High later", priority=1, items=["One", "Two"]))
        high_earlier = service.create(
            TodoInput(topic="High earlier", priority=1, items=["One", "Two"])
        )
        completed = service.create(TodoInput(topic="Completed", priority=1, items=["One", "Two"]))

        with database.sessions.begin() as session:
            session.get_one(TodoRecord, low_priority.id).position = 0
            session.get_one(TodoRecord, high_later.id).position = 2
            session.get_one(TodoRecord, high_earlier.id).position = 1
            completed_record = session.get_one(TodoRecord, completed.id)
            completed_record.position = 0
            for item in completed_record.items:
                item.completed = True

        assert [todo.topic for todo in service.list()] == [
            "High earlier",
            "High later",
            "Low priority",
            "Completed",
        ]
    finally:
        database.dispose()
