"""Normalize a complete native tool response without executing any calls."""

import json
import math
from typing import Any

from pydantic import ValidationError

from wisetodo.agent.results import AgentToolCall, ToolCallsResult
from wisetodo.model.contracts import ModelResponse


class InvalidToolCallsError(ValueError):
    def __init__(self) -> None:
        # Never expose model content, arguments or JSON decoder diagnostics.
        super().__init__("Invalid native tool response")


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ValueError("Non-JSON numeric constant")


def _float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Non-finite number")
    return result


def normalize_native_tool_calls(response: ModelResponse) -> ToolCallsResult:
    """Accept only a terminal tool_calls response, never incomplete stream deltas.

    Accompanying content is not interpreted as another Agent result. The caller
    retains the original response for tool-result message pairing. Registry checks
    and any single repair attempt belong to later execution layers.
    """
    try:
        response = ModelResponse.model_validate(response.model_dump())
        if (
            response.finish_reason != "tool_calls"
            or response.refusal is not None
            or not response.tool_calls
        ):
            raise ValueError("Expected successful native tool calls")
        calls: list[AgentToolCall] = []
        for call in response.tool_calls:
            # AgentToolCall trims strings; reject changes to opaque native IDs/names
            # so the eventual tool result can use the exact provider identifier.
            if call.id != call.id.strip() or call.name != call.name.strip():
                raise ValueError("Invalid native identifier")
            arguments = json.loads(
                call.arguments,
                object_pairs_hook=_object,
                parse_constant=_constant,
                parse_float=_float,
            )
            calls.append(AgentToolCall(callId=call.id, tool=call.name, arguments=arguments))
        return ToolCallsResult(type="tool_calls", calls=calls)
    except (ValueError, ValidationError, RecursionError):
        raise InvalidToolCallsError from None
