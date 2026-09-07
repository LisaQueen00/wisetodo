from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from wisetodo.todos.models import (
    Priority,
    Todo,
    TodoCaller,
    TodoChanges,
    TodoEdit,
    TodoInput,
    TodoItem,
)
from wisetodo.todos.tables import TodoItemRecord, TodoRecord

TodoItemRecordList = list[TodoItemRecord]
TodoList = list[Todo]


class TodoService:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def create(self, todo_input: TodoInput) -> Todo:
        with self._sessions.begin() as session:
            record = TodoRecord(
                topic=todo_input.topic,
                priority=todo_input.priority,
                position=0,
                items=[
                    TodoItemRecord(topic=topic, position=position)
                    for position, topic in enumerate(todo_input.items)
                ],
            )
            session.add(record)
            session.flush()
            session.refresh(record)
            return self._to_domain(record)

    def get(self, todo_id: str) -> Todo | None:
        with self._sessions() as session:
            record = session.scalar(self._record_query().where(TodoRecord.id == todo_id))
            return self._to_domain(record) if record is not None else None

    def list(self) -> list[Todo]:
        with self._sessions() as session:
            records = session.scalars(self._record_query()).all()
            records = sorted(records, key=self._sort_key)
            return [self._to_domain(record) for record in records]

    def update(self, todo_id: str, changes: TodoChanges | TodoEdit) -> Todo | None:
        with self._sessions.begin() as session:
            record = session.scalar(self._record_query().where(TodoRecord.id == todo_id))
            if record is None:
                return None

            if changes.topic is not None:
                record.topic = changes.topic
            if changes.priority is not None:
                record.priority = changes.priority
            if isinstance(changes, TodoEdit):
                existing = {item.id: item for item in record.items}
                edited: TodoItemRecordList = []
                for position, item in enumerate(changes.items):
                    old = existing.get(item.id) if item.id is not None else None
                    if item.id is not None and old is None:
                        raise ValueError("Item does not belong to this Todo")
                    updated = (
                        old
                        if old is not None and old.topic == item.topic
                        else (TodoItemRecord(topic=item.topic, completed=False))
                    )
                    updated.position = position
                    edited.append(updated)
                record.items = edited
            elif changes.items is not None:
                self._update_items(record, changes.items)

            record.updated_at = datetime.now(UTC)

            session.flush()
            session.refresh(record)
            return self._to_domain(record)

    def set_item_completed(self, todo_id: str, item_id: str, completed: bool) -> Todo | None:
        if not isinstance(completed, bool):
            raise ValueError("Completion must be a boolean")
        with self._sessions.begin() as session:
            record = session.scalar(self._record_query().where(TodoRecord.id == todo_id))
            if record is None:
                return None
            item = next((item for item in record.items if item.id == item_id), None)
            if item is None:
                raise LookupError("Todo item not found")
            if item.completed != completed:
                item.completed = completed
                record.updated_at = datetime.now(UTC)
            session.flush()
            session.refresh(record)
            return self._to_domain(record)

    def move(self, todo_id: str, target_id: str) -> TodoList:
        """Move to the target's slot within the same completion/priority group."""
        with self._sessions.begin() as session:
            records = sorted(session.scalars(self._record_query()).all(), key=self._sort_key)
            by_id = {record.id: record for record in records}
            source, target = by_id.get(todo_id), by_id.get(target_id)
            if source is None or target is None:
                raise LookupError("Todo not found")
            group_key = self._sort_key(source)[:2]
            if group_key != self._sort_key(target)[:2]:
                raise ValueError("Cannot move across completion or priority groups")
            if source is not target:
                group = [record for record in records if self._sort_key(record)[:2] == group_key]
                target_index = group.index(target)
                group.remove(source)
                group.insert(target_index, source)
                now = datetime.now(UTC)
                for position, record in enumerate(group):
                    if record.position != position:
                        record.position = position
                        record.updated_at = now
                session.flush()
                for record in group:
                    session.refresh(record)
            return [self._to_domain(record) for record in sorted(records, key=self._sort_key)]

    def delete(self, todo_id: str, *, caller: TodoCaller) -> bool:
        if caller is not TodoCaller.USER:
            raise PermissionError("Only user callers can delete top-level todos")

        with self._sessions.begin() as session:
            record = session.get(TodoRecord, todo_id)
            if record is None:
                return False
            session.delete(record)
            return True

    @staticmethod
    def _record_query() -> Select[tuple[TodoRecord]]:
        return select(TodoRecord).options(selectinload(TodoRecord.items))

    @staticmethod
    def _sort_key(record: TodoRecord) -> tuple[bool, int, int, datetime, str]:
        completed = all(item.completed for item in record.items)
        return completed, -record.priority, record.position, record.created_at, record.id

    @staticmethod
    def _update_items(record: TodoRecord, topics: Sequence[str]) -> None:
        existing_by_topic: defaultdict[str, deque[TodoItemRecord]] = defaultdict(deque)
        for item in record.items:
            existing_by_topic[item.topic.strip()].append(item)

        updated_items: TodoItemRecordList = []
        for position, topic in enumerate(topics):
            matches = existing_by_topic[topic]
            item = matches.popleft() if matches else TodoItemRecord(topic=topic)
            item.position = position
            updated_items.append(item)

        record.items = updated_items

    @staticmethod
    def _to_domain(record: TodoRecord) -> Todo:
        return Todo(
            id=record.id,
            topic=record.topic,
            priority=cast(Priority, record.priority),
            position=record.position,
            created_at=record.created_at,
            updated_at=record.updated_at,
            items=[
                TodoItem(
                    id=item.id,
                    todo_id=item.todo_id,
                    topic=item.topic,
                    completed=item.completed,
                    position=item.position,
                )
                for item in record.items
            ],
        )
