from pathlib import Path

from alembic.config import Config
from sqlalchemy import text

from alembic import command
from wisetodo.database import create_database

BACKEND_DIR = Path(__file__).resolve().parents[1]


def sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def test_database_enables_sqlite_safety_pragmas(tmp_path: Path) -> None:
    database = create_database(sqlite_url(tmp_path / "runtime.db"))

    try:
        with database.engine.connect() as connection:
            foreign_keys = connection.execute(text("PRAGMA foreign_keys")).scalar_one()
            busy_timeout = connection.execute(text("PRAGMA busy_timeout")).scalar_one()

        assert foreign_keys == 1
        assert busy_timeout == 5000
    finally:
        database.dispose()


def test_alembic_upgrades_a_new_database_to_head(tmp_path: Path) -> None:
    config = Config(BACKEND_DIR / "alembic.ini")
    config.set_main_option("sqlalchemy.url", sqlite_url(tmp_path / "migration.db"))

    command.upgrade(config, "head")

    database = create_database(config.get_main_option("sqlalchemy.url"))
    try:
        with database.engine.connect() as connection:
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()

        assert revision == "0001_baseline"
    finally:
        database.dispose()
