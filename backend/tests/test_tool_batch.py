import asyncio

import pytest
from pydantic import ValidationError

from wisetodo.agent.results import AgentToolCall
from wisetodo.tools.batch import execute_batch


def calls():
    return [AgentToolCall(callId=str(i), tool="read", arguments={"index": i}) for i in range(2)]


async def test_calls_start_concurrently_and_results_keep_input_order():
    started = []
    both_started = asyncio.Event()
    second_done = asyncio.Event()

    class Runner:
        async def execute(self, name, arguments):
            index = arguments["index"]
            started.append(index)
            if len(started) == 2:
                both_started.set()
            await both_started.wait()
            if index == 0:
                await second_done.wait()
            else:
                second_done.set()
            return {"index": index}

    async with asyncio.timeout(2):
        result = await execute_batch(Runner(), calls())
    assert result == ({"index": 0}, {"index": 1})


@pytest.mark.parametrize("batch", [[], [calls()[0], calls()[0]]])
async def test_invalid_batch_never_starts(batch):
    class Runner:
        async def execute(self, name, arguments):
            pytest.fail("Invalid batch must not run")

    with pytest.raises(ValidationError):
        await execute_batch(Runner(), batch)


async def test_snapshot_is_detached_before_execution():
    batch = calls()

    class Runner:
        async def execute(self, name, arguments):
            batch[1].arguments["index"] = 99
            return arguments["index"]

    assert await execute_batch(Runner(), batch) == (0, 1)


async def test_caller_cancellation_cleans_up_all_children():
    started = asyncio.Event()
    running = []
    finished = []

    class Runner:
        async def execute(self, name, arguments):
            index = arguments["index"]
            running.append(index)
            if len(running) == 2:
                started.set()
            try:
                await asyncio.Event().wait()
            finally:
                finished.append(index)

    async with asyncio.timeout(2):
        task = asyncio.create_task(execute_batch(Runner(), calls()))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert sorted(finished) == [0, 1]


async def test_failure_is_propagated_after_siblings_finish_without_retry():
    completed = []

    class Runner:
        async def execute(self, name, arguments):
            index = arguments["index"]
            if index == 0:
                raise ValueError("failure")
            await asyncio.sleep(0)
            completed.append(index)
            return None

    with pytest.raises(ValueError, match="failure"):
        await execute_batch(Runner(), calls())
    assert completed == [1]
