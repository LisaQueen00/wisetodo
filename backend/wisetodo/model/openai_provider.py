"""OpenAI-compatible streaming transport; does not execute Agent operations."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import aclosing
from typing import Any, Literal

import httpx2 as httpx
from openai import AsyncOpenAI

from wisetodo.model.contracts import Contract, ModelRequest, ModelResponse, ToolCall
from wisetodo.model.provider import ModelRequestError
from wisetodo.settings import ResolvedSettings


class ModelDelta(Contract):
    kind: Literal["text", "refusal", "tool"]
    text: str = ""
    index: int | None = None
    call_id: str | None = None
    name: str | None = None


def check_cancelled() -> None:
    task = asyncio.current_task()
    if task is not None and task.cancelling():
        raise asyncio.CancelledError


class OpenAIProvider:
    def __init__(
        self, settings: ResolvedSettings, *, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._settings = settings.model_copy(deep=True)
        self._closed = False

        async def local_auth(request: httpx.Request) -> None:
            if settings.api_key is None:
                request.headers.pop("Authorization", None)

        self._client = AsyncOpenAI(
            base_url=settings.base_url,
            api_key=settings.api_key.get_secret_value() if settings.api_key else "local-no-key",
            organization="",
            project="",
            admin_api_key="",
            max_retries=0,
            http_client=httpx.AsyncClient(
                transport=transport,
                follow_redirects=False,
                trust_env=False,
                event_hooks={"request": [local_auth]},
                timeout=httpx.Timeout(60, connect=10),
            ),
            timeout=httpx.Timeout(60, connect=10),
        )

    def _payload(self, request: ModelRequest) -> dict[str, Any]:
        messages: list[dict[str, Any]] = []
        for message in request.messages:
            item: dict[str, Any] = {"role": message.role, "content": message.content}
            if message.tool_call_id is not None:
                item["tool_call_id"] = message.tool_call_id
            if message.tool_calls:
                item["tool_calls"] = [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": call.arguments,
                        },
                    }
                    for call in message.tool_calls
                ]
            messages.append(item)
        payload: dict[str, Any] = {
            "model": self._settings.model,
            "messages": messages,
            "stream": True,
        }
        if request.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
                for tool in request.tools
            ]
        if request.output_schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": request.output_schema.name,
                    "schema": request.output_schema.json_schema,
                    "strict": True,
                },
            }
        return payload

    async def stream(
        self, request: ModelRequest
    ) -> AsyncGenerator[ModelDelta | ModelResponse, None]:
        check_cancelled()
        if self._closed:
            raise ModelRequestError
        request = request.model_copy(deep=True)
        text: list[str] = []
        refusal: list[str] = []
        calls: dict[int, dict[str, str]] = {}
        finish: str | None = None
        size = 0
        try:
            async with await self._client.chat.completions.create(
                **self._payload(request)
            ) as chunks:
                async for chunk in chunks:
                    check_cancelled()
                    size += len(chunk.model_dump_json())
                    if size > 16 * 1024 * 1024:
                        raise ValueError("Stream exceeds memory limit")
                    if not chunk.choices:  # Optional usage-only final chunk.
                        continue
                    if len(chunk.choices) != 1 or chunk.choices[0].index != 0 or finish is not None:
                        raise ValueError("Unexpected stream choice")
                    choice = chunk.choices[0]
                    delta = choice.delta
                    if delta.content:
                        text.append(delta.content)
                        yield ModelDelta(kind="text", text=delta.content)
                    if delta.refusal:
                        refusal.append(delta.refusal)
                        yield ModelDelta(kind="refusal", text=delta.refusal)
                    for call in delta.tool_calls or []:
                        if call.index < 0 or call.type not in {None, "function"}:
                            raise ValueError("Unsupported tool call")
                        entry = calls.setdefault(
                            call.index, {"id": "", "name": "", "arguments": ""}
                        )
                        if call.id:
                            if entry["id"] and entry["id"] != call.id:
                                raise ValueError("Changing tool call ID")
                            entry["id"] = call.id
                        name = call.function.name if call.function else None
                        arguments = call.function.arguments if call.function else None
                        entry["name"] += name or ""
                        entry["arguments"] += arguments or ""
                        yield ModelDelta(
                            kind="tool",
                            index=call.index,
                            call_id=call.id,
                            name=name,
                            text=arguments or "",
                        )
                    if choice.finish_reason is not None:
                        finish = choice.finish_reason
            check_cancelled()
            if finish is None:
                raise ValueError("Stream ended without a terminal reason")
            result = ModelResponse.model_validate(
                {
                    "content": "".join(text),
                    "refusal": "".join(refusal) or None,
                    "tool_calls": [ToolCall(**calls[index]) for index in sorted(calls)],
                    "finish_reason": finish
                    if finish in {"stop", "tool_calls", "length", "content_filter"}
                    else "unknown",
                }
            )
            yield result
        except Exception:
            raise ModelRequestError from None

    async def complete(self, request: ModelRequest) -> ModelResponse:
        result: ModelResponse | None = None
        async with aclosing(self.stream(request)) as stream:
            async for event in stream:
                if isinstance(event, ModelResponse):
                    result = event
        check_cancelled()
        if result is None:
            raise ModelRequestError
        return result

    async def aclose(self) -> None:
        if not self._closed:
            self._closed = True
            await self._client.close()
