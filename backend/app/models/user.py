"""User model with tenant and role relationships."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TenantModel


class User(TenantModel):
    """Represents a user in the system.

    Users belong to a tenant and have a role that determines their
    permissions. Passwords are stored as Argon2id hashes.
    """

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    username: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Preferences stored as JSON string
    preferences_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Foreign keys
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        back_populates="users"
    )
    role: Mapped["Role"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        back_populates="users"
    )
    chats: Mapped[list["Chat"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
    documents: Mapped[list["Document"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        back_populates="uploaded_by_user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(email='{self.email}', username='{self.username}')>"
