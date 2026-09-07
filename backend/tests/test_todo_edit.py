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


def test_completion_targets_exact_item_and_persists(service: tuple[Database, TodoService]) -> None:
    _, todos = service
    original = todos.create(TodoInput(topic="Book", items=["Same", "Same"]))
    updated = todos.set_item_completed(original.id, original.items[1].id, True)
    assert updated is not None
    assert [item.completed for item in updated.items] == [False, True]
    assert updated.progress == 0.5
    assert not updated.completed
    assert todos.get(original.id) == updated
    assert todos.set_item_completed(original.id, original.items[1].id, True) == updated
    finished = todos.set_item_completed(original.id, original.items[0].id, True)
    assert finished is not None and finished.completed and finished.progress == 1
    reopened = todos.set_item_completed(original.id, original.items[1].id, False)
    assert reopened is not None and not reopened.completed and reopened.progress == 0.5
    assert [item.id for item in reopened.items] == [item.id for item in original.items]


def test_completion_rejects_foreign_or_missing_item(service: tuple[Database, TodoService]) -> None:
    _, todos = service
    first = todos.create(TodoInput(topic="First", items=["One", "Two"]))
    second = todos.create(TodoInput(topic="Second", items=["One", "Two"]))
    for item_id in [second.items[0].id, "missing"]:
        with pytest.raises(LookupError):
            todos.set_item_completed(first.id, item_id, True)
    assert todos.set_item_completed("missing", first.items[0].id, True) is None
    assert todos.get(first.id) == first
    assert todos.get(second.id) == second


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
