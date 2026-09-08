from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from wisetodo.agent.generation import ResultGenerator
from wisetodo.agent.state import AgentState


def prepare_context(state: AgentState) -> AgentState:
    """Prepare deterministic runtime context before the first model call."""
    return {"validation_attempts": state.get("validation_attempts", 0)}


def build_agent_graph(generator: ResultGenerator | None = None):  # type: ignore[no-untyped-def]
    """Build the bounded no-tool graph; optional generator keeps scaffold tests usable."""
    builder = StateGraph(AgentState)
    builder.add_node("prepare_context", prepare_context)
    builder.add_edge(START, "prepare_context")
    if generator is not None:

        async def generate(state: AgentState) -> AgentState:
            return {"generation": await generator.generate(state["model_request"])}

        builder.add_node("generate", generate)
        builder.add_edge("prepare_context", "generate")
        builder.add_edge("generate", END)
    else:
        builder.add_edge("prepare_context", END)
    return builder.compile()
