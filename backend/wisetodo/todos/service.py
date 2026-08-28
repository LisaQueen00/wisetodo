from __future__ import annotations

from datetime import datetime
from typing import cast

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from wisetodo.todos.models import (
    Priority,
    Todo,
    TodoCaller,
    TodoChanges,
    TodoInput,
    TodoItem,
)
from wisetodo.todos.tables import TodoItemRecord, TodoRecord


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

    def update(self, todo_id: str, changes: TodoChanges) -> Todo | None:
        with self._sessions.begin() as session:
            record = session.scalar(self._record_query().where(TodoRecord.id == todo_id))
            if record is None:
                return None

            if changes.topic is not None:
                record.topic = changes.topic
            if changes.priority is not None:
                record.priority = changes.priority
            if changes.items is not None:
                record.items = [
                    TodoItemRecord(topic=topic, position=position)
                    for position, topic in enumerate(changes.items)
                ]

            session.flush()
            session.refresh(record)
            return self._to_domain(record)

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
