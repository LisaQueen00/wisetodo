"""Apply a final result; Session/run ownership remains the Runtime's job."""

import asyncio
from dataclasses import dataclass, field
from typing import Literal

from wisetodo.agent.results import (
    AGENT_RESULT_ADAPTER,
    AgentResult,
    ClarificationResult,
    CreateOperation,
    ToolCallsResult,
)
from wisetodo.sessions.state_machine import SessionEvent
from wisetodo.todos.models import Todo
from wisetodo.todos.service import TodoService


@dataclass(frozen=True)
class TodoCommitted:
    todo: Todo
    action: Literal["create", "update"]
    message: str
    event: Literal[SessionEvent.TODO_COMMITTED] = field(
        default=SessionEvent.TODO_COMMITTED, init=False
    )


@dataclass(frozen=True)
class ClarificationRequested:
    message: str
    event: Literal[SessionEvent.REQUEST_INPUT] = field(
        default=SessionEvent.REQUEST_INPUT, init=False
    )


class AgentResultHandler:
    def __init__(self, todos: TodoService) -> None:
        self._todos = todos

    async def handle(self, result: AgentResult) -> TodoCommitted | ClarificationRequested:
        """Not idempotent: the caller must claim a live Run before calling once.

        This does not save history or change Session status. No await occurs between
        the cancellation checkpoint and the synchronous Todo transaction's return.
        """
        # Models are mutable; validate a fresh snapshot, not just the instance type.
        result = AGENT_RESULT_ADAPTER.validate_python(result.model_dump(exclude_unset=True))
        await asyncio.sleep(0)
        task = asyncio.current_task()
        if task is not None and task.cancelling():
            raise asyncio.CancelledError
        if isinstance(result, ToolCallsResult):
            raise ValueError("Tool calls must be handled by the tool executor")
        if isinstance(result, ClarificationResult):
            return ClarificationRequested(message=result.question)
        operation = result.operation
        if isinstance(operation, CreateOperation):
            todo = self._todos.create(operation.todo)
            message = f"已创建：{todo.topic}"
        else:
            updated = self._todos.update(operation.todoId, operation.changes)
            if updated is None:
                raise LookupError("Todo not found")
            todo = updated
            message = f"已修改：{todo.topic}"
        # Service returns only after its transaction has committed successfully.
        return TodoCommitted(todo=todo, action=operation.action, message=message)
