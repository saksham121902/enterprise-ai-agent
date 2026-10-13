"""Chat API endpoints.

Provides chat message processing, session management, and history retrieval.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.schemas.auth import MessageResponse as GenericMessageResponse
from app.schemas.chat import (
    ChatDetail,
    ChatMessageRequest,
    ChatMessageResponse,
    ChatSummary,
    MessageResponse,
)
from app.services.chat_service import ChatService

router = APIRouter()


@router.post(
    "/message",
    response_model=ChatMessageResponse,
    summary="Send a message to the AI agent",
)
async def send_message(
    request: ChatMessageRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatMessageResponse:
    """Send a message and receive an AI agent response.

    The message is processed through the multi-agent pipeline
    (supervisor → specialist agents). Returns the response with
    reasoning steps, token usage, and cost.
    """
    service = ChatService(db)
    return await service.process_message(
        request=request,
        user_id=user["sub"],
        tenant_id=user.get("tenant_id", ""),
        role=user.get("role", "employee"),
    )


@router.get(
    "/",
    response_model=list[ChatSummary],
    summary="List chat sessions",
)
async def list_chats(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ChatSummary]:
    """List the current user's chat sessions, newest first."""
    service = ChatService(db)
    chats = await service.list_chats(
        user_id=user["sub"],
        tenant_id=user.get("tenant_id", ""),
    )
    return [
        ChatSummary(
            id=c.id,
            title=c.title,
            total_messages=c.total_messages,
            total_tokens=c.total_tokens,
            total_cost=c.total_cost,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in chats
    ]


@router.get(
    "/{chat_id}",
    response_model=ChatDetail,
    summary="Get chat with messages",
)
async def get_chat(
    chat_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatDetail:
    """Get a specific chat session with all its messages."""
    service = ChatService(db)
    chat = await service.get_chat(
        chat_id=chat_id,
        user_id=user["sub"],
        tenant_id=user.get("tenant_id", ""),
    )
    return ChatDetail(
        id=chat.id,
        title=chat.title,
        total_messages=chat.total_messages,
        total_tokens=chat.total_tokens,
        total_cost=chat.total_cost,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
        messages=[
            MessageResponse(
                id=m.id,
                role=m.role,
                content=m.content,
                model=m.model,
                provider=m.provider,
                input_tokens=m.input_tokens,
                output_tokens=m.output_tokens,
                cost=m.cost,
                processing_time_ms=m.processing_time_ms,
                created_at=m.created_at,
            )
            for m in chat.messages
        ],
    )


@router.delete(
    "/{chat_id}",
    response_model=GenericMessageResponse,
    summary="Delete a chat session",
)
async def delete_chat(
    chat_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GenericMessageResponse:
    """Delete a chat session and all its messages."""
    service = ChatService(db)
    await service.delete_chat(
        chat_id=chat_id,
        user_id=user["sub"],
        tenant_id=user.get("tenant_id", ""),
    )
    return GenericMessageResponse(message="Chat deleted successfully")
