"""Memory management API endpoints.

Provides CRUD operations for long-term memory entries used
by the AI agent for contextual awareness across sessions.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.exceptions import NotFoundError
from app.models.operational import Memory
from app.schemas.auth import MessageResponse

router = APIRouter()


@router.get(
    "/",
    summary="List memory entries",
)
async def list_memories(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all active memory entries for the current user."""
    user_id = uuid.UUID(user["sub"])
    tenant_id = uuid.UUID(user.get("tenant_id", ""))

    result = await db.execute(
        select(Memory)
        .where(
            Memory.tenant_id == tenant_id,
            Memory.user_id == user_id,
            Memory.is_active.is_(True),
        )
        .order_by(Memory.created_at.desc())
        .limit(100)
    )
    memories = result.scalars().all()

    return [
        {
            "id": str(m.id),
            "memory_type": m.memory_type,
            "content": m.content,
            "importance_score": float(m.importance_score) if m.importance_score else None,
            "source": m.source,
            "created_at": m.created_at.isoformat(),
        }
        for m in memories
    ]


@router.post(
    "/",
    status_code=201,
    summary="Create a memory entry",
)
async def create_memory(
    body: dict,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new long-term memory entry.

    Body fields:
    - memory_type (str): Type of memory (preference, fact, summary)
    - content (str): The memory content
    - importance_score (float, optional): 0.0 to 10.0
    - source (str, optional): Origin of this memory
    """
    user_id = uuid.UUID(user["sub"])
    tenant_id = uuid.UUID(user.get("tenant_id", ""))

    memory = Memory(
        memory_type=body.get("memory_type", "fact"),
        content=body["content"],
        importance_score=body.get("importance_score"),
        source=body.get("source"),
        user_id=user_id,
        tenant_id=tenant_id,
    )
    db.add(memory)
    await db.flush()

    return {
        "id": str(memory.id),
        "memory_type": memory.memory_type,
        "content": memory.content,
        "importance_score": float(memory.importance_score) if memory.importance_score else None,
        "source": memory.source,
        "message": "Memory created successfully",
    }


@router.delete(
    "/{memory_id}",
    response_model=MessageResponse,
    summary="Delete a memory entry",
)
async def delete_memory(
    memory_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Soft-delete a memory entry by marking it inactive."""
    user_id = uuid.UUID(user["sub"])
    tenant_id = uuid.UUID(user.get("tenant_id", ""))

    result = await db.execute(
        select(Memory).where(
            Memory.id == memory_id,
            Memory.tenant_id == tenant_id,
            Memory.user_id == user_id,
        )
    )
    memory = result.scalar_one_or_none()

    if not memory:
        raise NotFoundError("Memory", str(memory_id))

    memory.is_active = False

    return MessageResponse(message="Memory deleted successfully")
