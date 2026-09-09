import json
import sys
from pathlib import Path

import pytest
from test_agent_runtime import Scope, create_output, message

from wisetodo.agent.runtime import AgentRuntime
from wisetodo.database import initialize_database
from wisetodo.model.contracts import ModelResponse, ToolCall
from wisetodo.sessions.service import SessionService
from wisetodo.todos import TodoService


@pytest.mark.parametrize("mode", ["native", "prompt_compat"])
async def test_runtime_real_stdio_and_fake_model_commit(tmp_path, mode):
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
            self.requests.append(request)
            if len(self.requests) == 1:
                # Changes after loading cannot affect this Run.
                path.write_text("invalid next run", encoding="utf-8")
                if mode == "native":
                    return ModelResponse(
                        finish_reason="tool_calls",
                        tool_calls=(
                            ToolCall(
                                id="call-1",
                                name="echo",
                                arguments='{"value":"verified-local"}',
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
                                    "arguments": {"value": "verified-local"},
                                }
                            ],
                        }
                    ),
                )
            assert request.tools == ()
            assert "verified-local" in request.model_dump_json()
            return ModelResponse(content=json.dumps(create_output()), finish_reason="stop")

    db = initialize_database(tmp_path / "test.db")
    try:
        scope = Provider()
        sessions, todos = SessionService(db.sessions), TodoService(db.sessions)
        sessions.agent_executor = AgentRuntime(sessions, todos, scope, mode=mode, tool_config=path)
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
