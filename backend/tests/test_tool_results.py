import asyncio

import pytest
from pydantic import ValidationError

from wisetodo.agent.results import AgentToolCall
from wisetodo.tools.results import execute_results


def calls():
    return [
        AgentToolCall(callId=f"call-{i}", tool="read", arguments={"index": i}) for i in range(2)
    ]


async def test_reverse_completion_same_tool_and_mutated_caller_ids():
    batch = calls()
    second_done = asyncio.Event()
    completed = []

    class Runner:
        async def execute(self, name, arguments):
            index = arguments["index"]
            batch[index].callId = "changed"
            if index == 0:
                await second_done.wait()
            completed.append(index)
            if index == 1:
                second_done.set()
            return {"index": index}

    async with asyncio.timeout(2):
        result = await execute_results(Runner(), batch)
    assert completed == [1, 0]
    assert list(result) == ["call-0", "call-1"]
    assert result == {"call-0": {"index": 0}, "call-1": {"index": 1}}


async def test_results_are_detached_and_preserve_null():
    shared = {"items": [1]}

    class Runner:
        async def execute(self, name, arguments):
            return shared if arguments["index"] == 0 else None

    result = await execute_results(Runner(), calls())
    shared["items"].append(2)
    assert result == {"call-0": {"items": [1]}, "call-1": None}


async def test_duplicate_ids_never_execute():
    batch = calls()
    batch[1].callId = batch[0].callId

    class Runner:
        async def execute(self, name, arguments):
            pytest.fail("must not execute")

    with pytest.raises(ValidationError):
        await execute_results(Runner(), batch)


async def test_failure_does_not_return_partial_results():
    class Runner:
        async def execute(self, name, arguments):
            if arguments["index"] == 1:
                raise ValueError("failed")
            return "success"

    with pytest.raises(ValueError, match="failed"):
        await execute_results(Runner(), calls())
