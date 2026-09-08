import json

import pytest
from pydantic import ValidationError

from wisetodo.agent.results import (
    AGENT_RESULT_ADAPTER,
    AgentTodoChanges,
    AgentTodoInput,
    CreateOperation,
    TodoOperationResult,
    UpdateOperation,
    agent_result_schema,
    parse_agent_result,
)
from wisetodo.todos.models import TodoChanges, TodoInput


def operation(action: str, **fields: object) -> dict:
    return {"type": "todo_operation", "operation": {"action": action, **fields}}


def test_create_normalizes_and_reuses_service_input() -> None:
    result = parse_agent_result(
        json.dumps(
            operation("create", todo={"topic": " 阅读书籍 ", "items": [" 第一章 ", "第二章"]})
        )
    )
    assert isinstance(result, TodoOperationResult)
    assert isinstance(result.operation, CreateOperation)
    todo = result.operation.todo
    assert isinstance(todo, TodoInput)
    assert todo.model_dump() == {"topic": "阅读书籍", "priority": 0, "items": ["第一章", "第二章"]}
    assert parse_agent_result(result.model_dump_json(exclude_unset=True)) == result


@pytest.mark.parametrize(
    "changes",
    [
        {"topic": "新主题"},
        {"priority": 0},
        {"priority": 1},
        {"items": ["第一章", "第二章"]},
        {"topic": "新主题", "priority": 1, "items": ["配置环境", "运行测试"]},
    ],
)
def test_partial_update_roundtrip(changes: dict) -> None:
    result = AGENT_RESULT_ADAPTER.validate_python(
        operation("update", todoId=" id ", changes=changes)
    )
    assert isinstance(result, TodoOperationResult)
    assert isinstance(result.operation, UpdateOperation)
    assert result.operation.todoId == "id"
    assert isinstance(result.operation.changes, TodoChanges)
    assert result.operation.changes.model_dump(exclude_unset=True) == changes
    assert parse_agent_result(result.model_dump_json(exclude_unset=True)) == result


@pytest.mark.parametrize("value", [True, False, 1.0, "1", 2, -1, None])
def test_priority_rejects_coercion(value: object) -> None:
    with pytest.raises(ValidationError):
        AgentTodoInput.model_validate({"topic": "x", "priority": value, "items": ["a", "b"]})
    with pytest.raises(ValidationError):
        AgentTodoChanges.model_validate({"priority": value})


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"topic": None},
        {"items": None},
        {"topic": " "},
        {"items": []},
        {"items": ["a"]},
        {"items": ["a", " "]},
        {"completed": True},
        {"progress": 1},
        {"position": 1},
        {"topic": "x", "items": None},
    ],
)
def test_invalid_changes(changes: dict) -> None:
    with pytest.raises(ValidationError):
        AGENT_RESULT_ADAPTER.validate_python(operation("update", todoId="id", changes=changes))


@pytest.mark.parametrize(
    "todo",
    [
        {"topic": " ", "items": ["a", "b"]},
        {"topic": 1, "items": ["a", "b"]},
        {"topic": "x", "items": ["a"]},
        {"topic": "x", "items": ["a", 2]},
        {"topic": "x", "items": [{"topic": "a", "completed": False}, {"topic": "b"}]},
        {"topic": "x", "items": ["a", "b"], "id": "injected"},
    ],
)
def test_invalid_create(todo: dict) -> None:
    with pytest.raises(ValidationError):
        AGENT_RESULT_ADAPTER.validate_python(operation("create", todo=todo))


@pytest.mark.parametrize(
    "result",
    [
        {"type": "clarification", "question": "先阅读哪一本？"},
        {
            "type": "tool_calls",
            "calls": [
                {
                    "callId": "a",
                    "tool": "read",
                    "arguments": {"pages": [1, 2], "options": {"x": True}},
                },
                {"callId": "b", "tool": "read", "arguments": {}},
            ],
        },
    ],
)
def test_other_result_roundtrips(result: dict) -> None:
    parsed = parse_agent_result(json.dumps(result))
    assert parsed.model_dump() == result


@pytest.mark.parametrize(
    "result",
    [
        [],
        {},
        {"type": "delete"},
        operation("delete", todoId="id"),
        operation("update", todoId=" ", changes={"priority": 1}),
        {"type": "clarification", "question": " "},
        {"type": "clarification", "question": "x", "operation": {}},
        {"type": "tool_calls", "calls": []},
        {"type": "tool_calls", "calls": [{"callId": "a", "tool": "read", "arguments": "{}"}]},
        {"type": "tool_calls", "calls": [{"callId": "a", "tool": " ", "arguments": {}}]},
        {
            "type": "tool_calls",
            "calls": [
                {"callId": " a ", "tool": "read", "arguments": {}},
                {"callId": "a", "tool": "read", "arguments": {}},
            ],
        },
    ],
)
def test_invalid_result(result: object) -> None:
    with pytest.raises(ValidationError):
        parse_agent_result(json.dumps(result))


@pytest.mark.parametrize("text", ["not json", "```json\n{}\n```", "{} {}", '{"type":'])
def test_no_prose_fences_or_partial_json(text: str) -> None:
    with pytest.raises(ValidationError):
        parse_agent_result(text)


def test_schema_is_serializable_discriminated_and_closed() -> None:
    schema = json.loads(json.dumps(agent_result_schema()))
    assert schema["discriminator"]["propertyName"] == "type"
    assert len(schema["oneOf"]) == 3
    for definition in schema["$defs"].values():
        if definition.get("type") == "object":
            assert definition["additionalProperties"] is False
    assert schema["$defs"]["AgentTodoInput"]["properties"]["items"]["minItems"] == 2
    changes = schema["$defs"]["AgentTodoChanges"]
    assert changes["minProperties"] == 1
    assert "required" not in changes
    assert changes["properties"]["topic"]["type"] == "string"
    assert "default" not in changes["properties"]["topic"]
