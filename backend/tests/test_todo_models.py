from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from wisetodo.todos.models import Todo, TodoChanges, TodoInput, TodoItem


def make_todo(completion_states: list[bool]) -> Todo:
    now = datetime.now(UTC)
    return Todo(
        id="todo-1",
        topic="Read a book",
        priority=0,
        position=0,
        created_at=now,
        updated_at=now,
        items=[
            TodoItem(
                id=f"item-{position}",
                todo_id="todo-1",
                topic=f"Chapter {position + 1}",
                completed=completed,
                position=position,
            )
            for position, completed in enumerate(completion_states)
        ],
    )


@pytest.mark.parametrize("items", [[], ["Chapter 1"]])
def test_todo_requires_at_least_two_items(items: list[str]) -> None:
    with pytest.raises(ValidationError):
        TodoInput(topic="Read a book", items=items)


@pytest.mark.parametrize("items", [[], ["Chapter 1"]])
def test_todo_update_requires_at_least_two_items(items: list[str]) -> None:
    with pytest.raises(ValidationError):
        TodoChanges(items=items)


@pytest.mark.parametrize("model", [TodoInput, TodoChanges])
@pytest.mark.parametrize("items", [["One", ""], ["  \t", "Two"]])
def test_blank_items_are_rejected(
    model: type[TodoInput] | type[TodoChanges], items: list[str]
) -> None:
    with pytest.raises(ValidationError):
        model(topic="Task", items=items)


@pytest.mark.parametrize("model", [TodoInput, TodoChanges])
@pytest.mark.parametrize("priority", [-1, 2])
def test_invalid_priority_is_rejected(
    model: type[TodoInput] | type[TodoChanges], priority: int
) -> None:
    with pytest.raises(ValidationError):
        model.model_validate({"topic": "Task", "items": ["One", "Two"], "priority": priority})


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


@pytest.mark.parametrize(
    ("states", "expected_progress", "expected_completed"),
    [
        ([False, False], 0.0, False),
        ([True, False], 0.5, False),
        ([True, True], 1.0, True),
    ],
)
def test_todo_calculates_progress_and_completion(
    states: list[bool], expected_progress: float, expected_completed: bool
) -> None:
    todo = make_todo(states)

    assert todo.progress == expected_progress
    assert todo.completed is expected_completed


def test_todo_serialization_includes_calculated_state() -> None:
    serialized = make_todo([True, False]).model_dump()

    assert serialized["progress"] == 0.5
    assert serialized["completed"] is False
