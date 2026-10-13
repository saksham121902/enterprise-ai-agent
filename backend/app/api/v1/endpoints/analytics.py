"""Analytics, workflow, and admin API endpoints."""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_role
from app.core.constants import RoleName
from app.models.chat import Message
from app.models.document import Document
from app.models.operational import CostTracking, ToolExecution

router = APIRouter()


@router.get(
    "/overview",
    summary="Get analytics overview",
)
async def analytics_overview(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get high-level analytics: total chats, documents, tokens, and cost."""
    tenant_id = uuid.UUID(user.get("tenant_id", ""))

    # Total messages
    msg_count = await db.execute(
        select(func.count(Message.id)).where(Message.tenant_id == tenant_id)
    )
    total_messages = msg_count.scalar() or 0

    # Total documents
    doc_count = await db.execute(
        select(func.count(Document.id)).where(Document.tenant_id == tenant_id)
    )
    total_documents = doc_count.scalar() or 0

    # Total tokens and cost
    cost_result = await db.execute(
        select(
            func.coalesce(func.sum(CostTracking.input_tokens), 0),
            func.coalesce(func.sum(CostTracking.output_tokens), 0),
            func.coalesce(func.sum(CostTracking.cost_usd), Decimal("0")),
        ).where(CostTracking.tenant_id == tenant_id)
    )
    row = cost_result.one()
    total_input_tokens = row[0]
    total_output_tokens = row[1]
    total_cost_usd = float(row[2])

    # Top tools
    tool_result = await db.execute(
        select(
            ToolExecution.tool_name,
            func.count(ToolExecution.id).label("count"),
        )
        .where(ToolExecution.tenant_id == tenant_id)
        .group_by(ToolExecution.tool_name)
        .order_by(func.count(ToolExecution.id).desc())
        .limit(10)
    )
    top_tools = [{"name": r[0], "count": r[1]} for r in tool_result.all()]

    return {
        "total_messages": total_messages,
        "total_documents": total_documents,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_cost_usd": total_cost_usd,
        "top_tools": top_tools,
    }


@router.get(
    "/cost-breakdown",
    summary="Get cost breakdown by model",
)
async def cost_breakdown(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get AI cost breakdown grouped by provider and model."""
    tenant_id = uuid.UUID(user.get("tenant_id", ""))

    result = await db.execute(
        select(
            CostTracking.provider,
            CostTracking.model,
            func.count(CostTracking.id).label("requests"),
            func.sum(CostTracking.input_tokens).label("input_tokens"),
            func.sum(CostTracking.output_tokens).label("output_tokens"),
            func.sum(CostTracking.cost_usd).label("total_cost"),
        )
        .where(CostTracking.tenant_id == tenant_id)
        .group_by(CostTracking.provider, CostTracking.model)
        .order_by(func.sum(CostTracking.cost_usd).desc())
    )

    return [
        {
            "provider": r[0],
            "model": r[1],
            "requests": r[2],
            "input_tokens": r[3],
            "output_tokens": r[4],
            "total_cost_usd": float(r[5]),
        }
        for r in result.all()
    ]
