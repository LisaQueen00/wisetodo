import json

import pytest
from test_agent_runtime import Scope, create_output, message

from wisetodo.agent.runtime import AgentRuntime
from wisetodo.database import initialize_database
from wisetodo.model.contracts import ModelResponse, ToolCall
from wisetodo.sessions.service import SessionService
from wisetodo.todos import TodoService


@pytest.mark.parametrize("mode", ["native", "prompt_compat"])
@pytest.mark.parametrize("with_tool", [False, True])
async def test_url_to_readonly_tool_or_clarification(tmp_path, mode, with_tool):
    url = "https://example.org/book"
    seen = []

    async def read_url(arguments):
        seen.append(arguments)
        return {"url": url, "chapters": ["真实第一章", "真实第二章"]}

    path = tmp_path / "tools.json"
    path.write_text(
        json.dumps(
            {
                "tools": [
                    {
                        "name": "read_url",
                        "description": "Read URL",
                        "input_schema": {
                            "type": "object",
                            "required": ["url"],
                            "properties": {"url": {"type": "string"}},
                        },
                        "transport": {"type": "local", "handler": "read_url"},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    class Provider(Scope):
        async def complete(self, request):
            self.requests.append(request)
            assert any("未抓取" in m.content for m in request.messages)
            if not with_tool:
                assert not request.tools
                return ModelResponse(
                    finish_reason="stop",
                    content=json.dumps({"type": "clarification", "question": "请粘贴书籍目录。"}),
                )
            if len(self.requests) == 1:
                if mode == "native":
                    return ModelResponse(
                        finish_reason="tool_calls",
                        tool_calls=(
                            ToolCall(
                                id="url-call", name="read_url", arguments=json.dumps({"url": url})
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
                                    "callId": "url-call",
                                    "tool": "read_url",
                                    "arguments": {"url": url},
                                }
                            ],
                        }
                    ),
                )
            assert "真实第一章" in request.messages[-1].content
            assert not request.tools
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
            tool_config=path if with_tool else None,
            handlers={"read_url": read_url},
        )
        incoming = message().model_copy(update={"urls": [url]})
        result = await sessions.submit(sessions.create().id, incoming)
        assert result.status == ("completed" if with_tool else "waiting_input")
        assert len(todos.list()) == int(with_tool)
        assert seen == ([{"url": url}] if with_tool else [])
    finally:
        db.dispose()
