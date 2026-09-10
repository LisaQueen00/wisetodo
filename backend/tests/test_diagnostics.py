import json
import logging
import subprocess
import sys

import pytest

from wisetodo import diagnostics
from wisetodo.diagnostics import Event, LocalLog
from wisetodo.errors import ErrorCode, WiseTodoError
from wisetodo.ipc.server import _handle_invalid_request, _write_failure


@pytest.fixture(autouse=True)
def stop_log():
    diagnostics.stop()
    yield
    diagnostics.stop()


def test_allowlist_drops_sensitive_fields_and_preserves_stdout_protocol(tmp_path, capsys):
    assert diagnostics.start(tmp_path)
    error = WiseTodoError(
        code=ErrorCode.MODEL_REQUEST_FAILED,
        retryable=True,
        message="SECRET api-key",
        user_message="Safe user text",
        details={"path": "PRIVATE.pdf", "url": "https://private", "prompt": "CHAT"},
    )
    _write_failure("PRIVATE_REQUEST_ID", error)
    _handle_invalid_request("SECRET malformed input")
    diagnostics.record("SECRET")  # type: ignore[arg-type]
    diagnostics.record(Event.IPC_FAILED, "SECRET")  # type: ignore[arg-type]
    logging.getLogger("httpx").warning("PRIVATE_HTTP_BODY")
    diagnostics.stop()
    text = (tmp_path / "wisetodo.log").read_text(encoding="utf-8")
    assert all(secret not in text for secret in ["SECRET", "PRIVATE", "CHAT", "Safe user text"])
    rows = [json.loads(line) for line in text.splitlines()]
    assert rows[0]["code"] == "MODEL_REQUEST_FAILED"
    assert rows[1]["event"] == "ipc_rejected"
    assert all(set(row) <= {"time", "event", "code"} for row in rows)
    # Protocol stdout remains separate from the diagnostic file.
    assert json.loads(capsys.readouterr().out)["requestId"] == "PRIVATE_REQUEST_ID"


def test_rotation_keeps_only_three_backups(tmp_path):
    log = LocalLog(tmp_path, max_bytes=300)
    for _ in range(100):
        log.write(Event.IPC_SUCCEEDED)
    log.close()
    files = sorted(p.name for p in tmp_path.iterdir())
    assert files == ["wisetodo.log", "wisetodo.log.1", "wisetodo.log.2", "wisetodo.log.3"]
    assert all(p.stat().st_size <= 300 for p in tmp_path.iterdir())


def test_write_failure_never_prints_exception_or_fails_operation(tmp_path, monkeypatch, capsys):
    log = LocalLog(tmp_path)

    def fail(*args):
        raise OSError("SECRET disk failure")

    monkeypatch.setattr(log._handler, "doRollover", fail)
    monkeypatch.setattr(log._handler, "shouldRollover", lambda record: True)
    log.write(Event.IPC_FAILED, ErrorCode.TODO_SAVE_FAILED)
    log.close()
    assert not capsys.readouterr().err


def test_unavailable_directory_disables_logging(tmp_path):
    path = tmp_path / "not-directory"
    path.write_text("existing", encoding="utf-8")
    assert not diagnostics.start(path)
    diagnostics.record(Event.BACKEND_STARTED)
    assert path.read_text() == "existing"


def test_reconfigure_closes_old_sink(tmp_path):
    first, second = tmp_path / "a", tmp_path / "b"
    assert diagnostics.start(first)
    diagnostics.record(Event.BACKEND_STARTED)
    assert diagnostics.start(second)
    diagnostics.record(Event.BACKEND_STOPPED)
    diagnostics.stop()
    assert "backend_stopped" not in (first / "wisetodo.log").read_text()
    assert "backend_stopped" in (second / "wisetodo.log").read_text()


def test_real_sidecar_creates_only_safe_lifecycle_and_ipc_records(tmp_path):
    requests = [
        {
            "type": "request",
            "requestId": "SECRET-ID",
            "method": "unknown-SECRET",
            "params": {"api_key": "SECRET-KEY"},
        },
        {"type": "request", "requestId": "list", "method": "todos.list", "params": {}},
    ]
    result = subprocess.run(
        [sys.executable, "-m", "wisetodo.main", "--database", str(tmp_path / "test.db")],
        input="\n".join(json.dumps(r) for r in requests) + "\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    responses = [json.loads(line) for line in result.stdout.splitlines()]
    assert responses[0]["error"]["code"] == "IPC_METHOD_NOT_FOUND"
    assert responses[1]["result"] == {"todos": []}
    text = (tmp_path / "logs/wisetodo.log").read_text(encoding="utf-8")
    assert "SECRET" not in text
    assert [json.loads(line)["event"] for line in text.splitlines()] == [
        "backend_started",
        "ipc_failed",
        "ipc_succeeded",
        "backend_stopped",
    ]
