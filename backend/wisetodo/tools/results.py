"""Call-ID keyed results for a successful batch; no history or model invocation."""

import copy
from collections.abc import Sequence

from pydantic import JsonValue

from wisetodo.agent.results import AgentToolCall, ToolCallsResult
from wisetodo.tools.batch import ToolRunner, execute_batch


async def execute_results(
    executor: ToolRunner, calls: Sequence[AgentToolCall]
) -> dict[str, JsonValue]:
    """Return values keyed by callId, in original call order, only on full success.

    Capture IDs before awaiting: caller mutations cannot change result ownership.
    Tool names are not keys because one tool can be called multiple times.
    Failures/cancellation retain execute_batch semantics and expose no partial map.
    """
    snapshot = ToolCallsResult.model_validate(
        {"type": "tool_calls", "calls": [call.model_dump() for call in calls]}
    )
    results = await execute_batch(executor, snapshot.calls)
    return {
        call.callId: copy.deepcopy(result)
        for call, result in zip(snapshot.calls, results, strict=True)
    }
