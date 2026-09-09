"""Owned MCP connections for explicitly trusted server configurations."""

import os
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from typing import Annotated, Literal

import httpx2
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client
from pydantic import Field, StrictStr, field_validator

from wisetodo.tools.config import ConfigModel, HttpTransport, Name
from wisetodo.tools.transport import McpSessionFactory


class StdioConnection(ConfigModel):
    type: Literal["stdio"]
    command: Annotated[StrictStr, Field(min_length=1)]
    args: tuple[StrictStr, ...] = ()


class HttpConnection(ConfigModel):
    type: Literal["streamable_http"]
    url: StrictStr

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return HttpTransport.validate_url(value)


class McpServerConfig(ConfigModel):
    name: Name
    connection: Annotated[StdioConnection | HttpConnection, Field(discriminator="type")]


def session_factory(config: McpServerConfig) -> McpSessionFactory:
    snapshot = McpServerConfig.model_validate(config.model_dump())

    @asynccontextmanager
    async def connect() -> AsyncIterator[ClientSession]:
        connection = snapshot.connection
        if isinstance(connection, StdioConnection):
            parameters = StdioServerParameters(
                command=connection.command, args=list(connection.args)
            )
            # Child stderr may contain private documents or credentials.
            with open(os.devnull, "w") as errors:
                async with stdio_client(parameters, errlog=errors) as streams:
                    async with ClientSession(*streams) as session:
                        await session.initialize()
                        yield session
        else:
            async with (
                httpx2.AsyncClient(follow_redirects=False, trust_env=False) as client,
                streamable_http_client(connection.url, http_client=client) as streams,
                ClientSession(*streams) as session,
            ):
                await session.initialize()
                yield session

    return connect


def server_factories(configs: Iterable[McpServerConfig]) -> dict[str, McpSessionFactory]:
    result: dict[str, McpSessionFactory] = {}
    for config in configs:
        if config.name in result:
            raise ValueError("Duplicate MCP server name")
        result[config.name] = session_factory(config)
    return result
