"""Versioned API router aggregator.

Collects all endpoint routers under the ``/api/v1`` prefix.
New endpoint modules are added here as they are built in subsequent phases.

Router registration order determines the OpenAPI documentation order.
"""

from __future__ import annotations

from fastapi import APIRouter

# ── v1 API Router ────────────────────────────────────────────────────────
router = APIRouter()

# Phase 4: Authentication
from app.api.v1.endpoints.auth import router as auth_router
router.include_router(auth_router, prefix="/auth", tags=["Authentication"])

# Phase 8: Chat
from app.api.v1.endpoints.chat import router as chat_router
router.include_router(chat_router, prefix="/chat", tags=["Chat"])

# Phase 10: Documents
from app.api.v1.endpoints.documents import router as documents_router
router.include_router(documents_router, prefix="/documents", tags=["Documents"])

# Phase 14: Workflows
from app.api.v1.endpoints.workflows import router as workflows_router
router.include_router(workflows_router, prefix="/workflows", tags=["Workflows"])

# Phase 19: Analytics
from app.api.v1.endpoints.analytics import router as analytics_router
router.include_router(analytics_router, prefix="/analytics", tags=["Analytics"])


# Phase 13: Database Explorer
# from app.api.v1.endpoints.database import router as database_router
# router.include_router(database_router, prefix="/database", tags=["Database"])

# Phase 12: Memory
from app.api.v1.endpoints.memory import router as memory_router
router.include_router(memory_router, prefix="/memory", tags=["Memory"])

# Phase 13: Approvals
from app.api.v1.endpoints.approvals import router as approvals_router
router.include_router(approvals_router, prefix="/approvals", tags=["Approvals"])

# Phase 11: Knowledge Graph
# from app.api.v1.endpoints.knowledge_graph import router as kg_router
# router.include_router(kg_router, prefix="/knowledge-graph", tags=["Knowledge Graph"])

# Phase 17: Evaluation
# from app.api.v1.endpoints.evaluation import router as evaluation_router
# router.include_router(evaluation_router, prefix="/evaluation", tags=["Evaluation"])


# Temporary health endpoint under the versioned prefix
@router.get("/status", tags=["Health"])
async def api_status() -> dict[str, str]:
    """API v1 status check."""
    return {
        "api": "v1",
        "status": "operational",
    }
