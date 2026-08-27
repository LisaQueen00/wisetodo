from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    session_id: str
    user_message: str
    attachments: list[dict[str, Any]]
    current_todo: dict[str, Any] | None
    candidate_skills: list[dict[str, Any]]
    available_tools: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    agent_result: dict[str, Any] | None
    validation_attempts: int
