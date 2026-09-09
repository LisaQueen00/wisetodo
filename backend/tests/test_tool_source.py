import json

import pytest

from wisetodo.tools.source import load_tools


def test_load_http_snapshot(tmp_path):
    path = tmp_path / "tools.json"
    path.write_text(
        json.dumps(
            {
                "tools": [
                    {
                        "name": "read",
                        "description": "read",
                        "input_schema": {"type": "object"},
                        "transport": {"type": "http", "url": "http://127.0.0.1:8000/read"},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    registry, servers = load_tools(path)
    path.write_text("{}", encoding="utf-8")
    assert registry.names == ("read",)
    assert servers == {}
    assert load_tools(path)[0].names == ()


@pytest.mark.parametrize(
    "transport",
    [
        {"type": "local", "handler": "not_registered"},
        {"type": "mcp", "server": "missing", "tool": "read"},
    ],
)
def test_unavailable_configuration_rejected(tmp_path, transport):
    path = tmp_path / "tools.json"
    path.write_text(
        json.dumps(
            {
                "tools": [
                    {
                        "name": "read",
                        "description": "read",
                        "input_schema": {"type": "object"},
                        "transport": transport,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="^Invalid tool configuration$"):
        load_tools(path)
