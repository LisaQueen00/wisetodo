import json

import pytest
from pydantic import ValidationError

from wisetodo.agent.generation import InvalidAgentOutputError, ResultGenerator
from wisetodo.agent.prompts import build_agent_request
from wisetodo.agent.results import ToolCallsResult
from wisetodo.model.contracts import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ToolCall,
    ToolDefinition,
)
from wisetodo.model.openai_provider import OpenAIProvider
from wisetodo.settings import ResolvedSettings


def request(phase="decision"):
    return build_agent_request(
        [ModelMessage(role="user", content="read")],
        mode="prompt_compat",
        phase=phase,
        tools=[ToolDefinition(name="read", description="只读", parameters={"type": "object"})],
    )


def calls(arguments=None, name="read"):
    return ModelResponse(
        finish_reason="stop",
        content=json.dumps(
            {
                "type": "tool_calls",
                "calls": [{"callId": "one", "tool": name, "arguments": arguments or {}}],
            }
        ),
    )


class Provider:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    async def complete(self, incoming):
        self.requests.append(incoming)
        return self.responses.pop(0)

    async def aclose(self):
        pass


async def test_compat_text_call_normalizes_to_same_agent_result():
    provider = Provider(calls({"url": "example"}))
    result = await ResultGenerator(provider).generate(request())
    assert isinstance(result.result, ToolCallsResult)
    assert result.result.calls[0].arguments == {"url": "example"}
    assert len(provider.requests) == 1


def test_prompt_contains_tools_but_no_conflicting_native_instruction():
    content = request().messages[0].content
    assert "prompt_compat" in content
    assert '"name": "read"' in content
    assert "不在 content 中模拟" not in content
    assert "AgentResult Schema" in content
    assert "至少两个非空字符串" in content


async def test_wire_payload_has_no_native_tool_or_response_format_parameters():
    provider = OpenAIProvider(ResolvedSettings(base_url="http://invalid.test/v1", model="test"))
    try:
        payload = provider._payload(request())
        assert "tools" not in payload and "response_format" not in payload and "mode" not in payload
        assert payload["stream"] is True
    finally:
        await provider.aclose()


@pytest.mark.parametrize(
    "phase,bad",
    [
        ("decision", calls(name="unknown")),
        ("final", calls()),
        ("decision", calls("not an object")),
        (
            "decision",
            ModelResponse(
                finish_reason="tool_calls",
                tool_calls=(ToolCall(id="x", name="read", arguments="{}"),),
            ),
        ),
    ],
)
async def test_repair_preserves_mode_and_rejects_inappropriate_calls(phase, bad):
    good = ModelResponse(
        finish_reason="stop", content='{"type":"clarification","question":"what?"}'
    )
    provider = Provider(bad, good)
    await ResultGenerator(provider).generate(request(phase))
    assert len(provider.requests) == 2
    assert provider.requests[-1].mode == "prompt_compat"
    assert provider.requests[-1].tools == request(phase).tools


async def test_second_invalid_result_stops():
    provider = Provider(calls(name="unknown"), calls(name="unknown"))
    with pytest.raises(InvalidAgentOutputError):
        await ResultGenerator(provider).generate(request())
    assert len(provider.requests) == 2


def test_native_tool_history_cannot_leak_into_compat_request():
    with pytest.raises(ValidationError):
        ModelRequest(
            mode="prompt_compat",
            messages=(
                ModelMessage(
                    role="assistant", tool_calls=(ToolCall(id="x", name="read", arguments="{}"),)
                ),
                ModelMessage(role="tool", tool_call_id="x", content="ok"),
            ),
        )


@pytest.mark.parametrize(
    "content",
    [
        '{"type":"clarification","question":"哪本书？"}',
        '{"type":"todo_operation","operation":{"action":"create","todo":{"topic":"书","items":["一章","二章"]}}}',
        '{"type":"todo_operation","operation":{"action":"update","todoId":"id","changes":{"priority":1}}}',
    ],
)
async def test_final_json_operations_and_clarification(content):
    provider = Provider(ModelResponse(finish_reason="stop", content=content))
    result = await ResultGenerator(provider).generate(request("final"))
    assert result.result.type != "tool_calls"
