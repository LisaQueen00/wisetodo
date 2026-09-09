from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from wisetodo.agent.prompts import build_agent_request
from wisetodo.model.contracts import ModelMessage
from wisetodo.skills import SkillSource


def write(root: Path, name: str = "reading", body: str = "old", accepts: str = "pdf") -> Path:
    path = root / name / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\nname: {name}\ndescription: guide\naccepts: [{accepts}]\n---\n{body}",
        encoding="utf-8",
    )
    return path


def test_edit_is_visible_only_to_new_run(tmp_path: Path) -> None:
    write(tmp_path)
    source = SkillSource(tmp_path)
    first = source.begin_run()
    write(tmp_path, body="new", accepts="text")
    second = source.begin_run()
    assert first.candidates(["pdf"])[0].document.body == "old"
    assert second.candidates(["pdf"]) == ()
    assert second.candidates(["text"])[0].document.body == "new"


def test_creation_and_deletion_are_reloaded(tmp_path: Path) -> None:
    source = SkillSource(tmp_path / "skills")
    empty = source.begin_run()
    path = write(source.root)
    existing = source.begin_run()
    path.unlink()
    deleted = source.begin_run()
    assert empty.loaded.skills == deleted.loaded.skills == ()
    assert len(existing.candidates(["pdf"])) == 1


def test_bad_replacement_is_not_silently_reused_and_can_be_fixed(tmp_path: Path) -> None:
    path = write(tmp_path)
    write(tmp_path, "other")
    source = SkillSource(tmp_path)
    first = source.begin_run()
    path.write_text("broken", encoding="utf-8")
    bad = source.begin_run()
    assert len(first.loaded.skills) == 2
    assert [item.metadata.name for item in bad.loaded.skills] == ["other"]
    assert bad.loaded.issues[0].code == "missing_frontmatter"
    write(tmp_path, body="fixed")
    fixed = source.begin_run()
    assert not fixed.loaded.issues
    assert len(fixed.loaded.skills) == 2


def test_snapshot_can_build_multiple_phases_after_file_changes(tmp_path: Path) -> None:
    write(tmp_path)
    snapshot = SkillSource(tmp_path).begin_run()
    history = [ModelMessage(role="user", content="read")]
    decision = build_agent_request(history, skills=snapshot.candidates(["pdf"]))
    write(tmp_path, body="changed-guidance")
    final = build_agent_request(history, skills=snapshot.candidates(["pdf"]), phase="final")
    for request in [decision, final]:
        assert '"body":"old"' in request.messages[0].content
        assert "changed-guidance" not in request.messages[0].content


def test_snapshot_and_source_are_frozen(tmp_path: Path) -> None:
    source = SkillSource(tmp_path)
    snapshot = source.begin_run()
    with pytest.raises(FrozenInstanceError):
        source.root = tmp_path / "other"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        snapshot.loaded = snapshot.loaded  # type: ignore[misc]


def test_relative_root_rejected() -> None:
    with pytest.raises(ValueError, match="absolute"):
        SkillSource(Path("skills"))
