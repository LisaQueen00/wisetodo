from __future__ import annotations

import argparse
import asyncio
import sys
from io import TextIOWrapper
from pathlib import Path

from wisetodo.agent.runtime import AgentRuntime
from wisetodo.database import initialize_database
from wisetodo.ipc.server import run_stdio_server
from wisetodo.model.runtime import create_provider_scope
from wisetodo.sessions.service import SessionService
from wisetodo.settings import SettingsService
from wisetodo.settings.development import DevelopmentSettingsStore
from wisetodo.settings.storage import create_settings_store
from wisetodo.todos import TodoService


def main() -> None:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if isinstance(stream, TextIOWrapper):
            stream.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="WiseTodo JSON Lines sidecar")
    parser.add_argument("--database", type=Path, required=True, help="Absolute SQLite file path")
    parser.add_argument("--dev-model-config", type=Path, help="Explicit development JSON path")
    parser.add_argument("--model-mode", choices=("native", "prompt_compat"), default="native")
    parser.add_argument("--tool-config", type=Path, help="Explicit trusted tool JSON path")
    args = parser.parse_args()
    if args.tool_config is not None and not args.tool_config.is_absolute():
        parser.error("--tool-config requires an absolute path")
    if args.dev_model_config is not None and not args.dev_model_config.is_absolute():
        parser.error("--dev-model-config requires an absolute path")

    try:
        database = initialize_database(args.database)
    except Exception:
        print("WiseTodo database initialization failed", file=sys.stderr, flush=True)
        raise SystemExit(1) from None

    try:
        session_service = SessionService(database.sessions)
        session_service.recover_interrupted()
        todo_service = TodoService(database.sessions)
        settings_service = SettingsService(
            DevelopmentSettingsStore(
                create_settings_store(args.database.parent),
                args.dev_model_config,
            )
        )
        session_service.agent_executor = AgentRuntime(
            session_service,
            todo_service,
            create_provider_scope(settings_service),
            mode=args.model_mode,
            tool_config=args.tool_config
            or (
                args.database.parent / "tool-settings.json"
                if (args.database.parent / "tool-settings.json").exists()
                else None
            ),
        )
        asyncio.run(
            run_stdio_server(
                todo_service,
                session_service,
                settings_service,
            )
        )
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
