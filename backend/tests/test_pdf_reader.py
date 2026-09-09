import pytest
from pypdf import PdfWriter

from wisetodo.files import pdf
from wisetodo.files.pdf import PdfReadError, open_pdf
from wisetodo.files.references import FileReferenceError, FileReferences


def fixture(tmp_path, encrypted=False):
    path = tmp_path / "book.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.add_metadata({"/Title": "Test Book"})
    if encrypted:
        writer.encrypt("test-password")
    with path.open("wb") as stream:
        writer.write(stream)
    refs = FileReferences([str(path)])
    return path, refs, refs.descriptions()[0]["file_ref"]


def test_real_pdf_open_metadata_and_close(tmp_path):
    path, refs, reference = fixture(tmp_path)
    before = path.read_bytes()
    with open_pdf(refs, reference) as reader:
        assert len(reader.pages) == 1
        assert reader.metadata.title == "Test Book"
        stream = reader.stream
    assert stream.closed
    assert path.read_bytes() == before


def test_consumer_exception_closes_file(tmp_path):
    _, refs, reference = fixture(tmp_path)
    with pytest.raises(RuntimeError), open_pdf(refs, reference) as reader:
        stream = reader.stream
        raise RuntimeError("consumer")
    assert stream.closed


def test_encrypted_rejected(tmp_path):
    _, refs, reference = fixture(tmp_path, encrypted=True)
    with pytest.raises(PdfReadError, match="encrypted_pdf"), open_pdf(refs, reference):
        pass


@pytest.mark.parametrize("data", [b"not pdf", b"%PDF-1.7\nbroken"])
def test_invalid_document_safe_error(tmp_path, data):
    path, refs, reference = fixture(tmp_path)
    path.write_bytes(data)
    with pytest.raises(PdfReadError, match="^invalid_pdf$"), open_pdf(refs, reference):
        pass


def test_size_and_authorization(tmp_path, monkeypatch):
    _, refs, reference = fixture(tmp_path)
    monkeypatch.setattr(pdf, "MAX_PDF_BYTES", 1)
    with pytest.raises(PdfReadError, match="pdf_too_large"), open_pdf(refs, reference):
        pass
    with pytest.raises(FileReferenceError), open_pdf(refs, "unknown"):
        pass
