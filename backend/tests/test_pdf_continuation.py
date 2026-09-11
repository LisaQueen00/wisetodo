import json
import re

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from test_agent_runtime import Scope, create_output, message
from test_pdf_extract import save

from wisetodo.agent.runtime import AgentRuntime
from wisetodo.database import initialize_database
from wisetodo.files.model_content import PDF_CONTENT_CHARS, pdf_model_content
from wisetodo.files.pdf_extract import PdfContent, PdfPageText, PdfSection, extract_pdf
from wisetodo.model.contracts import ModelResponse, ToolCall
from wisetodo.sessions.service import SessionService
from wisetodo.todos import TodoService


def test_chapter_depth_avoids_losing_later_chapters(tmp_path):
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    for i in range(10):
        parent = writer.add_outline_item(f"Chapter {i + 1}", 0)
        for j in range(30):
            writer.add_outline_item(f"{i + 1}.{j + 1} detail", 0, parent=parent)
    refs, ref = save(tmp_path, writer)
    full = pdf_model_content(extract_pdf(refs, ref, mode="outline"))
    assert full["next_outline_offset"] is not None
    chapters = pdf_model_content(extract_pdf(refs, ref, mode="outline", outline_depth=0))
    assert len(chapters["sections"]) == 10
    assert chapters["sections"][-1]["title"] == "Chapter 10"
    assert chapters["outline_complete"] and chapters["next_outline_offset"] is None


def test_output_budget_exposes_exact_outline_cursor():
    rows = tuple(PdfSection(str(i) + "中" * 500, 1, 0) for i in range(200))
    first = pdf_model_content(PdfContent(None, 1, rows, (), False))
    assert first["next_outline_offset"] == len(first["sections"])
    assert not first["outline_complete"]
    assert len(json.dumps(first, ensure_ascii=False)) <= PDF_CONTENT_CHARS
    assert first["next_outline_offset"] > 0


def test_dropped_page_keeps_resume_position():
    rows = tuple(PdfSection("中" * 500, 1, 0) for _ in range(200))
    content = PdfContent(
        None,
        12,
        rows,
        (PdfPageText(8, "x" * 4000, True),),
        False,
        start_page=8,
        text_offset=4000,
        next_page=8,
        next_text_offset=8000,
    )
    payload = pdf_model_content(content)
    assert payload["pages"] == []
    assert payload["next_page"] == 8 and payload["next_text_offset"] == 4000


def test_physical_page_continuation(tmp_path):
    writer = PdfWriter()
    for _ in range(7):
        writer.add_blank_page(width=100, height=100)
    refs, ref = save(tmp_path, writer)
    first = pdf_model_content(extract_pdf(refs, ref, mode="pages"))
    assert first["next_page"] == 4
    second = pdf_model_content(extract_pdf(refs, ref, mode="pages", start_page=4))
    assert [p["page"] for p in second["pages"]] == [4, 5, 6]
    assert second["next_page"] == 7


def test_long_physical_page_resumes_text_instead_of_skipping(tmp_path):
    writer = PdfWriter()
    page = writer.add_blank_page(width=100, height=100)
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {
                    NameObject("/F1"): DictionaryObject(
                        {
                            NameObject("/Type"): NameObject("/Font"),
                            NameObject("/Subtype"): NameObject("/Type1"),
                            NameObject("/BaseFont"): NameObject("/Helvetica"),
                        }
                    )
                }
            )
        }
    )
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 10 50 Td (" + b"A" * 8500 + b") Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    refs, ref = save(tmp_path, writer)
    first = pdf_model_content(extract_pdf(refs, ref, mode="pages"))
    assert first["next_page"] == 1 and first["next_text_offset"] == 4000
    tail = pdf_model_content(extract_pdf(refs, ref, mode="pages", text_offset=8000))
    assert tail["next_page"] is None
    assert tail["pages"][0]["text"].count("A") == 500


@pytest.mark.parametrize("mode", ["native", "prompt_compat"])
async def test_real_pdf_worker_and_runtime_continue_outline(tmp_path, mode):
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    for i in range(205):
        writer.add_outline_item(f"Chapter {i + 1}", 0)
    save(tmp_path, writer)
    collected = []

    class Provider(Scope):
        async def complete(self, request):
            self.requests.append(request)
            if len(self.requests) == 1:
                reference = re.search(
                    r"file_[a-f0-9]{32}", "\n".join(m.content for m in request.messages)
                ).group()
                self.reference = reference
                offset = 0
            else:
                raw = request.messages[-1].content
                facts = json.loads(raw if mode == "native" else raw.split("\n", 1)[1])
                if mode != "native":
                    facts = next(iter(facts.values()))
                collected.extend(s["title"] for s in facts["sections"])
                offset = facts["next_outline_offset"]
                if offset is None:
                    assert facts["outline_complete"]
                    return ModelResponse(content=json.dumps(create_output()), finish_reason="stop")
                assert request.tools  # PDF is no longer forced into final after its first read.
            args = {"file_ref": self.reference, "mode": "outline", "outline_offset": offset}
            if mode == "native":
                return ModelResponse(
                    finish_reason="tool_calls",
                    tool_calls=(
                        ToolCall(
                            id=str(len(self.requests)), name="parse_pdf", arguments=json.dumps(args)
                        ),
                    ),
                )
            return ModelResponse(
                finish_reason="stop",
                content=json.dumps(
                    {
                        "type": "tool_calls",
                        "calls": [
                            {
                                "callId": str(len(self.requests)),
                                "tool": "parse_pdf",
                                "arguments": args,
                            }
                        ],
                    }
                ),
            )

    db = initialize_database(tmp_path / "test.db")
    try:
        sessions, todos, provider = (
            SessionService(db.sessions),
            TodoService(db.sessions),
            Provider(),
        )
        sessions.agent_executor = AgentRuntime(
            sessions,
            todos,
            provider,
            mode=mode,
            tool_config=tmp_path / "tools.json",
            optional_tool_config=True,
        )
        result = await sessions.submit(
            sessions.create().id,
            message().model_copy(update={"files": [str(tmp_path / "book.pdf")]}),
        )
        assert result.status == "completed" and len(todos.list()) == 1
        assert collected == [f"Chapter {i + 1}" for i in range(205)]
        assert len(provider.requests) >= 3
    finally:
        db.dispose()
