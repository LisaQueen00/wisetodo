from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry


@dataclass(frozen=True, slots=True)
class Database:
    """Database resources owned by the application runtime."""

    engine: Engine
    sessions: sessionmaker[Session]

    def dispose(self) -> None:
        self.engine.dispose()


def create_database(database_url: str) -> Database:
    """Create a SQLite engine and its session factory."""
    if not database_url.startswith("sqlite"):
        raise ValueError("WiseTodo currently supports SQLite database URLs only")

    engine = create_engine(database_url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def configure_sqlite(
        dbapi_connection: DBAPIConnection,
        _connection_record: ConnectionPoolEntry,
    ) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    return Database(engine=engine, sessions=sessions)
