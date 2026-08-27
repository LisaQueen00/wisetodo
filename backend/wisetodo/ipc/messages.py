from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class IpcRequest(BaseModel):
    type: Literal["request"] = "request"
    request_id: str = Field(alias="requestId")
    method: str
    params: dict[str, Any] = Field(default_factory=dict)


class IpcCancel(BaseModel):
    type: Literal["cancel"] = "cancel"
    request_id: str = Field(alias="requestId")


class IpcResponse(BaseModel):
    type: Literal["response"] = "response"
    request_id: str = Field(alias="requestId")
    result: dict[str, Any]

    model_config = {"populate_by_name": True}
