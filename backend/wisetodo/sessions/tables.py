from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wisetodo.database import Base
from wisetodo.sessions.models import SessionStatus


def new_id() -> str:
    return str(uuid4())


class SessionRecord(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ready', 'running', 'waiting_input', 'completed', 'failed', 'cancelled')",
            name="ck_sessions_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    label: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    active_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    target_todo_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    pending_operation: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=SessionStatus.READY, server_default="ready"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
    messages: Mapped[list[MessageRecord]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="MessageRecord.position",
    )
    tool_events: Mapped[list[ToolEventRecord]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ToolEventRecord.position",
    )


class MessageRecord(Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant', 'system')", name="ck_messages_role"),
        CheckConstraint("position >= 0", name="ck_messages_position"),
        UniqueConstraint("session_id", "position", name="uq_messages_session_position"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Paths only, never the original file bytes. Replace JSON values when editing.
    attachments: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.current_timestamp()
    )
    session: Mapped[SessionRecord] = relationship(back_populates="messages")


class ToolEventRecord(Base):
    """Append-only history: one row per event, not one mutable row per tool call."""

    __tablename__ = "tool_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('started', 'completed', 'failed', 'cancelled')",
            name="ck_tool_events_type",
        ),
        CheckConstraint("position >= 0", name="ck_tool_events_position"),
        UniqueConstraint("session_id", "position", name="uq_tool_events_session_position"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(nullable=False)
    run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    call_id: Mapped[str] = mapped_column(String, nullable=False)
    tool_name: Mapped[str] = mapped_column(String, nullable=False)
    event_type: Mapped[str] = mapped_column(String(16), nullable=False)
    # Event-specific arguments/result/error; never credentials or original file bytes.
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.current_timestamp()
    )
    session: Mapped[SessionRecord] = relationship(back_populates="tool_events")
