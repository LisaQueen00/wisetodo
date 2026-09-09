import pytest

from wisetodo.files.references import FileReferenceError, FileReferences, validate_attachment_path


def test_allowlist_is_run_scoped_and_does_not_expose_directory(tmp_path):
    path = tmp_path / "book.pdf"
    path.write_bytes(b"test")
    first = FileReferences([str(path), str(path)])
    (entry,) = first.descriptions()
    assert entry["name"] == "book.pdf"
    assert str(tmp_path) not in str(entry)
    assert first.resolve(entry["file_ref"]) == path.resolve()
    with pytest.raises(FileReferenceError, match="unknown"):
        FileReferences([str(path)]).resolve(entry["file_ref"])
    with pytest.raises(FileReferenceError, match="unknown"):
        first.resolve(str(path))
    path.unlink()
    with pytest.raises(FileReferenceError, match="unavailable"):
        first.resolve(entry["file_ref"])


@pytest.mark.parametrize(
    "value",
    [
        "relative.pdf",
        "//server/book.pdf",
        "\\\\server\\book.pdf",
        "/tmp/../book.pdf",
        "/tmp/book.exe",
        "/tmp/a\x00.pdf",
        "C:/book.pdf:secret.pdf",
    ],
)
def test_invalid_path(value):
    with pytest.raises(FileReferenceError):
        validate_attachment_path(value)


def test_directory_not_an_attachment(tmp_path):
    path = tmp_path / "book.pdf"
    path.mkdir()
    with pytest.raises(FileReferenceError):
        FileReferences([str(path)])
