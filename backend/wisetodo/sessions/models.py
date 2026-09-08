from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StrictStr,
    field_validator,
    model_validator,
)


class SessionStatus(StrEnum):
    READY = "ready"
    RUNNING = "running"
    WAITING_INPUT = "waiting_input"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ToolEventType(StrEnum):
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SessionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    label: str
    status: SessionStatus
    created_at: datetime
    updated_at: datetime


class Message(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    session_id: str
    position: int
    role: MessageRole
    content: str
    attachments: list[str]
    created_at: datetime


class ToolEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    session_id: str
    position: int
    run_id: str
    call_id: str
    tool_name: str
    event_type: ToolEventType
    payload: dict[str, Any]
    created_at: datetime


class SessionHistory(SessionSummary):
    target_todo_id: str | None = None
    messages: list[Message]
    tool_events: list[ToolEvent]


class ChatInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_id: UUID
    todo_id: UUID | None = None
    content: StrictStr
    urls: list[StrictStr] = Field(default_factory=list)
    files: list[StrictStr] = Field(default_factory=list)

    @field_validator("files")
    @classmethod
    def validate_files(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            path = Path(value)
            if (
                not path.is_absolute()
                or any(ord(char) < 32 for char in value)
                or path.suffix.lower() not in {".pdf", ".md", ".markdown", ".txt"}
            ):
                raise ValueError("Expected an absolute PDF, Markdown or TXT file path")
            if value not in result:
                result.append(value)
        return result

    @field_validator("urls")
    @classmethod
    def validate_urls(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        for raw in values:
            value = raw.strip()
            if any(
                char.isspace() or ord(char) < 32 or ord(char) == 127 or char == "\\"
                for char in value
            ):
                raise ValueError("URL contains invalid characters")
            parsed = urlsplit(value)
            if (
                parsed.scheme not in {"http", "https"}
                or not value.lower().startswith(("http://", "https://"))
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
            ):
                raise ValueError("Expected an HTTP(S) URL without credentials")
            _ = parsed.port  # Reject malformed or out-of-range ports.
            HttpUrl(value)  # Validate host syntax without normalizing the stored reference.
            if value not in result:
                result.append(value)
        return result

    @model_validator(mode="after")
    def nonempty(self) -> "ChatInput":
        if not self.content.strip() and not self.urls and not self.files:
            raise ValueError("Message must contain text, a URL or a file reference")
        return self
