from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from wisetodo.errors import ErrorCode, WiseTodoError
from wisetodo.ipc.messages import IpcRequest
from wisetodo.sessions.service import SessionService

METHODS = frozenset(
    {"sessions.list", "sessions.get", "user.sessions.create", "user.sessions.delete"}
)


class SessionRequestError(Exception):
    def __init__(self, error: WiseTodoError) -> None:
        self.error = error
        super().__init__(error.message)


def dispatch_session(request: IpcRequest, service: SessionService) -> dict[str, Any]:
    try:
        if request.method == "sessions.list":
            return {"sessions": [row.model_dump(mode="json") for row in service.list()]}
        if request.method == "user.sessions.create":
            label = request.params.get("label", "")
            if not isinstance(label, str):
                raise ValueError("Invalid label")
            return {"session": service.create(label).model_dump(mode="json")}
        session_id = request.params.get("session_id")
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("Missing Session ID")
        if request.method == "user.sessions.delete":
            return {"deleted": service.delete(session_id)}
        history = service.get(session_id)
        if history is None:
            raise LookupError("Session not found")
        return {"session": history.model_dump(mode="json")}
    except ValueError as error:
        raise SessionRequestError(
            WiseTodoError(
                code=ErrorCode.SESSION_VALIDATION_FAILED,
                message="Invalid Session operation",
                user_message="会话参数无效，或会话仍在执行；请检查并停止执行后重试。",
            )
        ) from error
    except LookupError as error:
        raise SessionRequestError(
            WiseTodoError(
                code=ErrorCode.SESSION_NOT_FOUND,
                message="Session not found",
                user_message="此会话已不存在，请刷新历史列表。",
            )
        ) from error
    except SQLAlchemyError as error:
        writing = request.method.startswith("user.sessions.")
        raise SessionRequestError(
            WiseTodoError(
                code=ErrorCode.SESSION_SAVE_FAILED if writing else ErrorCode.SESSION_READ_FAILED,
                message="Could not access Session history",
                user_message="无法保存会话，请重试。" if writing else "无法读取会话，请重试。",
                retryable=True,
            )
        ) from error
