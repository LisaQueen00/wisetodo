"""Safe run lifecycle events, correlated with the current IPC request."""

from contextvars import ContextVar
from typing import Literal

from pydantic import BaseModel

request_id: ContextVar[str | None] = ContextVar("ipc_request_id", default=None)


class RunEvent(BaseModel):
    type: Literal["event"] = "event"
    requestId: str
    event: Literal["run.started", "run.finished", "run.updated"]
    session_id: str
    run_id: str


def emit_run(
    event: Literal["run.started", "run.finished", "run.updated"], session_id: str, run_id: str
) -> None:
    correlation = request_id.get()
    if correlation is not None:
        print(
            RunEvent(
                requestId=correlation, event=event, session_id=session_id, run_id=run_id
            ).model_dump_json(),
            flush=True,
        )
