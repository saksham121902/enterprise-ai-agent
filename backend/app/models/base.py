"""Base model mixin providing common columns for all database models.

Every model in the application should inherit from ``TenantBase`` (for
tenant-scoped data) or ``Base`` directly (for global data like tenants).

Common columns provided:
- ``id``: UUID primary key
- ``created_at``: Auto-set creation timestamp
- ``updated_at``: Auto-updated modification timestamp
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class TimestampMixin:
    """Mixin that adds created_at and updated_at timestamp columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class BaseModel(Base, TimestampMixin):
    """Abstract base model with UUID primary key and timestamps.

    Use this for global tables that are NOT scoped to a tenant
    (e.g., the tenants table itself).
    """

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )


class TenantModel(Base, TimestampMixin):
    """Abstract base model with UUID primary key, timestamps, AND tenant_id.

    Use this for all tenant-scoped tables. The ``tenant_id`` column
    ensures data isolation between tenants via row-level filtering.
    """

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
