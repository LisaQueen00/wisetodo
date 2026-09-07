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
        }
    finally:
        database.dispose()

    reopened = initialize_database(database_path)
    try:
        assert TodoService(reopened.sessions).get(todo.id) == todo
        with reopened.engine.connect() as connection:
            assert (
                connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                == "0002_create_todo_tables"
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
