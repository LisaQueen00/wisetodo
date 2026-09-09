import asyncio
import json
import re
import sys
from pathlib import Path

import pytest
from pypdf import PdfWriter
from test_agent_runtime import Scope, create_output, message

from wisetodo.agent.runtime import AgentRuntime
from wisetodo.database import initialize_database
from wisetodo.files.pdf_tool import pdf_handler
from wisetodo.files.references import FileReferenceError, FileReferences
from wisetodo.model.contracts import ModelResponse, ToolCall
from wisetodo.sessions.service import SessionService
from wisetodo.skills import SkillSource
from wisetodo.todos import TodoService

ROOT = Path(__file__).resolve().parents[2]
CHAPTERS = ["第一章 初识数据库", "第二章 查询基础"]


@pytest.mark.parametrize("mode", ["native", "prompt_compat"])
@pytest.mark.parametrize("kind", ["outline", "empty", "invalid"])
async def test_reading_pdf_to_todo_or_clarification(tmp_path, mode, kind):
    pdf = tmp_path / "book.pdf"
    writer = PdfWriter()
    for chapter in CHAPTERS:
        writer.add_blank_page(width=100, height=100)
        if kind == "outline":
            writer.add_outline_item(chapter, len(writer.pages) - 1)
    writer.write(pdf)
    if kind == "invalid":
        pdf.write_bytes(b"not a PDF")
    config = tmp_path / "tools.json"
    config.write_text(
        (ROOT / "examples/reading-tools.json").read_text(encoding="utf-8"), encoding="utf-8"
    )

    class Provider(Scope):
        async def complete(self, request):
            self.requests.append(request)
            combined = "\n".join(m.content for m in request.messages)
            assert "阅读一本书" in combined
            assert str(pdf) not in combined
            if len(self.requests) == 1:
                reference = re.search(r"file_[a-f0-9]{32}", combined).group()
                arguments = {"file_ref": reference}
                if mode == "native":
                    return ModelResponse(
                        finish_reason="tool_calls",
                        tool_calls=(
                            ToolCall(id="pdf", name="parse_pdf", arguments=json.dumps(arguments)),
                        ),
                    )
                return ModelResponse(
                    finish_reason="stop",
                    content=json.dumps(
                        {
                            "type": "tool_calls",
                            "calls": [
                                {"callId": "pdf", "tool": "parse_pdf", "arguments": arguments}
                            ],
                        }
                    ),
                )
            assert not request.tools
            facts = request.messages[-1].content
            if kind == "outline":
                assert all(chapter in facts for chapter in CHAPTERS)
                output = create_output("阅读数据库书籍")
                output["operation"]["todo"]["items"] = [f"阅读{chapter}" for chapter in CHAPTERS]
            else:
                assert ('"sections": []' if kind == "empty" else "pdf_unavailable") in facts
                output = {"type": "clarification", "question": "请粘贴这本书的真实目录。"}
            return ModelResponse(finish_reason="stop", content=json.dumps(output))

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
            tool_config=config,
            skill_source=SkillSource(ROOT / "skills"),
        )
        result = await sessions.submit(
            sessions.create().id, message().model_copy(update={"files": [str(pdf)]})
        )
        assert result.status == ("completed" if kind == "outline" else "waiting_input")
        assert len(provider.requests) == 2
        assert [event.event_type for event in result.tool_events] == ["started", "completed"]
        assert len(todos.list()) == int(kind == "outline")
        if kind == "outline":
            todo = todos.list()[0]
            assert [item.topic for item in todo.items] == [f"阅读{chapter}" for chapter in CHAPTERS]
            assert all(not item.completed for item in todo.items)
    finally:
        db.dispose()


async def test_pdf_rejects_other_run_reference_before_starting_worker(tmp_path, monkeypatch):
    path = tmp_path / "book.pdf"
    path.write_bytes(b"%PDF-")
    old = FileReferences([str(path)])
    new = FileReferences([str(path)])

    async def forbidden(*args, **kwargs):
        pytest.fail("Unauthorized reference must not start a process")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    with pytest.raises(FileReferenceError):
        await pdf_handler(new)({"file_ref": old.descriptions()[0]["file_ref"]})


async def test_pdf_cancellation_reaps_worker(tmp_path, monkeypatch):
    path = tmp_path / "book.pdf"
    path.write_bytes(b"%PDF-")
    references = FileReferences([str(path)])
    original = asyncio.create_subprocess_exec
    started = asyncio.Event()
    processes = []

    async def slow_worker(*args, **kwargs):
        process = await original(sys.executable, "-c", "import time; time.sleep(60)", **kwargs)
        processes.append(process)
        started.set()
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", slow_worker)
    task = asyncio.create_task(
        pdf_handler(references)({"file_ref": references.descriptions()[0]["file_ref"]})
    )
    await asyncio.wait_for(started.wait(), 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 5)
    assert processes[0].returncode is not None


@pytest.mark.parametrize("mode", ["native", "prompt_compat"])
async def test_pasted_directory_needs_no_tool(tmp_path, mode):
    db = initialize_database(tmp_path / "text.db")
    try:
        sessions, todos = SessionService(db.sessions), TodoService(db.sessions)
        provider = Scope(create_output())
        sessions.agent_executor = AgentRuntime(
            sessions, todos, provider, mode=mode, skill_source=SkillSource(ROOT / "skills")
        )
        result = await sessions.submit(
            sessions.create().id, message("我要读这本书，目录：第一章、第二章。")
        )
        assert result.status == "completed"
        assert len(provider.requests) == 1
        assert not provider.requests[0].tools
        assert any("阅读一本书" in m.content for m in provider.requests[0].messages)
        assert not result.tool_events
    finally:
        db.dispose()
