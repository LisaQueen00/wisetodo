"""Pure Session lifecycle rules, independent of persistence and model providers."""

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from wisetodo.sessions.models import SessionStatus


class SessionEvent(StrEnum):
    SUBMIT = "submit"
    RETRY = "retry"
    REQUEST_INPUT = "request_input"
    TODO_COMMITTED = "todo_committed"
    FAIL = "fail"
    CANCEL = "cancel"


class InvalidSessionTransition(ValueError):
    def __init__(self, status: SessionStatus, event: SessionEvent) -> None:
        self.status = status
        self.event = event
        super().__init__(f"Cannot apply {event.value} to Session in {status.value}")


_TRANSITIONS: Final = MappingProxyType(
    {
        (SessionStatus.READY, SessionEvent.SUBMIT): SessionStatus.RUNNING,
        (SessionStatus.WAITING_INPUT, SessionEvent.SUBMIT): SessionStatus.RUNNING,
        (SessionStatus.FAILED, SessionEvent.SUBMIT): SessionStatus.RUNNING,
        (SessionStatus.CANCELLED, SessionEvent.SUBMIT): SessionStatus.RUNNING,
        (SessionStatus.FAILED, SessionEvent.RETRY): SessionStatus.RUNNING,
        (SessionStatus.CANCELLED, SessionEvent.RETRY): SessionStatus.RUNNING,
        (SessionStatus.RUNNING, SessionEvent.REQUEST_INPUT): SessionStatus.WAITING_INPUT,
        (SessionStatus.RUNNING, SessionEvent.TODO_COMMITTED): SessionStatus.COMPLETED,
        (SessionStatus.RUNNING, SessionEvent.FAIL): SessionStatus.FAILED,
        (SessionStatus.RUNNING, SessionEvent.CANCEL): SessionStatus.CANCELLED,
    }
)


def next_status(status: SessionStatus, event: SessionEvent) -> SessionStatus:
    """Validate a transition without mutating or saving anything.

    TODO_COMMITTED must only be emitted by the trusted runtime after a successful
    Todo Service commit, not by the model or UI. Callers also own run-ID checks,
    cancellation/commit coordination and atomic persistence of lifecycle changes.
    """
    if not isinstance(status, SessionStatus) or not isinstance(event, SessionEvent):
        raise TypeError("Expected SessionStatus and SessionEvent enum values")
    target = _TRANSITIONS.get((status, event))
    if target is None:
        raise InvalidSessionTransition(status, event)
    return target


@dataclass(frozen=True)
class SessionCapabilities:
    can_submit: bool
    can_retry: bool
    can_cancel: bool
    is_read_only: bool


def capabilities(status: SessionStatus) -> SessionCapabilities:
    """Describe lifecycle actions; read-only means a successfully closed chat.

    Loading/deleting history are separate operations, not lifecycle transitions.
    """
    if not isinstance(status, SessionStatus):
        raise TypeError("Expected a SessionStatus enum value")
    return SessionCapabilities(
        can_submit=(status, SessionEvent.SUBMIT) in _TRANSITIONS,
        can_retry=(status, SessionEvent.RETRY) in _TRANSITIONS,
        can_cancel=(status, SessionEvent.CANCEL) in _TRANSITIONS,
        is_read_only=status is SessionStatus.COMPLETED,
    )
