"""Workflow management API endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_db
from app.core.exceptions import NotFoundError
from app.models.workflow import Workflow

router = APIRouter()


@router.get(
    "/",
    summary="List workflows",
)
async def list_workflows(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all workflow executions for the current tenant."""
    tenant_id = uuid.UUID(user.get("tenant_id", ""))

    result = await db.execute(
        select(Workflow)
        .where(Workflow.tenant_id == tenant_id)
        .order_by(Workflow.created_at.desc())
        .limit(50)
    )
    workflows = result.scalars().all()

    return [
        {
            "id": str(w.id),
            "name": w.name,
            "status": w.status,
            "total_steps": w.total_steps,
            "completed_steps": w.completed_steps,
            "total_duration_ms": w.total_duration_ms,
            "created_at": w.created_at.isoformat(),
        }
        for w in workflows
    ]


@router.get(
    "/{workflow_id}",
    summary="Get workflow details with steps",
)
async def get_workflow(
    workflow_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get detailed workflow execution with all steps."""
    tenant_id = uuid.UUID(user.get("tenant_id", ""))

    result = await db.execute(
        select(Workflow)
        .options(selectinload(Workflow.steps))
        .where(
            Workflow.id == workflow_id,
            Workflow.tenant_id == tenant_id,
        )
    )
    workflow = result.scalar_one_or_none()

    if not workflow:
        raise NotFoundError("Workflow", str(workflow_id))

    return {
        "id": str(workflow.id),
        "name": workflow.name,
        "description": workflow.description,
        "status": workflow.status,
        "total_steps": workflow.total_steps,
        "completed_steps": workflow.completed_steps,
        "total_duration_ms": workflow.total_duration_ms,
        "total_tokens": workflow.total_tokens,
        "trigger_message": workflow.trigger_message,
        "final_output": workflow.final_output,
        "error_message": workflow.error_message,
        "created_at": workflow.created_at.isoformat(),
        "steps": [
            {
                "step_order": s.step_order,
                "agent_type": s.agent_type,
                "status": s.status,
                "input_data": s.input_data,
                "output_summary": s.output_summary,
                "error_message": s.error_message,
                "duration_ms": s.duration_ms,
                "model": s.model,
                "input_tokens": s.input_tokens,
                "output_tokens": s.output_tokens,
            }
            for s in workflow.steps
        ],
    }
