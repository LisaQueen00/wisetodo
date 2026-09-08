from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import inspect, text

from wisetodo.database import initialize_database
from wisetodo.todos import TodoInput, TodoService


def run_sidecar(
    database_path: Path, requests: list[dict[str, Any]], working_dir: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "wisetodo.main", "--database", str(database_path)],
        input="".join(json.dumps(request, ensure_ascii=False) + "\n" for request in requests),
        text=True,
        encoding="utf-8",
        capture_output=True,
        cwd=working_dir,
        timeout=20,
        check=False,
    )


def request(request_id: str, method: str) -> dict[str, Any]:
    return {"type": "request", "requestId": request_id, "method": method, "params": {}}


def test_file_only_message_survives_sidecar_restart(tmp_path: Path) -> None:
    from uuid import uuid4

    file = tmp_path / "阅读笔记.txt"
    file.write_text("Original file", encoding="utf-8")
    path = tmp_path / "files.db"
    created = json.loads(
        run_sidecar(path, [request("create", "user.sessions.create")], tmp_path).stdout
    )["result"]["session"]
    send = request("send", "user.sessions.send")
    send["params"] = {
        "session_id": created["id"],
        "message": {"message_id": str(uuid4()), "content": "", "files": [str(file)]},
    }
    saved = run_sidecar(path, [send], tmp_path)
    assert saved.returncode == 0, saved.stderr
    result = json.loads(saved.stdout)["result"]
    assert result["session"]["messages"][0]["attachments"] == [str(file)]
    read = request("read", "sessions.get")
    read["params"] = {"session_id": created["id"]}
    assert json.loads(run_sidecar(path, [read], tmp_path).stdout)["result"] == result
    assert file.read_text(encoding="utf-8") == "Original file"


def test_chat_send_persists_across_restart_and_deduplicates(tmp_path: Path) -> None:
    from uuid import uuid4

    path = tmp_path / "chat.db"
    created_process = run_sidecar(path, [request("create", "user.sessions.create")], tmp_path)
    created = json.loads(created_process.stdout)["result"]["session"]
    send = request("send", "user.sessions.send")
    send["params"] = {
        "session_id": created["id"],
        "message": {
            "message_id": str(uuid4()),
            "content": "第一行\n第二行 <script>",
            "urls": ["https://example.com/book"],
        },
    }
    result = run_sidecar(path, [send, send], tmp_path)
    assert result.returncode == 0, result.stderr
    first, second = map(json.loads, result.stdout.splitlines())
    assert first["result"] == second["result"]
    assert len(first["result"]["session"]["messages"]) == 1
    assert first["result"]["session"]["messages"][0]["attachments"] == ["https://example.com/book"]
    read = request("read", "sessions.get")
    read["params"] = {"session_id": created["id"]}
    restarted = run_sidecar(path, [read], tmp_path)
    assert json.loads(restarted.stdout)["result"] == first["result"]


def test_retry_without_executor_preserves_failed_session(tmp_path: Path) -> None:
    from wisetodo.sessions.service import SessionService
    from wisetodo.sessions.tables import MessageRecord, SessionRecord

    path = tmp_path / "retry-ipc.db"
    database = initialize_database(path)
    try:
        service = SessionService(database.sessions)
        created = service.create()
        with database.sessions.begin() as session:
            record = session.get_one(SessionRecord, created.id)
            record.status = "failed"
            record.messages = [MessageRecord(position=0, role="user", content="Original input")]
        original = service.get(created.id)
        assert original is not None
    finally:
        database.dispose()
    retry = request("retry", "user.sessions.retry")
    retry["params"] = {"session_id": created.id}
    read = request("read", "sessions.get")
    read["params"] = retry["params"]
    result = run_sidecar(path, [retry, read], tmp_path)
    assert result.returncode == 0, result.stderr
    failure, loaded = map(json.loads, result.stdout.splitlines())
    assert failure["error"]["code"] == "SESSION_RETRY_UNAVAILABLE"
    assert loaded["result"]["session"] == original.model_dump(mode="json")


def test_session_crud_over_real_sidecar(tmp_path: Path) -> None:
    path = tmp_path / "session-ipc.db"
    create = request("create", "user.sessions.create")
    create["params"] = {"label": "阅读计划"}
    result = run_sidecar(path, [create], tmp_path)
    assert result.returncode == 0, result.stderr
    created = json.loads(result.stdout)["result"]["session"]
    read = request("read", "sessions.get")
    read["params"] = {"session_id": created["id"]}
    delete = request("delete", "user.sessions.delete")
    delete["params"] = read["params"]
    invalid = request("invalid", "user.sessions.create")
    invalid["params"] = {"label": 42}
    result = run_sidecar(
        path,
        [
            request("list", "sessions.list"),
            read,
            invalid,
            delete,
            read,
            request("todos", "todos.list"),
        ],
        tmp_path,
    )
    listed, loaded, failed, deleted, missing, todos = map(json.loads, result.stdout.splitlines())
    assert listed["result"]["sessions"][0]["id"] == created["id"]
    assert "messages" not in listed["result"]["sessions"][0]
    assert loaded["result"]["session"] == created
    assert failed["error"]["code"] == "SESSION_VALIDATION_FAILED"
    assert deleted["result"] == {"deleted": True}
    assert missing["error"]["code"] == "SESSION_NOT_FOUND"
    assert todos["result"] == {"todos": []}
    restarted = run_sidecar(path, [request("list", "sessions.list")], tmp_path)
    assert json.loads(restarted.stdout)["result"] == {"sessions": []}


def test_runtime_migrates_nested_database_idempotently(tmp_path: Path) -> None:
    database_path = tmp_path / "用户 100%" / "data" / "wisetodo.db"
    database = initialize_database(database_path)
    try:
        todo = TodoService(database.sessions).create(
            TodoInput(topic="阅读书籍", items=["第一章：起步", "第二章：实践"])
        )
        assert set(inspect(database.engine).get_table_names()) == {
            "alembic_version",
            "todos",
            "todo_items",
            "sessions",
            "messages",
            "tool_events",
        }
    finally:
        database.dispose()

    reopened = initialize_database(database_path)
    try:
        assert TodoService(reopened.sessions).get(todo.id) == todo
        with reopened.engine.connect() as connection:
            assert (
                connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                == "0003_create_session_tables"
            )
    finally:
        reopened.dispose()


def test_runtime_rejects_relative_database_paths() -> None:
    with pytest.raises(ValueError, match="absolute"):
        initialize_database(Path("relative.db"))


def test_sidecar_migrates_before_serving_and_returns_empty_list(tmp_path: Path) -> None:
    database_path = tmp_path / "new" / "runtime.db"
    result = run_sidecar(database_path, [request("first", "todos.list")], tmp_path)

    assert result.returncode == 0, result.stderr
    assert database_path.is_file()
    assert json.loads(result.stdout) == {
        "type": "response",
        "requestId": "first",
        "result": {"todos": []},
    }


def test_sidecar_reads_persisted_todos_across_restarts(tmp_path: Path) -> None:
    database_path = tmp_path / "用户 数据" / "runtime.db"
    database = initialize_database(database_path)
    try:
        todo = TodoService(database.sessions).create(
            TodoInput(topic="学习项目 📝", priority=1, items=["安装依赖", "启动项目"])
        )
    finally:
        database.dispose()

    for _ in range(2):
        result = run_sidecar(
            database_path,
            [request("检查连接", "health"), request("读取待办", "todos.list")],
            tmp_path,
        )
        assert result.returncode == 0, result.stderr
        responses = [json.loads(line) for line in result.stdout.splitlines()]
        assert responses == [
            {"type": "response", "requestId": "检查连接", "result": {"status": "ok"}},
            {
                "type": "response",
                "requestId": "读取待办",
                "result": {"todos": [todo.model_dump(mode="json")]},
            },
        ]


def test_sidecar_recovers_after_invalid_and_unknown_requests(tmp_path: Path) -> None:
    result = run_sidecar(
        tmp_path / "runtime.db",
        [
            {"type": "request", "requestId": "invalid", "method": 123},
            request("unknown", "todos.delete"),
            request("next", "health"),
            request("list", "todos.list"),
        ],
        tmp_path,
    )

    assert result.returncode == 0, result.stderr
    invalid, unknown, health, todos = [json.loads(line) for line in result.stdout.splitlines()]
    assert invalid["requestId"] == "invalid"
    assert invalid["error"]["code"] == "IPC_INVALID_REQUEST"
    assert unknown["requestId"] == "unknown"
    assert unknown["error"]["code"] == "IPC_METHOD_NOT_FOUND"
    assert set(unknown["error"]) == {"code", "message", "user_message", "retryable"}
    assert health == {"type": "response", "requestId": "next", "result": {"status": "ok"}}
    assert todos["result"] == {"todos": []}


def test_sidecar_read_failure_does_not_stop_server_or_leak_sql(tmp_path: Path) -> None:
    database_path = tmp_path / "runtime.db"
    database = initialize_database(database_path)
    try:
        TodoService(database.sessions).create(TodoInput(topic="项目", items=["安装", "运行"]))
        with database.engine.begin() as connection:
            connection.execute(text("DROP TABLE todo_items"))
    finally:
        database.dispose()

    result = run_sidecar(
        database_path, [request("failed", "todos.list"), request("next", "health")], tmp_path
    )

    assert result.returncode == 0, result.stderr
    failed, health = [json.loads(line) for line in result.stdout.splitlines()]
    assert failed == {
        "type": "response",
        "requestId": "failed",
        "error": {
            "code": "TODO_READ_FAILED",
            "message": "Could not read todos",
            "user_message": "无法读取待办，请重试。",
            "retryable": True,
        },
    }
    assert health["result"] == {"status": "ok"}
    assert "SELECT" not in result.stdout
    assert str(database_path) not in result.stdout


def test_sidecar_initialization_failure_exits_without_protocol_output(tmp_path: Path) -> None:
    result = run_sidecar(tmp_path, [request("unserved", "health")], tmp_path)

    assert result.returncode == 1
    assert result.stdout == ""
    assert "database initialization failed" in result.stderr
    assert str(tmp_path) not in result.stderr


def test_sidecar_sorting_survives_restart_and_validates_targets(tmp_path: Path) -> None:
    path = tmp_path / "order.db"
    database = initialize_database(path)
    try:
        service = TodoService(database.sessions)
        for name in "AB":
            service.create(TodoInput(topic=name, items=["One", "Two"]))
        a, b = service.list()
    finally:
        database.dispose()
    move = request("move", "user.todos.move")
    move["params"] = {"todo_id": b.id, "target_id": a.id}
    invalid = request("invalid", "user.todos.move")
    invalid["params"] = {"todo_id": b.id, "target_id": 123}
    missing = request("missing", "user.todos.move")
    missing["params"] = {"todo_id": b.id, "target_id": "missing"}
    result = run_sidecar(path, [move, invalid, missing], tmp_path)
    assert result.returncode == 0, result.stderr
    moved, invalid_response, missing_response = map(json.loads, result.stdout.splitlines())
    assert [todo["id"] for todo in moved["result"]["todos"]] == [b.id, a.id]
    assert invalid_response["error"]["code"] == "TODO_VALIDATION_FAILED"
    assert missing_response["error"]["code"] == "TODO_NOT_FOUND"
    restarted = run_sidecar(path, [request("read", "todos.list")], tmp_path)
    assert json.loads(restarted.stdout)["result"] == moved["result"]


def test_sidecar_completion_persists_and_rejects_non_boolean_values(tmp_path: Path) -> None:
    path = tmp_path / "completion.db"
    database = initialize_database(path)
    try:
        todo = TodoService(database.sessions).create(TodoInput(topic="Book", items=["One", "Two"]))
    finally:
        database.dispose()
    requests = []
    for index, completed in enumerate([True, "false", 0, None, False, True]):
        change = request(str(index), "user.todos.set_item_completed")
        change["params"] = {"todo_id": todo.id, "item_id": todo.items[0].id, "completed": completed}
        requests.append(change)
    result = run_sidecar(path, requests, tmp_path)
    assert result.returncode == 0, result.stderr
    responses = list(map(json.loads, result.stdout.splitlines()))
    assert responses[0]["result"]["todo"]["progress"] == 0.5
    for response in responses[1:4]:
        assert response["error"]["code"] == "TODO_VALIDATION_FAILED"
    assert responses[4]["result"]["todo"]["progress"] == 0
    restarted = run_sidecar(path, [request("read", "todos.list")], tmp_path)
    assert json.loads(restarted.stdout)["result"]["todos"] == [responses[5]["result"]["todo"]]


def test_sidecar_manual_create_update_delete_and_invalid_update(tmp_path: Path) -> None:
    path = tmp_path / "writes.db"
    create = request("create", "user.todos.create")
    create["params"] = {"todo": {"topic": "阅读", "items": ["第一章", "第二章"]}}
    created_process = run_sidecar(path, [create], tmp_path)
    assert created_process.returncode == 0
    todo = json.loads(created_process.stdout)["result"]["todo"]
    update = request("update", "user.todos.update")
    update["params"] = {
        "todo_id": todo["id"],
        "todo": {
            "topic": "阅读新版",
            "priority": 1,
            "items": [{"id": item["id"], "topic": item["topic"]} for item in todo["items"]],
        },
    }
    invalid = request("invalid", "user.todos.update")
    invalid["params"] = {"todo_id": todo["id"], "todo": {"topic": "Invalid", "items": []}}
    delete = request("delete", "user.todos.delete")
    delete["params"] = {"todo_id": todo["id"]}
    result = run_sidecar(
        path,
        [update, invalid, request("read", "todos.list"), delete, request("empty", "todos.list")],
        tmp_path,
    )
    assert result.returncode == 0
    updated, failed, read, deleted, empty = map(json.loads, result.stdout.splitlines())
    assert updated["result"]["todo"]["topic"] == "阅读新版"
    assert updated["result"]["todo"]["items"] == todo["items"]
    assert failed["error"]["code"] == "TODO_VALIDATION_FAILED"
    assert read["result"]["todos"] == [updated["result"]["todo"]]
    assert deleted["result"] == {"deleted": True}
    assert empty["result"] == {"todos": []}
    restarted = run_sidecar(path, [request("persisted", "todos.list")], tmp_path)
    assert json.loads(restarted.stdout)["result"] == {"todos": []}
