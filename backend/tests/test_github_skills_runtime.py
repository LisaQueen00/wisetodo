import json
from pathlib import Path

import pytest
from test_agent_runtime import Scope, create_output, message
from test_github_tools import github_api  # noqa: F401 -- shared isolated HTTP fixture

from wisetodo.agent.runtime import AgentRuntime
from wisetodo.database import initialize_database
from wisetodo.model.contracts import ModelResponse, ToolCall
from wisetodo.sessions.service import SessionService
from wisetodo.skills import SkillSource
from wisetodo.todos import TodoService

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("mode", ["native", "prompt_compat"])
@pytest.mark.parametrize("scenario", ["learn", "contribute", "search", "missing", "no_tool"])
async def test_github_skill_flows(tmp_path, request, mode, scenario):
    github_requests = request.getfixturevalue("github_api")
    items = (
        ["运行 examples/hello.py 示例", "从 src/cli.py 追踪参数解析"]
        if scenario == "learn"
        else ["修正 docs/usage.md 的选项名示例", "按贡献指南准备文档 PR"]
    )

    class Provider(Scope):
        async def complete(self, request):
            self.requests.append(request)
            combined = "\n".join(m.content for m in request.messages)
            assert "学习一个开源项目" in combined
            assert "参与开源贡献" in combined
            index = len(self.requests)
            if scenario == "no_tool":
                assert not request.tools
                output = {"type": "clarification", "question": "请提供 README 与目录。"}
            elif index % 2:
                tool = (
                    "search_projects"
                    if scenario == "search" and index == 1
                    else "read_github_project"
                )
                arguments = (
                    {"query": "language:Python cli archived:false"}
                    if tool == "search_projects"
                    else {
                        "url": "https://github.com/missing/repo"
                        if scenario == "missing"
                        else "https://github.com/sample/cli/issues/7"
                    }
                )
                if mode == "native":
                    return ModelResponse(
                        finish_reason="tool_calls",
                        tool_calls=(ToolCall(id="gh", name=tool, arguments=json.dumps(arguments)),),
                    )
                output = {
                    "type": "tool_calls",
                    "calls": [{"callId": "gh", "tool": tool, "arguments": arguments}],
                }
            elif scenario == "search" and index == 2:
                assert "https://github.com/sample/cli" in request.messages[-1].content
                assert request.tools  # Search may now be followed by a dependent read.
                output = {
                    "type": "clarification",
                    "question": "候选 https://github.com/sample/cli 是 Python CLI，是否选择它？",
                }
            elif scenario == "missing":
                assert "repository_unavailable" in request.messages[-1].content
                output = {"type": "clarification", "question": "请确认项目链接或粘贴资料。"}
            else:
                assert "docs/usage.md" in request.messages[-1].content
                assert not request.tools
                output = create_output("学习 CLI" if scenario == "learn" else "修正文档示例")
                output["operation"]["todo"]["items"] = items
            return ModelResponse(finish_reason="stop", content=json.dumps(output))

    db = initialize_database(tmp_path / "test.db")
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
            skill_source=SkillSource(ROOT / "skills"),
            tool_config=None if scenario == "no_tool" else ROOT / "examples/github-tools.json",
        )
        session = sessions.create()
        content = "我想学习这个项目" if scenario == "learn" else "我想贡献 Python CLI 文档"
        if scenario != "search":
            content += (
                " https://github.com/missing/repo"
                if scenario == "missing"
                else " https://github.com/sample/cli/issues/7"
            )
        result = await sessions.submit(session.id, message(content))
        if scenario == "search":
            assert result.status == "waiting_input"
            assert not todos.list()
            result = await sessions.submit(
                session.id, message("选择 https://github.com/sample/cli，修复 issue 7 的文档示例。")
            )
        expected = "waiting_input" if scenario in {"missing", "no_tool"} else "completed"
        assert result.status == expected
        assert len(provider.requests) == (
            4 if scenario == "search" else 1 if scenario == "no_tool" else 2
        )
        assert len(todos.list()) == int(expected == "completed")
        if expected == "completed":
            assert [item.topic for item in todos.list()[0].items] == items
        if scenario == "no_tool":
            assert not github_requests
    finally:
        db.dispose()
