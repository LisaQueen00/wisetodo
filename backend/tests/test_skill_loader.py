from dataclasses import FrozenInstanceError

import pytest

from wisetodo.skills.loader import MAX_SKILL_BYTES, parse_skill_document, scan_skills


def write(root, name, data="---\nname: reading\n---\n按章节阅读。\n"):
    path = root / name / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode("utf-8") if isinstance(data, str) else data)
    return path


def test_scan_one_level_and_stable_order(tmp_path):
    write(tmp_path, "z")
    write(tmp_path, "A")
    write(tmp_path, "nested/deeper")
    (tmp_path / "SKILL.md").write_text("ignored", encoding="utf-8")
    result = scan_skills(tmp_path)
    assert [doc.directory for doc in result.documents] == ["A", "z"]
    assert not result.issues
    assert result.documents[0].frontmatter == "name: reading\n"
    assert result.documents[0].body == "按章节阅读。\n"


def test_bom_crlf_and_body_separators_preserved(tmp_path):
    write(tmp_path, "book", "\ufeff---\r\nname: book\r\n---\r\n# 阅读\r\n---\r\n正文")
    doc = scan_skills(tmp_path).documents[0]
    assert doc.frontmatter == "name: book\n"
    assert doc.body == "# 阅读\n---\n正文"


@pytest.mark.parametrize(
    "data,code",
    [
        ("body", "missing_frontmatter"),
        ("---\nname: x", "unclosed_frontmatter"),
        (b"\xff", "invalid_utf8"),
        (b"x" * (MAX_SKILL_BYTES + 1), "document_too_large"),
    ],
    ids=["missing-header", "unclosed-header", "invalid-utf8", "oversized"],
)
def test_bad_document_does_not_block_others(tmp_path, data, code):
    bad = write(tmp_path, "bad", data)
    write(tmp_path, "good")
    result = scan_skills(tmp_path)
    assert [doc.directory for doc in result.documents] == ["good"]
    assert result.issues[0].path == bad
    assert result.issues[0].code == code


def test_missing_root_and_relative_root(tmp_path):
    assert scan_skills(tmp_path / "missing").documents == ()
    with pytest.raises(ValueError):
        scan_skills(type(tmp_path)("relative"))


def test_snapshot_unchanged_after_file_edit(tmp_path):
    path = write(tmp_path, "book")
    old = scan_skills(tmp_path)
    path.write_text("---\nname: new\n---\nnew body", encoding="utf-8")
    assert old.documents[0].body == "按章节阅读。\n"
    assert scan_skills(tmp_path).documents[0].body == "new body"
    with pytest.raises(FrozenInstanceError):
        old.documents[0].body = "changed"


def test_yaml_is_not_executed_or_validated_yet(tmp_path):
    doc = parse_skill_document(
        tmp_path / "SKILL.md", "---\n!!python/object:untrusted {}\n---\nbody"
    )
    assert "!!python/object" in doc.frontmatter


def test_unreadable_file_is_isolated(tmp_path, monkeypatch):
    path = write(tmp_path, "bad")
    write(tmp_path, "good")
    original = type(path).open

    def denied(self, *args, **kwargs):
        if self == path:
            raise PermissionError("private content")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(type(path), "open", denied)
    result = scan_skills(tmp_path)
    assert result.issues[0].code == "document_unreadable"
    assert len(result.documents) == 1


def test_linked_entry_not_read(tmp_path, monkeypatch):
    path = write(tmp_path, "linked")
    original = type(path).is_symlink
    monkeypatch.setattr(type(path), "is_symlink", lambda self: self == path or original(self))
    result = scan_skills(tmp_path)
    assert not result.documents
    assert result.issues[0].code == "linked_path"
