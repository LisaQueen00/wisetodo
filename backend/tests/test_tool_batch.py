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


@pytest.mark.parametrize("failure", [ValueError("failure"), TimeoutError("timeout")])
async def test_first_failure_cancels_siblings_and_waits_for_cleanup(failure):
    started = asyncio.Event()
    cleaned = []
    invocations = []

    class Runner:
        async def execute(self, name, arguments):
            index = arguments["index"]
            invocations.append(index)
            if index == 0:
                await started.wait()
                raise failure
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                await asyncio.sleep(0)
                cleaned.append(index)

    async with asyncio.timeout(2):
        with pytest.raises(type(failure)) as caught:
            await execute_batch(Runner(), calls())
    assert caught.value is failure
    assert cleaned == [1]
    assert sorted(invocations) == [0, 1]


async def test_cleanup_failure_does_not_replace_original_error():
    started = asyncio.Event()
    original = ValueError("original")

    class Runner:
        async def execute(self, name, arguments):
            if arguments["index"] == 0:
                await started.wait()
                raise original
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                raise RuntimeError("cleanup")

    async with asyncio.timeout(2):
        with pytest.raises(ValueError) as caught:
            await execute_batch(Runner(), calls())
    assert caught.value is original


async def test_child_cancellation_cancels_sibling():
    started = asyncio.Event()
    cleaned = []

    class Runner:
        async def execute(self, name, arguments):
            if arguments["index"] == 0:
                await started.wait()
                raise asyncio.CancelledError
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleaned.append(True)

    async with asyncio.timeout(2):
        with pytest.raises(asyncio.CancelledError):
            await execute_batch(Runner(), calls())
    assert cleaned == [True]
