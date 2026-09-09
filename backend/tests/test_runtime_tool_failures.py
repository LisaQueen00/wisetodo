import asyncio
import json

import pytest
from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError
from test_agent_runtime import Scope, create_output, message

from wisetodo.agent.runtime import AgentRuntime
from wisetodo.database import initialize_database
from wisetodo.model.contracts import ModelResponse, ToolCall
from wisetodo.sessions.retry import RetryExecutionError
from wisetodo.sessions.service import SessionService
from wisetodo.sessions.tables import SessionRecord
from wisetodo.todos import TodoService
from wisetodo.tools.transport import ToolExecutor, ToolTransportError


@pytest.mark.parametrize("mode", ["native", "prompt_compat"])
@pytest.mark.parametrize("scenario", ["failure", "cancel", "commit_retry"])
async def test_tool_runtime_fault_combinations(tmp_path, monkeypatch, mode, scenario):
    path = tmp_path / "tools.json"
    path.write_text(
        json.dumps(
            {
                "tools": [
                    {
                        "name": "read",
                        "description": "test",
                        "input_schema": {"type": "object"},
                        "transport": {"type": "http", "url": "http://127.0.0.1:1"},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    count = 2 if scenario == "failure" else 1
    started = asyncio.Event()
    invoked, cleaned = [], []

    async def execute(self, name, arguments):
        index = arguments["index"]
        invoked.append(index)
        try:
            if scenario == "commit_retry":
                return {"private-result": True}
            if scenario == "failure" and index == 0:
                await started.wait()
                raise ToolTransportError("private-error")
            started.set()
            await asyncio.Event().wait()
        finally:
            cleaned.append(index)

    monkeypatch.setattr(ToolExecutor, "execute", execute)

    class Provider(Scope):
        async def complete(self, request):
            self.requests.append(request)
            if len(self.requests) > 1:
                return ModelResponse(content=json.dumps(create_output()), finish_reason="stop")
            if mode == "native":
                return ModelResponse(
                    finish_reason="tool_calls",
                    tool_calls=tuple(
                        ToolCall(id=f"c{i}", name="read", arguments=json.dumps({"index": i}))
                        for i in range(count)
                    ),
                )
            return ModelResponse(
                finish_reason="stop",
                content=json.dumps(
                    {
                        "type": "tool_calls",
                        "calls": [
                            {"callId": f"c{i}", "tool": "read", "arguments": {"index": i}}
                            for i in range(count)
                        ],
                    }
                ),
            )

    db = initialize_database(tmp_path / "test.db")
    task = None
    try:
        provider = Provider()
        sessions, todos = SessionService(db.sessions), TodoService(db.sessions)
        sessions.agent_executor = AgentRuntime(
            sessions, todos, provider, mode=mode, tool_config=path
        )
        session = sessions.create()

        def fail_commit(tx):
            if any(
                isinstance(row, SessionRecord) and row.status == "completed"
                for row in tx.identity_map.values()
            ):
                raise SQLAlchemyError("private database error")

        if scenario == "commit_retry":
            event.listen(db.sessions, "before_commit", fail_commit)
        try:
            async with asyncio.timeout(5):
                task = asyncio.create_task(sessions.submit(session.id, message()))
                if scenario == "cancel":
                    await started.wait()
                    with db.sessions() as tx:
                        run_id = tx.get(SessionRecord, session.id).active_run_id
                    assert sessions.cancel(session.id, run_id)
                    with pytest.raises(asyncio.CancelledError):
                        await task
                else:
                    with pytest.raises(RetryExecutionError):
                        await task
        finally:
            if scenario == "commit_retry":
                event.remove(db.sessions, "before_commit", fail_commit)

        history = sessions.get(session.id)
        assert history.status == ("cancelled" if scenario == "cancel" else "failed")
        assert todos.list() == []
        assert sorted(invoked) == sorted(cleaned) == list(range(count))
        assert provider.opens == provider.closes == 1
        assert len(provider.requests) == (2 if scenario == "commit_retry" else 1)
        terminals = {item.call_id: item.event_type for item in history.tool_events}
        assert terminals == (
            {"c0": "completed"}
            if scenario == "commit_retry"
            else {"c0": "cancelled"}
            if scenario == "cancel"
            else {"c0": "failed", "c1": "cancelled"}
        )
        assert "private" not in json.dumps([item.payload for item in history.tool_events])
        with db.sessions() as tx:
            pending = tx.get(SessionRecord, session.id).pending_operation
            assert (pending is not None) == (scenario == "commit_retry")

        if scenario == "commit_retry":
            # A fresh service simulates restarting; broken config must not be read.
            path.write_text("invalid configuration", encoding="utf-8")
            restarted = SessionService(db.sessions)
            no_model = Scope()
            restarted.agent_executor = AgentRuntime(
                restarted, todos, no_model, mode=mode, tool_config=path
            )
            result = await restarted.retry(session.id)
            assert result.status == "completed"
            assert len(todos.list()) == 1
            assert no_model.opens == 0 and invoked == [0]
            assert len(result.tool_events) == len(history.tool_events)
            with pytest.raises(PermissionError):
                await restarted.retry(session.id)
            assert len(todos.list()) == 1
    finally:
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        db.dispose()
