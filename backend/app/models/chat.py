"""Chat and Message models for conversation tracking."""

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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TenantModel


class Chat(TenantModel):
    """Represents a chat conversation session.

    Each chat belongs to a user and tenant. It contains a list of
    messages exchanged between the user and the AI agent.
    """

    __tablename__ = "chats"

    title: Mapped[str] = mapped_column(String(500), nullable=False, default="New Chat")
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Metadata
    total_messages: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 6), default=Decimal("0"), nullable=False
    )

    # Foreign keys
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        back_populates="chats"
    )
    messages: Mapped[list["Message"]] = relationship(
        back_populates="chat",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )

    def __repr__(self) -> str:
        return f"<Chat(title='{self.title}', messages={self.total_messages})>"


class Message(TenantModel):
    """Represents a single message in a chat conversation.

    Tracks both the content and metadata (model used, token counts,
    cost, processing time) for analytics and cost dashboarding.
    """

    __tablename__ = "messages"

    role: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "user", "assistant", "system"
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # AI response metadata
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 6), default=Decimal("0"), nullable=False
    )
    processing_time_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Agent routing metadata (which agents were invoked)
    agent_trace_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Foreign keys
    chat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chats.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    chat: Mapped["Chat"] = relationship(back_populates="messages")

    def __repr__(self) -> str:
        return f"<Message(role='{self.role}', tokens={self.input_tokens + self.output_tokens})>"
