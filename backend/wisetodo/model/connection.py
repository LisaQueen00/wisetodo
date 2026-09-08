"""A bounded, user-triggered connectivity probe, not an Agent execution."""

import asyncio
import json
from typing import Literal

import httpx

from wisetodo.settings import SettingsNotConfiguredError, SettingsService
from wisetodo.settings.storage import SettingsStorageError

ConnectionStatus = Literal[
    "ok",
    "not_configured",
    "settings_unavailable",
    "authentication",
    "not_found",
    "rate_limited",
    "timeout",
    "request_failed",
    "invalid_response",
]


async def check_connection(
    settings: SettingsService,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> ConnectionStatus:
    try:
        config = settings.resolve()
    except SettingsNotConfiguredError:
        return "not_configured"
    except SettingsStorageError:
        return "settings_unavailable"
    headers = {}
    if config.api_key is not None:
        headers["Authorization"] = f"Bearer {config.api_key.get_secret_value()}"
    try:
        async with (
            asyncio.timeout(15),
            httpx.AsyncClient(
                transport=transport,
                timeout=10,
                follow_redirects=False,
                trust_env=False,
            ) as client,client.stream(
            "POST",
            config.base_url.rstrip("/") + "/chat/completions",
            headers=headers,
            json={
                "model": config.model,
                "messages": [{"role": "user", "content": "Reply OK."}],
                "stream": False,
                "max_completion_tokens": 64,
            },
        ) as response
        ):
            if response.status_code in {401, 403}:
                return "authentication"
            if response.status_code == 404:
                return "not_found"
            if response.status_code == 429:
                return "rate_limited"
            if not 200 <= response.status_code < 300:
                return "request_failed"
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > 65536:
                    return "invalid_response"
            data = json.loads(body)
            choice = data["choices"][0]
            message = choice["message"]
            if (
                message.get("role") != "assistant"
                or choice.get("finish_reason") != "stop"
                or message.get("refusal")
                or message.get("tool_calls")
                or not isinstance(message.get("content"), str)
                or not message["content"].strip()
            ):
                return "invalid_response"
            return "ok"
    except (TimeoutError, httpx.TimeoutException):
        return "timeout"
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        return "invalid_response"
    except Exception:
        return "request_failed"
