from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

Priority = Literal[0, 1]


class TodoCaller(StrEnum):
    USER = "user"
    AGENT = "agent"


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

    @field_validator("topic")
    @classmethod
    def topic_must_not_be_blank(cls, value: str | None) -> str | None:
        return TodoInput.topic_must_not_be_blank(value) if value is not None else None

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


class TodoEditItem(BaseModel):
    id: str | None = None
    topic: str

    @field_validator("topic")
    @classmethod
    def topic_must_not_be_blank(cls, value: str) -> str:
        return TodoInput.topic_must_not_be_blank(value)


class TodoEdit(BaseModel):
    """Full manual edit; IDs identify exact rows even when topics repeat."""

    topic: str
    priority: Priority = 0
    items: list[TodoEditItem] = Field(min_length=2)

    @field_validator("topic")
    @classmethod
    def topic_must_not_be_blank(cls, value: str) -> str:
        return TodoInput.topic_must_not_be_blank(value)

    @model_validator(mode="after")
    def unique_item_ids(self) -> TodoEdit:
        ids = [item.id for item in self.items if item.id is not None]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate item IDs")
        return self


class Todo(BaseModel):
    id: str
    topic: str
    priority: Priority
    position: int
    created_at: datetime
    updated_at: datetime
    items: list[TodoItem] = Field(min_length=2)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def progress(self) -> float:
        completed_count = sum(item.completed for item in self.items)
        return completed_count / len(self.items)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def completed(self) -> bool:
        return all(item.completed for item in self.items)
