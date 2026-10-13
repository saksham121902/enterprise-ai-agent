"""Agent state definitions for the LangGraph multi-agent system.

Defines the shared state schema that flows through the agent graph.
All agents read from and write to this state, enabling data sharing
and reasoning chain tracking across the orchestration pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langgraph.graph import MessagesState


class AgentState(MessagesState):
    """Shared state for the multi-agent LangGraph pipeline.

    Extends LangGraph's ``MessagesState`` (which manages the message
    list) with additional fields for routing, tool results, metadata,
    and reasoning chain tracking.

    Attributes:
        current_agent: Name of the agent currently processing.
        next_agent: Name of the next agent to route to (set by supervisor).
        user_message: The original user message.
        user_id: Authenticated user's UUID.
        tenant_id: Tenant UUID for data isolation.
        role: User's role name for permission checking.
        chat_id: Chat session UUID.
        tool_results: Results from tool executions in this turn.
        retrieved_chunks: RAG context chunks from vector search.
        sql_query: Generated SQL query (if SQL agent was invoked).
        sql_result: SQL query execution result.
        plan: Multi-step plan (if planner agent was invoked).
        memory_context: Long-term memory entries for this user.
        reasoning_steps: Chain of reasoning for transparency.
        final_response: The final synthesized response to the user.
        metadata: Additional metadata (model, tokens, cost, etc.).
        requires_approval: Whether the current operation needs human approval.
        approval_id: UUID of the pending approval (if any).
        error: Error message if any agent failed.
    """

    current_agent: str = ""
    next_agent: str = ""
    user_message: str = ""
    user_id: str = ""
    tenant_id: str = ""
    role: str = ""
    chat_id: str = ""

    # Agent outputs
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    retrieved_chunks: list[dict[str, Any]] = field(default_factory=list)
    sql_query: str = ""
    sql_result: str = ""
    plan: dict[str, Any] = field(default_factory=dict)
    memory_context: str = ""

    # Reasoning & transparency
    reasoning_steps: list[dict[str, Any]] = field(default_factory=list)

    # Output
    final_response: str = ""

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    # Approval flow
    requires_approval: bool = False
    approval_id: str = ""

    # Error handling
    error: str = ""
