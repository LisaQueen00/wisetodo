from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from wisetodo.agent.state import AgentState


def prepare_context(state: AgentState) -> AgentState:
    """Prepare deterministic runtime context before the first model call."""
    return {"validation_attempts": state.get("validation_attempts", 0)}


def build_agent_graph():  # type: ignore[no-untyped-def]
    """Build the bounded WiseTodo graph; model and tool nodes are added next."""
    builder = StateGraph(AgentState)
    builder.add_node("prepare_context", prepare_context)
    builder.add_edge(START, "prepare_context")
    builder.add_edge("prepare_context", END)
    return builder.compile()
