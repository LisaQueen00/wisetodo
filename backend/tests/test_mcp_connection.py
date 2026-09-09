import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from wisetodo.tools.mcp_connection import McpServerConfig, server_factories, session_factory


def config():
    return McpServerConfig.model_validate(
        {
            "name": "test",
            "connection": {
                "type": "stdio",
                "command": sys.executable,
                "args": [str(Path(__file__).parent / "fixtures" / "mcp_server.py")],
            },
        }
    )


async def test_real_stdio_initialization_and_call():
    async with asyncio.timeout(15):
        async with session_factory(config())() as session:
            result = await session.call_tool("echo", arguments={"value": "local-test"})
            assert not result.is_error
            assert "local-test" in result.model_dump_json()


def test_duplicate_servers_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        server_factories([config(), config()])


@pytest.mark.parametrize(
    "connection",
    [
        {"type": "streamable_http", "url": "https://user:secret@example.org"},
        {"type": "streamable_http", "url": "https://example.org", "method": "GET"},
        {"type": "stdio", "command": ""},
        {"type": "stdio", "command": "python", "env": {"KEY": "secret"}},
    ],
)
def test_invalid_configuration(connection):
    with pytest.raises(ValidationError):
        McpServerConfig.model_validate({"name": "test", "connection": connection})


async def test_http_factory_initializes_and_closes_on_failure(monkeypatch):
    from wisetodo.tools import mcp_connection

    events = []
    session = AsyncMock()

    @asynccontextmanager
    async def transport(url, *, http_client):
        assert url == "http://127.0.0.1:8000/mcp"
        assert not http_client.follow_redirects
        try:
            yield ("read", "write")
        finally:
            events.append("transport_closed")

    @asynccontextmanager
    async def client_session(read, write):
        assert (read, write) == ("read", "write")
        try:
            yield session
        finally:
            events.append("session_closed")

    monkeypatch.setattr(mcp_connection, "streamable_http_client", transport)
    monkeypatch.setattr(mcp_connection, "ClientSession", client_session)
    settings = McpServerConfig.model_validate(
        {
            "name": "test",
            "connection": {
                "type": "streamable_http",
                "url": "http://127.0.0.1:8000/mcp",
            },
        }
    )
    with pytest.raises(RuntimeError, match="test failure"):
        async with session_factory(settings)() as initialized:
            assert initialized is session
            session.initialize.assert_awaited_once()
            raise RuntimeError("test failure")
    assert events == ["session_closed", "transport_closed"]
