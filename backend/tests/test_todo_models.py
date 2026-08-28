from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from wisetodo.todos.models import Todo, TodoChanges, TodoInput, TodoItem


def test_todo_requires_at_least_two_items() -> None:
    with pytest.raises(ValidationError):
        TodoInput(topic="Read a book", items=["Chapter 1"])


def test_todo_update_requires_at_least_two_items() -> None:
    with pytest.raises(ValidationError):
        TodoChanges(items=["Chapter 1"])


def test_todo_domain_requires_at_least_two_items() -> None:
    item = TodoItem(
        id="item-1",
        todo_id="todo-1",
        topic="Chapter 1",
        completed=False,
        position=0,
    )

    with pytest.raises(ValidationError):
        Todo(
            id="todo-1",
            topic="Read a book",
            priority=0,
            position=0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            items=[item],
        )


def test_todo_normalizes_topics() -> None:
    todo = TodoInput(topic="  Read a book  ", items=[" Chapter 1 ", " Chapter 2 "])
    assert todo.topic == "Read a book"
    assert todo.items == ["Chapter 1", "Chapter 2"]


def test_todo_update_normalizes_item_topics() -> None:
    changes = TodoChanges(items=[" Chapter 1 ", " Chapter 2 "])

    assert changes.items == ["Chapter 1", "Chapter 2"]
