from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from alembic import command
from wisetodo.database import Database, create_database
from wisetodo.todos.tables import TodoItemRecord, TodoRecord

BACKEND_DIR = Path(__file__).resolve().parents[1]


def migrated_database(tmp_path: Path) -> Database:
    database_url = f"sqlite:///{(tmp_path / 'todos.db').as_posix()}"
    config = Config(BACKEND_DIR / "alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    return create_database(database_url)


def test_migration_creates_todo_tables(tmp_path: Path) -> None:
    database = migrated_database(tmp_path)
    try:
        inspector = inspect(database.engine)
        assert {"alembic_version", "todos", "todo_items"} <= set(
            inspector.get_table_names()
        )
        assert inspector.get_foreign_keys("todo_items")[0]["options"] == {
            "ondelete": "CASCADE"
        }
    finally:
        database.dispose()


def test_records_persist_with_ordered_items(tmp_path: Path) -> None:
    database = migrated_database(tmp_path)
    try:
        with database.sessions.begin() as session:
            todo = TodoRecord(topic="Read a book", priority=1, position=0)
            todo.items = [
                TodoItemRecord(topic="Chapter 2", position=1),
                TodoItemRecord(topic="Chapter 1", position=0),
            ]
            session.add(todo)
            session.flush()
            todo_id = todo.id

        with database.sessions() as session:
            stored = session.get_one(TodoRecord, todo_id)
            assert stored.priority == 1
            assert [item.topic for item in stored.items] == ["Chapter 1", "Chapter 2"]
            assert all(not item.completed for item in stored.items)
    finally:
        database.dispose()


def test_database_rejects_invalid_priority(tmp_path: Path) -> None:
    database = migrated_database(tmp_path)
    try:
        with pytest.raises(IntegrityError), database.sessions.begin() as session:
            session.add(TodoRecord(topic="Invalid", priority=2, position=0))
    finally:
        database.dispose()
