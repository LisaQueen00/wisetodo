from collections.abc import Iterator
from pathlib import Path

import pytest

from wisetodo.database import initialize_database
from wisetodo.todos import TodoInput, TodoService


@pytest.fixture
def service(tmp_path: Path) -> Iterator[TodoService]:
    database = initialize_database(tmp_path / "order.db")
    try:
        yield TodoService(database.sessions)
    finally:
        database.dispose()


def test_move_normalizes_positions_and_preserves_content(service: TodoService) -> None:
    original = [service.create(TodoInput(topic=name, items=["One", "Two"])) for name in "ABC"]
    a, b, c = service.list()
    result = service.move(c.id, a.id)
    assert [todo.id for todo in result] == [c.id, a.id, b.id]
    assert [todo.position for todo in result] == [0, 1, 2]
    assert service.list() == result
    for todo in result:
        before = next(item for item in original if item.id == todo.id)
        assert todo.model_dump(exclude={"position", "updated_at"}) == before.model_dump(
            exclude={"position", "updated_at"}
        )
    result = service.move(c.id, b.id)
    assert [todo.id for todo in result] == [a.id, b.id, c.id]
    assert service.move(a.id, a.id) == result


def test_move_rejects_cross_group_and_missing_ids_without_writes(service: TodoService) -> None:
    normal = service.create(TodoInput(topic="Normal", items=["One", "Two"]))
    high = service.create(TodoInput(topic="High", priority=1, items=["One", "Two"]))
    done = service.create(TodoInput(topic="Done", items=["One", "Two"]))
    for item in done.items:
        service.set_item_completed(done.id, item.id, True)
    before = service.list()
    for target in [high.id, done.id]:
        with pytest.raises(ValueError):
            service.move(normal.id, target)
    for source_id, target_id in [("missing", normal.id), (normal.id, "missing")]:
        with pytest.raises(LookupError):
            service.move(source_id, target_id)
    assert service.list() == before


def test_completed_group_can_be_sorted_without_changing_other_groups(service: TodoService) -> None:
    normal = service.create(TodoInput(topic="Normal", items=["One", "Two"]))
    a, b = [service.create(TodoInput(topic=name, items=["One", "Two"])) for name in "AB"]
    for todo in [a, b]:
        for item in todo.items:
            service.set_item_completed(todo.id, item.id, True)
    a, b = [todo for todo in service.list() if todo.completed]
    result = service.move(b.id, a.id)
    assert [todo.id for todo in result] == [normal.id, b.id, a.id]
    assert result[0] == normal
    assert all(todo.completed for todo in result[1:])
