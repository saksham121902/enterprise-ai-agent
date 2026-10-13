"""Agents package — LangGraph multi-agent orchestration system.

The agent system uses a supervisor pattern:

1. **Supervisor**: Analyzes user intent and routes to specialist agents
2. **RAG Agent**: Retrieves documents and answers questions from knowledge base
3. **SQL Agent**: Translates natural language to SQL and executes queries
4. **Tool Agent**: Selects and executes tools from the dynamic registry
5. **Memory Agent**: Retrieves and manages long-term user context

The agents are assembled into a LangGraph StateGraph that can be
invoked asynchronously.
"""

try:
    from app.agents.graph import build_agent_graph, get_agent_graph
    from app.agents.state import AgentState
    __all__ = ["AgentState", "build_agent_graph", "get_agent_graph"]
except ImportError:
    # Graceful fallback when LangGraph is not installed in the current environment
    build_agent_graph = None  # type: ignore[assignment]
    get_agent_graph = None  # type: ignore[assignment]
    AgentState = dict  # type: ignore[assignment,misc]
    __all__ = ["AgentState"]
