"""Explicit, bounded MCP server configuration loading without starting servers."""

from pathlib import Path

from pydantic import Field, ValidationError

from wisetodo.tools.config import ConfigModel
from wisetodo.tools.mcp_connection import McpServerConfig, server_factories
from wisetodo.tools.transport import McpSessionFactory


class McpSettings(ConfigModel):
    servers: list[McpServerConfig] = Field(default_factory=list)


def load_server_factories(path: Path) -> dict[str, McpSessionFactory]:
    """The explicit path must exist; invalid files never silently disable tools."""
    if not path.is_absolute():
        raise ValueError("MCP configuration requires an absolute path")
    try:
        with path.open("rb") as stream:
            data = stream.read(256 * 1024 + 1)
        if len(data) > 256 * 1024:
            raise ValueError("oversized")
        settings = McpSettings.model_validate_json(data)
        return server_factories(settings.servers)
    except (OSError, ValueError, ValidationError):
        raise ValueError("Invalid MCP server configuration") from None
