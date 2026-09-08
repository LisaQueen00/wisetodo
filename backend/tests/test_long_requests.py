import asyncio
import json
from io import StringIO
from pathlib import Path
from uuid import uuid4

import pytest

from wisetodo.database import initialize_database
from wisetodo.ipc import server
from wisetodo.ipc.events import request_id
from wisetodo.ipc.messages import IpcRequest
from wisetodo.sessions.models import ChatInput
from wisetodo.sessions.retry import RetryOutcome, RetryRequest
from wisetodo.sessions.service import SessionService


async def test_long_request_does_not_block_health_and_cancels(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def dispatch(request: IpcRequest, *args: object) -> dict:
        if request.method == "user.sessions.retry":
            await asyncio.Event().wait()
        return {"status": "ok"}

    monkeypatch.setattr(server, "dispatch", dispatch)
    inputs = [
        {"type": "request", "requestId": "slow", "method": "user.sessions.retry"},
        {"type": "request", "requestId": "fast", "method": "health"},
        {"type": "cancel", "requestId": "slow"},
    ]
    monkeypatch.setattr("sys.stdin", StringIO("\n".join(map(json.dumps, inputs)) + "\n"))
    await asyncio.wait_for(server.run_stdio_server(), timeout=2)
    output = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert output[0]["requestId"] == "fast"
    assert output[1]["requestId"] == "slow"
    assert output[1]["error"]["code"] == "RUN_CANCELLED"


async def test_run_id_cancel_events_and_restart_recovery(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database = initialize_database(tmp_path / "runs.db")
    started = asyncio.Event()
    requests: list[RetryRequest] = []

    async def execute(request: RetryRequest) -> RetryOutcome:
        requests.append(request)
        started.set()
        await asyncio.Event().wait()
        raise AssertionError("Unreachable")

    try:
        service = SessionService(database.sessions, execute)
        history = service.create()
        service.send_message(history.id, ChatInput(message_id=uuid4(), content="test"))
        with service.write_history(history.id) as record:
            record.status = "failed"
        token = request_id.set("ipc-run")
        task = asyncio.create_task(service.retry(history.id))
        request_id.reset(token)
        await asyncio.wait_for(started.wait(), 2)
        run = requests[0].run_id
        assert not service.cancel(history.id, "old-run")
        assert service.cancel(history.id, run)
        assert not service.cancel(history.id, run)
        with pytest.raises(asyncio.CancelledError):
            await task
        assert service.get(history.id).status == "cancelled"
        events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
        assert [event["event"] for event in events] == ["run.started", "run.finished"]
        assert all(event["run_id"] == run and event["requestId"] == "ipc-run" for event in events)
        with service.write_history(history.id) as record:
            record.status = "running"
        recovered = SessionService(database.sessions)
        assert recovered.recover_interrupted() == 1
        assert recovered.recover_interrupted() == 0
        assert recovered.get(history.id).status == "failed"
        assert recovered.get(history.id).messages[-1].role == "system"
        assert recovered.get(history.id).messages[0].content == "test"
    finally:
        database.dispose()
