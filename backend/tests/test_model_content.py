import json

import pytest

from wisetodo.files.model_content import PDF_CONTENT_CHARS, pdf_model_content
from wisetodo.files.pdf_extract import PdfContent, PdfPageText, PdfSection
from wisetodo.tools.model_content import (
    BATCH_RESULT_CHARS,
    ToolResultBudgetError,
    model_tool_results,
)


def test_pdf_keeps_structure_before_page_text():
    content = PdfContent(
        "book", 100, (PdfSection("chapter", 1, 0),), (PdfPageText(1, "x" * 20_000, False),), False
    )
    payload = pdf_model_content(content)
    assert payload["sections"] == [{"title": "chapter", "page": 1, "depth": 0}]
    assert payload["pages"] == []
    assert payload["partial"] is True
    assert len(json.dumps(payload, ensure_ascii=False)) <= PDF_CONTENT_CHARS


def test_pdf_outline_stops_at_whole_entry_boundary():
    sections = tuple(PdfSection(str(i) + "中" * 500, i + 1, 0) for i in range(200))
    payload = pdf_model_content(PdfContent(None, 200, sections, (), True))
    assert 0 < len(payload["sections"]) < 200
    assert len(json.dumps(payload, ensure_ascii=False)) <= PDF_CONTENT_CHARS


def test_batch_budget_preserves_ids_and_null():
    result = model_tool_results(
        {"a": "x" * 15_000, "b": "y" * 15_000, "c": "z" * 15_000, "d": None, "e": "q" * 20_000}
    )
    assert list(result) == ["a", "b", "c", "d", "e"]
    assert result["d"] is None
    assert result["c"]["omitted"] is True
    assert result["e"]["omitted"] is True
    assert len(json.dumps(result, ensure_ascii=False)) <= BATCH_RESULT_CHARS


def test_escaping_counts_and_input_is_not_mutated():
    original = {"a": {"text": "\n" * 9000}}
    assert model_tool_results(original)["a"]["omitted"] is True
    assert original["a"]["text"] == "\n" * 9000


def test_oversized_id_fails_instead_of_breaking_pairing():
    with pytest.raises(ToolResultBudgetError):
        model_tool_results({"x" * 40_000: None})
