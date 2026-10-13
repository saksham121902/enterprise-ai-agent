"""Tool execution agent node.

Selects and executes tools from the registry based on the user's request.
Uses the LLM to decide which tool to call and with what arguments.
"""

from __future__ import annotations

import json
import time
from typing import Any

from langchain_core.messages import AIMessage

from app.agents.state import AgentState
from app.core.logging import get_logger
from app.core.telemetry import AGENT_EXECUTIONS_TOTAL, AGENT_EXECUTION_DURATION
from app.llm.factory import get_llm_service
from app.tools import tool_registry

logger = get_logger(__name__, agent="tool")


async def tool_node(state: AgentState) -> dict[str, Any]:
    """Tool agent node — selects and executes tools.

    Uses the LLM with function calling format to decide which tool
    to invoke and generates the arguments.

    Args:
        state: The current agent pipeline state.

    Returns:
        State updates with tool results and response.
    """
    start = time.perf_counter()
    user_message = state.get("user_message", "")

    logger.info("Tool agent processing", message_preview=user_message[:100])

    # Get available tools
    tools = tool_registry.list_tools()
    tool_descriptions = "\n".join(
        f"- **{t.name}**: {t.description}" for t in tools
    )

    # Ask LLM which tool to use
    llm = get_llm_service()
    tool_selection_prompt = (
        f"You have access to these tools:\n{tool_descriptions}\n\n"
        f"The user's request is: {user_message}\n\n"
        f"Respond with a JSON object:\n"
        f'{{"tool_name": "name", "arguments": {{...}}, "reasoning": "why this tool"}}\n\n'
        f"If no tool is appropriate, set tool_name to 'none' and provide a direct answer in 'reasoning'."
    )

    response = await llm.generate(
        prompt=tool_selection_prompt,
        temperature=0.1,
        max_tokens=1000,
    )

    # Parse tool selection
    try:
        content = response.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        parsed = json.loads(content)
        tool_name = parsed.get("tool_name", "none")
        arguments = parsed.get("arguments", {})
        reasoning = parsed.get("reasoning", "")
    except (json.JSONDecodeError, IndexError):
        tool_name = "none"
        arguments = {}
        reasoning = response.content

    # Execute the tool
    tool_result = ""
    if tool_name != "none":
        try:
            tool_result = await tool_registry.execute(tool_name, arguments)
            tool_result = str(tool_result)
        except Exception as exc:
            tool_result = f"Tool execution error: {exc}"
            logger.error("Tool execution failed", tool=tool_name, error=str(exc))

    AGENT_EXECUTIONS_TOTAL.labels(agent_type="tool", status="success").inc()
    AGENT_EXECUTION_DURATION.labels(
        agent_type="tool", model=response.model
    ).observe(time.perf_counter() - start)

    reasoning_step = {
        "agent": "tool",
        "action": f"execute_{tool_name}",
        "tool_name": tool_name,
        "arguments": arguments,
        "result_preview": str(tool_result)[:200] if tool_result else "",
        "duration_ms": int((time.perf_counter() - start) * 1000),
    }

    existing_reasoning = state.get("reasoning_steps", [])
    existing_reasoning.append(reasoning_step)

    # Build response
    if tool_name == "none":
        final = reasoning
    elif tool_result:
        final = f"**Tool**: {tool_name}\n**Result**: {tool_result}"
    else:
        final = f"Tool '{tool_name}' was called but returned no result."

    existing_tool_results = state.get("tool_results", [])
    existing_tool_results.append({
        "tool_name": tool_name,
        "arguments": arguments,
        "result": tool_result,
    })

    return {
        "current_agent": "tool",
        "next_agent": "end",
        "tool_results": existing_tool_results,
        "final_response": final,
        "reasoning_steps": existing_reasoning,
        "messages": [AIMessage(content=final)],
    }
