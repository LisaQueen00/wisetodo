"""Bounded PDF facts; bookmarks are source structure, never inferred chapters."""

from collections.abc import Sequence
from dataclasses import dataclass

from pypdf.generic import Destination

from wisetodo.files.pdf import PdfReadError, open_pdf
from wisetodo.files.references import FileReferences


@dataclass(frozen=True)
class PdfSection:
    title: str
    page: int | None  # One-based physical page, not printed page label.
    depth: int


@dataclass(frozen=True)
class PdfPageText:
    page: int
    text: str
    truncated: bool


@dataclass(frozen=True)
class PdfContent:
    title: str | None
    page_count: int
    sections: tuple[PdfSection, ...]
    pages: tuple[PdfPageText, ...]
    outline_truncated: bool


def extract_pdf(references: FileReferences, file_ref: str) -> PdfContent:
    """Read metadata/bookmarks and at most three opening pages (4000 chars each).

    No OCR or heading inference. No bookmarks means empty sections, not a claim
    that no contents page exists. Output bounds do not bound decompression costs;
    this synchronous helper still needs isolation before production tool use.
    """
    with open_pdf(references, file_ref) as reader:
        try:
            count = len(reader.pages)
            metadata = reader.metadata
            raw_title = metadata.title if metadata else None
            title = raw_title.strip()[:512] if isinstance(raw_title, str) else None
            sections: list[PdfSection] = []
            clipped = False

            def visit(entries: Sequence[object], depth: int = 0) -> None:
                nonlocal clipped
                for entry in entries:
                    if len(sections) >= 200 or depth > 16:
                        clipped = True
                        return
                    if isinstance(entry, list):
                        visit(entry, depth + 1)
                    elif isinstance(entry, Destination):
                        label = str(entry.title).strip()
                        if not label:
                            continue
                        destination = reader.get_destination_page_number(entry)
                        page = (
                            destination + 1
                            if destination is not None and 0 <= destination < count
                            else None
                        )
                        sections.append(PdfSection(label[:512], page, depth))

            visit(reader.outline)
            pages = []
            for index in range(min(count, 3)):
                text = reader.pages[index].extract_text() or ""
                pages.append(PdfPageText(index + 1, text[:4000], len(text) > 4000))
            return PdfContent(title or None, count, tuple(sections), tuple(pages), clipped)
        except Exception:
            raise PdfReadError("pdf_extraction_failed") from None
