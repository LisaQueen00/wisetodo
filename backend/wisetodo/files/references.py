"""Run-scoped file allowlist. Never resolve arbitrary model-supplied paths."""

from collections.abc import Iterable
from pathlib import Path
from uuid import uuid4


class FileReferenceError(ValueError):
    pass


def validate_attachment_path(value: str) -> Path:
    path = Path(value)
    if (
        not path.is_absolute()
        or value.startswith(("\\\\", "//"))
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
        or ":" in value[2:]
        or ".." in path.parts
        or path.suffix.lower() not in {".pdf", ".md", ".markdown", ".txt"}
    ):
        raise FileReferenceError("invalid_file_path")
    return path


def _checked(path: Path) -> Path:
    try:
        if any(part.is_symlink() or part.is_junction() for part in (path, *path.parents)):
            raise FileReferenceError("linked_file_path")
        if not path.is_file():
            raise FileReferenceError("file_unavailable")
        return path.resolve(strict=True)
    except OSError:
        raise FileReferenceError("file_unavailable") from None


class FileReferences:
    """Create only from trusted user attachments, never model arguments.

    Links are rejected and checked again on lookup. This is not an OS sandbox or
    atomic protection against an adversarial filesystem replacement during open.
    Consumers must only read files; no write API is provided.
    """

    def __init__(self, attachments: Iterable[str]) -> None:
        self._paths: dict[str, Path] = {}
        seen: set[Path] = set()
        for value in attachments:
            path = _checked(validate_attachment_path(value))
            if path not in seen:
                self._paths[f"file_{uuid4().hex}"] = path
                seen.add(path)

    def descriptions(self) -> tuple[dict[str, str], ...]:
        return tuple({"file_ref": key, "name": path.name} for key, path in self._paths.items())

    def resolve(self, reference: str) -> Path:
        path = self._paths.get(reference)
        if path is None:
            raise FileReferenceError("unknown_file_reference")
        return _checked(path)
