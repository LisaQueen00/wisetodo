from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from sqlalchemy import URL

from alembic import command
from wisetodo.database.engine import Database, create_database


def initialize_database(path: Path) -> Database:
    """Open the application's database and upgrade it before accepting requests."""
    if not path.is_absolute():
        raise ValueError("The database path must be absolute")

    path.parent.mkdir(parents=True, exist_ok=True)
    database_url = URL.create("sqlite", database=str(path)).render_as_string(hide_password=False)
    database = create_database(database_url)

    # Resolve development resources relative to this module, never the launch directory.
    # The packaged sidecar must include these Alembic resources in the same layout.
    backend_dir = Path(__file__).resolve().parents[2]
    config = Config(backend_dir / "alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

    try:
        with database.engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
    except Exception:
        database.dispose()
        raise

    return database
