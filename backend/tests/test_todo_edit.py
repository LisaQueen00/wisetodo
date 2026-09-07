from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError

from wisetodo.database import Database, initialize_database
from wisetodo.todos import TodoInput, TodoService
from wisetodo.todos.models import TodoEdit, TodoEditItem
from wisetodo.todos.tables import TodoItemRecord


@pytest.fixture
def service(tmp_path: Path) -> Iterator[tuple[Database, TodoService]]:
    database = initialize_database(tmp_path / "manual.db")
    try:
        yield database, TodoService(database.sessions)
    finally:
        database.dispose()


def test_manual_edit_targets_exact_duplicate_and_resets_renamed_item(
    service: tuple[Database, TodoService],
) -> None:
    database, todos = service
    original = todos.create(TodoInput(topic="Book", items=["Same", "Same", "Rename"]))
    with database.sessions.begin() as session:
        for item in original.items:
            session.get_one(TodoItemRecord, item.id).completed = True
    updated = todos.update(
        original.id,
        TodoEdit(
            topic="Edited",
            priority=1,
            items=[
                TodoEditItem(id=original.items[1].id, topic="Same"),
                TodoEditItem(id=original.items[2].id, topic="Changed"),
                TodoEditItem(topic="New"),
            ],
        ),
    )
    assert updated is not None
    assert updated.items[0].id == original.items[1].id
    assert updated.items[0].completed
    assert updated.items[1].id != original.items[2].id
    assert not updated.items[1].completed
    assert not updated.items[2].completed
    assert updated.progress == 1 / 3
    assert updated.priority == 1
    assert [item.position for item in updated.items] == [0, 1, 2]
    assert todos.get(original.id) == updated
    with database.sessions() as session:
        assert session.get(TodoItemRecord, original.items[0].id) is None


def test_foreign_item_id_rolls_back_all_changes(service: tuple[Database, TodoService]) -> None:
    _, todos = service
    first = todos.create(TodoInput(topic="First", items=["One", "Two"]))
    second = todos.create(TodoInput(topic="Second", items=["One", "Two"]))
    with pytest.raises(ValueError, match="belong"):
        todos.update(
            first.id,
            TodoEdit(
                topic="Must roll back",
                items=[
                    TodoEditItem(id=first.items[0].id, topic="Changed"),
                    TodoEditItem(id=second.items[0].id, topic="One"),
                ],
            ),
        )
    assert todos.get(first.id) == first
    assert todos.get(second.id) == second


@pytest.mark.parametrize(
    "payload",
    [
        {"topic": "   ", "items": [{"topic": "One"}, {"topic": "Two"}]},
        {"topic": "Title", "items": [{"topic": "One"}]},
        {"topic": "Title", "items": [{"topic": "One"}, {"topic": " "}]},
        {
            "topic": "Title",
            "items": [{"id": "same", "topic": "One"}, {"id": "same", "topic": "Two"}],
        },
    ],
)
def test_invalid_manual_edit_is_rejected(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        TodoEdit.model_validate(payload)
