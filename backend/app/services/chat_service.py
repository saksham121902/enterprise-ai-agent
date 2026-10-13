"""Chat service — orchestrates AI agent execution for chat messages.

Handles the full lifecycle of a chat message:
1. Create or retrieve chat session
2. Store the user message
3. Invoke the LangGraph agent pipeline
4. Store the AI response with metadata
5. Track cost and token usage
"""

from __future__ import annotations

import time
import uuid
from decimal import Decimal
from typing import Any

from langchain_core.messages import HumanMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.graph import get_agent_graph
from app.agents.state import AgentState
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models.chat import Chat, Message
from app.schemas.chat import ChatMessageRequest, ChatMessageResponse, ReasoningStep

logger = get_logger(__name__)


class ChatService:
    """Service for processing chat messages through the agent pipeline."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def process_message(
        self,
        request: ChatMessageRequest,
        user_id: str,
        tenant_id: str,
        role: str,
    ) -> ChatMessageResponse:
        """Process a user message through the multi-agent system.

        Args:
            request: The chat message request.
            user_id: Authenticated user's UUID.
            tenant_id: Tenant UUID for data isolation.
            role: User's role name.

        Returns:
            The AI agent's response with metadata.
        """
        start_time = time.perf_counter()

        # Step 1: Get or create chat
        chat = await self._get_or_create_chat(request.chat_id, user_id, tenant_id)

        # Step 2: Store user message
        user_msg = Message(
            role="user",
            content=request.message,
            chat_id=chat.id,
            tenant_id=uuid.UUID(tenant_id),
        )
        self._db.add(user_msg)
        await self._db.flush()

        # Step 3: Invoke the agent graph
        graph = get_agent_graph()
        initial_state: dict[str, Any] = {
            "messages": [HumanMessage(content=request.message)],
            "user_message": request.message,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "role": role,
            "chat_id": str(chat.id),
        }

        try:
            result = await graph.ainvoke(initial_state)
        except Exception as exc:
            logger.error("Agent pipeline failed", error=str(exc), exc_info=True)
            result = {
                "final_response": f"I encountered an error processing your request: {exc}",
                "reasoning_steps": [],
                "metadata": {},
                "requires_approval": False,
            }

        processing_time_ms = int((time.perf_counter() - start_time) * 1000)

        # Extract response data
        content = result.get("final_response", "I couldn't generate a response.")
        metadata = result.get("metadata", {})
        reasoning = result.get("reasoning_steps", [])
        requires_approval = result.get("requires_approval", False)
        approval_id = result.get("approval_id", "")

        # Calculate token totals from reasoning steps
        total_input = sum(s.get("tokens", 0) for s in reasoning)
        total_output = 0
        model_used = metadata.get("supervisor_model", "")
        provider_used = ""
        total_cost = metadata.get("supervisor_cost", 0.0)

        # Step 4: Store AI response
        ai_msg = Message(
            role="assistant",
            content=content,
            model=model_used,
            provider=provider_used,
            input_tokens=total_input,
            output_tokens=total_output,
            cost=Decimal(str(round(total_cost, 6))),
            processing_time_ms=processing_time_ms,
            agent_trace_json=str(reasoning),
            chat_id=chat.id,
            tenant_id=uuid.UUID(tenant_id),
        )
        self._db.add(ai_msg)

        # Step 5: Update chat metadata
        chat.total_messages += 2
        chat.total_tokens += total_input + total_output
        chat.total_cost += Decimal(str(round(total_cost, 6)))

        # Auto-generate chat title from first message
        if chat.title == "New Chat" and len(request.message) > 0:
            chat.title = request.message[:80] + ("..." if len(request.message) > 80 else "")

        await self._db.flush()

        logger.info(
            "Chat message processed",
            chat_id=str(chat.id),
            processing_time_ms=processing_time_ms,
            agents_invoked=len(reasoning),
        )

        return ChatMessageResponse(
            chat_id=chat.id,
            message_id=ai_msg.id,
            content=content,
            model=model_used,
            provider=provider_used,
            input_tokens=total_input,
            output_tokens=total_output,
            total_tokens=total_input + total_output,
            cost_usd=total_cost,
            processing_time_ms=processing_time_ms,
            reasoning_steps=[
                ReasoningStep(
                    agent=s.get("agent", ""),
                    action=s.get("action", ""),
                    reasoning=s.get("reasoning", ""),
                    duration_ms=s.get("duration_ms", 0),
                    model=s.get("model"),
                    tokens=s.get("tokens", 0),
                )
                for s in reasoning
            ],
            requires_approval=requires_approval,
            approval_id=approval_id or None,
        )

    async def list_chats(
        self, user_id: str, tenant_id: str, limit: int = 50
    ) -> list[Chat]:
        """List chat sessions for a user.

        Args:
            user_id: User UUID.
            tenant_id: Tenant UUID.
            limit: Max chats to return.

        Returns:
            List of Chat model instances.
        """
        result = await self._db.execute(
            select(Chat)
            .where(
                Chat.user_id == uuid.UUID(user_id),
                Chat.tenant_id == uuid.UUID(tenant_id),
                Chat.is_archived.is_(False),
            )
            .order_by(Chat.updated_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_chat(
        self, chat_id: uuid.UUID, user_id: str, tenant_id: str
    ) -> Chat:
        """Get a chat with its messages.

        Args:
            chat_id: Chat UUID.
            user_id: User UUID (for ownership check).
            tenant_id: Tenant UUID.

        Returns:
            Chat with messages loaded.

        Raises:
            NotFoundError: If chat not found.
        """
        result = await self._db.execute(
            select(Chat)
            .options(selectinload(Chat.messages))
            .where(
                Chat.id == chat_id,
                Chat.user_id == uuid.UUID(user_id),
                Chat.tenant_id == uuid.UUID(tenant_id),
            )
        )
        chat = result.scalar_one_or_none()
        if not chat:
            raise NotFoundError("Chat", str(chat_id))
        return chat

    async def delete_chat(
        self, chat_id: uuid.UUID, user_id: str, tenant_id: str
    ) -> None:
        """Delete a chat session.

        Args:
            chat_id: Chat UUID.
            user_id: User UUID.
            tenant_id: Tenant UUID.
        """
        chat = await self.get_chat(chat_id, user_id, tenant_id)
        await self._db.delete(chat)

    async def _get_or_create_chat(
        self, chat_id: uuid.UUID | None, user_id: str, tenant_id: str
    ) -> Chat:
        """Get existing chat or create a new one."""
        if chat_id:
            return await self.get_chat(chat_id, user_id, tenant_id)

        chat = Chat(
            title="New Chat",
            user_id=uuid.UUID(user_id),
            tenant_id=uuid.UUID(tenant_id),
        )
        self._db.add(chat)
        await self._db.flush()
        return chat
