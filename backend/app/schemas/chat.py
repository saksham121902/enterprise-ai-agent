"""Pydantic v2 schemas for chat API requests and responses."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChatMessageRequest(BaseModel):
    """Send a message to the AI agent."""

    message: str = Field(min_length=1, max_length=10000)
    chat_id: uuid.UUID | None = None  # None = create new chat
    model: str | None = None  # Override default model
    provider: str | None = None  # Override default provider


class ReasoningStep(BaseModel):
    """A single step in the agent's reasoning chain."""

    agent: str
    action: str
    reasoning: str | None = None
    duration_ms: int = 0
    model: str | None = None
    tokens: int = 0
    extra: dict[str, Any] = Field(default_factory=dict)


class ChatMessageResponse(BaseModel):
    """Response from the AI agent."""

    chat_id: uuid.UUID
    message_id: uuid.UUID
    content: str
    model: str | None = None
    provider: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    processing_time_ms: int = 0
    reasoning_steps: list[ReasoningStep] = Field(default_factory=list)
    requires_approval: bool = False
    approval_id: str | None = None


class ChatSummary(BaseModel):
    """Brief chat session summary for listing."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    total_messages: int
    total_tokens: int
    total_cost: Decimal
    created_at: datetime
    updated_at: datetime


class ChatDetail(ChatSummary):
    """Full chat session with messages."""

    messages: list["MessageResponse"] = Field(default_factory=list)


class MessageResponse(BaseModel):
    """Single message in a chat."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    model: str | None = None
    provider: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost: Decimal = Decimal("0")
    processing_time_ms: int = 0
    created_at: datetime
