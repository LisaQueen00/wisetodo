from pathlib import Path

import pytest

from wisetodo.skills import load_skills, select_skills, validate_skill_document
from wisetodo.skills.loader import SkillDocument
from wisetodo.skills.metadata import ValidatedSkill


def skill(name: str, accepts: str) -> ValidatedSkill:
    return validate_skill_document(
        SkillDocument(
            Path(name) / "SKILL.md",
            name,
            f"name: {name}\ndescription: guidance\naccepts: [{accepts}]\n"
            "tools: {required: [not_installed]}\n",
            "Instructions are not inspected for matching.",
        )
    )


def test_matches_any_type_once_in_snapshot_order() -> None:
    reading = skill("reading", "pdf, book_url")
    coding = skill("coding", "github_url")
    generic = skill("generic", "pdf")
    snapshot = (reading, coding, generic)
    result = select_skills(snapshot, ["book_url", "pdf", "pdf"])
    assert result == (reading, generic)
    assert result[0] is reading
    assert snapshot == (reading, coding, generic)


@pytest.mark.parametrize("types", [[], ["unknown"], ["PDF"], ["pd"], ["url"]])
def test_no_implicit_matches(types: list[str]) -> None:
    assert select_skills([skill("reading", "pdf, book_url")], types) == ()


def test_supports_future_types_and_iterators() -> None:
    candidate = skill("future", "custom_document")
    assert select_skills(iter([candidate]), iter(["custom_document"])) == (candidate,)


def test_does_not_rank_by_description_or_require_installed_tools() -> None:
    candidate = skill("reading", "pdf")
    assert select_skills([candidate], ["pdf"]) == (candidate,)


def test_empty_registry() -> None:
    assert select_skills([], ["text"]) == ()


@pytest.mark.parametrize("types", ["pdf", [""], [" pdf"], ["bad/type"], ["x" * 65], [1]])
def test_rejects_malformed_types(types: object) -> None:
    with pytest.raises(ValueError):
        select_skills([], types)  # type: ignore[arg-type]


def test_filters_validated_files_and_retains_original_snapshot(tmp_path: Path) -> None:
    for name, accepts in [("a-reading", "pdf"), ("b-code", "github_url")]:
        directory = tmp_path / name
        directory.mkdir()
        (directory / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: guide\naccepts: [{accepts}]\n---\nbody",
            encoding="utf-8",
        )
    snapshot = load_skills(tmp_path)
    (tmp_path / "a-reading" / "SKILL.md").write_text("changed", encoding="utf-8")
    selected = select_skills(snapshot.skills, ["pdf"])
    assert [entry.metadata.name for entry in selected] == ["a-reading"]
    assert selected[0].document.body == "body"
