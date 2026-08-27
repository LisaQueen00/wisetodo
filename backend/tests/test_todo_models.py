import pytest
from pydantic import ValidationError

from wisetodo.todos.models import TodoInput


def test_todo_requires_at_least_two_items() -> None:
    with pytest.raises(ValidationError):
        TodoInput(topic="Read a book", items=["Chapter 1"])


def test_todo_normalizes_topics() -> None:
    todo = TodoInput(topic="  Read a book  ", items=[" Chapter 1 ", " Chapter 2 "])
    assert todo.topic == "Read a book"
    assert todo.items == ["Chapter 1", "Chapter 2"]
