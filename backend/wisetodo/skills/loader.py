"""Discover Skill documents without executing or trusting their instructions."""

from dataclasses import dataclass
from pathlib import Path

MAX_SKILL_BYTES = 256 * 1024


class SkillDocumentError(ValueError):
    """Safe diagnostic code, never includes document contents."""


@dataclass(frozen=True)
class SkillDocument:
    path: Path
    directory: str
    frontmatter: str
    body: str


@dataclass(frozen=True)
class SkillLoadIssue:
    path: Path
    code: str


@dataclass(frozen=True)
class SkillScan:
    documents: tuple[SkillDocument, ...]
    issues: tuple[SkillLoadIssue, ...]


def parse_skill_document(path: Path, text: str) -> SkillDocument:
    """Split frontmatter only; YAML syntax and field validation are a later step."""
    lines = text.removeprefix("\ufeff").replace("\r\n", "\n").splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise SkillDocumentError("missing_frontmatter")
    end = next((index for index in range(1, len(lines)) if lines[index].strip() == "---"), None)
    if end is None:
        raise SkillDocumentError("unclosed_frontmatter")
    return SkillDocument(
        path=path,
        directory=path.parent.name,
        frontmatter="".join(lines[1:end]),
        body="".join(lines[end + 1 :]),
    )


def _linked(path: Path) -> bool:
    return path.is_symlink() or path.is_junction()


def scan_skills(root: Path) -> SkillScan:
    """Read root/*/SKILL.md in stable order. Never recurse or follow linked entries.

    A missing root is a valid empty installation. Failed files are reported alongside
    valid documents. The returned immutable text snapshot does not change on disk edits.
    """
    if not root.is_absolute():
        raise ValueError("Skill root must be absolute")
    documents: list[SkillDocument] = []
    issues: list[SkillLoadIssue] = []
    try:
        if _linked(root):
            return SkillScan((), (SkillLoadIssue(root, "linked_path"),))
        if not root.exists():
            return SkillScan((), ())
        resolved = root.resolve(strict=True)
        entries = sorted(root.iterdir(), key=lambda path: (path.name.casefold(), path.name))
    except OSError:
        return SkillScan((), (SkillLoadIssue(root, "root_unreadable"),))
    for directory in entries:
        path = directory / "SKILL.md"
        try:
            if _linked(directory):
                issues.append(SkillLoadIssue(directory, "linked_path"))
                continue
            if not directory.is_dir():
                continue
            if _linked(path):
                issues.append(SkillLoadIssue(path, "linked_path"))
                continue
            if not path.exists():
                continue
            if not path.is_file() or not path.resolve(strict=True).is_relative_to(resolved):
                issues.append(SkillLoadIssue(path, "invalid_path"))
                continue
            with path.open("rb") as stream:
                data = stream.read(MAX_SKILL_BYTES + 1)
            if len(data) > MAX_SKILL_BYTES:
                raise SkillDocumentError("document_too_large")
            documents.append(parse_skill_document(path, data.decode("utf-8-sig")))
        except UnicodeError:
            issues.append(SkillLoadIssue(path, "invalid_utf8"))
        except SkillDocumentError as error:
            issues.append(SkillLoadIssue(path, str(error)))
        except OSError:
            issues.append(SkillLoadIssue(path, "document_unreadable"))
    return SkillScan(tuple(documents), tuple(issues))
