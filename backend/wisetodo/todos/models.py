from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Priority = Literal[0, 1]


def normalize_item_topics(items: list[str]) -> list[str]:
    normalized = [item.strip() for item in items]
    if any(not item for item in normalized):
        raise ValueError("todo items must not be blank")
    return normalized


class TodoInput(BaseModel):
    topic: str = Field(min_length=1)
    priority: Priority = 0
    items: list[str] = Field(min_length=2)

    @field_validator("topic")
    @classmethod
    def topic_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("topic must not be blank")
        return value

    @field_validator("items")
    @classmethod
    def items_must_not_be_blank(cls, items: list[str]) -> list[str]:
        return normalize_item_topics(items)


class TodoChanges(BaseModel):
    topic: str | None = None
    priority: Priority | None = None
    items: list[str] | None = Field(default=None, min_length=2)

    @field_validator("items")
    @classmethod
    def items_must_not_be_blank(cls, items: list[str] | None) -> list[str] | None:
        return normalize_item_topics(items) if items is not None else None


class TodoItem(BaseModel):
    id: str
    todo_id: str
    topic: str
    completed: bool
    position: int


class Todo(BaseModel):
    id: str
    topic: str
    priority: Priority
    position: int
    created_at: datetime
    updated_at: datetime
    items: list[TodoItem] = Field(min_length=2)
