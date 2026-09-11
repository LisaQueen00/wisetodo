import base64
import json

import httpx
import pytest

from wisetodo.tools import github
from wisetodo.tools.transport import ToolTransportError


@pytest.mark.parametrize("mode", ["native", "prompt_compat"])
async def test_runtime_allows_dependent_file_reads(tmp_path, api, mode):
    from test_agent_runtime import Scope, create_output, message

    from wisetodo.agent.runtime import AgentRuntime
    from wisetodo.database import initialize_database
    from wisetodo.model.contracts import ModelResponse, ToolCall
    from wisetodo.sessions.service import SessionService
    from wisetodo.todos import TodoService

    class Provider(Scope):
        async def complete(self, request):
            self.requests.append(request)
            step = len(self.requests)
            if step == 3:
                assert "app/index.ts" in request.messages[-1].content
                return ModelResponse(content=json.dumps(create_output()), finish_reason="stop")
            args = {
                "url": "https://github.com/a/b",
                "paths": ["package.json" if step == 1 else "app"],
            }
            if mode == "native":
                return ModelResponse(
                    finish_reason="tool_calls",
                    tool_calls=(
                        ToolCall(
                            id=str(step), name="read_github_project", arguments=json.dumps(args)
                        ),
                    ),
                )
            return ModelResponse(
                finish_reason="stop",
                content=json.dumps(
                    {
                        "type": "tool_calls",
                        "calls": [
                            {"callId": str(step), "tool": "read_github_project", "arguments": args}
                        ],
                    }
                ),
            )

    db = initialize_database(tmp_path / "runtime.db")
    try:
        sessions, todos, provider = (
            SessionService(db.sessions),
            TodoService(db.sessions),
            Provider(),
        )
        sessions.agent_executor = AgentRuntime(
            sessions,
            todos,
            provider,
            mode=mode,
            tool_config=tmp_path / "tools.json",
            optional_tool_config=True,
        )
        result = await sessions.submit(sessions.create().id, message("学习项目"))
        assert result.status == "completed" and len(todos.list()) == 1
        assert len(api) == 2 and len(result.tool_events) == 4
    finally:
        db.dispose()


@pytest.fixture
def api(monkeypatch):
    seen = []

    def respond(request):
        seen.append(request)
        path = request.url.path
        if path.endswith("/app") or path.endswith("/packages"):
            return httpx.Response(200, json=[{"path": "app/index.ts", "type": "file"}])
        content = (
            '{"scripts":{"start":"electron .","test":"node --test"}}'
            if path.endswith("package.json")
            else "test code\n" * 400
        )
        return httpx.Response(
            200,
            json={
                "type": "file",
                "encoding": "base64",
                "content": base64.b64encode(content.encode()).decode(),
            },
        )

    monkeypatch.setattr(
        github, "_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(respond))
    )
    return seen


async def test_requested_manifest_directories_and_test_file(api):
    result = await github.read_github_project(
        {
            "url": "https://github.com/a/b",
            "paths": ["package.json", "app", "packages", "tests/app-indexer.test.mjs"],
            "ref": "main",
        }
    )
    assert "electron" in result["files"][0]["text"]
    assert result["files"][1]["entries"][0]["path"] == "app/index.ts"
    assert result["files"][3]["next_offset"] == 2400
    assert len(api) == 4 and all(r.url.params["ref"] == "main" for r in api)
    assert len(json.dumps(result)) < 16000
    more = await github.read_github_project(
        {"url": "https://github.com/a/b", "paths": ["tests/app-indexer.test.mjs"], "offset": 2400}
    )
    assert more["files"][0]["offset"] == 2400
    assert more["files"][0]["next_offset"] is None


@pytest.mark.parametrize(
    "path", ["../secret", "/etc/passwd", "a//b", "a%2fb", "a?ref=evil", "a\\b"]
)
async def test_invalid_paths_never_request(api, path):
    with pytest.raises(ToolTransportError):
        await github.read_github_project({"url": "https://github.com/a/b", "paths": [path]})
    assert not api
