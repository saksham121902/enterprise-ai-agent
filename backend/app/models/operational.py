"""Memory, Approval, CostTracking, ToolExecution, Analytics, AuditLog, and BackgroundTask models."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantModel


class Memory(TenantModel):
    """Long-term memory entries for contextual awareness.

    Stores user preferences, important facts, conversation summaries,
    and other information the AI agent should remember across sessions.
    """

    __tablename__ = "memories"

    memory_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    importance_score: Mapped[float | None] = mapped_column(
        Numeric(4, 2), nullable=True
    )
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Optional embedding ID in ChromaDB for semantic retrieval
    embedding_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<Memory(type='{self.memory_type}', score={self.importance_score})>"


class Approval(TenantModel):
    """Human approval requests for sensitive operations.

    Created when the AI agent wants to execute a potentially
    destructive operation (SQL write, email, external API call).
    """

    __tablename__ = "approvals"

    operation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending", index=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # The operation details (e.g., SQL query, email content)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Who requested and who reviewed
    requested_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Associated workflow step (if part of a workflow)
    workflow_step_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_steps.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<Approval(type='{self.operation_type}', status='{self.status}')>"


class CostTracking(TenantModel):
    """Per-request AI cost tracking for the cost dashboard.

    Records token usage and cost for every LLM API call,
    aggregated for per-user, per-model, and per-day reporting.
    """

    __tablename__ = "cost_tracking"

    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 6), default=Decimal("0"), nullable=False
    )

    # Context
    agent_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    chat_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<CostTracking(model='{self.model}', cost=${self.cost_usd})>"


class ToolExecution(TenantModel):
    """Tracks tool invocations by AI agents.

    Records which tools were called, their inputs/outputs,
    duration, and success/failure status for debugging and analytics.
    """

    __tablename__ = "tool_executions"

    tool_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="started"
    )

    input_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Context
    agent_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    chat_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<ToolExecution(tool='{self.tool_name}', status='{self.status}')>"


class AnalyticsEvent(TenantModel):
    """General-purpose analytics event tracking.

    Captures custom events for the analytics dashboard (e.g., daily
    active users, popular tools, workflow success rates).
    """

    __tablename__ = "analytics_events"

    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    event_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    metric_value: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<AnalyticsEvent(type='{self.event_type}')>"


class AuditLog(TenantModel):
    """Immutable audit trail for security and compliance.

    Records all significant actions (login, data access, modifications,
    admin operations) with full context for forensic analysis.
    """

    __tablename__ = "audit_logs"

    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    details_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<AuditLog(action='{self.action}', resource='{self.resource_type}')>"


class BackgroundTask(TenantModel):
    """Tracks Celery background task status and results.

    Provides database-backed task tracking complementing Celery's
    Redis result backend, with richer metadata and tenant scoping.
    """

    __tablename__ = "background_tasks"

    celery_task_id: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    task_name: Mapped[str] = mapped_column(String(255), nullable=False)
    queue: Mapped[str] = mapped_column(String(100), nullable=False, default="default")
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending", index=True
    )

    # Task data
    args_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Retry tracking
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    # Timing
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<BackgroundTask(task='{self.task_name}', status='{self.status}')>"
