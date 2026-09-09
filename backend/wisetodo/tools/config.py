"""Declarative tool configuration; no imports, connections or execution."""

from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    JsonValue,
    StrictStr,
    field_validator,
)

from wisetodo.model.contracts import ToolDefinition
from wisetodo.tools.validation import validate_schema

Name = Annotated[StrictStr, Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")]


class ConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LocalTransport(ConfigModel):
    type: Literal["local"]
    handler: Name


class HttpTransport(ConfigModel):
    type: Literal["http"]
    url: StrictStr
    method: Literal["GET", "POST"] = "POST"

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        if any(char.isspace() or ord(char) < 32 or char == "\\" for char in value):
            raise ValueError("Invalid tool endpoint")
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Expected HTTP(S) endpoint without credentials, query or fragment")
        HttpUrl(value)
        return value


class McpTransport(ConfigModel):
    type: Literal["mcp"]
    server: Name
    tool: Annotated[StrictStr, Field(min_length=1, max_length=128)]

    @field_validator("tool")
    @classmethod
    def validate_tool(cls, value: str) -> str:
        if value != value.strip() or any(ord(char) < 32 for char in value):
            raise ValueError("Invalid remote tool name")
        return value


Transport = Annotated[LocalTransport | HttpTransport | McpTransport, Field(discriminator="type")]


class ToolConfig(ConfigModel):
    name: Name
    description: Annotated[StrictStr, Field(min_length=1)]
    input_schema: dict[str, JsonValue]
    transport: Transport

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Description must not be blank")
        return value.strip()

    @field_validator("input_schema")
    @classmethod
    def validate_schema_root(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        if value.get("type") != "object":
            raise ValueError("Tool input schema must declare type object")
        validate_schema(value)
        return value

    def to_definition(self) -> ToolDefinition:
        """Detach nested schema data and omit all transport details."""
        return ToolDefinition(
            name=self.name, description=self.description, parameters=self.input_schema
        ).model_copy(deep=True)
