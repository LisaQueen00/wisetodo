from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TodoInput(BaseModel):
    topic: str = Field(min_length=1)
    priority: Literal[0, 1] = 0
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
        normalized = [item.strip() for item in items]
        if any(not item for item in normalized):
            raise ValueError("todo items must not be blank")
        return normalized


class TodoChanges(BaseModel):
    topic: str | None = None
    priority: Literal[0, 1] | None = None
    items: list[str] | None = Field(default=None, min_length=2)
