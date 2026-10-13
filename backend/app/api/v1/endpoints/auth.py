"""Authentication API endpoints.

Provides user registration, login, token refresh, logout,
and password management endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    MessageResponse,
    RefreshTokenRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import AuthService

router = APIRouter()


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=201,
    summary="Register a new user",
)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    """Register a new user account.

    Creates the user in the default tenant with the 'employee' role.
    Returns the user profile and JWT access/refresh token pair.
    """
    service = AuthService(db)
    return await service.register(request)


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Login with credentials",
)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Authenticate with email/username and password.

    Returns the user profile and JWT access/refresh token pair.
    """
    service = AuthService(db)
    return await service.login(request)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
)
async def refresh_token(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Exchange a valid refresh token for a new access/refresh token pair."""
    service = AuthService(db)
    return await service.refresh_token(request)


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Logout",
)
async def logout(
    _user: dict = Depends(get_current_user),
) -> MessageResponse:
    """Log out the current user.

    In a JWT-based system, logout is handled client-side by discarding
    the tokens. This endpoint exists for audit logging and to support
    future token blacklisting via Redis.
    """
    return MessageResponse(message="Successfully logged out")


@router.post(
    "/change-password",
    response_model=MessageResponse,
    summary="Change password",
)
async def change_password(
    request: ChangePasswordRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Change the current user's password.

    Requires the current password for verification.
    """
    service = AuthService(db)
    await service.change_password(
        user_id=user["sub"],
        current_password=request.current_password,
        new_password=request.new_password,
    )
    return MessageResponse(message="Password changed successfully")


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
async def get_me(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Get the authenticated user's profile information."""
    import uuid

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.models.user import User

    result = await db.execute(
        select(User)
        .options(selectinload(User.role))
        .where(User.id == uuid.UUID(user["sub"]))
    )
    db_user = result.scalar_one_or_none()

    if not db_user:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("User", user["sub"])

    role_name = db_user.role.name if db_user.role else None
    return UserResponse(
        id=db_user.id,
        email=db_user.email,
        username=db_user.username,
        full_name=db_user.full_name,
        is_active=db_user.is_active,
        is_verified=db_user.is_verified,
        role_name=role_name,
        tenant_id=db_user.tenant_id,
        created_at=db_user.created_at,
    )
