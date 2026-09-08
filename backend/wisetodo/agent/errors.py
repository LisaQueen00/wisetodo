"""Safe Runtime error translation; never inspect upstream exception text."""

import asyncio
from typing import Literal

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from wisetodo.agent.generation import InvalidAgentOutputError, UnusableModelResponseError
from wisetodo.agent.tool_calls import InvalidToolCallsError
from wisetodo.errors import ErrorCode, WiseTodoError
from wisetodo.model.provider import ModelCapabilityError, ModelRequestError

KNOWN_MODEL_ERRORS = (
    ModelCapabilityError,
    ModelRequestError,
    InvalidAgentOutputError,
    InvalidToolCallsError,
    UnusableModelResponseError,
)


class AgentExecutionError(Exception):
    def __init__(self, error: WiseTodoError) -> None:
        self.error = error
        super().__init__(error.message)


def map_agent_error(
    error: BaseException, *, stage: Literal["model", "todo", "runtime"] = "runtime"
) -> WiseTodoError:
    """Stage comes from trusted Runtime code, never from model output.

    Cancellation is translated only at a terminal presentation boundary; execution
    code must still propagate CancelledError. No raw inputs, SQL or causes are copied.
    """
    if stage not in {"model", "todo", "runtime"}:
        raise ValueError("Unknown error stage")
    code = ErrorCode.INTERNAL_ERROR
    message = "Agent execution failed"
    user_message = "处理任务时发生错误，请重试。"
    retryable = False
    if isinstance(error, asyncio.CancelledError):
        code, message, user_message = ErrorCode.RUN_CANCELLED, "Request cancelled", "已停止执行。"
    elif isinstance(error, ModelCapabilityError):
        code = ErrorCode.MODEL_CAPABILITY_INSUFFICIENT
        message = "Required model capability unavailable"
        user_message = "当前模型不支持所需能力，请在设置中更换支持工具调用和结构化输出的模型。"
    elif isinstance(error, (ModelRequestError, UnusableModelResponseError)):
        code = ErrorCode.MODEL_REQUEST_FAILED
        message = "Model response unavailable"
        user_message = (
            "模型未返回可用的完整结果，可能已拒绝或输出中断；本次结果未提交。"
            if isinstance(error, UnusableModelResponseError)
            else "模型请求失败，请检查连接设置、服务状态后重试。"
        )
        retryable = isinstance(error, ModelRequestError)
    elif isinstance(error, InvalidToolCallsError):
        code = ErrorCode.TOOL_ARGUMENT_INVALID
        message = "Invalid native tool calls"
        user_message = "模型返回的工具调用格式无效，未执行这些调用。"
    elif isinstance(error, InvalidAgentOutputError) or (
        stage == "model" and isinstance(error, ValidationError)
    ):
        code = ErrorCode.INVALID_AGENT_OUTPUT
        message = "Invalid Agent output"
        user_message = "模型输出未通过校验，本次结果未提交；请调整描述或模型后重试。"
    elif stage == "todo":
        if isinstance(error, SQLAlchemyError):
            code = ErrorCode.TODO_SAVE_FAILED
            message, user_message = "Todo commit failed", "无法保存待办，请重试。"
            retryable = True
        elif isinstance(error, LookupError):
            code = ErrorCode.TODO_NOT_FOUND
            message, user_message = "Todo not found", "目标 Todo 已不存在，请重新选择任务。"
        elif isinstance(error, ValueError):
            code = ErrorCode.TODO_VALIDATION_FAILED
            message, user_message = "Invalid Todo data", "待办数据无效，请检查标题和至少两个子项。"
    return WiseTodoError(code=code, message=message, user_message=user_message, retryable=retryable)
