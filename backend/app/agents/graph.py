"""LangGraph agent graph builder.

Assembles the multi-agent system as a LangGraph StateGraph with:
- Supervisor as the entry node
- Specialist agents (RAG, SQL, Tool, Memory) as worker nodes
- Conditional routing based on supervisor decisions
- Error handling with graceful degradation

The compiled graph is the main entry point for processing user messages.

Usage::

    from app.agents.graph import get_agent_graph

    graph = get_agent_graph()
    result = await graph.ainvoke(initial_state)
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from app.agents.memory_agent import memory_node
from app.agents.rag_agent import rag_node
from app.agents.sql_agent import sql_node
from app.agents.state import AgentState
from app.agents.supervisor import supervisor_node
from app.agents.tool_agent import tool_node
from app.core.logging import get_logger

logger = get_logger(__name__)


def _route_after_supervisor(state: AgentState) -> str:
    """Route to the next agent based on the supervisor's decision.

    Args:
        state: The current agent state with ``next_agent`` set.

    Returns:
        The name of the next node to execute, or END.
    """
    next_agent = state.get("next_agent", "direct")

    # Check for errors
    if state.get("error"):
        return END

    if next_agent == "rag":
        return "rag_agent"
    elif next_agent == "sql":
        return "sql_agent"
    elif next_agent == "tool":
        return "tool_agent"
    elif next_agent == "memory":
        return "memory_agent"
    elif next_agent in ("direct", "end"):
        return END
    else:
        logger.warning("Unknown routing target, ending", next_agent=next_agent)
        return END


def build_agent_graph() -> StateGraph:
    """Build the LangGraph multi-agent state graph.

    Graph structure::

        START → supervisor → [conditional routing]
                               ├─ rag_agent → END
                               ├─ sql_agent → END
                               ├─ tool_agent → END
                               ├─ memory_agent → END
                               └─ END (direct response)

    Returns:
        A compiled LangGraph ``StateGraph``.
    """
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("rag_agent", rag_node)
    graph.add_node("sql_agent", sql_node)
    graph.add_node("tool_agent", tool_node)
    graph.add_node("memory_agent", memory_node)

    # Set entry point
    graph.set_entry_point("supervisor")

    # Conditional routing from supervisor
    graph.add_conditional_edges(
        "supervisor",
        _route_after_supervisor,
        {
            "rag_agent": "rag_agent",
            "sql_agent": "sql_agent",
            "tool_agent": "tool_agent",
            "memory_agent": "memory_agent",
            END: END,
        },
    )

    # All specialist agents route to END after completion
    graph.add_edge("rag_agent", END)
    graph.add_edge("sql_agent", END)
    graph.add_edge("tool_agent", END)
    graph.add_edge("memory_agent", END)

    logger.info("Agent graph built successfully")
    return graph


# Compiled graph singleton
_compiled_graph: Any = None


def get_agent_graph():
    """Get or build the compiled agent graph.

    The graph is built once and cached for the process lifetime.

    Returns:
        The compiled LangGraph agent graph.
    """
    global _compiled_graph  # noqa: PLW0603
    if _compiled_graph is None:
        graph = build_agent_graph()
        _compiled_graph = graph.compile()
        logger.info("Agent graph compiled")
    return _compiled_graph
