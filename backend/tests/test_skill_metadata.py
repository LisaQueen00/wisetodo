from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from wisetodo.skills import load_skills, validate_skill_document
from wisetodo.skills.loader import SkillDocument, SkillDocumentError

HEADER = "name: reading-book\ndescription: 阅读章节\naccepts: [pdf, book_url]\n"


def document(header: str) -> SkillDocument:
    return SkillDocument(Path("reading-book/SKILL.md"), "reading-book", header, "按章节阅读。")


def test_valid_header_and_immutable_snapshot() -> None:
    skill = validate_skill_document(
        document(HEADER + "tools:\n  required: [parse_pdf]\n  optional: [read_url]\n")
    )
    assert skill.metadata.name == "reading-book"
    assert skill.metadata.description == "阅读章节"
    assert skill.metadata.accepts == ("pdf", "book_url")
    assert skill.metadata.required_tools == ("parse_pdf",)
    assert skill.metadata.optional_tools == ("read_url",)
    assert skill.document.body == "按章节阅读。"
    with pytest.raises(FrozenInstanceError):
        skill.metadata.name = "changed"  # type: ignore[misc]


def test_tools_optional_and_input_types_extensible() -> None:
    metadata = validate_skill_document(document(HEADER.replace("pdf", "future_type"))).metadata
    assert metadata.required_tools == metadata.optional_tools == ()
    assert metadata.accepts == ("future_type", "book_url")


@pytest.mark.parametrize(
    "header",
    [
        "",
        "[]",
        "name: only",
        HEADER + "extra: value\n",
        HEADER.replace("reading-book", "Bad Name"),
        HEADER.replace("reading-book", "a" * 65),
        HEADER.replace("阅读章节", "' '"),
        HEADER.replace("阅读章节", "false"),
        HEADER.replace("[pdf, book_url]", "pdf"),
        HEADER.replace("[pdf, book_url]", "[]"),
        HEADER.replace("[pdf, book_url]", "[pdf, pdf]"),
        HEADER.replace("[pdf, book_url]", "[42]"),
        HEADER + "tools: []\n",
        HEADER + "tools: null\n",
        HEADER + "tools: {unknown: []}\n",
        HEADER + "tools: {required: parse_pdf}\n",
        HEADER + "tools: {required: [parse_pdf, parse_pdf]}\n",
        HEADER + "tools: {required: [parse_pdf], optional: [parse_pdf]}\n",
        HEADER + "tools: {optional: ['bad/name']}\n",
        HEADER + "name: duplicate\n",
        HEADER + "tools: {required: [], required: []}\n",
        HEADER + "tools: &shared {required: []}\n",
        HEADER + "tools: *missing\n",
        HEADER + "tools: {<<: {required: []}}\n",
        HEADER + "tools: !!python/object/apply:os.system ['echo secret']\n",
        HEADER + "tools: !custom {}\n",
        HEADER + "tools: [\n",
        HEADER + "---\nname: second\n",
        HEADER + "tools: " + "[" * 12 + "]" * 12,
        HEADER + "tools: {[complex, key]: []}\n",
    ],
    ids=[f"invalid-{index}" for index in range(30)],
)
def test_rejects_invalid_metadata_without_exposing_contents(header: str) -> None:
    with pytest.raises(SkillDocumentError) as caught:
        validate_skill_document(document(header))
    assert str(caught.value) in {
        "invalid_metadata",
        "invalid_yaml",
        "invalid_yaml_type",
        "duplicate_yaml_key",
        "duplicate_metadata_value",
        "conflicting_tool_dependencies",
        "yaml_alias_not_allowed",
        "yaml_too_deep",
    }


def test_loading_isolates_bad_headers_and_preserves_scan_issues(tmp_path: Path) -> None:
    for name, text in {
        "good": "---\n" + HEADER + "---\n正文",
        "bad": "---\nname: incomplete\n---\n正文",
        "broken": "no header",
    }.items():
        directory = tmp_path / name
        directory.mkdir()
        (directory / "SKILL.md").write_text(text, encoding="utf-8")
    result = load_skills(tmp_path)
    assert len(result.skills) == 1
    assert result.skills[0].document.body == "正文"
    assert {issue.code for issue in result.issues} == {"invalid_metadata", "missing_frontmatter"}


def test_direct_validation_limits_header_size() -> None:
    with pytest.raises(SkillDocumentError, match="^document_too_large$"):
        validate_skill_document(document(HEADER + "#" * (256 * 1024)))
