import asyncio
import json

import pytest

from wisetodo.agent.generation import (
    InvalidAgentOutputError,
    ResultGenerator,
    UnusableModelResponseError,
)
from wisetodo.agent.prompts import build_agent_request
from wisetodo.agent.results import ClarificationResult, ToolCallsResult
from wisetodo.model.contracts import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ToolCall,
    ToolDefinition,
)
from wisetodo.model.provider import ModelRequestError


def valid() -> ModelResponse:
    return ModelResponse(
        content='{"type":"clarification","question":"哪本书？"}', finish_reason="stop"
    )


def request(tools=()) -> ModelRequest:
    return build_agent_request([ModelMessage(role="user", content="阅读计划")], tools=tools)


class FakeProvider:
    def __init__(self, *outputs) -> None:
        self.outputs = list(outputs)
        self.requests = []

    async def complete(self, incoming: ModelRequest) -> ModelResponse:
        self.requests.append(incoming)
        output = self.outputs.pop(0)
        if isinstance(output, BaseException):
            raise output
        return output

    async def aclose(self) -> None:
        raise AssertionError("Generator does not own Provider lifetime")


async def test_valid_first_output_needs_one_call() -> None:
    provider = FakeProvider(valid())
    outcome = await ResultGenerator(provider).generate(request())
    assert isinstance(outcome.result, ClarificationResult)
    assert outcome.response == valid()
    assert len(provider.requests) == 1


@pytest.mark.parametrize(
    "content",
    [
        "not JSON",
        "",
        "```json\n{}\n```",
        '{"type":"todo_operation","operation":{"action":"create","todo":{"topic":"书","items":["章"]}}}',
        '{"type":"todo_operation","operation":{"action":"update","todoId":"1","changes":{}}}',
    ],
)
async def test_one_repair_appends_feedback_preserves_request(content: str) -> None:
    provider = FakeProvider(ModelResponse(content=content, finish_reason="stop"), valid())
    original = request()
    before = original.model_dump_json()
    result = await ResultGenerator(provider).generate(original)
    assert isinstance(result.result, ClarificationResult)
    assert len(provider.requests) == 2
    fixed = provider.requests[1]
    assert fixed.messages[:-1] == original.messages
    assert "Schema 校验错误" in fixed.messages[-1].content
    assert "唯一一次修复" in fixed.messages[-1].content
    assert fixed.messages[-1].role == "user"
    assert original.model_dump_json() == before


async def test_again_invalid_stops_at_two_calls_with_safe_error() -> None:
    bad = ModelResponse(content="private-invalid-output", finish_reason="stop")
    provider = FakeProvider(bad, bad, valid())
    with pytest.raises(InvalidAgentOutputError) as caught:
        await ResultGenerator(provider).generate(request())
    assert str(caught.value) == "Invalid Agent output"
    assert len(provider.requests) == 2


async def test_repair_budget_shared_across_phases() -> None:
    bad = ModelResponse(content="bad", finish_reason="stop")
    provider = FakeProvider(bad, valid(), bad, valid())
    generator = ResultGenerator(provider)
    await generator.generate(request())
    with pytest.raises(InvalidAgentOutputError):
        await generator.generate(request())
    assert len(provider.requests) == 3
    # A new Run gets a new budget.
    other = FakeProvider(bad, valid())
    await ResultGenerator(other).generate(request())
    assert len(other.requests) == 2


@pytest.mark.parametrize(
    "output",
    [
        ModelRequestError(),
        asyncio.CancelledError(),
        ModelResponse(content="{}", refusal="refused", finish_reason="stop"),
        ModelResponse(content="{}", finish_reason="length"),
        ModelResponse(content="{}", finish_reason="content_filter"),
        ModelResponse(content="{}", finish_reason="unknown"),
    ],
)
async def test_non_validation_failures_do_not_repair(output) -> None:
    provider = FakeProvider(output, valid())
    with pytest.raises((ModelRequestError, asyncio.CancelledError, UnusableModelResponseError)):
        await ResultGenerator(provider).generate(request())
    assert len(provider.requests) == 1


async def test_native_repair_has_no_dangling_or_fabricated_tool_messages() -> None:
    definition = ToolDefinition(name="read", description="read only", parameters={"type": "object"})
    bad = ModelResponse(
        finish_reason="tool_calls", tool_calls=(ToolCall(id="old", name="read", arguments="{"),)
    )
    good = ModelResponse(
        finish_reason="tool_calls", tool_calls=(ToolCall(id="new", name="read", arguments="{}"),)
    )
    provider = FakeProvider(bad, good)
    result = await ResultGenerator(provider).generate(request([definition]))
    assert isinstance(result.result, ToolCallsResult)
    assert result.result.calls[0].callId == "new"
    assert result.response == good
    repair = provider.requests[1]
    assert repair.tools == (definition,)
    assert not any(message.tool_calls or message.role == "tool" for message in repair.messages)
    assert "arguments" in repair.messages[-1].content
    assert ModelRequest.model_validate_json(repair.model_dump_json()) == repair


@pytest.mark.parametrize("native", [True, False])
async def test_unavailable_or_text_tools_are_repaired(native: bool) -> None:
    bad = (
        ModelResponse(
            finish_reason="tool_calls",
            tool_calls=(ToolCall(id="x", name="missing", arguments="{}"),),
        )
        if native
        else ModelResponse(
            content=json.dumps(
                {
                    "type": "tool_calls",
                    "calls": [{"callId": "x", "tool": "read", "arguments": {}}],
                }
            ),
            finish_reason="stop",
        )
    )
    provider = FakeProvider(bad, valid())
    await ResultGenerator(provider).generate(request())
    assert len(provider.requests) == 2
    assert provider.requests[1].tools == ()


async def test_cancel_after_provider_returns_prevents_repair() -> None:
    class CancellingProvider(FakeProvider):
        async def complete(self, incoming):
            result = await super().complete(incoming)
            asyncio.current_task().cancel()
            return result

    provider = CancellingProvider(ModelResponse(content="bad", finish_reason="stop"), valid())
    task = asyncio.create_task(ResultGenerator(provider).generate(request()))
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(provider.requests) == 1


async def test_cancel_during_repair_is_propagated() -> None:
    started = asyncio.Event()

    class BlockingProvider(FakeProvider):
        async def complete(self, incoming):
            if self.requests:
                self.requests.append(incoming)
                started.set()
                await asyncio.Event().wait()
            return await super().complete(incoming)

    provider = BlockingProvider(ModelResponse(content="bad", finish_reason="stop"))
    task = asyncio.create_task(ResultGenerator(provider).generate(request()))
    await asyncio.wait_for(started.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(provider.requests) == 2


async def test_feedback_identifies_invalid_item_count() -> None:
    bad = ModelResponse(
        content=json.dumps(
            {
                "type": "todo_operation",
                "operation": {
                    "action": "create",
                    "todo": {"topic": "书", "items": ["一章"]},
                },
            }
        ),
        finish_reason="stop",
    )
    provider = FakeProvider(bad, valid())
    await ResultGenerator(provider).generate(request())
    feedback = provider.requests[1].messages[-1].content
    assert "todo_operation.operation.create.todo.items: too_short" in feedback
