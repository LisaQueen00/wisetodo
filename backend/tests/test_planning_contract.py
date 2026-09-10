"""Offline prompt/fixture/commit contracts, not a real-model semantic evaluation."""

import json
from pathlib import Path

import pytest
from test_agent_runtime import Scope, message

from wisetodo.agent.prompts import build_agent_request
from wisetodo.agent.results import AGENT_RESULT_ADAPTER
from wisetodo.agent.runtime import AgentRuntime
from wisetodo.database import initialize_database
from wisetodo.model.contracts import ModelMessage, ToolDefinition
from wisetodo.sessions.service import SessionService
from wisetodo.skills import SkillSource
from wisetodo.todos import TodoService

ROOT = Path(__file__).resolve().parents[2]
CASES = json.loads(
    (Path(__file__).parent / "fixtures/planning_cases.json").read_text(encoding="utf-8")
)
RULES = (
    "真实章节及标题",
    "不编造目录",
    "实际模块",
    "按实际行动及依赖顺序规划",
    "不能用通用步骤替代未知的书籍目录或项目结构",
    "不按天、周或时间段切分",
    "真实章节标题应保留",
    "多个独立目标时用 clarification",
)


def example_result(case):
    if "question" in case:
        return {"type": "clarification", "question": case["question"]}
    return {
        "type": "todo_operation",
        "operation": {
            "action": "create",
            "todo": {"topic": case["id"], "items": case["items"]},
        },
    }


@pytest.mark.parametrize("mode", ["native", "prompt_compat"])
@pytest.mark.parametrize("phase", ["decision", "final"])
@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_planning_rules_and_complete_skills_reach_each_request(case, phase, mode):
    snapshot = SkillSource(ROOT / "skills").begin_run()
    candidates = snapshot.candidates(["text"])
    assert len(candidates) == 3
    request = build_agent_request(
        [ModelMessage(role="user", content=case["input"])],
        mode=mode,
        phase=phase,
        skills=candidates,
        tools=[
            ToolDefinition(
                name="read_github_project", description="只读资料", parameters={"type": "object"}
            )
        ],
    )
    system = request.messages[0].content
    assert all(rule in system for rule in RULES)
    # Check complete guidance survives the shared injection budget, not just names.
    for skill in candidates:
        assert json.dumps(skill.document.body, ensure_ascii=False) in system
    if case["skill"]:
        assert case["skill"] in {skill.metadata.name for skill in candidates}
    assert request.messages[-1].content == case["input"]
    assert bool(request.tools) == (phase == "decision")
    assert AGENT_RESULT_ADAPTER.validate_python(example_result(case))
    assert case["reject"]  # Human semantic rubric; not an asserted model behavior.


@pytest.mark.parametrize("mode", ["native", "prompt_compat"])
@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
async def test_reference_outputs_commit_without_rewriting_or_fabrication(tmp_path, mode, case):
    db = initialize_database(tmp_path / "case.db")
    try:
        sessions, todos = SessionService(db.sessions), TodoService(db.sessions)
        provider = Scope(example_result(case))
        sessions.agent_executor = AgentRuntime(
            sessions, todos, provider, mode=mode, skill_source=SkillSource(ROOT / "skills")
        )
        result = await sessions.submit(sessions.create().id, message(case["input"]))
        assert len(provider.requests) == 1
        assert all(rule in provider.requests[0].messages[0].content for rule in RULES)
        if "question" in case:
            assert result.status == "waiting_input"
            assert result.messages[-1].content == case["question"]
            assert not todos.list()
        else:
            assert result.status == "completed"
            assert len(todos.list()) == 1
            assert [item.topic for item in todos.list()[0].items] == case["items"]
            assert all(not item.completed for item in todos.list()[0].items)
        assert not result.tool_events
    finally:
        db.dispose()
