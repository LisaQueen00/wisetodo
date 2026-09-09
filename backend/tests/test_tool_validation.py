from unittest.mock import AsyncMock

import httpx
import pytest
from pydantic import ValidationError

from wisetodo.tools import ToolConfig, ToolRegistry
from wisetodo.tools.transport import ToolExecutor, ToolTransportError
from wisetodo.tools.validation import ToolArgumentsError, validate_arguments

SCHEMA = {
    "type": "object",
    "required": ["count"],
    "additionalProperties": False,
    "properties": {
        "count": {"type": "integer", "minimum": 1},
        "tags": {"type": "array", "items": {"enum": ["a", "b"]}},
    },
}


def config(schema, transport=None):
    return ToolConfig.model_validate(
        {
            "name": "read",
            "description": "read",
            "input_schema": schema,
            "transport": transport or {"type": "local", "handler": "read"},
        }
    )


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"count": "1"},
        {"count": True},
        {"count": 0},
        {"count": 1, "extra": "private"},
        {"count": 1, "tags": ["c"]},
        {"count": float("nan")},
        [],
    ],
)
def test_arguments_rejected_without_values(arguments):
    with pytest.raises(ToolArgumentsError, match="^invalid_tool_arguments$"):
        validate_arguments(SCHEMA, arguments)


def test_valid_values_and_local_reference():
    validate_arguments(SCHEMA, {"count": 2, "tags": ["a"]})
    schema = {
        "type": "object",
        "$defs": {"word": {"type": "string"}},
        "properties": {"value": {"$ref": "#/$defs/word"}},
    }
    config(schema)
    validate_arguments(schema, {"value": "ok"})
    with pytest.raises(ToolArgumentsError):
        validate_arguments(schema, {"value": 1})


@pytest.mark.parametrize(
    "schema",
    [
        {"type": "object", "required": "x"},
        {"type": "object", "properties": {"x": {"type": "bogus"}}},
        {"type": "object", "$ref": "https://example.org/schema"},
        {"type": "object", "$dynamicRef": "file:///private"},
        {"type": "object", "$id": "https://example.org/"},
        {"type": "object", "$schema": "http://json-schema.org/draft-07/schema#"},
    ],
)
def test_bad_schema_rejected_at_registration(schema):
    with pytest.raises(ValidationError):
        config(schema)


@pytest.mark.parametrize(
    "transport",
    [
        {"type": "local", "handler": "read"},
        {"type": "http", "url": "https://example.org"},
        {"type": "mcp", "server": "docs", "tool": "read"},
    ],
)
async def test_invalid_arguments_never_reach_transport(transport):
    handler = AsyncMock()
    factory = AsyncMock()

    def http_handler(request):
        pytest.fail("HTTP must not be called")

    async with httpx.AsyncClient(transport=httpx.MockTransport(http_handler)) as client:
        executor = ToolExecutor(
            ToolRegistry([config(SCHEMA, transport)]),
            http=client,
            handlers={"read": handler},
            servers={"docs": factory},
        )
        with pytest.raises(ToolTransportError, match="^invalid_tool_arguments$"):
            await executor.execute("read", {"count": "private"})
        handler.assert_not_called()
        factory.assert_not_called()
