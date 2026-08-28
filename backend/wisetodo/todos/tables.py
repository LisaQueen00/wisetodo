from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wisetodo.database import Base


def new_id() -> str:
    return str(uuid4())


class TodoRecord(Base):
    __tablename__ = "todos"
    __table_args__ = (
        CheckConstraint("priority IN (0, 1)", name="ck_todos_priority"),
        CheckConstraint("position >= 0", name="ck_todos_position"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    topic: Mapped[str] = mapped_column(String, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
    items: Mapped[list[TodoItemRecord]] = relationship(
        back_populates="todo",
        cascade="all, delete-orphan",
        order_by="TodoItemRecord.position",
    )


class TodoItemRecord(Base):
    __tablename__ = "todo_items"
    __table_args__ = (
        CheckConstraint("completed IN (0, 1)", name="ck_todo_items_completed"),
        CheckConstraint("position >= 0", name="ck_todo_items_position"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    todo_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("todos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic: Mapped[str] = mapped_column(String, nullable=False)
    completed: Mapped[bool] = mapped_column(nullable=False, default=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    todo: Mapped[TodoRecord] = relationship(back_populates="items")
