from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StrictStr, field_validator


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

    @field_validator("content")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message cannot be blank")
        return value
