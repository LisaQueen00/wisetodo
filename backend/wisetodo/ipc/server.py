from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from pydantic import TypeAdapter, ValidationError
from sqlalchemy.exc import SQLAlchemyError

from wisetodo.errors import ErrorCode, WiseTodoError
from wisetodo.ipc.messages import IpcCancel, IpcFailure, IpcRequest, IpcResponse
from wisetodo.todos import TodoService

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
        except SQLAlchemyError:
            error = WiseTodoError(
                code=ErrorCode.TODO_READ_FAILED,
                message="Could not read todos",
                user_message="无法读取待办，请重试。",
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
