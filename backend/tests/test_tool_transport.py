import asyncio
import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import httpx
import pytest
from mcp import ClientSession
from mcp.types import CallToolResult

from wisetodo.tools import ToolConfig, ToolRegistry
from wisetodo.tools.transport import ToolExecutor, ToolTransportError


def registry(transport):
    return ToolRegistry(
        [
            ToolConfig.model_validate(
                {
                    "name": "read",
                    "description": "read",
                    "input_schema": {"type": "object"},
                    "transport": transport,
                }
            )
        ]
    )


async def test_local_isolation_and_unknown_handler():
    async def handler(args):
        args["x"] = 2
        return args

    async with httpx.AsyncClient() as client:
        reg = registry({"type": "local", "handler": "reader"})
        executor = ToolExecutor(reg, http=client, handlers={"reader": handler})
        args = {"x": 1}
        assert await executor.execute("read", args) == {"x": 2}
        assert args == {"x": 1}
        with pytest.raises(ToolTransportError, match="unknown_tool"):
            await executor.execute("missing", {})
        with pytest.raises(ToolTransportError, match="handler_unavailable"):
            await ToolExecutor(reg, http=client).execute("read", {})


@pytest.mark.parametrize("method", ["GET", "POST"])
async def test_http_argument_mapping(method):
    def respond(request):
        assert request.method == method
        if method == "GET":
            assert json.loads(request.url.params["x"]) == [1, "a"]
        else:
            assert request.content == b'{"x":[1,"a"]}'
        return httpx.Response(200, json={"ok": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        executor = ToolExecutor(
            registry({"type": "http", "url": "https://example.org", "method": method}), http=client
        )
        assert await executor.execute("read", {"x": [1, "a"]}) == {"ok": True}


@pytest.mark.parametrize(
    "status,body,code",
    [
        (302, b"secret", "http_failed"),
        (500, b"secret", "http_failed"),
        (200, b"not json secret", "tool_failed"),
        (200, b"x" * (1024 * 1024 + 1), "result_too_large"),
    ],
    ids=["redirect", "server-error", "invalid-json", "oversized"],
)
async def test_http_failures_are_safe(status, body, code):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(status, content=body))
    ) as client:
        executor = ToolExecutor(
            registry({"type": "http", "url": "https://example.org"}), http=client
        )
        with pytest.raises(ToolTransportError) as caught:
            await executor.execute("read", {})
        assert str(caught.value) == code


@pytest.mark.parametrize("failed", [False, True])
async def test_mcp_session_mapping_and_cleanup(failed):
    session = AsyncMock(spec=ClientSession)
    session.call_tool.return_value = CallToolResult.model_validate(
        {"content": [], "isError": failed}
    )
    closed = []

    @asynccontextmanager
    async def factory():
        try:
            yield session
        finally:
            closed.append(True)

    async with httpx.AsyncClient() as client:
        executor = ToolExecutor(
            registry({"type": "mcp", "server": "docs", "tool": "remote_read"}),
            http=client,
            servers={"docs": factory},
        )
        if failed:
            with pytest.raises(ToolTransportError, match="remote_tool_failed"):
                await executor.execute("read", {"x": 1})
        else:
            assert isinstance(await executor.execute("read", {"x": 1}), dict)
        session.call_tool.assert_awaited_once_with("remote_read", arguments={"x": 1})
        assert closed == [True]


async def test_timeout_and_cancellation_propagate():
    started = asyncio.Event()

    async def wait(args):
        started.set()
        await asyncio.Event().wait()

    async with httpx.AsyncClient() as client:
        reg = registry({"type": "local", "handler": "wait"})
        with pytest.raises(ToolTransportError, match="tool_timeout"):
            await ToolExecutor(reg, http=client, handlers={"wait": wait}, timeout=0.01).execute(
                "read", {}
            )
        started.clear()
        executor = ToolExecutor(reg, http=client, handlers={"wait": wait})
        task = asyncio.create_task(executor.execute("read", {}))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
