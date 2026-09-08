import asyncio

import pytest
from pydantic import ValidationError

from wisetodo.model import ModelMessage, ModelProvider, ModelRequest, ModelResponse, ToolCall


def test_roundtrip_parallel_tool_results() -> None:
    calls = tuple(
        ToolCall(id=str(i), name="read_url", arguments='{"url":"test"}') for i in range(2)
    )
    request = ModelRequest(
        messages=(
            ModelMessage(role="user", content="学习项目"),
            ModelMessage(role="assistant", tool_calls=calls),
            ModelMessage(role="tool", tool_call_id="1", content="result one"),
            ModelMessage(role="tool", tool_call_id="0", content="result zero"),
        )
    )
    assert ModelRequest.model_validate_json(request.model_dump_json()) == request


@pytest.mark.parametrize(
    "messages",
    [
        [],
        [{"role": "tool", "content": "missing ID"}],
        [{"role": "user", "tool_call_id": "bad"}],
        [{"role": "tool", "tool_call_id": "orphan"}],
        [{"role": "assistant", "tool_calls": [{"id": "1", "name": "read", "arguments": "{}"}]}],
        [{"role": "user", "tool_calls": [{"id": "1", "name": "read", "arguments": "{}"}]}],
    ],
)
def test_invalid_message_sequences(messages: list) -> None:
    with pytest.raises(ValidationError):
        ModelRequest.model_validate({"messages": messages})


def test_duplicate_tools_and_credentials_rejected() -> None:
    base = {"messages": [{"role": "user", "content": "test"}]}
    tool = {"name": "read", "description": "read", "parameters": {"type": "object"}}
    for extra in ({"tools": [tool, tool]}, {"api_key": "secret"}, {"model": "override"}):
        with pytest.raises(ValidationError):
            ModelRequest.model_validate({**base, **extra})


def test_incomplete_response_preserves_untrusted_arguments() -> None:
    result = ModelResponse(
        finish_reason="length",
        tool_calls=(ToolCall(id="1", name="read", arguments='{"incomplete":'),),
    )
    assert result.tool_calls[0].arguments == '{"incomplete":'
    assert result.finish_reason == "length"


def test_refusal_and_empty_output_are_not_fabricated_success() -> None:
    assert ModelResponse(finish_reason="content_filter", refusal="refused").refusal == "refused"
    assert ModelResponse(finish_reason="unknown").content == ""


class FakeProvider:
    closed = False

    async def complete(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(content=request.messages[-1].content, finish_reason="stop")

    async def aclose(self) -> None:
        self.closed = True


async def test_provider_substitution_without_sdk_or_network() -> None:
    provider: ModelProvider = FakeProvider()
    assert isinstance(provider, ModelProvider)
    result = await provider.complete(
        ModelRequest(messages=(ModelMessage(role="user", content="hello"),))
    )
    assert result.content == "hello"
    await provider.aclose()
    await provider.aclose()


async def test_cancellation_remains_control_flow() -> None:
    class CancelledProvider(FakeProvider):
        async def complete(self, request: ModelRequest) -> ModelResponse:
            raise asyncio.CancelledError

    provider: ModelProvider = CancelledProvider()
    with pytest.raises(asyncio.CancelledError):
        await provider.complete(ModelRequest(messages=(ModelMessage(role="user", content="test"),)))
