from datetime import datetime
from enum import StrEnum
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
    messages: list[Message]
    tool_events: list[ToolEvent]


class ChatInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_id: UUID
    content: StrictStr
    urls: list[StrictStr] = Field(default_factory=list)

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
        if not self.content.strip() and not self.urls:
            raise ValueError("Message must contain text or a URL")
        return self
