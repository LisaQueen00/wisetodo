import json
from io import StringIO
from unittest.mock import AsyncMock

import pytest

from wisetodo.ipc import server
from wisetodo.ipc.messages import IpcRequest
from wisetodo.ipc.server import dispatch
from wisetodo.sessions.service import SessionReadOnlyError


@pytest.mark.asyncio
async def test_health_request() -> None:
    request = IpcRequest(requestId="req_1", method="health")
    assert await dispatch(request) == {"status": "ok"}


@pytest.mark.asyncio
async def test_readonly_error_is_safe_and_does_not_stop_server(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    requests = [IpcRequest(requestId=str(index), method="health") for index in range(2)]
    monkeypatch.setattr(
        "sys.stdin",
        StringIO("".join(request.model_dump_json(by_alias=True) + "\n" for request in requests)),
    )
    monkeypatch.setattr(
        server,
        "dispatch",
        AsyncMock(
            side_effect=[
                SessionReadOnlyError("private-session-id"),
                {"status": "ok"},
            ]
        ),
    )
    await server.run_stdio_server()
    output = capsys.readouterr().out
    failure, success = map(json.loads, output.splitlines())
    assert failure["error"]["code"] == "SESSION_READ_ONLY"
    assert failure["error"]["retryable"] is False
    assert "新建会话" in failure["error"]["user_message"]
    assert "private-session-id" not in output
    assert success["result"] == {"status": "ok"}
