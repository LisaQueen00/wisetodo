"""SDK-independent, text-only contracts for the first compatible Provider."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, StrictStr, model_validator

Name = Annotated[StrictStr, Field(min_length=1)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class ToolCall(Contract):
    id: Name
    name: Name
    arguments: StrictStr  # Untrusted JSON text, validated by the later Tool layer.


class ModelMessage(Contract):
    role: Literal["system", "user", "assistant", "tool"]
    content: StrictStr = ""
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: Name | None = None

    @model_validator(mode="after")
    def validate_role(self) -> "ModelMessage":
        if self.tool_calls and self.role != "assistant":
            raise ValueError("Only assistant messages may contain tool calls")
        if (self.role == "tool") != (self.tool_call_id is not None):
            raise ValueError("Only tool messages require a tool call ID")
        if len({call.id for call in self.tool_calls}) != len(self.tool_calls):
            raise ValueError("Duplicate tool call IDs")
        return self


class ToolDefinition(Contract):
    name: Annotated[StrictStr, Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")]
    description: StrictStr
    parameters: dict[str, JsonValue]


class OutputSchema(Contract):
    name: Annotated[StrictStr, Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")]
    json_schema: dict[str, JsonValue]


class ModelRequest(Contract):
    mode: Literal["native", "prompt_compat"] = "native"
    messages: Annotated[tuple[ModelMessage, ...], Field(min_length=1)]
    tools: tuple[ToolDefinition, ...] = ()
    output_schema: OutputSchema | None = None

    @model_validator(mode="after")
    def validate_tools(self) -> "ModelRequest":
        if self.mode == "prompt_compat" and (
            self.output_schema is not None
            or any(message.tool_calls or message.role == "tool" for message in self.messages)
        ):
            raise ValueError("Compatibility requests use text messages and prompt schemas only")
        if len({tool.name for tool in self.tools}) != len(self.tools):
            raise ValueError("Duplicate tool definitions")
        pending: set[str] = set()
        seen: set[str] = set()
        for message in self.messages:
            if message.role == "tool":
                if message.tool_call_id not in pending:
                    raise ValueError("Tool result must match a pending call")
                pending.remove(message.tool_call_id)
            else:
                if pending:
                    raise ValueError("Missing tool results before next message")
                for call in message.tool_calls:
                    if call.id in seen:
                        raise ValueError("Repeated tool call ID")
                    seen.add(call.id)
                    pending.add(call.id)
        if pending:
            raise ValueError("Tool results must be supplied before requesting the model")
        return self


class ModelResponse(Contract):
    content: StrictStr = ""
    tool_calls: tuple[ToolCall, ...] = ()
    finish_reason: Literal["stop", "tool_calls", "length", "content_filter", "unknown"]
    refusal: StrictStr | None = None

    @model_validator(mode="after")
    def unique_calls(self) -> "ModelResponse":
        if len({call.id for call in self.tool_calls}) != len(self.tool_calls):
            raise ValueError("Duplicate response tool call IDs")
        return self
