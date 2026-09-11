"""Size-bounded PDF facts for model consumption, not a token estimator."""

import json
from dataclasses import asdict

from pydantic import JsonValue

from wisetodo.files.pdf_extract import PdfContent

PDF_CONTENT_CHARS = 12_000


def pdf_model_content(content: PdfContent) -> dict[str, JsonValue]:
    """Preserve complete outline entries before complete page excerpts."""
    sections: list[JsonValue] = []
    pages: list[JsonValue] = []
    result: dict[str, JsonValue] = {
        "title": content.title,
        "page_count": content.page_count,
        "sections": sections,
        "pages": pages,
        "partial": True,
        "next_outline_offset": content.next_outline_offset,
        "next_page": content.next_page,
        "next_text_offset": content.next_text_offset,
        "outline_complete": False,
        "outline_depth": content.outline_depth,
        "outline_scope": "完整性仅指所选层级的 PDF 书签；空书签不表示没有印刷目录。",
        "notice": "有限资料，不是原书截断。按指针续读；partial 不等于章节目录不完整。",
    }
    # Keep the marker in every payload, including fully fitting excerpts: extraction
    # already samples only opening pages and may have clipped text or bookmarks.
    if len(json.dumps(result, ensure_ascii=False)) > PDF_CONTENT_CHARS:
        result["title"] = None
    for section in content.sections:
        sections.append(asdict(section))
        if len(json.dumps(result, ensure_ascii=False)) > PDF_CONTENT_CHARS - 256:
            sections.pop()
            break
    for page in content.pages:
        pages.append(asdict(page))
        if len(json.dumps(result, ensure_ascii=False)) > PDF_CONTENT_CHARS - 256:
            pages.pop()
            break
    if len(sections) < len(content.sections):
        result["next_outline_offset"] = content.outline_offset + len(sections)
    result["outline_complete"] = (
        content.mode != "pages"
        and not content.outline_truncated
        and len(sections) == len(content.sections)
    )
    if len(pages) < len(content.pages):
        missing = content.pages[len(pages)]
        result["next_page"] = missing.page
        result["next_text_offset"] = content.text_offset if not pages else 0
    return result
