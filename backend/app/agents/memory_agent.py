"""Memory agent node for long-term context retrieval and storage.

Manages the user's long-term memory, including:
- Retrieving relevant memories for context enrichment
- Storing new facts, preferences, and conversation summaries
- Providing memory context to other agents
"""

from __future__ import annotations

import time
from typing import Any

from langchain_core.messages import AIMessage

from app.agents.state import AgentState
from app.core.logging import get_logger
from app.core.telemetry import AGENT_EXECUTIONS_TOTAL, AGENT_EXECUTION_DURATION
from app.llm.factory import get_llm_service

logger = get_logger(__name__, agent="memory")


async def memory_node(state: AgentState) -> dict[str, Any]:
    """Memory agent node — retrieves and manages long-term context.

    Args:
        state: The current agent pipeline state.

    Returns:
        State updates with memory context and response.
    """
    start = time.perf_counter()
    user_message = state.get("user_message", "")
    user_id = state.get("user_id", "")

    logger.info("Memory agent processing", message_preview=user_message[:100])

    # Retrieve relevant memories
    memories = await _retrieve_memories(user_id, user_message)

    if memories:
        memory_text = "\n".join(
            f"- [{m['type']}] {m['content']}" for m in memories
        )
        context = f"Relevant memories for this user:\n{memory_text}"
    else:
        context = "No relevant memories found for this user."

    # Generate response using memory context
    llm = get_llm_service()
    response = await llm.generate(
        prompt=(
            f"The user asked: {user_message}\n\n"
            f"Memory context:\n{context}\n\n"
            f"Respond using the memory context to personalize your answer."
        ),
        temperature=0.5,
        max_tokens=1000,
    )

    duration = time.perf_counter() - start

    AGENT_EXECUTIONS_TOTAL.labels(agent_type="memory", status="success").inc()
    AGENT_EXECUTION_DURATION.labels(
        agent_type="memory", model=response.model
    ).observe(duration)

    reasoning_step = {
        "agent": "memory",
        "action": "memory_retrieval",
        "memories_found": len(memories),
        "duration_ms": int(duration * 1000),
    }

    existing_reasoning = state.get("reasoning_steps", [])
    existing_reasoning.append(reasoning_step)

    return {
        "current_agent": "memory",
        "next_agent": "end",
        "memory_context": context,
        "final_response": response.content,
        "reasoning_steps": existing_reasoning,
        "messages": [AIMessage(content=response.content)],
    }


async def _retrieve_memories(
    user_id: str, query: str, limit: int = 10
) -> list[dict[str, Any]]:
    """Retrieve relevant memories for a user.

    Queries the database for memory entries matching the user
    and optionally uses semantic search for relevance ranking.

    Args:
        user_id: The user's UUID.
        query: The search query for relevance matching.
        limit: Maximum memories to retrieve.

    Returns:
        List of memory dicts with type and content.
    """
    try:
        from sqlalchemy import select

        from app.database.session import get_session_factory
        from app.models.operational import Memory

        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(Memory)
                .where(
                    Memory.user_id == user_id,
                    Memory.is_active.is_(True),
                )
                .order_by(Memory.importance_score.desc().nullslast())
                .limit(limit)
            )
            memories = result.scalars().all()

            return [
                {
                    "type": m.memory_type,
                    "content": m.content,
                    "importance": float(m.importance_score) if m.importance_score else 0.0,
                    "source": m.source or "unknown",
                }
                for m in memories
            ]
    except Exception as exc:
        logger.error("Memory retrieval failed", error=str(exc), exc_info=True)
        return []
