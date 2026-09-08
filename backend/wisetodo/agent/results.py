"""Validated Agent output, independent of model transport and execution."""

from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    TypeAdapter,
    field_validator,
    model_validator,
)

from wisetodo.todos.models import TodoChanges, TodoInput

Text = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1)]


def _changes_schema(schema: dict[str, Any]) -> None:
    schema["minProperties"] = 1
    for field in schema["properties"].values():
        field.pop("default", None)
        choices = field.pop("anyOf", [])
        for choice in choices:
            if choice.get("type") != "null":
                field.update(choice)


class ResultContract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)


class AgentTodoInput(TodoInput, ResultContract):
    @field_validator("priority", mode="before")
    @classmethod
    def integer_priority(cls, value: object) -> object:
        # Literal[0, 1] alone also accepts bool and equivalent floats.
        if type(value) is not int:
            raise ValueError("priority must be integer 0 or 1")
        return value


class AgentTodoChanges(TodoChanges, ResultContract):
    model_config = ConfigDict(json_schema_extra=_changes_schema)

    @field_validator("priority", mode="before")
    @classmethod
    def integer_priority(cls, value: object) -> object:
        return AgentTodoInput.integer_priority(value)

    @model_validator(mode="after")
    def nonempty_changes(self) -> "AgentTodoChanges":
        if not self.model_fields_set:
            raise ValueError("changes must contain at least one field")
        if any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError("Supplied change fields must not be null")
        return self


class CreateOperation(ResultContract):
    action: Literal["create"]
    todo: AgentTodoInput


class UpdateOperation(ResultContract):
    action: Literal["update"]
    todoId: Text
    changes: AgentTodoChanges


TodoOperation = Annotated[CreateOperation | UpdateOperation, Field(discriminator="action")]


class TodoOperationResult(ResultContract):
    type: Literal["todo_operation"]
    operation: TodoOperation


class AgentToolCall(ResultContract):
    callId: Text
    tool: Text
    arguments: dict[str, JsonValue]


class ToolCallsResult(ResultContract):
    type: Literal["tool_calls"]
    calls: list[AgentToolCall] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_call_ids(self) -> "ToolCallsResult":
        if len({call.callId for call in self.calls}) != len(self.calls):
            raise ValueError("Duplicate tool call IDs")
        return self


class ClarificationResult(ResultContract):
    type: Literal["clarification"]
    question: Text


AgentResult = Annotated[
    TodoOperationResult | ToolCallsResult | ClarificationResult, Field(discriminator="type")
]
AGENT_RESULT_ADAPTER: TypeAdapter[AgentResult] = TypeAdapter(AgentResult)


def parse_agent_result(content: str) -> AgentResult:
    """Accept one JSON result; propagate ValidationError for later repair handling."""
    return AGENT_RESULT_ADAPTER.validate_json(content)


def agent_result_schema() -> dict[str, object]:
    """Application schema, not a provider-specific strict-output schema."""
    return AGENT_RESULT_ADAPTER.json_schema()
