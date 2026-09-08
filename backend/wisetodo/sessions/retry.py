"""Executor contract for retrying retained Session input, without a model dependency."""

from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import BaseModel

from wisetodo.sessions.models import SessionHistory
from wisetodo.sessions.state_machine import SessionEvent


class RetryUnavailableError(RuntimeError):
    pass


class RetryExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class RetryRequest:
    run_id: str
    history: SessionHistory


class RetryOutcome(BaseModel):
    # Successful Todo commits belong to the future transactional Runtime, not a
    # model's claim that it is done. This contract cannot fabricate completion.
    event: Literal[SessionEvent.REQUEST_INPUT, SessionEvent.FAIL, SessionEvent.CANCEL]


class RetryExecutor(Protocol):
    async def __call__(self, request: RetryRequest) -> RetryOutcome: ...


class AgentExecutor(Protocol):
    async def execute(self, session_id: str, run_id: str) -> None:
        """Persist a terminal result atomically, checking the persisted Run owner."""
        ...
