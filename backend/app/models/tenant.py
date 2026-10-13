"""Tenant model for multi-tenant data isolation."""

from __future__ import annotations

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Tenant(BaseModel):
    """Represents an organization/company in the multi-tenant system.

    Each tenant has isolated data (documents, chats, memory, analytics).
    The default tenant is created during initial setup.
    """

    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Settings stored as JSON string (LLM preferences, feature flags, etc.)
    settings_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    users: Mapped[list["User"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        back_populates="tenant", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Tenant(name='{self.name}', slug='{self.slug}')>"
