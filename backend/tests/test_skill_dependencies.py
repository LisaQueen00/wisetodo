from dataclasses import replace
from pathlib import Path
from typing import Literal

import pytest

from wisetodo.agent.prompts import build_agent_request
from wisetodo.model.contracts import ModelMessage, ToolDefinition
from wisetodo.skills import filter_available_skills
from wisetodo.skills.loader import SkillDocument
from wisetodo.skills.metadata import SkillMetadata, ValidatedSkill


def skill(required: tuple[str, ...] = (), optional: tuple[str, ...] = ()) -> ValidatedSkill:
    return ValidatedSkill(
        SkillDocument(Path("skill/SKILL.md"), "skill", "", "依赖测试指导正文"),
        SkillMetadata("skill", "guide", ("pdf",), required, optional),
    )


@pytest.mark.parametrize(
    "available,enabled",
    [
        ([], False),
        (["parse_pdf"], False),
        (["read_url"], False),
        (["parse_pdf", "read_url"], True),
        (["parse_pdf", "read_url", "extra"], True),
        (["PARSE_PDF", "read_url"], False),
    ],
)
def test_all_required_tools_must_exist(available: list[str], enabled: bool) -> None:
    candidate = skill(("parse_pdf", "read_url"))
    assert filter_available_skills([candidate], available) == ((candidate,) if enabled else ())


def test_optional_tools_and_no_dependencies_do_not_disable() -> None:
    candidates = (skill(), skill(optional=("missing",)))
    assert filter_available_skills(candidates, []) == candidates


def test_order_identity_and_run_snapshot_are_preserved() -> None:
    independent = skill()
    dependent = skill(("parse_pdf",))
    tools = ["parse_pdf"]
    result = filter_available_skills(iter([dependent, independent]), iter(tools))
    tools.clear()
    assert result == (dependent, independent)
    assert result[0] is dependent
    assert filter_available_skills(result, tools) == (independent,)


def test_rejects_bare_tool_name() -> None:
    with pytest.raises(ValueError):
        filter_available_skills([], "parse_pdf")


@pytest.mark.parametrize("mode", ["native", "prompt_compat"])
@pytest.mark.parametrize("phase", ["decision", "final"])
def test_request_checks_run_tools_before_phase_restrictions(
    mode: Literal["native", "prompt_compat"], phase: Literal["decision", "final"]
) -> None:
    history = [ModelMessage(role="user", content="read")]
    candidate = skill(("parse_pdf",))
    baseline = build_agent_request(history, mode=mode, phase=phase)
    assert build_agent_request(history, skills=[candidate], mode=mode, phase=phase) == baseline
    definition = ToolDefinition(name="parse_pdf", description="read", parameters={"type": "object"})
    request = build_agent_request(
        history, skills=[candidate], tools=[definition], mode=mode, phase=phase
    )
    assert candidate.document.body in request.messages[0].content
    assert request.tools == ((definition,) if phase == "decision" else ())
    if phase == "final":
        assert "当前禁止调用工具" in request.messages[0].content


def test_disabled_candidates_do_not_consume_injection_budget() -> None:
    disabled = skill(("missing",))
    enabled = replace(skill(), document=replace(skill().document, body="可用指导"))
    request = build_agent_request(
        [ModelMessage(role="user", content="read")], skills=[disabled] * 3 + [enabled]
    )
    assert disabled.document.body not in request.messages[0].content
    assert enabled.document.body in request.messages[0].content
