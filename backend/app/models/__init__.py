"""Models package — SQLAlchemy ORM model registry.

All models must be imported here so Alembic can discover them
for migration autogeneration.
"""

from app.models.base import BaseModel, TenantModel, TimestampMixin
from app.models.chat import Chat, Message
from app.models.document import Document, EmbeddingMetadata
from app.models.operational import (
    AnalyticsEvent,
    Approval,
    AuditLog,
    BackgroundTask,
    CostTracking,
    Memory,
    ToolExecution,
)
from app.models.role import Role
from app.models.tenant import Tenant
from app.models.user import User
from app.models.workflow import Workflow, WorkflowStep

__all__ = [
    "BaseModel",
    "TenantModel",
    "TimestampMixin",
    "Tenant",
    "Role",
    "User",
    "Chat",
    "Message",
    "Document",
    "EmbeddingMetadata",
    "Workflow",
    "WorkflowStep",
    "Memory",
    "Approval",
    "CostTracking",
    "ToolExecution",
    "AnalyticsEvent",
    "AuditLog",
    "BackgroundTask",
]
