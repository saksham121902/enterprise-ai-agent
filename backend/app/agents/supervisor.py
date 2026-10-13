"""Supervisor agent — the orchestrator of the multi-agent system.

The supervisor receives user messages, analyzes intent, and routes
to the appropriate specialist agent(s). It implements:
- Intent classification
- Agent routing decisions
- Multi-step workflow orchestration
- Response synthesis from agent outputs

This is the entry point of the LangGraph agent graph.
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agents.state import AgentState
from app.core.constants import AgentType
from app.core.logging import get_logger
from app.core.telemetry import AGENT_EXECUTIONS_TOTAL, AGENT_EXECUTION_DURATION
from app.llm.factory import get_llm_service
from app.prompts import prompt_manager

logger = get_logger(__name__, agent="supervisor")

# Agent descriptions for prompt template
AGENT_DESCRIPTIONS = [
    {"name": "rag", "description": "Search and retrieve information from uploaded company documents"},
    {"name": "sql", "description": "Query databases using natural language, generate and execute SQL"},
    {"name": "tool", "description": "Execute tools like calculator, date/time, text processing"},
    {"name": "memory", "description": "Recall past conversations, user preferences, and important context"},
    {"name": "planner", "description": "Create step-by-step execution plans for complex multi-agent tasks"},
]


async def supervisor_node(state: AgentState) -> dict[str, Any]:
    """Supervisor agent node for the LangGraph graph.

    Analyzes the user's message and decides which agent(s) to invoke.
    Sets ``next_agent`` in the state to control routing.

    Args:
        state: The current agent pipeline state.

    Returns:
        State updates with routing decision and reasoning.
    """
    import time

    start = time.perf_counter()
    user_message = state.get("user_message", "")

    logger.info("Supervisor analyzing request", message_preview=user_message[:100])

    # Build tool descriptions from registry
    from app.tools import tool_registry

    tool_descriptions = [
        {"name": t.name, "description": t.description}
        for t in tool_registry.list_tools()
    ]

    # Render the supervisor prompt
    system_prompt = prompt_manager.render(
        "supervisor",
        available_agents=AGENT_DESCRIPTIONS,
        available_tools=tool_descriptions,
        memory_context=state.get("memory_context", ""),
        user_message=user_message,
    )

    # Ask the LLM to classify intent and decide routing
    llm = get_llm_service()
    routing_prompt = (
        f"Analyze this request and respond with a JSON object containing:\n"
        f"- \"reasoning\": your analysis of what the user needs\n"
        f"- \"route_to\": the agent name to route to (rag, sql, tool, memory, planner, or direct)\n"
        f"- \"direct_response\": if route_to is 'direct', provide the response here\n\n"
        f"User message: {user_message}"
    )

    response = await llm.generate(
        prompt=routing_prompt,
        system_prompt=system_prompt,
        temperature=0.1,
        max_tokens=1000,
    )

    duration = time.perf_counter() - start

    # Parse the routing decision
    route_to = "direct"
    reasoning = ""
    direct_response = ""

    try:
        # Try to extract JSON from the response
        content = response.content.strip()
        # Handle markdown code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        parsed = json.loads(content)
        route_to = parsed.get("route_to", "direct")
        reasoning = parsed.get("reasoning", "")
        direct_response = parsed.get("direct_response", "")
    except (json.JSONDecodeError, IndexError):
        # If JSON parsing fails, treat the whole response as direct
        direct_response = response.content
        reasoning = "Could not parse routing decision; responding directly"

    AGENT_EXECUTIONS_TOTAL.labels(agent_type="supervisor", status="success").inc()
    AGENT_EXECUTION_DURATION.labels(
        agent_type="supervisor", model=response.model
    ).observe(duration)

    # Build reasoning step
    reasoning_step = {
        "agent": "supervisor",
        "action": "route_decision",
        "reasoning": reasoning,
        "route_to": route_to,
        "duration_ms": int(duration * 1000),
        "model": response.model,
        "tokens": response.total_tokens,
    }

    existing_reasoning = state.get("reasoning_steps", [])
    existing_reasoning.append(reasoning_step)

    # Build metadata
    existing_metadata = state.get("metadata", {})
    existing_metadata["supervisor_model"] = response.model
    existing_metadata["supervisor_tokens"] = response.total_tokens
    existing_metadata["supervisor_cost"] = response.cost_usd

    logger.info(
        "Supervisor routing decision",
        route_to=route_to,
        reasoning=reasoning[:200],
        duration_ms=int(duration * 1000),
    )

    updates: dict[str, Any] = {
        "current_agent": "supervisor",
        "next_agent": route_to,
        "reasoning_steps": existing_reasoning,
        "metadata": existing_metadata,
    }

    if route_to == "direct":
        updates["final_response"] = direct_response
        updates["messages"] = [AIMessage(content=direct_response)]

    return updates
