"""Concurrent execution for a caller-vetted batch of independent read-only calls."""

import asyncio
from collections.abc import Sequence
from typing import Protocol

from pydantic import JsonValue

from wisetodo.agent.results import AgentToolCall, ToolCallsResult


class ToolRunner(Protocol):
    async def execute(self, name: str, arguments: dict[str, JsonValue]) -> JsonValue: ...


async def execute_batch(
    executor: ToolRunner, calls: Sequence[AgentToolCall]
) -> tuple[JsonValue, ...]:
    """Detach and revalidate the batch before scheduling; preserve input order.

    Independence and read-only permission are the caller's responsibility. This
    layer neither infers dependencies nor retries calls. Per-call validation and
    timeouts remain with ToolExecutor. The first observed failure cancels unfinished
    siblings; cleanup finishes before that original exception is propagated.
    """
    snapshot = ToolCallsResult.model_validate(
        {"type": "tool_calls", "calls": [call.model_dump() for call in calls]}
    )
    tasks = [
        asyncio.create_task(executor.execute(call.tool, call.arguments)) for call in snapshot.calls
    ]
    try:
        return tuple(await asyncio.gather(*tasks))
    finally:
        # gather propagates failures without cancelling siblings; explicitly own cleanup.
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
