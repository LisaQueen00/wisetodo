import json

import pytest

from wisetodo.tools.mcp_settings import load_server_factories


def test_load_is_lazy_and_keeps_factory_snapshot(tmp_path):
    path = tmp_path / "servers.json"
    path.write_text(
        json.dumps(
            {
                "servers": [
                    {
                        "name": "docs",
                        "connection": {
                            "type": "stdio",
                            "command": "nonexistent-executable",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    factories = load_server_factories(path)
    path.write_text('{"servers": []}', encoding="utf-8")
    assert tuple(factories) == ("docs",)
    assert load_server_factories(path) == {}


@pytest.mark.parametrize("content", ["broken secret", '{"extra": 1}', '{"servers": [null]}'])
def test_invalid_file_safe_error(tmp_path, content):
    path = tmp_path / "servers.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match="^Invalid MCP server configuration$"):
        load_server_factories(path)


def test_missing_explicit_file_fails(tmp_path):
    with pytest.raises(ValueError, match="Invalid MCP"):
        load_server_factories(tmp_path / "missing.json")
