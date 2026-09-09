import pytest
from pydantic import ValidationError

from wisetodo.tools import ToolConfig


def config(transport: dict) -> dict:
    return {
        "name": "parse_pdf",
        "description": "提取目录",
        "input_schema": {"type": "object", "properties": {"file_ref": {"type": "string"}}},
        "transport": transport,
    }


@pytest.mark.parametrize(
    "transport",
    [
        {"type": "local", "handler": "parse_pdf"},
        {"type": "http", "url": "http://localhost:8000/parse"},
        {"type": "http", "url": "https://example.org/read", "method": "GET"},
        {"type": "mcp", "server": "documents", "tool": "pdf.read"},
    ],
)
def test_transports_roundtrip_and_model_projection(transport: dict) -> None:
    parsed = ToolConfig.model_validate(config(transport))
    assert ToolConfig.model_validate_json(parsed.model_dump_json()) == parsed
    definition = parsed.to_definition()
    assert set(definition.model_dump()) == {"name", "description", "parameters"}
    assert definition.name == parsed.name
    assert definition.parameters == parsed.input_schema
    definition.parameters["properties"] = {}
    assert parsed.input_schema["properties"] != {}


@pytest.mark.parametrize(
    "transport",
    [
        {},
        {"type": "unknown"},
        {"type": "local"},
        {"type": "local", "handler": "module:function"},
        {"type": "local", "handler": "read", "command": "run"},
        {"type": "http", "url": "file:///private"},
        {"type": "http", "url": "https://user:secret@example.org"},
        {"type": "http", "url": "https://example.org?key=secret"},
        {"type": "http", "url": "https://example.org#secret"},
        {"type": "http", "url": "https://example.org", "method": "DELETE"},
        {"type": "http", "url": "https://example.org", "headers": {"Authorization": "secret"}},
        {"type": "http", "url": 123},
        {"type": "mcp", "server": "docs"},
        {"type": "mcp", "server": "../docs", "tool": "read"},
        {"type": "mcp", "server": "docs", "tool": " "},
        {"type": "mcp", "server": "docs", "tool": "read\n"},
    ],
)
def test_rejects_invalid_or_mixed_transport(transport: dict) -> None:
    with pytest.raises(ValidationError):
        ToolConfig.model_validate(config(transport))


@pytest.mark.parametrize(
    "field,value",
    [
        ("name", "bad name"),
        ("name", 42),
        ("description", " "),
        ("input_schema", {}),
        ("input_schema", {"type": "array"}),
        ("extra", True),
    ],
)
def test_common_fields_are_validated(field: str, value: object) -> None:
    data = config({"type": "local", "handler": "read"})
    data[field] = value
    with pytest.raises(ValidationError):
        ToolConfig.model_validate(data)


def test_config_schema_exposes_discriminated_transport() -> None:
    schema = ToolConfig.model_json_schema()
    assert schema["properties"]["transport"]["discriminator"]["propertyName"] == "type"
    assert schema["additionalProperties"] is False
