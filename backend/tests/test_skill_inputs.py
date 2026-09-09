from datetime import UTC, datetime

from wisetodo.sessions.models import Message
from wisetodo.skills.inputs import input_types


def message(content="", attachments=None, role="user"):
    return Message(
        id="m",
        session_id="s",
        position=0,
        role=role,
        content=content,
        attachments=attachments or [],
        created_at=datetime.now(UTC),
    )


def test_input_hints_are_conservative():
    assert input_types([message("学习 https://github.com/owner/repo", ["D:/book.PDF"])]) == (
        "github_url",
        "pdf",
        "text",
        "url",
    )
    assert input_types(
        [message(attachments=["https://github.com.evil.org/a/b", "https://example.org/book.pdf"])]
    ) == ("url",)
    assert input_types([message("https://github.com/a/b", role="assistant")]) == ()


def test_file_types_and_empty_input():
    assert input_types([]) == ()
    assert input_types([message(attachments=["/tmp/a.md", "/tmp/b.txt"])]) == (
        "markdown",
        "text_file",
    )
