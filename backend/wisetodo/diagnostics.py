"""Bounded local diagnostics: allowlisted events only, never arbitrary text."""

import json
import logging
from contextlib import suppress
from datetime import UTC, datetime
from enum import StrEnum
from logging.handlers import RotatingFileHandler
from pathlib import Path

from wisetodo.errors import ErrorCode


class Event(StrEnum):
    BACKEND_STARTED = "backend_started"
    BACKEND_STOPPED = "backend_stopped"
    BACKEND_FAILED = "backend_failed"
    DATABASE_INIT_FAILED = "database_init_failed"
    IPC_SUCCEEDED = "ipc_succeeded"
    IPC_FAILED = "ipc_failed"
    IPC_REJECTED = "ipc_rejected"
    TOOL_STARTED = "tool_started"
    TOOL_COMPLETED = "tool_completed"
    TOOL_FAILED = "tool_failed"
    TOOL_CANCELLED = "tool_cancelled"
    CREDENTIAL_CLEANUP_FAILED = "credential_cleanup_failed"


class _Handler(RotatingFileHandler):
    def handleError(self, record: logging.LogRecord) -> None:  # noqa: N802
        # Disk-full/rotation errors must not print traceback or disrupt the app.
        pass


class LocalLog:
    def __init__(self, directory: Path, *, max_bytes: int = 1024 * 1024) -> None:
        if not directory.is_absolute():
            raise ValueError("Expected absolute diagnostics directory")
        path = directory / "wisetodo.log"
        if any(p.is_symlink() or p.is_junction() for p in (path, *path.parents)):
            raise ValueError("Linked diagnostics path")
        directory.mkdir(parents=True, exist_ok=True)
        # Do not attach to root/SDK loggers: their messages may contain user data.
        self._handler = _Handler(path, maxBytes=max_bytes, backupCount=3, encoding="utf-8")

    def write(self, event: Event, code: ErrorCode | None = None) -> None:
        if not isinstance(event, Event) or (code is not None and not isinstance(code, ErrorCode)):
            return
        payload = {"time": datetime.now(UTC).isoformat(), "event": event.value}
        if code is not None:
            payload["code"] = code.value
        record = logging.LogRecord(
            "wisetodo.safe", logging.INFO, "", 0, json.dumps(payload), (), None
        )
        # Diagnostics are best-effort, including failures outside emit().
        with suppress(Exception):
            self._handler.handle(record)

    def close(self) -> None:
        self._handler.close()


_active: LocalLog | None = None


def start(directory: Path) -> bool:
    global _active
    stop()
    try:
        _active = LocalLog(directory)
    except Exception:
        return False
    return True


def record(event: Event, code: ErrorCode | None = None) -> None:
    if _active is not None:
        _active.write(event, code)


def stop() -> None:
    global _active
    active, _active = _active, None
    if active is not None:
        with suppress(Exception):
            active.close()
