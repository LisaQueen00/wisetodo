import json
from pathlib import Path

from wisetodo.skills import SkillSource
from wisetodo.skills.injection import render_skill_guidance

ROOT = Path(__file__).resolve().parents[2] / "skills"


def test_shipped_examples_load_without_issues() -> None:
    snapshot = SkillSource(ROOT).begin_run()
    assert not snapshot.loaded.issues
    assert {skill.metadata.name for skill in snapshot.loaded.skills} == {
        "reading-book",
        "learn-github-project",
        "join-open-source",
    }
    for skill in snapshot.loaded.skills:
        assert skill.document.body.strip()
        assert not skill.metadata.required_tools


def test_example_type_selection_and_whole_body_injection() -> None:
    snapshot = SkillSource(ROOT).begin_run()
    expected = {
        "pdf": {"reading-book"},
        "book_url": {"reading-book"},
        "github_url": {"learn-github-project", "join-open-source"},
        "text": {"join-open-source"},
        "url": set(),
    }
    for kind, names in expected.items():
        candidates = snapshot.candidates([kind])
        assert {skill.metadata.name for skill in candidates} == names
    all_candidates = snapshot.candidates(["pdf", "github_url", "text"])
    payload = json.loads(render_skill_guidance(all_candidates).splitlines()[-1])
    assert payload == [
        {"name": skill.metadata.name, "body": skill.document.body} for skill in all_candidates
    ]
