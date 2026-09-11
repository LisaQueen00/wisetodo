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
    outline_offset: int = 0
    next_outline_offset: int | None = None
    start_page: int = 1
    text_offset: int = 0
    next_page: int | None = None
    next_text_offset: int = 0
    mode: str = "auto"
    outline_depth: int = 16


def extract_pdf(
    references: FileReferences,
    file_ref: str,
    *,
    mode: str = "auto",
    outline_offset: int = 0,
    outline_depth: int = 16,
    start_page: int = 1,
    text_offset: int = 0,
) -> PdfContent:
    """Read metadata/bookmarks and at most three opening pages (4000 chars each).

    No OCR or heading inference. No bookmarks means empty sections, not a claim
    that no contents page exists. Output bounds do not bound decompression costs;
    this synchronous helper still needs isolation before production tool use.
    """
    if (
        mode not in {"auto", "outline", "pages"}
        or any(type(v) is not int for v in (outline_offset, outline_depth, start_page, text_offset))
        or not 0 <= outline_offset <= 100000
        or not 0 <= outline_depth <= 16
        or not 1 <= start_page <= 1000000
        or not 0 <= text_offset <= 10000000
    ):
        raise ValueError("invalid_pdf_options")
    with open_pdf(references, file_ref) as reader:
        try:
            count = len(reader.pages)
            metadata = reader.metadata
            raw_title = metadata.title if metadata else None
            title = raw_title.strip()[:512] if isinstance(raw_title, str) else None
            sections: list[PdfSection] = []
            clipped = False
            seen = 0

            def visit(entries: Sequence[object], depth: int = 0) -> None:
                nonlocal clipped, seen
                if depth > outline_depth:
                    return
                for entry in entries:
                    if clipped:
                        return
                    if isinstance(entry, list):
                        visit(entry, depth + 1)
                    elif isinstance(entry, Destination):
                        label = str(entry.title).strip()
                        if not label:
                            continue
                        seen += 1
                        if seen <= outline_offset:
                            continue
                        if len(sections) >= 200:
                            clipped = True
                            return
                        destination = reader.get_destination_page_number(entry)
                        page = (
                            destination + 1
                            if destination is not None and 0 <= destination < count
                            else None
                        )
                        sections.append(PdfSection(label[:512], page, depth))

            if mode != "pages":
                visit(reader.outline)
            pages = []
            next_page = None
            next_text_offset = 0
            if mode != "outline":
                for index in range(start_page - 1, min(count, start_page + 2)):
                    text = reader.pages[index].extract_text() or ""
                    offset = text_offset if index == start_page - 1 else 0
                    more = len(text) > offset + 4000
                    pages.append(PdfPageText(index + 1, text[offset : offset + 4000], more))
                    next_page = index + 2 if index + 1 < count else None
                    if more:
                        next_page, next_text_offset = index + 1, offset + 4000
                        break
            return PdfContent(
                title or None,
                count,
                tuple(sections),
                tuple(pages),
                clipped,
                outline_offset,
                outline_offset + len(sections) if clipped else None,
                start_page,
                text_offset,
                next_page,
                next_text_offset,
                mode,
                outline_depth,
            )
        except Exception:
            raise PdfReadError("pdf_extraction_failed") from None
