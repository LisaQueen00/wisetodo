import asyncio
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from wisetodo.agent.errors import map_agent_error
from wisetodo.agent.generation import InvalidAgentOutputError, UnusableModelResponseError
from wisetodo.agent.results import AgentTodoInput
from wisetodo.agent.tool_calls import InvalidToolCallsError
from wisetodo.database import initialize_database
from wisetodo.errors import ErrorCode
from wisetodo.ipc.messages import IpcRequest
from wisetodo.ipc.sessions import SessionRequestError, dispatch_session
from wisetodo.model.provider import ModelCapabilityError, ModelRequestError
from wisetodo.sessions.service import SessionService
from wisetodo.sessions.tables import MessageRecord, SessionRecord


@pytest.mark.parametrize(
    "error,stage,code,retryable",
    [
        (ModelCapabilityError(), "runtime", ErrorCode.MODEL_CAPABILITY_INSUFFICIENT, False),
        (ModelRequestError(), "runtime", ErrorCode.MODEL_REQUEST_FAILED, True),
        (UnusableModelResponseError(), "runtime", ErrorCode.MODEL_REQUEST_FAILED, False),
        (InvalidAgentOutputError(), "model", ErrorCode.INVALID_AGENT_OUTPUT, False),
        (InvalidToolCallsError(), "model", ErrorCode.TOOL_ARGUMENT_INVALID, False),
        (asyncio.CancelledError(), "runtime", ErrorCode.RUN_CANCELLED, False),
        (SQLAlchemyError("secret SQL"), "todo", ErrorCode.TODO_SAVE_FAILED, True),
        (LookupError("private ID"), "todo", ErrorCode.TODO_NOT_FOUND, False),
        (ValueError("private data"), "todo", ErrorCode.TODO_VALIDATION_FAILED, False),
        (ValueError("unsupported model secret"), "runtime", ErrorCode.INTERNAL_ERROR, False),
        (SQLAlchemyError("secret SQL"), "runtime", ErrorCode.INTERNAL_ERROR, False),
    ],
)
def test_safe_mapping(error, stage, code, retryable) -> None:
    mapped = map_agent_error(error, stage=stage)
    assert mapped.code == code
    assert mapped.retryable is retryable
    assert mapped.details is None
    serialized = mapped.model_dump_json()
    assert "secret" not in serialized and "private" not in serialized
    assert mapped.user_message


def test_validation_is_classified_by_trusted_stage() -> None:
    with pytest.raises(ValidationError) as caught:
        AgentTodoInput.model_validate({"topic": "private", "items": []})
    assert map_agent_error(caught.value, stage="model").code == ErrorCode.INVALID_AGENT_OUTPUT
    assert map_agent_error(caught.value, stage="todo").code == ErrorCode.TODO_VALIDATION_FAILED
    assert map_agent_error(caught.value).code == ErrorCode.INTERNAL_ERROR
    with pytest.raises(ValueError):
        map_agent_error(caught.value, stage="bad")


@pytest.mark.parametrize(
    "failure,code",
    [
        (ModelCapabilityError(), ErrorCode.MODEL_CAPABILITY_INSUFFICIENT),
        (ModelRequestError(), ErrorCode.MODEL_REQUEST_FAILED),
        (InvalidAgentOutputError(), ErrorCode.INVALID_AGENT_OUTPUT),
        (UnusableModelResponseError(), ErrorCode.MODEL_REQUEST_FAILED),
        (InvalidToolCallsError(), ErrorCode.TOOL_ARGUMENT_INVALID),
        (RuntimeError("secret failure"), ErrorCode.SESSION_RETRY_FAILED),
    ],
)
async def test_real_retry_preserves_model_classification_and_history(
    tmp_path: Path, failure, code
) -> None:
    database = initialize_database(tmp_path / "errors.db")
    try:
        with database.sessions.begin() as session:
            record = SessionRecord(status="failed", label="test")
            record.messages = [
                MessageRecord(position=0, role="user", content="阅读", attachments=[])
            ]
            session.add(record)
            session.flush()
            session_id = record.id

        async def executor(request):
            raise failure

        service = SessionService(database.sessions, retry_executor=executor)
        before = service.get(session_id)
        with pytest.raises(SessionRequestError) as caught:
            await dispatch_session(
                IpcRequest(
                    requestId="test",
                    method="user.sessions.retry",
                    params={"session_id": session_id},
                ),
                service,
            )
        assert caught.value.error.code == code
        assert "secret" not in caught.value.error.model_dump_json()
        after = service.get(session_id)
        assert after.status == "failed"
        assert after.messages == before.messages
    finally:
        database.dispose()


async def test_retry_cancellation_stays_cancelled_not_failure(tmp_path: Path) -> None:
    database = initialize_database(tmp_path / "cancel.db")
    try:
        with database.sessions.begin() as session:
            record = SessionRecord(status="failed")
            record.messages = [
                MessageRecord(position=0, role="user", content="阅读", attachments=[])
            ]
            session.add(record)
            session.flush()
            session_id = record.id

        async def executor(request):
            raise asyncio.CancelledError

        service = SessionService(database.sessions, retry_executor=executor)
        with pytest.raises(asyncio.CancelledError):
            await dispatch_session(
                IpcRequest(
                    requestId="test",
                    method="user.sessions.retry",
                    params={"session_id": session_id},
                ),
                service,
            )
        assert service.get(session_id).status == "cancelled"
    finally:
        database.dispose()
