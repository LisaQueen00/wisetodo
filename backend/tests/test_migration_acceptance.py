"""Exercise real Alembic revisions on disposable SQLite files."""

from pathlib import Path

import pytest
from alembic.config import Config
from alembic.util.exc import CommandError
from sqlalchemy import MetaData, Table, inspect, select, text
from sqlalchemy.exc import DatabaseError

from alembic import command
from wisetodo.database import create_database, initialize_database


def config_for(path):
    config = Config(Path(__file__).resolve().parents[1] / "alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{path.as_posix()}".replace("%", "%%"))
    return config


def snapshot(connection, names):
    return {
        name: connection.execute(select(Table(name, MetaData(), autoload_with=connection)))
        .mappings()
        .all()
        for name in names
    }


@pytest.mark.parametrize(
    "revision", ["0001_baseline", "0002_create_todo_tables", "0003_create_session_tables"]
)
def test_every_old_revision_upgrades_and_reopens(tmp_path, revision):
    path = tmp_path / "old.db"
    command.upgrade(config_for(path), revision)
    database = initialize_database(path)
    try:
        assert set(inspect(database.engine).get_table_names()) == {
            "alembic_version",
            "todos",
            "todo_items",
            "sessions",
            "messages",
            "tool_events",
        }
        with database.engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                "0004_session_execution"
            )
    finally:
        database.dispose()
    initialize_database(path).dispose()


def test_old_history_survives_upgrade_and_repeated_startup(tmp_path):
    path = tmp_path / "history.db"
    config = config_for(path)
    command.upgrade(config, "0003_create_session_tables")
    old = create_database(config.get_main_option("sqlalchemy.url"))
    names = ["sessions", "messages", "tool_events"]
    try:
        with old.engine.begin() as connection:
            connection.execute(
                text("INSERT INTO sessions (id, label, status) VALUES ('s', '阅读', 'failed')")
            )
            connection.execute(
                text(
                    "INSERT INTO messages (id, session_id, position, role, content, attachments) "
                    "VALUES ('m', 's', 0, 'user', '第一章', '[]')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO tool_events (id, session_id, position, run_id, call_id, "
                    "tool_name, event_type, payload) "
                    "VALUES ('e', 's', 0, 'r', 'c', 'read', 'failed', '{}')"
                )
            )
            before = snapshot(connection, names)
    finally:
        old.dispose()
    for _ in range(2):
        database = initialize_database(path)
        try:
            with database.engine.connect() as connection:
                after = snapshot(connection, names)
                for name in names:
                    assert len(after[name]) == len(before[name])
                    for previous, current in zip(before[name], after[name], strict=True):
                        assert all(current[key] == value for key, value in previous.items())
                row = after["sessions"][0]
                assert all(
                    row[key] is None
                    for key in ("active_run_id", "target_todo_id", "pending_operation")
                )
                assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
        finally:
            database.dispose()


def test_startup_from_other_directory_with_unicode_space_and_percent_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "中文 100%" / "app.db"
    initialize_database(path).dispose()
    assert path.is_file()
    assert not (tmp_path / "wisetodo.db").exists()


def test_unknown_revision_is_rejected_without_rewriting_database(tmp_path):
    path = tmp_path / "future.db"
    database = initialize_database(path)
    try:
        with database.engine.begin() as connection:
            connection.execute(text("UPDATE alembic_version SET version_num='unknown_future'"))
    finally:
        database.dispose()
    before = path.read_bytes()
    with pytest.raises(CommandError):
        initialize_database(path)
    assert path.read_bytes() == before


def test_corrupt_database_is_not_replaced(tmp_path):
    path = tmp_path / "corrupt.db"
    path.write_bytes(b"not a SQLite database")
    before = path.read_bytes()
    with pytest.raises(DatabaseError):
        initialize_database(path)
    assert path.read_bytes() == before
