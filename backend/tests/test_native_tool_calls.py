import json

import pytest

from wisetodo.agent.results import parse_agent_result
from wisetodo.agent.tool_calls import InvalidToolCallsError, normalize_native_tool_calls
from wisetodo.model.contracts import ModelMessage, ModelRequest, ModelResponse, ToolCall


def response(arguments: str = "{}", **changes) -> ModelResponse:
    return ModelResponse.model_validate(
        {
            "finish_reason": "tool_calls",
            "tool_calls": [{"id": "call_1", "name": "read", "arguments": arguments}],
            **changes,
        }
    )


def test_parallel_calls_preserve_order_ids_values_and_input() -> None:
    native = response(
        tool_calls=[
            {"id": "b", "name": "read", "arguments": '{"章节":[1,true,null,{"x":2.5}]}'},
            {"id": "a", "name": "read", "arguments": "{}"},
        ],
        content="先读取资料。",
    )
    before = native.model_dump_json()
    result = normalize_native_tool_calls(native)
    assert [call.callId for call in result.calls] == ["b", "a"]
    assert result.calls[0].arguments == {"章节": [1, True, None, {"x": 2.5}]}
    assert result.calls[1].arguments == {}
    assert parse_agent_result(result.model_dump_json()) == result
    assert native.model_dump_json() == before
    result.calls[0].arguments["extra"] = "detached"
    assert native.model_dump_json() == before


def test_ids_pair_with_original_assistant_message_and_out_of_order_results() -> None:
    native = response(
        tool_calls=[
            {"id": "b", "name": "read", "arguments": "{}"},
            {"id": "a", "name": "read", "arguments": "{}"},
        ]
    )
    result = normalize_native_tool_calls(native)
    request = ModelRequest(
        messages=(
            ModelMessage(role="user", content="读取资料"),
            ModelMessage(role="assistant", tool_calls=native.tool_calls),
            *(
                ModelMessage(role="tool", tool_call_id=call.callId, content="ok")
                for call in reversed(result.calls)
            ),
        )
    )
    assert request.messages[-1].tool_call_id == "b"


@pytest.mark.parametrize(
    "arguments",
    [
        "",
        "{",
        "[]",
        "null",
        "1",
        '"text"',
        "true",
        "{} {}",
        "```json\n{}\n```",
        '{"x":NaN}',
        '{"x":Infinity}',
        '{"x":-Infinity}',
        '{"x":1e999}',
        '{"x":1,"x":2}',
        '{"nested":{"x":1,"x":2}}',
    ],
)
def test_invalid_arguments_rejected(arguments: str) -> None:
    with pytest.raises(InvalidToolCallsError):
        normalize_native_tool_calls(response(arguments))


@pytest.mark.parametrize("reason", ["stop", "length", "content_filter", "unknown"])
def test_non_tool_terminal_reason_rejected(reason: str) -> None:
    with pytest.raises(InvalidToolCallsError):
        normalize_native_tool_calls(response(finish_reason=reason))


@pytest.mark.parametrize(
    "changes",
    [
        {"tool_calls": []},
        {"refusal": "拒绝"},
        {"refusal": ""},
    ],
)
def test_missing_calls_and_refusal_rejected(changes: dict) -> None:
    with pytest.raises(InvalidToolCallsError):
        normalize_native_tool_calls(response(**changes))


@pytest.mark.parametrize("field,value", [("id", " x "), ("name", " read"), ("id", " ")])
def test_identifiers_never_silently_rewritten(field: str, value: str) -> None:
    call = {"id": "1", "name": "read", "arguments": "{}", field: value}
    with pytest.raises(InvalidToolCallsError):
        normalize_native_tool_calls(response(tool_calls=[call]))


def test_forged_duplicate_ids_revalidated() -> None:
    call = ToolCall(id="1", name="read", arguments="{}")
    native = ModelResponse.model_construct(finish_reason="tool_calls", tool_calls=(call, call))
    with pytest.raises(InvalidToolCallsError):
        normalize_native_tool_calls(native)


def test_invalid_later_call_never_returns_partial_batch_or_raw_error() -> None:
    native = response(
        tool_calls=[
            {"id": "1", "name": "read", "arguments": "{}"},
            {"id": "2", "name": "read", "arguments": '{"secret":"do-not-expose",'},
        ]
    )
    with pytest.raises(InvalidToolCallsError) as caught:
        normalize_native_tool_calls(native)
    assert str(caught.value) == "Invalid native tool response"
    assert caught.value.__suppress_context__


def test_valid_json_escapes_and_empty_object() -> None:
    arguments = {"text": '引号"与换行\n', "nested": {}, "value": 0}
    assert (
        normalize_native_tool_calls(response(json.dumps(arguments))).calls[0].arguments == arguments
    )
