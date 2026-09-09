import pytest
from test_agent_runtime import Scope, create_output, message

from wisetodo.agent.errors import map_agent_error
from wisetodo.agent.runtime import AgentRuntime
from wisetodo.database import initialize_database
from wisetodo.files.references import FileReferenceError
from wisetodo.ipc.messages import IpcRequest
from wisetodo.ipc.sessions import SessionRequestError, dispatch_session
from wisetodo.sessions.retry import RetryExecutionError
from wisetodo.sessions.service import SessionService
from wisetodo.todos import TodoService


@pytest.mark.parametrize("moved", [False, True])
async def test_missing_file_fails_before_model_and_restore_allows_retry(tmp_path, moved):
    path = tmp_path / "book.pdf"
    path.write_bytes(b"local test")
    db = initialize_database(tmp_path / "test.db")
    try:
        provider = Scope(create_output())
        sessions, todos = SessionService(db.sessions), TodoService(db.sessions)
        sessions.agent_executor = AgentRuntime(sessions, todos, provider)
        incoming = message().model_copy(update={"files": [str(path)]})
        session = sessions.create()
        sessions.send_message(session.id, incoming)
        if moved:
            path.rename(tmp_path / "moved.pdf")
        else:
            path.unlink()
        with pytest.raises(RetryExecutionError):
            await sessions.submit(session.id, message("请根据刚才的附件继续"))
        assert provider.opens == 0
        assert todos.list() == []
        assert sessions.get(session.id).status == "failed"
        path.write_bytes(b"restored")
        assert (await sessions.retry(session.id)).status == "completed"
        assert provider.opens == 1 and len(todos.list()) == 1
    finally:
        db.dispose()


@pytest.mark.parametrize("code", ["file_unavailable", "linked_file_path", "unknown_file_reference"])
def test_safe_actionable_error(code):
    error = map_agent_error(FileReferenceError(code), stage="todo")
    assert error.code == (
        "FILE_UNAVAILABLE" if code == "file_unavailable" else "FILE_REFERENCE_INVALID"
    )
    assert "重新附加" in error.user_message
    assert error.details is None


async def test_missing_file_on_send_has_specific_ipc_error_and_saves_nothing(tmp_path):
    db = initialize_database(tmp_path / "test.db")
    try:
        service = SessionService(db.sessions)
        session = service.create()
        incoming = message().model_copy(update={"files": [str(tmp_path / "missing.pdf")]})
        request = IpcRequest(
            requestId="test",
            method="user.sessions.send",
            params={
                "session_id": session.id,
                "message": incoming.model_dump(mode="json"),
            },
        )
        with pytest.raises(SessionRequestError) as caught:
            await dispatch_session(request, service)
        assert caught.value.error.code == "FILE_UNAVAILABLE"
        assert "恢复原路径" in caught.value.error.user_message
        assert str(tmp_path) not in caught.value.error.model_dump_json()
        assert service.get(session.id).messages == []
    finally:
        db.dispose()
