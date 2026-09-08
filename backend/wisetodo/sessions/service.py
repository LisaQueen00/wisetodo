import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session, object_session, selectinload, sessionmaker

from wisetodo.ipc.events import emit_run
from wisetodo.sessions.models import ChatInput, SessionHistory, SessionStatus, SessionSummary
from wisetodo.sessions.retry import (
    RetryExecutionError,
    RetryExecutor,
    RetryOutcome,
    RetryRequest,
    RetryUnavailableError,
)
from wisetodo.sessions.state_machine import SessionEvent, capabilities, next_status
from wisetodo.sessions.tables import MessageRecord, SessionRecord


class SessionReadOnlyError(PermissionError):
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        super().__init__("Completed Sessions are read-only; create a new Session")


class SessionService:
    def __init__(
        self, sessions: sessionmaker[Session], retry_executor: RetryExecutor | None = None
    ) -> None:
        self._sessions = sessions
        self._retry_executor = retry_executor
        self._active_retries: dict[str, str] = {}
        self._run_tasks: dict[str, asyncio.Task[object]] = {}

    def cancel(self, session_id: str, run_id: str) -> bool:
        if self._active_retries.get(session_id) != run_id:
            return False
        task = self._run_tasks.get(run_id)
        if task is None or task.done() or task.cancelling():
            return False
        task.cancel()
        return True

    def recover_interrupted(self) -> int:
        """Call once before accepting IPC in a new single-owner sidecar."""
        with self._sessions.begin() as session:
            records = session.scalars(
                select(SessionRecord).where(SessionRecord.status == SessionStatus.RUNNING)
            ).all()
            for record in records:
                record.status = SessionStatus.FAILED
                record.updated_at = datetime.now(UTC)
                record.messages.append(
                    MessageRecord(
                        role="system",
                        content="上次执行因程序退出而中断，未自动重试，请检查任务后重试。",
                        attachments=[],
                        position=max((m.position for m in record.messages), default=-1) + 1,
                    )
                )
            return len(records)

    async def retry(self, session_id: str) -> SessionHistory:
        run_id = str(uuid4())
        with self.write_history(session_id) as record:
            target = next_status(SessionStatus(record.status), SessionEvent.RETRY)
            if session_id in self._active_retries:
                raise ValueError("Session already has an active retry")
            if self._retry_executor is None:
                raise RetryUnavailableError("Retry executor is not configured")
            if not any(message.role == "user" for message in record.messages):
                raise ValueError("Session has no retained user input")
            history = SessionHistory.model_validate(record)
            record.status = target
            record.updated_at = datetime.now(UTC)
        self._active_retries[session_id] = run_id
        task = asyncio.current_task()
        if task is not None:
            self._run_tasks[run_id] = task
        try:
            emit_run("run.started", session_id, run_id)
            try:
                outcome = await self._retry_executor(RetryRequest(run_id=run_id, history=history))
                if task is not None and task.cancelling():
                    raise asyncio.CancelledError
                outcome = RetryOutcome.model_validate(outcome)
            except asyncio.CancelledError:
                self._finish_retry(session_id, run_id, SessionEvent.CANCEL)
                raise
            except Exception as error:
                self._finish_retry(session_id, run_id, SessionEvent.FAIL)
                raise RetryExecutionError("Retry execution failed") from error
            self._finish_retry(session_id, run_id, outcome.event)
            result = self.get(session_id)
            if result is None:
                raise LookupError("Session not found")
            return result
        finally:
            self._run_tasks.pop(run_id, None)
            if self._active_retries.get(session_id) == run_id:
                del self._active_retries[session_id]
            emit_run("run.finished", session_id, run_id)

    def _finish_retry(self, session_id: str, run_id: str, event: SessionEvent) -> None:
        if self._active_retries.get(session_id) != run_id:
            raise ValueError("Stale retry result")
        with self.write_history(session_id) as record:
            if record.status != SessionStatus.RUNNING:
                raise ValueError("Session is no longer running")
            record.status = next_status(SessionStatus(record.status), event)
            record.updated_at = datetime.now(UTC)

    def create(self, label: str = "") -> SessionHistory:
        if not isinstance(label, str):
            raise ValueError("Session label must be a string")
        with self._sessions.begin() as session:
            record = SessionRecord(label=label.strip())
            session.add(record)
            session.flush()
            session.refresh(record)
            return SessionHistory.model_validate(record)

    def send_message(self, session_id: str, message: ChatInput) -> SessionHistory:
        """Save user input only; starting execution is a separate Runtime operation."""
        with self.write_history(session_id) as record:
            if not capabilities(SessionStatus(record.status)).can_submit:
                raise ValueError("Session cannot accept user input")
            existing = next(
                (row for row in record.messages if row.id == str(message.message_id)), None
            )
            if existing is not None:
                if (
                    existing.role != "user"
                    or existing.content != message.content
                    or existing.attachments != [*message.urls, *message.files]
                ):
                    raise ValueError("Message ID reused for different content")
            else:
                if any(not Path(path).is_file() for path in message.files):
                    raise ValueError("Attachment is missing or is not a regular file")
                record.messages.append(
                    MessageRecord(
                        id=str(message.message_id),
                        attachments=[*message.urls, *message.files],
                        role="user",
                        content=message.content,
                        position=max((row.position for row in record.messages), default=-1) + 1,
                    )
                )
                record.updated_at = datetime.now(UTC)
            session = object_session(record)
            assert session is not None
            session.flush()
            session.refresh(record)
            return SessionHistory.model_validate(record)

    def list(self) -> list[SessionSummary]:
        # History bodies are fetched only after the user selects a Session.
        with self._sessions() as session:
            records = session.scalars(
                select(SessionRecord).order_by(
                    SessionRecord.updated_at.desc(),
                    SessionRecord.created_at.desc(),
                    SessionRecord.id,
                )
            )
            return [SessionSummary.model_validate(record) for record in records]

    def get(self, session_id: str) -> SessionHistory | None:
        with self._sessions() as session:
            record = session.scalar(
                select(SessionRecord)
                .where(SessionRecord.id == session_id)
                .options(
                    selectinload(SessionRecord.messages), selectinload(SessionRecord.tool_events)
                )
            )
            return SessionHistory.model_validate(record) if record is not None else None

    @contextmanager
    def write_history(self, session_id: str) -> Iterator[SessionRecord]:
        """Transaction boundary for future message/event and lifecycle writers.

        Acquire SQLite's write lock before checking status, so a concurrent completion
        cannot slip between the check and the write. No-op updates preserve timestamps.
        Callers still enforce lifecycle transitions and run IDs; this only guards the
        successful terminal state. Deleting an entire Session is intentionally separate.
        """
        with self._sessions.begin() as session:
            result = session.execute(
                update(SessionRecord)
                .where(
                    SessionRecord.id == session_id, SessionRecord.status != SessionStatus.COMPLETED
                )
                .values(status=SessionRecord.status, updated_at=SessionRecord.updated_at)
                .returning(SessionRecord.id)
            )
            if result.scalar_one_or_none() is None:
                if session.get(SessionRecord, session_id) is None:
                    raise LookupError("Session not found")
                raise SessionReadOnlyError(session_id)
            record = session.get_one(SessionRecord, session_id)
            yield record

    def delete(self, session_id: str) -> bool:
        with self._sessions.begin() as session:
            record = session.get(SessionRecord, session_id)
            if record is None:
                return False
            # Never remove a live run's history beneath the future runtime.
            if record.status == SessionStatus.RUNNING:
                raise ValueError("Stop the running Session before deleting it")
            session.delete(record)
            return True
