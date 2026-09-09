"""Async adapters for vetted tools; connection ownership stays with the caller."""

import asyncio
import copy
import json
from collections.abc import Awaitable, Callable, Mapping
from contextlib import AbstractAsyncContextManager

import httpx
from mcp import ClientSession
from pydantic import JsonValue, TypeAdapter

from wisetodo.tools.config import HttpTransport, LocalTransport
from wisetodo.tools.registry import ToolRegistry

LocalHandler = Callable[[dict[str, JsonValue]], Awaitable[JsonValue]]
McpSessionFactory = Callable[[], AbstractAsyncContextManager[ClientSession]]
JSON_VALUE: TypeAdapter[JsonValue] = TypeAdapter(JsonValue)
MAX_RESPONSE_BYTES = 1024 * 1024


class ToolTransportError(RuntimeError):
    """Fixed safe error code; never includes arguments or remote error bodies."""


class ToolExecutor:
    def __init__(
        self,
        registry: ToolRegistry,
        *,
        http: httpx.AsyncClient,
        handlers: Mapping[str, LocalHandler] | None = None,
        servers: Mapping[str, McpSessionFactory] | None = None,
        timeout: float = 30,
    ) -> None:
        if not 0 < timeout < float("inf"):
            raise ValueError("Expected a finite positive timeout")
        self._registry = registry
        self._http = http
        self._handlers = dict(handlers or {})
        self._servers = dict(servers or {})
        self._timeout = timeout

    async def execute(self, name: str, arguments: dict[str, JsonValue]) -> JsonValue:
        config = self._registry.get(name)
        if config is None:
            raise ToolTransportError("unknown_tool")
        try:
            args = copy.deepcopy(arguments)
            async with asyncio.timeout(self._timeout):
                transport = config.transport
                if isinstance(transport, LocalTransport):
                    handler = self._handlers.get(transport.handler)
                    if handler is None:
                        raise ToolTransportError("handler_unavailable")
                    result = await handler(args)
                elif isinstance(transport, HttpTransport):
                    result = await self._request(transport, args)
                else:
                    factory = self._servers.get(transport.server)
                    if factory is None:
                        raise ToolTransportError("server_unavailable")
                    # Factory enters an initialized SDK session and closes it on exit.
                    async with factory() as session:
                        response = await session.call_tool(transport.tool, arguments=args)
                        if response.is_error:
                            raise ToolTransportError("remote_tool_failed")
                        result = response.model_dump(mode="json", exclude_none=True)
                validated = JSON_VALUE.validate_python(result)
                if len(json.dumps(validated, allow_nan=False).encode()) > MAX_RESPONSE_BYTES:
                    raise ToolTransportError("result_too_large")
                return copy.deepcopy(validated)
        except asyncio.CancelledError:
            raise
        except ToolTransportError:
            raise
        except TimeoutError:
            raise ToolTransportError("tool_timeout") from None
        except Exception:
            raise ToolTransportError("tool_failed") from None

    async def _request(self, transport: HttpTransport, args: dict[str, JsonValue]) -> JsonValue:
        # GET uses JSON-encoded values per query key; POST sends the argument object.
        params = (
            {
                key: json.dumps(value, ensure_ascii=False, allow_nan=False)
                for key, value in args.items()
            }
            if transport.method == "GET"
            else None
        )
        async with self._http.stream(
            transport.method,
            transport.url,
            params=params,
            json=args if transport.method == "POST" else None,
            follow_redirects=False,
            timeout=self._timeout,
        ) as response:
            if not 200 <= response.status_code < 300:
                raise ToolTransportError("http_failed")
            data = bytearray()
            async for chunk in response.aiter_bytes():
                data.extend(chunk)
                if len(data) > MAX_RESPONSE_BYTES:
                    raise ToolTransportError("result_too_large")
            return JSON_VALUE.validate_json(bytes(data))
