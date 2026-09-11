import json

import pytest
from test_agent_runtime import Scope, create_output, message

from wisetodo.agent.runtime import AgentRuntime
from wisetodo.database import initialize_database
from wisetodo.sessions.service import SessionService
from wisetodo.todos import TodoService
from wisetodo.tools.defaults import builtin_tools
from wisetodo.tools.local_handlers import registered_handlers
from wisetodo.tools.repository import SPECS
from wisetodo.tools.source import load_tools


def load(path, **kwargs):
    return load_tools(path, defaults=builtin_tools(), handlers=registered_handlers(), **kwargs)[0]


def test_missing_optional_config_uses_detached_defaults_without_writes(tmp_path):
    path = tmp_path / "tool-settings.json"
    registry = load(path, optional=True)
    assert set(registry.names) == {
        "read_url",
        "parse_pdf",
        "read_github_project",
        "search_projects",
        *SPECS,
    }
    assert not path.exists()
    configs = builtin_tools()
    configs[0].input_schema.clear()
    assert load(path, optional=True).definitions() == registry.definitions()
    with pytest.raises(ValueError):
        load(path)  # Explicit missing config must not silently fall back.


@pytest.mark.parametrize("content", ["{}", '{"tools":[]}', '{"tools":[],"servers":[]}'])
def test_existing_empty_config_disables_every_default(tmp_path, content):
    path = tmp_path / "tools.json"
    path.write_text(content)
    assert load(path, optional=True).names == ()
    assert path.read_text() == content


def test_user_config_replaces_defaults_and_reload_keeps_old_snapshot(tmp_path):
    path = tmp_path / "tools.json"
    old = load(path, optional=True)
    config = next(t for t in builtin_tools() if t.name == "read_github_project").model_dump(
        mode="json"
    )
    config["description"] = "User override"
    content = json.dumps({"tools": [config]})
    path.write_text(content)
    current = load(path, optional=True)
    assert current.names == ("read_github_project",)
    assert current.definitions()[0].description == "User override"
    assert len(old.names) == 4 + len(SPECS)
    assert path.read_text() == content


@pytest.mark.parametrize(
    "content",
    ["invalid", '{"tools":null}', "x" * 262145],
    ids=["invalid-json", "invalid-schema", "oversized"],
)
def test_bad_configuration_never_reenables_defaults(tmp_path, content):
    path = tmp_path / "tools.json"
    path.write_text(content)
    with pytest.raises(ValueError, match="Invalid tool configuration"):
        load(path, optional=True)
    assert path.read_text() == content


@pytest.mark.parametrize("mode", ["native", "prompt_compat"])
async def test_runtime_exposes_defaults_then_honors_disable(tmp_path, mode):
    database = initialize_database(tmp_path / "test.db")
    try:
        path = tmp_path / "tool-settings.json"
        scope = Scope(create_output(), create_output())
        sessions, todos = SessionService(database.sessions), TodoService(database.sessions)
        sessions.agent_executor = AgentRuntime(
            sessions,
            todos,
            scope,
            mode=mode,
            tool_config=path,
            optional_tool_config=True,
        )
        await sessions.submit(sessions.create().id, message())
        assert {tool.name for tool in scope.requests[0].tools} == {
            "read_url",
            "parse_pdf",
            "read_github_project",
            "search_projects",
            *SPECS,
        }
        assert not path.exists()
        path.write_text('{"tools":[]}')
        await sessions.submit(sessions.create().id, message())
        assert scope.requests[1].tools == ()
        assert len(scope.requests) == 2
    finally:
        database.dispose()
