import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest

from wisetodo.database import Database, initialize_database
from wisetodo.sessions.models import SessionStatus
from wisetodo.sessions.retry import (
    RetryExecutionError,
    RetryOutcome,
    RetryRequest,
    RetryUnavailableError,
)
from wisetodo.sessions.service import SessionReadOnlyError, SessionService
from wisetodo.sessions.state_machine import InvalidSessionTransition, SessionEvent
from wisetodo.sessions.tables import MessageRecord, SessionRecord


@pytest.fixture
def database(tmp_path: Path) -> Iterator[Database]:
    database = initialize_database(tmp_path / "retry.db")
    try:
        yield database
    finally:
        database.dispose()


def seed(database: Database, status: str = "failed", with_input: bool = True) -> str:
    with database.sessions.begin() as session:
        record = SessionRecord(status=status, label="Read")
        if with_input:
            record.messages = [
                MessageRecord(
                    position=0, role="user", content="读这本书", attachments=["D:/book.pdf"]
                )
            ]
        session.add(record)
        session.flush()
        return record.id


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["failed", "cancelled"])
async def test_retry_preserves_history_and_uses_fresh_run_ids(
    database: Database, status: str
) -> None:
    calls: list[RetryRequest] = []

    async def executor(request: RetryRequest) -> RetryOutcome:
        calls.append(request)
        assert request.history.status in {SessionStatus.FAILED, SessionStatus.CANCELLED}
        assert request.history.messages[0].attachments == ["D:/book.pdf"]
        return RetryOutcome(
            event=SessionEvent.FAIL if len(calls) == 1 else SessionEvent.REQUEST_INPUT
        )

    service = SessionService(database.sessions, retry_executor=executor)
    session_id = seed(database, status)
    before = service.get(session_id)
    first = await service.retry(session_id)
    assert first.status == "failed"
    second = await service.retry(session_id)
    assert second.status == "waiting_input"
    assert calls[0].run_id != calls[1].run_id
    assert before is not None and second.messages == before.messages
    assert second.tool_events == before.tool_events
    assert second.id == before.id


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["ready", "running", "waiting_input", "completed"])
async def test_non_retryable_status_never_calls_executor(database: Database, status: str) -> None:
    async def executor(request: RetryRequest) -> RetryOutcome:
        pytest.fail("Must not execute")

    service = SessionService(database.sessions, retry_executor=executor)
    session_id = seed(database, status)
    before = service.get(session_id)
    with pytest.raises((SessionReadOnlyError, InvalidSessionTransition)):
        await service.retry(session_id)
    assert service.get(session_id) == before


@pytest.mark.asyncio
async def test_unconfigured_executor_and_missing_input_do_not_change_status(
    database: Database,
) -> None:
    service = SessionService(database.sessions)
    session_id = seed(database)
    before = service.get(session_id)
    with pytest.raises(RetryUnavailableError):
        await service.retry(session_id)
    assert service.get(session_id) == before
    with pytest.raises(LookupError):
        await service.retry("missing")

    async def executor(request: RetryRequest) -> RetryOutcome:
        pytest.fail("Must not execute without input")

    service = SessionService(database.sessions, retry_executor=executor)
    empty_id = seed(database, with_input=False)
    empty = service.get(empty_id)
    with pytest.raises(ValueError, match="input"):
        await service.retry(empty_id)
    assert service.get(empty_id) == empty


@pytest.mark.asyncio
async def test_executor_error_returns_to_failed(database: Database) -> None:
    async def executor(request: RetryRequest) -> RetryOutcome:
        raise RuntimeError("private provider diagnostic")

    service = SessionService(database.sessions, retry_executor=executor)
    session_id = seed(database, "cancelled")
    with pytest.raises(RetryExecutionError):
        await service.retry(session_id)
    result = service.get(session_id)
    assert result is not None and result.status == "failed" and len(result.messages) == 1


@pytest.mark.asyncio
async def test_duplicate_retry_rejected_and_task_cancellation_retained(database: Database) -> None:
    entered = asyncio.Event()

    async def executor(request: RetryRequest) -> RetryOutcome:
        entered.set()
        await asyncio.Future[None]()
        return RetryOutcome(event=SessionEvent.FAIL)

    service = SessionService(database.sessions, retry_executor=executor)
    session_id = seed(database)
    task = asyncio.create_task(service.retry(session_id))
    try:
        await asyncio.wait_for(entered.wait(), timeout=2)
        with pytest.raises(InvalidSessionTransition):
            await service.retry(session_id)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    result = service.get(session_id)
    assert result is not None and result.status == "cancelled"
    assert len(result.messages) == 1


@pytest.mark.asyncio
async def test_old_run_id_cannot_apply_results(database: Database) -> None:
    async def executor(request: RetryRequest) -> RetryOutcome:
        with pytest.raises(ValueError, match="Stale"):
            service._finish_retry(request.history.id, "old-run-id", SessionEvent.FAIL)
        return RetryOutcome(event=SessionEvent.REQUEST_INPUT)

    service = SessionService(database.sessions, retry_executor=executor)
    result = await service.retry(seed(database))
    assert result.status == "waiting_input"
