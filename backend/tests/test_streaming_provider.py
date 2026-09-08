import asyncio
import json
from contextlib import aclosing

import httpx2 as httpx
import pytest
from pydantic import SecretStr

from wisetodo.model import ModelMessage, ModelRequest, ModelRequestError, ModelResponse
from wisetodo.model.openai_provider import ModelDelta, OpenAIProvider
from wisetodo.settings import ResolvedSettings


def request() -> ModelRequest:
    return ModelRequest(messages=(ModelMessage(role="user", content="test"),))


def event(delta: dict, finish: str | None = None) -> bytes:
    return (
        "data: "
        + json.dumps(
            {
                "id": "chunk",
                "object": "chat.completion.chunk",
                "created": 0,
                "model": "test",
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
            },
            ensure_ascii=False,
        )
        + "\n\n"
    ).encode()


class Stream(httpx.AsyncByteStream):
    def __init__(self, data: bytes, block: bool = False) -> None:
        self.data = data
        self.block = block
        self.waiting = asyncio.Event()
        self.closed = False

    async def __aiter__(self):
        # Split UTF-8/SSE arbitrarily to test the real SDK decoder.
        for index in range(0, len(self.data), 7):
            yield self.data[index : index + 7]
        if self.block:
            self.waiting.set()
            await asyncio.Event().wait()

    async def aclose(self) -> None:
        self.closed = True


def provider(stream: Stream, key: str | None = None) -> OpenAIProvider:
    return OpenAIProvider(
        ResolvedSettings(
            base_url="http://localhost:8000/v1",
            model="test",
            api_key=SecretStr(key) if key else None,
        ),
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200, headers={"content-type": "text/event-stream"}, stream=stream
            )
        ),
    )


async def test_text_stream_and_terminal_result() -> None:
    data = Stream(
        event({"content": "你好"})
        + event({"content": "世界"})
        + event({}, "stop")
        + b"data: [DONE]\n\n"
    )
    client = provider(data)
    try:
        results = [item async for item in client.stream(request())]
        assert [item.text for item in results if isinstance(item, ModelDelta)] == ["你好", "世界"]
        assert results[-1] == ModelResponse(content="你好世界", finish_reason="stop")
        assert data.closed
    finally:
        await client.aclose()
        await client.aclose()


async def test_interleaved_tool_arguments_are_preserved() -> None:
    data = Stream(
        event(
            {
                "tool_calls": [
                    {
                        "index": 1,
                        "id": "b",
                        "type": "function",
                        "function": {"name": "read", "arguments": "{"},
                    }
                ]
            }
        )
        + event(
            {
                "tool_calls": [
                    {
                        "index": 0,
                        "id": "a",
                        "type": "function",
                        "function": {"name": "read", "arguments": "{}"},
                    },
                    {"index": 1, "function": {"arguments": "}"}},
                ]
            }
        )
        + event({}, "tool_calls")
        + b"data: [DONE]\n\n"
    )
    client = provider(data)
    try:
        result = await client.complete(request())
        assert [call.id for call in result.tool_calls] == ["a", "b"]
        assert [call.arguments for call in result.tool_calls] == ["{}", "{}"]
    finally:
        await client.aclose()


@pytest.mark.parametrize(
    "body", [event({"content": "partial"}), b"data: broken\n\n", b"data: [DONE]\n\n"]
)
async def test_incomplete_stream_is_safe_failure(body: bytes) -> None:
    client = provider(Stream(body))
    try:
        with pytest.raises(ModelRequestError):
            await client.complete(request())
    finally:
        await client.aclose()


async def test_cancellation_closes_active_stream_without_final_result() -> None:
    stream = Stream(event({"content": "partial"}), block=True)
    client = provider(stream)
    task = asyncio.create_task(client.complete(request()))
    await asyncio.wait_for(stream.waiting.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert stream.closed
    await client.aclose()


async def test_consumer_closes_early() -> None:
    data = Stream(event({"content": "first"}), block=True)
    client = provider(data)
    try:
        async with aclosing(client.stream(request())) as chunks:
            async for _ in chunks:
                break
        assert data.closed
    finally:
        await client.aclose()


@pytest.mark.parametrize(
    "reason,delta", [("length", {"content": "partial"}), ("content_filter", {"refusal": "refused"})]
)
async def test_non_success_terminal_state_preserved(reason: str, delta: dict) -> None:
    client = provider(Stream(event(delta) + event({}, reason) + b"data: [DONE]\n\n"))
    try:
        result = await client.complete(request())
        assert result.finish_reason == reason
        if reason == "content_filter":
            assert result.refusal == "refused"
    finally:
        await client.aclose()


async def test_cancelled_before_request_sends_nothing() -> None:
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        return httpx.Response(500)

    client = OpenAIProvider(
        ResolvedSettings(base_url="http://localhost", model="test"),
        transport=httpx.MockTransport(handler),
    )

    async def cancelled() -> None:
        task = asyncio.current_task()
        assert task is not None
        task.cancel()
        await client.complete(request())

    try:
        with pytest.raises(asyncio.CancelledError):
            await asyncio.create_task(cancelled())
        assert calls == []
    finally:
        await client.aclose()


@pytest.mark.parametrize("key", [None, "configured-key"])
async def test_explicit_config_no_environment_key_or_retries(
    key: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "environment-secret")
    requests = []

    def handler(req: httpx.Request) -> httpx.Response:
        requests.append(req)
        assert str(req.url) == "http://localhost:8000/v1/chat/completions"
        assert req.headers.get("authorization") == (f"Bearer {key}" if key else None)
        assert json.loads(req.content)["stream"] is True
        return httpx.Response(401, json={"error": {"message": "environment-secret"}})

    client = OpenAIProvider(
        ResolvedSettings(
            base_url="http://localhost:8000/v1",
            model="test",
            api_key=SecretStr(key) if key else None,
        ),
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(ModelRequestError) as error:
            await client.complete(request())
        assert "environment-secret" not in str(error.value)
        assert len(requests) == 1
    finally:
        await client.aclose()
