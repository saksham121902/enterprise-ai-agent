"""Role and Permission models for RBAC."""

from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Role(BaseModel):
    """Defines a role that can be assigned to users.

    Roles determine which permissions a user has. The three default
    roles are: admin, manager, and employee. Custom roles can be
    added for tenant-specific needs.
    """

    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Comma-separated permission strings (e.g., "chat:create,document:upload")
    # Parsed by the RBAC system at runtime
    permissions_csv: Mapped[str] = mapped_column(
        Text, nullable=False, default=""
    )

    # Relationships
    users: Mapped[list["User"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        back_populates="role"
    )

    @property
    def permissions(self) -> set[str]:
        """Parse the permissions CSV into a set of permission strings."""
        if not self.permissions_csv:
            return set()
        return {p.strip() for p in self.permissions_csv.split(",") if p.strip()}

    def __repr__(self) -> str:
        return f"<Role(name='{self.name}')>"
