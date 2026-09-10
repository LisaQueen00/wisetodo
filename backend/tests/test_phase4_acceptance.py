import json

import pytest
from test_agent_runtime import Scope, create_output, message

from wisetodo.agent.runtime import AgentRuntime
from wisetodo.database import initialize_database
from wisetodo.model.contracts import ModelResponse, ToolCall
from wisetodo.sessions.service import SessionService
from wisetodo.skills import SkillSource
from wisetodo.todos import TodoService
from wisetodo.tools.source import load_tools


@pytest.mark.parametrize("mode", ["native", "prompt_compat"])
async def test_same_runtime_discovers_additions_changes_and_removal(tmp_path, mode):
    path = tmp_path / "tool-settings.json"
    skill_path = tmp_path / "skills" / "guide" / "SKILL.md"
    version = ""
    seen = []

    def write(version):
        path.write_text(
            json.dumps(
                {
                    "tools": [
                        {
                            "name": version,
                            "description": "local",
                            "input_schema": {"type": "object"},
                            "transport": {"type": "local", "handler": "trusted"},
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        skill_path.parent.mkdir(parents=True, exist_ok=True)
        skill_path.write_text(
            f"---\nname: guide\ndescription: guide\naccepts: [text]\n---\nguidance-{version}",
            encoding="utf-8",
        )

    async def handler(arguments):
        seen.append(version)
        return {"value": version}

    class Provider(Scope):
        async def complete(self, request):
            self.requests.append(request)
            if not version:
                assert {tool.name for tool in request.tools} == {
                    "parse_pdf",
                    "read_github_project",
                    "search_projects",
                }
                assert "guidance-" not in request.messages[0].content
            else:
                assert f"guidance-{version}" in request.messages[0].content
                if request.tools:
                    assert [tool.name for tool in request.tools] == [version]
                    if mode == "native":
                        return ModelResponse(
                            finish_reason="tool_calls",
                            tool_calls=(ToolCall(id="call", name=version, arguments="{}"),),
                        )
                    return ModelResponse(
                        finish_reason="stop",
                        content=json.dumps(
                            {
                                "type": "tool_calls",
                                "calls": [{"callId": "call", "tool": version, "arguments": {}}],
                            }
                        ),
                    )
            return ModelResponse(finish_reason="stop", content=json.dumps(create_output()))

    db = initialize_database(tmp_path / "test.db")
    try:
        sessions, todos = SessionService(db.sessions), TodoService(db.sessions)
        provider = Provider()
        sessions.agent_executor = AgentRuntime(
            sessions,
            todos,
            provider,
            mode=mode,
            tool_config=path,
            optional_tool_config=True,
            skill_source=SkillSource(tmp_path / "skills"),
            handlers={"trusted": handler},
        )
        for version in ("", "first", "second", ""):
            if version:
                write(version)
            elif path.exists():
                path.unlink()
                skill_path.unlink()
            result = await sessions.submit(sessions.create().id, message())
            assert result.status == "completed"
        assert seen == ["first", "second"]
        assert len(todos.list()) == 4
        assert len(provider.requests) == 6
    finally:
        db.dispose()


def test_optional_is_not_a_bypass_for_invalid_config(tmp_path):
    path = tmp_path / "tools.json"
    assert load_tools(path, optional=True)[0].names == ()
    with pytest.raises(ValueError):
        load_tools(path)
    path.write_text("broken", encoding="utf-8")
    with pytest.raises(ValueError):
        load_tools(path, optional=True)
