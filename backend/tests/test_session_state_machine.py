from dataclasses import FrozenInstanceError
from itertools import product

import pytest

from wisetodo.sessions.models import SessionStatus as Status
from wisetodo.sessions.state_machine import (
    InvalidSessionTransition,
    SessionCapabilities,
    capabilities,
    next_status,
)
from wisetodo.sessions.state_machine import (
    SessionEvent as Event,
)

# Independent specification: every state/event pair is checked, including replays.
EXPECTED = {
    Status.READY: {Event.SUBMIT: Status.RUNNING},
    Status.RUNNING: {
        Event.REQUEST_INPUT: Status.WAITING_INPUT,
        Event.TODO_COMMITTED: Status.COMPLETED,
        Event.FAIL: Status.FAILED,
        Event.CANCEL: Status.CANCELLED,
    },
    Status.WAITING_INPUT: {Event.SUBMIT: Status.RUNNING},
    Status.COMPLETED: {},
    Status.FAILED: {Event.SUBMIT: Status.RUNNING, Event.RETRY: Status.RUNNING},
    Status.CANCELLED: {Event.SUBMIT: Status.RUNNING, Event.RETRY: Status.RUNNING},
}


@pytest.mark.parametrize(("status", "event"), list(product(Status, Event)))
def test_complete_transition_matrix(status: Status, event: Event) -> None:
    if event in EXPECTED[status]:
        assert next_status(status, event) is EXPECTED[status][event]
    else:
        with pytest.raises(InvalidSessionTransition) as failure:
            next_status(status, event)
        assert failure.value.status is status
        assert failure.value.event is event
        assert status.value in str(failure.value)
        assert event.value in str(failure.value)


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (Status.READY, SessionCapabilities(True, False, False, False)),
        (Status.RUNNING, SessionCapabilities(False, False, True, False)),
        (Status.WAITING_INPUT, SessionCapabilities(True, False, False, False)),
        (Status.COMPLETED, SessionCapabilities(False, False, False, True)),
        (Status.FAILED, SessionCapabilities(True, True, False, False)),
        (Status.CANCELLED, SessionCapabilities(True, True, False, False)),
    ],
)
def test_capabilities(status: Status, expected: SessionCapabilities) -> None:
    assert capabilities(status) == expected


def test_clarification_failure_cancel_retry_and_commit_sequence() -> None:
    status = Status.READY
    steps = [
        (Event.SUBMIT, Status.RUNNING),
        (Event.REQUEST_INPUT, Status.WAITING_INPUT),
        (Event.SUBMIT, Status.RUNNING),
        (Event.FAIL, Status.FAILED),
        (Event.RETRY, Status.RUNNING),
        (Event.CANCEL, Status.CANCELLED),
        (Event.RETRY, Status.RUNNING),
        (Event.TODO_COMMITTED, Status.COMPLETED),
    ]
    for event, expected in steps:
        status = next_status(status, event)
        assert status is expected
    for event in Event:
        with pytest.raises(InvalidSessionTransition):
            next_status(status, event)


def test_late_commit_after_cancel_and_duplicate_submit_are_rejected() -> None:
    status = next_status(Status.READY, Event.SUBMIT)
    with pytest.raises(InvalidSessionTransition):
        next_status(status, Event.SUBMIT)
    status = next_status(status, Event.CANCEL)
    with pytest.raises(InvalidSessionTransition):
        next_status(status, Event.TODO_COMMITTED)
    assert status is Status.CANCELLED


def test_capabilities_are_immutable() -> None:
    result = capabilities(Status.COMPLETED)
    with pytest.raises(FrozenInstanceError):
        result.can_submit = True  # type: ignore[misc]


@pytest.mark.parametrize("status", ["ready", "unknown", None, 1])
def test_unparsed_status_is_rejected(status: object) -> None:
    with pytest.raises(TypeError):
        next_status(status, Event.SUBMIT)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        capabilities(status)  # type: ignore[arg-type]


@pytest.mark.parametrize("event", ["submit", "unknown", None, 1])
def test_unparsed_event_is_rejected(event: object) -> None:
    with pytest.raises(TypeError):
        next_status(Status.READY, event)  # type: ignore[arg-type]
