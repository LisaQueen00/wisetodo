"""Local PDF reader boundary; consumers own subsequent extraction policy."""

from collections.abc import Iterator
from contextlib import contextmanager

from pypdf import PdfReader

from wisetodo.files.references import FileReferences

MAX_PDF_BYTES = 64 * 1024 * 1024


class PdfReadError(ValueError):
    """Safe fixed code, never the underlying parser error or document content."""


@contextmanager
def open_pdf(references: FileReferences, file_ref: str) -> Iterator[PdfReader]:
    """Open only an authorized PDF, read-only, and close on success or failure.

    Synchronous: do not invoke on the UI/event loop. The byte limit is not a
    decompressed-memory or CPU limit; process isolation belongs to tool integration.
    Encrypted PDFs are intentionally unsupported in the first version.
    """
    path = references.resolve(file_ref)
    if path.suffix.lower() != ".pdf":
        raise PdfReadError("not_pdf")
    try:
        stream = path.open("rb")
    except OSError:
        raise PdfReadError("pdf_unavailable") from None
    with stream:
        try:
            stream.seek(0, 2)
            if stream.tell() > MAX_PDF_BYTES:
                raise PdfReadError("pdf_too_large")
            stream.seek(0)
            if stream.read(5) != b"%PDF-":
                raise PdfReadError("invalid_pdf")
            stream.seek(0)
            reader = PdfReader(stream, strict=True)
            if reader.is_encrypted:
                raise PdfReadError("encrypted_pdf")
        except PdfReadError:
            raise
        except Exception:
            raise PdfReadError("invalid_pdf") from None
        # Don't mask consumer extraction failures as opening errors.
        yield reader
