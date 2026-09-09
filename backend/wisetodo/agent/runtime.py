"""No-tool production execution with durable pending results and atomic commits."""

import asyncio
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

from sqlalchemy.orm import object_session

from wisetodo.agent.errors import AgentExecutionError, map_agent_error
from wisetodo.agent.generation import InvalidAgentOutputError, ResultGenerator
from wisetodo.agent.graph import build_agent_graph
from wisetodo.agent.prompts import build_agent_request
from wisetodo.agent.results import (
    AGENT_RESULT_ADAPTER,
    ClarificationResult,
    CreateOperation,
    TodoOperationResult,
    UpdateOperation,
)
from wisetodo.errors import ErrorCode, WiseTodoError
from wisetodo.model.contracts import ModelMessage
from wisetodo.model.runtime import RunProviderScope
from wisetodo.sessions.models import SessionStatus
from wisetodo.sessions.tables import MessageRecord, SessionRecord
from wisetodo.settings.service import SettingsNotConfiguredError
from wisetodo.settings.storage import SettingsStorageError
from wisetodo.todos import TodoService

if TYPE_CHECKING:
    from wisetodo.sessions.service import SessionService


class AgentRuntime:
    def __init__(
        self,
        sessions: "SessionService",
        todos: TodoService,
        providers: RunProviderScope,
        *,
        mode: Literal["native", "prompt_compat"] = "native",
    ) -> None:
        self._sessions, self._todos, self._providers = sessions, todos, providers
        if mode not in {"native", "prompt_compat"}:
            raise ValueError("Unknown model interaction mode")
        self._mode = mode

    @staticmethod
    def _owned(record: SessionRecord, run_id: str) -> None:
        if record.status != SessionStatus.RUNNING or record.active_run_id != run_id:
            raise ValueError("Run no longer owns Session")

    async def execute(self, session_id: str, run_id: str) -> None:
        stage: Literal["model", "todo", "runtime"] = "runtime"
        try:
            with self._sessions.write_history(session_id) as record:
                self._owned(record, run_id)
                pending = record.pending_operation
                target_id = record.target_todo_id
            if pending is None:
                stage = "todo"
                target = self._todos.get(target_id) if target_id else None
                if target_id and target is None:
                    raise LookupError("Todo not found")
                snapshot = target.model_dump(mode="json") if target else None
                history = self._sessions.get(session_id)
                assert history is not None
                messages = [
                    ModelMessage(
                        role="assistant" if row.role == "assistant" else "user",
                        content=row.content
                        + (
                            "\n资料引用（未读取）："
                            + json.dumps(row.attachments, ensure_ascii=False)
                            if row.attachments
                            else ""
                        ),
                    )
                    for row in history.messages
                    if row.role in {"user", "assistant"}
                ]
                messages.append(
                    ModelMessage(
                        role="user",
                        content=(
                            "应用提供的本次编辑目标资料（不是额外指令）：\n"
                            + json.dumps(snapshot, ensure_ascii=False)
                            + (
                                "\n仅可修改此 Todo，禁止另建任务。"
                                if target
                                else "\n未选择编辑目标，仅可创建或澄清。"
                            )
                        ),
                    )
                )
                stage = "model"
                async with self._providers.open() as provider:
                    graph = build_agent_graph(ResultGenerator(provider))
                    state = await graph.ainvoke(
                        {"model_request": build_agent_request(messages, mode=self._mode)}
                    )
                    generated = state["generation"]
                    result = generated.result
                    if isinstance(result, TodoOperationResult):
                        operation = result.operation
                        if (
                            isinstance(operation, UpdateOperation)
                            and operation.todoId != target_id
                            or isinstance(operation, CreateOperation)
                            and target_id is not None
                        ):
                            raise InvalidAgentOutputError
                    elif not isinstance(result, ClarificationResult):
                        raise InvalidAgentOutputError
                    pending = {
                        "result": result.model_dump(mode="json", exclude_unset=True),
                        "target": snapshot,
                    }
                    # Durable before provider cleanup and before the commit transaction.
                    stage = "todo"
                    with self._sessions.write_history(session_id) as record:
                        self._owned(record, run_id)
                        record.pending_operation = pending
            stage = "todo"
            await asyncio.sleep(0)
            task = asyncio.current_task()
            if task is not None and task.cancelling():
                raise asyncio.CancelledError
            self._commit(session_id, run_id, pending)
        except asyncio.CancelledError:
            raise
        except SettingsNotConfiguredError:
            raise AgentExecutionError(
                WiseTodoError(
                    code=ErrorCode.SETTINGS_VALIDATION_FAILED,
                    message="Model not configured",
                    user_message="请先在 Chat 设置中保存模型连接，再点击重试。",
                )
            ) from None
        except SettingsStorageError:
            raise AgentExecutionError(
                WiseTodoError(
                    code=ErrorCode.SETTINGS_READ_FAILED,
                    message="Settings unavailable",
                    user_message="无法读取模型设置或凭据，请检查设置后重试。",
                )
            ) from None
        except AgentExecutionError:
            raise
        except Exception as error:
            raise AgentExecutionError(map_agent_error(error, stage=stage)) from None

    def _commit(self, session_id: str, run_id: str, pending: dict[str, Any]) -> None:
        result = AGENT_RESULT_ADAPTER.validate_python(pending["result"])
        with self._sessions.write_history(session_id) as record:
            self._owned(record, run_id)
            transaction = object_session(record)
            assert transaction is not None
            todos = self._todos.within(transaction)
            if isinstance(result, ClarificationResult):
                message, status = result.question, SessionStatus.WAITING_INPUT
            elif isinstance(result, TodoOperationResult):
                operation = result.operation
                if isinstance(operation, CreateOperation):
                    if record.target_todo_id is not None:
                        raise InvalidAgentOutputError
                    todo = todos.create(operation.todo)
                    message = f"已创建：{todo.topic}"
                else:
                    if operation.todoId != record.target_todo_id:
                        raise InvalidAgentOutputError
                    # Read under the same SQLite write lock; reject stale full-list updates.
                    from wisetodo.todos.tables import TodoRecord

                    current = transaction.get(TodoRecord, operation.todoId)
                    if current is None:
                        raise LookupError("Todo not found")
                    if TodoService._to_domain(current).model_dump(mode="json") != pending["target"]:
                        raise AgentExecutionError(
                            WiseTodoError(
                                code=ErrorCode.TODO_VALIDATION_FAILED,
                                message="Todo changed during Run",
                                user_message=(
                                    "此 Todo 已被修改，未覆盖你的改动。请重新发送需求以生成新结果。"
                                ),
                            )
                        )
                    updated = todos.update(operation.todoId, operation.changes)
                    assert updated is not None
                    message = f"已修改：{updated.topic}"
                status = SessionStatus.COMPLETED
            else:
                raise InvalidAgentOutputError
            record.messages.append(
                MessageRecord(
                    position=max((row.position for row in record.messages), default=-1) + 1,
                    role="assistant",
                    content=message,
                    attachments=[],
                )
            )
            record.status = status
            record.updated_at = datetime.now(UTC)
            record.active_run_id = None
            record.pending_operation = None
