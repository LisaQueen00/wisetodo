import pytest

from wisetodo.ipc.messages import IpcRequest
from wisetodo.ipc.server import dispatch


@pytest.mark.asyncio
async def test_health_request() -> None:
    request = IpcRequest(requestId="req_1", method="health")
    assert await dispatch(request) == {"status": "ok"}
