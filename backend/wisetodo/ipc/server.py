from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from pydantic import TypeAdapter, ValidationError
from sqlalchemy.exc import SQLAlchemyError

from wisetodo.errors import ErrorCode, WiseTodoError
from wisetodo.ipc.messages import IpcCancel, IpcFailure, IpcRequest, IpcResponse
from wisetodo.todos import TodoCaller, TodoService
from wisetodo.todos.models import TodoEdit, TodoInput

IncomingMessage: TypeAdapter[IpcRequest | IpcCancel] = TypeAdapter(IpcRequest | IpcCancel)


class UnknownMethodError(ValueError):
    pass


async def dispatch(request: IpcRequest, todo_service: TodoService | None = None) -> dict[str, Any]:
    if request.method == "health":
        return {"status": "ok"}
    if request.method == "todos.list":
        if todo_service is None:
            raise RuntimeError("Todo service is not initialized")
        return {"todos": [todo.model_dump(mode="json") for todo in todo_service.list()]}
    if request.method in {
        "user.todos.create",
        "user.todos.update",
        "user.todos.delete",
        "user.todos.set_item_completed",
        "user.todos.move",
    }:
        if todo_service is None:
            raise RuntimeError("Todo service is not initialized")
        if request.method == "user.todos.create":
            todo = todo_service.create(TodoInput.model_validate(request.params.get("todo")))
            return {"todo": todo.model_dump(mode="json")}
        todo_id = request.params.get("todo_id")
        if not isinstance(todo_id, str) or not todo_id:
            raise ValueError("Missing Todo ID")
        if request.method == "user.todos.move":
            target_id = request.params.get("target_id")
            if not isinstance(target_id, str) or not target_id:
                raise ValueError("Missing target ID")
            return {
                "todos": [
                    todo.model_dump(mode="json") for todo in todo_service.move(todo_id, target_id)
                ]
            }
        if request.method == "user.todos.delete":
            return {"deleted": todo_service.delete(todo_id, caller=TodoCaller.USER)}
        if request.method == "user.todos.set_item_completed":
            item_id = request.params.get("item_id")
            completed = request.params.get("completed")
            if not isinstance(item_id, str) or not item_id or not isinstance(completed, bool):
                raise ValueError("Expected an item ID and boolean completion")
            updated = todo_service.set_item_completed(todo_id, item_id, completed)
        else:
            updated = todo_service.update(
                todo_id, TodoEdit.model_validate(request.params.get("todo"))
            )
        if updated is None:
            raise LookupError("Todo not found")
        return {"todo": updated.model_dump(mode="json")}
    raise UnknownMethodError("Unknown IPC method")


def _write_failure(request_id: str, error: WiseTodoError) -> None:
    response = IpcFailure(requestId=request_id, error=error)
    print(response.model_dump_json(by_alias=True, exclude_none=True), flush=True)


def _handle_invalid_request(line: str) -> None:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        payload = None

    if isinstance(payload, dict) and isinstance(payload.get("requestId"), str):
        _write_failure(
            payload["requestId"],
            WiseTodoError(
                code=ErrorCode.IPC_INVALID_REQUEST,
                message="Invalid IPC request",
                user_message="请求格式有误，请重试。",
            ),
        )
    else:
        # There is no request ID to correlate; keep stdout strictly response-only.
        print("Ignored invalid IPC input without a request ID", file=sys.stderr, flush=True)


async def run_stdio_server(todo_service: TodoService | None = None) -> None:
    """Read one JSON request per line and emit one JSON response per line."""
    while line := await asyncio.to_thread(sys.stdin.readline):
        try:
            message = IncomingMessage.validate_json(line)
        except ValidationError:
            _handle_invalid_request(line)
            continue

        if isinstance(message, IpcCancel):
            continue

        try:
            result = await dispatch(message, todo_service)
        except UnknownMethodError:
            error = WiseTodoError(
                code=ErrorCode.IPC_METHOD_NOT_FOUND,
                message="Unknown IPC method",
                user_message="当前版本不支持此操作。",
            )
        except ValueError:
            error = WiseTodoError(
                code=ErrorCode.TODO_VALIDATION_FAILED,
                message="Invalid Todo data",
                user_message=(
                    "只能在相同完成状态、相同优先级内排序，请重新读取列表后重试。"
                    if message.method == "user.todos.move"
                    else "子项 ID 或完成状态无效，请重新读取列表后重试。"
                    if message.method == "user.todos.set_item_completed"
                    else "标题和子项不能为空，且至少保留两个子项。请检查输入后重试。"
                ),
            )
        except LookupError:
            error = WiseTodoError(
                code=ErrorCode.TODO_NOT_FOUND,
                message="Todo not found",
                user_message="此 Todo 或子项已不存在，请重新读取列表。",
            )
        except SQLAlchemyError:
            error = WiseTodoError(
                code=(
                    ErrorCode.TODO_SAVE_FAILED
                    if message.method.startswith("user.todos.")
                    else ErrorCode.TODO_READ_FAILED
                ),
                message="Could not read todos",
                user_message=(
                    "无法保存待办，请重试。"
                    if message.method.startswith("user.todos.")
                    else "无法读取待办，请重试。"
                ),
                retryable=True,
            )
        except Exception:
            error = WiseTodoError(
                code=ErrorCode.INTERNAL_ERROR,
                message="Could not process IPC request",
                user_message="处理请求时发生错误，请重试。",
            )
        else:
            response = IpcResponse(requestId=message.request_id, result=result)
            print(response.model_dump_json(by_alias=True), flush=True)
            continue

        _write_failure(message.request_id, error)
