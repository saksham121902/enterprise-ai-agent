"""Pydantic v2 schemas for authentication API requests and responses."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ── Request Schemas ──────────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    """User registration request."""

    email: EmailStr
    username: str = Field(min_length=3, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    tenant_name: str | None = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    """User login request. Accepts either email or username."""

    login: str = Field(
        description="Email address or username",
        min_length=1,
    )
    password: str = Field(min_length=1, max_length=128)


class RefreshTokenRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """Password change request."""

    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)


# ── Response Schemas ─────────────────────────────────────────────────────


class TokenResponse(BaseModel):
    """JWT token pair response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token expiry in seconds")


class UserResponse(BaseModel):
    """User profile response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    username: str
    full_name: str
    is_active: bool
    is_verified: bool
    role_name: str | None = None
    tenant_id: uuid.UUID
    created_at: datetime


class RegisterResponse(BaseModel):
    """Registration response with user profile and tokens."""

    user: UserResponse
    tokens: TokenResponse


class LoginResponse(BaseModel):
    """Login response with user profile and tokens."""

    user: UserResponse
    tokens: TokenResponse


class MessageResponse(BaseModel):
    """Generic message response for operations without data."""

    message: str
    success: bool = True
