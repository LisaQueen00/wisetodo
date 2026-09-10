import asyncio
import base64
import json

import httpx
import pytest

from wisetodo.tools import github
from wisetodo.tools.transport import ToolTransportError


@pytest.fixture
def github_api(monkeypatch):
    requests = []

    def document(body):
        return {"encoding": "base64", "content": base64.b64encode(body.encode()).decode()}

    def respond(request):
        requests.append(request)
        assert request.method == "GET"
        assert request.url.host == "api.github.com"
        path = request.url.path
        data = {
            "/search/repositories": {
                "items": [
                    {
                        "full_name": "sample/cli",
                        "description": "Python CLI",
                        "language": "Python",
                        "archived": False,
                    }
                ]
            },
            "/repos/sample/cli": {
                "description": "Example CLI",
                "default_branch": "main",
                "archived": False,
            },
            "/repos/sample/cli/readme": document(
                "Run examples/hello.py; trace src/cli.py for argument parsing."
            ),
            "/repos/sample/cli/contents/CONTRIBUTING.md": document(
                "Documentation fixes belong in docs/usage.md. Submit a documentation PR."
            ),
            "/repos/sample/cli/contents": [
                {"path": "src", "type": "dir"},
                {"path": "docs", "type": "dir"},
            ],
            "/repos/sample/cli/issues/7": {
                "number": 7,
                "title": "Correct usage example",
                "body": "docs/usage.md uses the wrong option name.",
                "state": "open",
            },
            "/repos/sample/cli/issues": [
                {"number": 8, "title": "This is a PR", "pull_request": {}},
                {
                    "number": 7,
                    "title": "Correct usage example",
                    "body": "docs/usage.md uses the wrong option name.",
                    "state": "open",
                },
            ],
        }
        return httpx.Response(200, json=data[path]) if path in data else httpx.Response(404)

    monkeypatch.setattr(
        github,
        "_client",
        lambda: httpx.AsyncClient(
            transport=httpx.MockTransport(respond), trust_env=False, follow_redirects=False
        ),
    )
    return requests


async def test_read_repository_facts_and_specific_issue(github_api):
    result = await github.read_github_project({"url": "https://github.com/sample/cli/issues/7"})
    assert result["partial"] is True
    assert result["issues"][0]["url"].endswith("/issues/7")
    assert "docs/usage.md" in result["documents"][1]["text"]
    assert result["entries"][0]["path"] == "src"
    assert len(github_api) == 5


async def test_read_root_excludes_pull_requests(github_api):
    result = await github.read_github_project({"url": "https://github.com/sample/cli.git/"})
    assert len(result["issues"]) == 1
    assert result["issues"][0]["url"].endswith("/issues/7")


async def test_search_is_bounded_and_preserves_query(github_api):
    query = "language:Python cli archived:false"
    result = await github.search_projects({"query": query})
    assert result["candidates"][0]["url"] == "https://github.com/sample/cli"
    assert github_api[0].url.params["q"] == query
    assert github_api[0].url.params["per_page"] == "3"


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/a/b",
        "https://localhost/a/b",
        "https://github.com.evil/a/b",
        "https://github.com@evil/a/b",
        "https://github.com/a/../b",
        "https://github.com/a/%2e%2e",
        "https://github.com/a/b/tree/main",
        "https://github.com/a/b?url=https://evil",
        "https://github.com/a/b#fragment",
        "https://github.com/a/b\n",
        "https://github.com/a/b/issues/0",
    ],
)
async def test_invalid_urls_never_fetch(url, github_api):
    with pytest.raises(ToolTransportError):
        await github.read_github_project({"url": url})
    assert not github_api


@pytest.mark.parametrize("status", [301, 403, 429, 500])
async def test_failures_do_not_redirect_or_leak_body(monkeypatch, status):
    seen = []

    def reply(request):
        seen.append(request)
        return httpx.Response(
            status, text="private remote detail", headers={"Location": "https://evil"}
        )

    monkeypatch.setattr(
        github,
        "_client",
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(reply), follow_redirects=False),
    )
    with pytest.raises(ToolTransportError, match="^github_unavailable$"):
        await github.read_github_project({"url": "https://github.com/a/b"})
    assert len(seen) == 1


async def test_missing_repo_returns_clarification_facts(github_api):
    result = await github.read_github_project({"url": "https://github.com/missing/repo"})
    assert result["error"] == "repository_unavailable"
    assert len(github_api) == 1


async def test_size_budget_and_cancellation(monkeypatch):
    monkeypatch.setattr(github, "MAX_BYTES", 10)
    monkeypatch.setattr(
        github,
        "_client",
        lambda: httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b"x" * 11))
        ),
    )
    with pytest.raises(ToolTransportError, match="github_response_too_large"):
        await github.search_projects({"query": "python"})
    entered = asyncio.Event()
    cleaned = asyncio.Event()

    async def blocked(request):
        entered.set()
        try:
            await asyncio.Future()
        finally:
            cleaned.set()

    monkeypatch.setattr(
        github, "_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(blocked))
    )
    task = asyncio.create_task(github.search_projects({"query": "python"}))
    await asyncio.wait_for(entered.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cleaned.is_set()


def test_aggregate_budget_keeps_whole_entries():
    result = {"partial": True, "entries": []}
    for _ in range(20):
        github._append(result, "entries", {"path": "x" * 1000})
    assert len(json.dumps(result, ensure_ascii=False)) <= github.MAX_CHARS
    assert all(len(item["path"]) == 1000 for item in result["entries"])
