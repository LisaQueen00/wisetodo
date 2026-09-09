"""Load a complete tool configuration snapshot without activating connections."""

from collections.abc import Iterable
from pathlib import Path

from pydantic import Field

from wisetodo.tools.config import ConfigModel, ToolConfig
from wisetodo.tools.mcp_connection import McpServerConfig, server_factories
from wisetodo.tools.registry import ToolRegistry
from wisetodo.tools.transport import McpSessionFactory


class ToolSettings(ConfigModel):
    tools: list[ToolConfig] = Field(default_factory=list)
    servers: list[McpServerConfig] = Field(default_factory=list)


def load_tools(
    path: Path, *, optional: bool = False, handlers: Iterable[str] = ()
) -> tuple[ToolRegistry, dict[str, McpSessionFactory]]:
    if not path.is_absolute():
        raise ValueError("Tool configuration requires absolute path")
    try:
        try:
            with path.open("rb") as stream:
                data = stream.read(256 * 1024 + 1)
        except FileNotFoundError:
            if optional:
                return ToolRegistry(), {}
            raise
        if len(data) > 256 * 1024:
            raise ValueError("oversized")
        settings = ToolSettings.model_validate_json(data)
        registry = ToolRegistry(settings.tools)
        servers = server_factories(settings.servers)
        for config in settings.tools:
            if config.transport.type == "local" and config.transport.handler not in handlers:
                raise ValueError("Unknown local handler")
            if config.transport.type == "mcp" and config.transport.server not in servers:
                raise ValueError("Unknown MCP server")
        return registry, servers
    except Exception:
        raise ValueError("Invalid tool configuration") from None
