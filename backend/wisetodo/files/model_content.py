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
        "notice": "有限资料；未返回的章节或页面不代表不存在，不得编造。",
    }
    # Keep the marker in every payload, including fully fitting excerpts: extraction
    # already samples only opening pages and may have clipped text or bookmarks.
    if len(json.dumps(result, ensure_ascii=False)) > PDF_CONTENT_CHARS:
        result["title"] = None
    for section in content.sections:
        sections.append(asdict(section))
        if len(json.dumps(result, ensure_ascii=False)) > PDF_CONTENT_CHARS:
            sections.pop()
            break
    for page in content.pages:
        pages.append(asdict(page))
        if len(json.dumps(result, ensure_ascii=False)) > PDF_CONTENT_CHARS:
            pages.pop()
            break
    return result
