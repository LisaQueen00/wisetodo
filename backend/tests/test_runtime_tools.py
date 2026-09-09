import json
import sys
from pathlib import Path

import pytest
from test_agent_runtime import Scope, create_output, message

from wisetodo.agent.runtime import AgentRuntime
from wisetodo.database import initialize_database
from wisetodo.model.contracts import ModelResponse, ToolCall
from wisetodo.sessions.service import SessionService
from wisetodo.skills import SkillSource
from wisetodo.todos import TodoService


@pytest.mark.parametrize("mode", ["native", "prompt_compat"])
@pytest.mark.parametrize("oversized", [False, True])
async def test_runtime_real_stdio_and_fake_model_commit(tmp_path, mode, oversized):
    skill_path = tmp_path / "skills" / "guide" / "SKILL.md"
    skill_path.parent.mkdir(parents=True)
    skill_path.write_text(
        "---\nname: guide\ndescription: guide\naccepts: [text]\n---\noriginal-guidance",
        encoding="utf-8",
    )
    path = tmp_path / "tools.json"
    path.write_text(
        json.dumps(
            {
                "tools": [
                    {
                        "name": "echo",
                        "description": "test",
                        "input_schema": {
                            "type": "object",
                            "properties": {"value": {"type": "string"}},
                            "required": ["value"],
                        },
                        "transport": {"type": "mcp", "server": "test", "tool": "echo"},
                    }
                ],
                "servers": [
                    {
                        "name": "test",
                        "connection": {
                            "type": "stdio",
                            "command": sys.executable,
                            "args": [str(Path(__file__).parent / "fixtures" / "mcp_server.py")],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    class Provider(Scope):
        async def complete(self, request):
            assert "original-guidance" in request.messages[0].content
            assert "changed-guidance" not in request.messages[0].content
            self.requests.append(request)
            if len(self.requests) == 1:
                # Changes after loading cannot affect this Run.
                path.write_text("invalid next run", encoding="utf-8")
                skill_path.write_text(
                    "---\nname: guide\ndescription: guide\naccepts: [text]\n---\nchanged-guidance",
                    encoding="utf-8",
                )
                if mode == "native":
                    return ModelResponse(
                        finish_reason="tool_calls",
                        tool_calls=(
                            ToolCall(
                                id="call-1",
                                name="echo",
                                arguments=json.dumps(
                                    {"value": "x" * 20_000 if oversized else "verified-local"}
                                ),
                            ),
                        ),
                    )
                return ModelResponse(
                    finish_reason="stop",
                    content=json.dumps(
                        {
                            "type": "tool_calls",
                            "calls": [
                                {
                                    "callId": "call-1",
                                    "tool": "echo",
                                    "arguments": {
                                        "value": "x" * 20_000 if oversized else "verified-local"
                                    },
                                }
                            ],
                        }
                    ),
                )
            assert request.tools == ()
            if oversized:
                # Inspect result message only; the call arguments also appear in history.
                assert "content_budget" in request.messages[-1].content
                assert "x" * 20_000 not in request.messages[-1].content
            else:
                assert "verified-local" in request.model_dump_json()
            return ModelResponse(content=json.dumps(create_output()), finish_reason="stop")

    db = initialize_database(tmp_path / "test.db")
    try:
        scope = Provider()
        sessions, todos = SessionService(db.sessions), TodoService(db.sessions)
        sessions.agent_executor = AgentRuntime(
            sessions,
            todos,
            scope,
            mode=mode,
            tool_config=path,
            skill_source=SkillSource(tmp_path / "skills"),
        )
        result = await sessions.submit(sessions.create().id, message())
        assert result.status == "completed"
        assert [event.event_type for event in result.tool_events] == ["started", "completed"]
        assert {event.call_id for event in result.tool_events} == {"call-1"}
        assert "verified-local" not in json.dumps([event.payload for event in result.tool_events])
        assert len(todos.list()) == 1
        assert len(scope.requests) == 2
        assert scope.opens == scope.closes == 1
    finally:
        db.dispose()
