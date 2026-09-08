import asyncio
import json

import httpx
import pytest
from pydantic import SecretStr

from wisetodo.model.connection import check_connection
from wisetodo.settings import ResolvedSettings, SettingsService


class Store:
    def __init__(self, key: str | None = None) -> None:
        self.value = ResolvedSettings(
            base_url="http://localhost:8000/v1/",
            model="test",
            api_key=SecretStr(key) if key else None,
        )

    def load(self) -> ResolvedSettings | None:
        return self.value

    def replace(self, value: ResolvedSettings) -> None:
        pytest.fail("Probe must not save")


@pytest.mark.parametrize("key", [None, "private-secret"])
async def test_minimal_request_and_no_body_echo(key: str | None) -> None:
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert str(request.url) == "http://localhost:8000/v1/chat/completions"
        assert request.headers.get("authorization") == (f"Bearer {key}" if key else None)
        assert json.loads(request.content) == {
            "model": "test",
            "messages": [{"role": "user", "content": "Reply OK."}],
            "stream": False,
            "max_completion_tokens": 64,
        }
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "private-secret"},
                    }
                ]
            },
        )

    assert (
        await check_connection(SettingsService(Store(key)), transport=httpx.MockTransport(handler))
        == "ok"
    )
    assert len(seen) == 1


@pytest.mark.parametrize(
    "status,expected",
    [
        (401, "authentication"),
        (403, "authentication"),
        (404, "not_found"),
        (429, "rate_limited"),
        (500, "request_failed"),
        (302, "request_failed"),
    ],
)
async def test_safe_http_errors_no_retry(status: int, expected: str) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            status, text="private-secret", headers={"Location": "https://other.example"}
        )

    assert (
        await check_connection(SettingsService(Store()), transport=httpx.MockTransport(handler))
        == expected
    )
    assert len(calls) == 1


@pytest.mark.parametrize(
    "body",
    [
        b"not json",
        b"{}",
        pytest.param(b"x" * 65537, id="oversized"),
        b'{"choices":[{"finish_reason":"length","message":{"role":"assistant","content":"OK"}}]}',
    ],
)
async def test_invalid_response(body: bytes) -> None:
    assert (
        await check_connection(
            SettingsService(Store()),
            transport=httpx.MockTransport(lambda _: httpx.Response(200, content=body)),
        )
        == "invalid_response"
    )


async def test_timeout_and_cancellation() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("private-secret")

    assert (
        await check_connection(SettingsService(Store()), transport=httpx.MockTransport(timeout))
        == "timeout"
    )

    async def cancel(request: httpx.Request) -> httpx.Response:
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await check_connection(SettingsService(Store()), transport=httpx.MockTransport(cancel))


async def test_ipc_rejects_content_and_uses_only_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    from wisetodo.ipc.messages import IpcRequest
    from wisetodo.ipc.settings import SettingsRequestError, dispatch_settings

    async def probe(settings: SettingsService) -> str:
        return "ok"

    monkeypatch.setattr("wisetodo.ipc.settings.check_connection", probe)
    request = IpcRequest.model_validate(
        {"type": "request", "requestId": "1", "method": "user.settings.test", "params": {}}
    )
    assert await dispatch_settings(request, SettingsService(Store())) == {"connection_test": "ok"}
    with pytest.raises(SettingsRequestError):
        await dispatch_settings(
            request.model_copy(update={"params": {"content": "secret"}}), SettingsService(Store())
        )
