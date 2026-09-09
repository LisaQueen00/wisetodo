from datetime import UTC, datetime

from wisetodo.agent.url_context import url_context
from wisetodo.sessions.models import Message


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


def test_collects_user_urls_without_fetching_or_duplicates():
    result = url_context(
        [
            message("阅读 https://example.org/book", ["https://example.org/book"]),
            message("https://other.org", role="assistant"),
        ]
    )
    assert result is not None
    assert result.content.count("https://example.org/book") == 1
    assert "other.org" not in result.content
    assert "未抓取" in result.content and "粘贴" in result.content


def test_invalid_and_non_url_references_are_ignored():
    assert (
        url_context([message(attachments=["D:/book.pdf", "https://user:secret@example.org"])])
        is None
    )
