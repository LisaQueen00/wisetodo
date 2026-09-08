from __future__ import annotations

import argparse
import asyncio
import sys
from io import TextIOWrapper
from pathlib import Path

from wisetodo.database import initialize_database
from wisetodo.ipc.server import run_stdio_server
from wisetodo.sessions.service import SessionService
from wisetodo.todos import TodoService


def main() -> None:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if isinstance(stream, TextIOWrapper):
            stream.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="WiseTodo JSON Lines sidecar")
    parser.add_argument("--database", type=Path, required=True, help="Absolute SQLite file path")
    args = parser.parse_args()

    try:
        database = initialize_database(args.database)
    except Exception:
        print("WiseTodo database initialization failed", file=sys.stderr, flush=True)
        raise SystemExit(1) from None

    try:
        asyncio.run(
            run_stdio_server(TodoService(database.sessions), SessionService(database.sessions))
        )
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
