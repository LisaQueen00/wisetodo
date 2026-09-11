"""Offline contracts: immutable reads, pagination, search scope and safe failure."""

import asyncio
import base64
import json

import httpx
import pytest

from wisetodo.tools import github
from wisetodo.tools.repository import RepositoryReader, repository_tools
from wisetodo.tools.transport import ToolTransportError

SHA = "a" * 40
URL = "https://github.com/example/project"


@pytest.fixture
def api(monkeypatch):
    seen = []

    def reply(request):
        seen.append(request)
        path = request.url.path
        if path.endswith("/commits"):
            return httpx.Response(
                200,
                json=[
                    {
                        "sha": SHA,
                        "commit": {
                            "message": "add indexing",
                            "author": {"name": "A", "date": "2026-01-01"},
                        },
                    }
                ],
            )
        if "/commits/" in path:
            return httpx.Response(
                200,
                json={
                    "sha": SHA,
                    "commit": {"message": "fix"},
                    "files": [{"filename": "main.py", "status": "modified", "patch": "@@\n+ok"}],
                },
            )
        if "/git/trees/" in path:
            return httpx.Response(
                200,
                json={
                    "tree": [{"path": f"src/file{i}.py", "type": "blob"} for i in range(7)],
                    "truncated": True,
                },
            )
        if path.endswith("/comments"):
            return httpx.Response(200, json=[{"body": "design discussion", "html_url": URL}])
        if "/issues/" in path:
            return httpx.Response(200, json={"title": "why", "body": "context", "pull_request": {}})
        if path.endswith("/contents/") or path.endswith("/contents/src"):
            return httpx.Response(
                200, json=[{"path": f"src/{i}.py", "type": "file"} for i in range(30)]
            )
        if path.endswith("missing"):
            return httpx.Response(404)
        if "/contents/" in path or path.endswith("/readme"):
            body = "class Index:\n    def run(self):\n        return 'needle'\n" + "# tail\n" * 100
            return httpx.Response(
                200,
                json={
                    "type": "file",
                    "encoding": "base64",
                    "content": base64.b64encode(body.encode()).decode(),
                },
            )
        return httpx.Response(200, json={"description": "example"})

    monkeypatch.setattr(
        github, "_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(reply))
    )
    return seen


async def test_snapshot_and_cache_shared_between_parallel_reads(api):
    reader = RepositoryReader()
    args = {"url": URL, "path": "main.py"}
    results = await asyncio.gather(*(reader.execute("read_github_file", args) for _ in range(2)))
    assert results[0] == results[1]
    assert results[0]["commit"] == SHA
    assert len(api) == 2
    assert api[-1].url.params["ref"] == SHA
    assert results[0]["next_line"] == 81
    results[0]["lines"].clear()
    assert (await reader.execute("read_github_file", args))["lines"]


async def test_inspect_directory_and_line_pagination(api):
    reader = RepositoryReader()
    overview = await reader.execute("inspect_github_project", {"url": URL})
    assert overview["next_page"] == 2 and overview["readme"]
    tree = await reader.execute("list_github_tree", {"url": URL, "path": "src", "page": 2})
    assert len(tree["entries"]) == 5 and tree["next_page"] is None
    tail = await reader.execute(
        "read_github_file", {"url": URL, "path": "main.py", "start_line": 81}
    )
    assert tail["lines"][0]["line"] == 81 and tail["next_line"] is None


async def test_search_is_bounded_and_reports_truncated_tree(api):
    reader = RepositoryReader()
    args = {"url": URL, "query": "needle", "path": "src"}
    first = await reader.execute("search_github_code", args)
    assert len(first["scanned_paths"]) == 5 and first["next_page"] == 2
    assert first["tree_truncated"] is True
    assert first["matches"][0]["hits"][0]["line"] == 3
    second = await reader.execute("search_github_code", {**args, "page": 2})
    assert len(second["scanned_paths"]) == 2 and second["next_page"] is None


async def test_symbols_are_python_definitions_not_references(api):
    reader = RepositoryReader()
    result = await reader.execute("inspect_github_file_symbols", {"url": URL, "path": "main.py"})
    assert [s["name"] for s in result["symbols"]] == ["Index", "run"]
    assert result["symbols"][1]["scope"] == "Index"
    unsupported = await reader.execute(
        "inspect_github_file_symbols", {"url": URL, "path": "main.ts"}
    )
    assert unsupported["error"] == "unsupported_symbol_language"


async def test_history_commit_and_discussion_scopes(api):
    reader = RepositoryReader()
    history = await reader.execute(
        "read_github_history", {"url": URL, "query": "index", "path": "src"}
    )
    assert history["commits"][0]["sha"] == SHA
    assert api[-1].url.params["path"] == "src"
    absent = await reader.execute("read_github_history", {"url": URL, "query": "absent"})
    assert absent["commits"] == []
    commit = await reader.execute("read_github_commit", {"url": URL, "commit": SHA})
    assert commit["files"][0]["patch"]["lines"][1]["text"] == "+ok"
    discussion = await reader.execute("read_github_discussion_context", {"url": URL, "number": 1})
    assert discussion["kind"] == "pull_request" and discussion["comments"]


@pytest.mark.parametrize("path", ["../secret", "/etc/passwd", "a//b", "a%2fb", "a?b", "a\\b"])
async def test_invalid_path_never_reaches_network(api, path):
    with pytest.raises(ToolTransportError):
        await RepositoryReader().execute("read_github_file", {"url": URL, "path": path})
    assert not api


async def test_missing_file_explicit(api):
    result = await RepositoryReader().execute("read_github_file", {"url": URL, "path": "missing"})
    assert result["error"] == "file_unavailable_or_unsupported"


def test_all_tools_registered_and_long_lines_marked():
    assert len(repository_tools()) == 8
    assert set(RepositoryReader().handlers()) == {t.name for t in repository_tools()}
    result = RepositoryReader.lines("x" * 9000 + "\ntail", 1)
    assert result["line_truncated"] and result["next_line"] == 2
    assert RepositoryReader.symbols("broken python !", 1)["error"] == "symbol_parse_failed"


@pytest.mark.parametrize("mode", ["native", "prompt_compat"])
@pytest.mark.parametrize("scenario,expected", [("chain", 9), ("repeat", 3), ("no_progress", 3)])
async def test_runtime_dependent_reads_stop_on_budget_or_no_progress(
    tmp_path, api, mode, scenario, expected
):
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
            if step == expected:
                assert not request.tools
                return ModelResponse(content=json.dumps(create_output()), finish_reason="stop")
            assert request.tools
            line = step if scenario == "chain" else 1 if scenario == "repeat" else 1000 + step
            args = {"url": URL, "path": "main.py", "start_line": line}
            if mode == "native":
                return ModelResponse(
                    finish_reason="tool_calls",
                    tool_calls=(
                        ToolCall(id=str(step), name="read_github_file", arguments=json.dumps(args)),
                    ),
                )
            return ModelResponse(
                finish_reason="stop",
                content=json.dumps(
                    {
                        "type": "tool_calls",
                        "calls": [
                            {"callId": str(step), "tool": "read_github_file", "arguments": args}
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
        assert len(provider.requests) == expected
        assert len(api) == 2  # Run-scoped file cache, regardless of model rounds.
    finally:
        db.dispose()


async def test_cancel_releases_cache_lock(monkeypatch):
    started = asyncio.Event()

    async def waiting(client, path, **params):
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(github, "_get", waiting)
    reader = RepositoryReader()
    task = asyncio.create_task(reader.execute("inspect_github_project", {"url": URL}))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not reader.lock.locked() and reader.cache_bytes == 0
