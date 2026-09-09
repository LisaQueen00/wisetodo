import pytest
from pydantic import ValidationError

from wisetodo.tools import DuplicateToolNameError, ToolConfig, ToolRegistry


def config(name: str = "read", kind: str = "local") -> ToolConfig:
    transports = {
        "local": {"type": "local", "handler": "read"},
        "http": {"type": "http", "url": "https://example.org/read"},
        "mcp": {"type": "mcp", "server": "docs", "tool": "read"},
    }
    return ToolConfig.model_validate(
        {
            "name": name,
            "description": "Read",
            "input_schema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
            },
            "transport": transports[kind],
        }
    )


def test_empty_registry_and_unknown_lookup() -> None:
    registry = ToolRegistry()
    assert registry.names == registry.definitions() == ()
    assert registry.get("missing") is None


def test_stable_order_and_case_sensitive_namespace() -> None:
    configs = [config("z"), config("a", "http"), config("A", "mcp")]
    registry = ToolRegistry(iter(configs))
    assert registry.names == ("z", "a", "A")
    assert [tool.name for tool in registry.definitions()] == ["z", "a", "A"]
    for original in configs:
        assert registry.get(original.name) == original


@pytest.mark.parametrize("kind", ["local", "http", "mcp"])
def test_duplicates_rejected_across_transports(kind: str) -> None:
    with pytest.raises(DuplicateToolNameError) as caught:
        ToolRegistry([config(), config(kind=kind)])
    assert caught.value.name == "read"
    assert str(caught.value) == "Duplicate tool name: read"


def test_input_and_output_mutations_cannot_change_registry() -> None:
    original = config()
    registry = ToolRegistry([original])
    original.input_schema["properties"] = {}
    first = registry.get("read")
    assert first is not None
    assert first.input_schema["properties"] != {}
    first.input_schema["properties"] = {}
    registry.definitions()[0].parameters["properties"] = {}
    second = registry.get("read")
    assert second is not None
    assert second.input_schema["properties"] != {}
    assert set(registry.definitions()[0].model_dump()) == {"name", "description", "parameters"}


def test_invalid_mutated_config_is_revalidated() -> None:
    original = config()
    original.input_schema["type"] = "array"
    with pytest.raises(ValidationError):
        ToolRegistry([original])


def test_failed_replacement_and_new_snapshot_leave_old_registry_unchanged() -> None:
    old = ToolRegistry([config()])
    with pytest.raises(DuplicateToolNameError):
        ToolRegistry([config("new"), config("new")])
    new = ToolRegistry([config("new")])
    assert old.names == ("read",)
    assert new.names == ("new",)
