"""Authentication service — business logic for user auth operations.

Handles registration, login, token refresh, and password management.
All database operations use async SQLAlchemy sessions.
"""

from __future__ import annotations

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.constants import RoleName
from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    needs_rehash,
    verify_password,
)
from app.models.role import Role
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserResponse,
)

logger = get_logger(__name__)


class AuthService:
    """Service for authentication operations.

    All methods receive a database session and operate within the
    caller's transaction scope.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def register(self, request: RegisterRequest) -> RegisterResponse:
        """Register a new user.

        Creates the user with the 'employee' role in the default (or
        specified) tenant. Returns the user profile and JWT tokens.

        Args:
            request: Registration request data.

        Returns:
            User profile and JWT token pair.

        Raises:
            ConflictError: If email or username already exists.
        """
        # Check for existing user
        existing = await self._db.execute(
            select(User).where(
                or_(
                    User.email == request.email,
                    User.username == request.username,
                )
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictError("A user with this email or username already exists")

        # Get or create tenant
        tenant = await self._get_or_create_tenant(
            request.tenant_name or get_settings().default_tenant_name
        )

        # Get default role (employee)
        role = await self._get_or_create_role(RoleName.EMPLOYEE)

        # Create user
        user = User(
            email=request.email,
            username=request.username,
            hashed_password=hash_password(request.password),
            full_name=request.full_name,
            tenant_id=tenant.id,
            role_id=role.id,
            is_active=True,
            is_verified=False,
        )
        self._db.add(user)
        await self._db.flush()  # Get the user ID without committing

        logger.info("User registered", user_id=str(user.id), email=user.email)

        tokens = self._create_tokens(user, role.name)
        user_response = self._build_user_response(user, role.name)

        return RegisterResponse(user=user_response, tokens=tokens)

    async def login(self, request: LoginRequest) -> LoginResponse:
        """Authenticate a user with email/username and password.

        Args:
            request: Login credentials.

        Returns:
            User profile and JWT token pair.

        Raises:
            AuthenticationError: If credentials are invalid.
        """
        # Find user by email or username
        result = await self._db.execute(
            select(User)
            .options(selectinload(User.role))
            .where(
                or_(
                    User.email == request.login,
                    User.username == request.login,
                )
            )
        )
        user = result.scalar_one_or_none()

        if not user:
            raise AuthenticationError("Invalid credentials")

        if not user.is_active:
            raise AuthenticationError("Account is deactivated")

        if not verify_password(request.password, user.hashed_password):
            raise AuthenticationError("Invalid credentials")

        # Rehash password if using deprecated algorithm
        if needs_rehash(user.hashed_password):
            user.hashed_password = hash_password(request.password)
            logger.info("Password rehashed for user", user_id=str(user.id))

        role_name = user.role.name if user.role else RoleName.EMPLOYEE
        tokens = self._create_tokens(user, role_name)
        user_response = self._build_user_response(user, role_name)

        logger.info("User logged in", user_id=str(user.id))

        return LoginResponse(user=user_response, tokens=tokens)

    async def refresh_token(self, request: RefreshTokenRequest) -> TokenResponse:
        """Issue new tokens using a valid refresh token.

        Args:
            request: Refresh token request.

        Returns:
            New JWT token pair.

        Raises:
            AuthenticationError: If the refresh token is invalid.
        """
        payload = decode_refresh_token(request.refresh_token)
        user_id = payload.get("sub")

        result = await self._db.execute(
            select(User)
            .options(selectinload(User.role))
            .where(User.id == uuid.UUID(user_id))
        )
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            raise AuthenticationError("Invalid refresh token — user not found or inactive")

        role_name = user.role.name if user.role else RoleName.EMPLOYEE
        return self._create_tokens(user, role_name)

    async def change_password(
        self, user_id: str, current_password: str, new_password: str
    ) -> None:
        """Change a user's password.

        Args:
            user_id: The user's UUID.
            current_password: The current password for verification.
            new_password: The new password to set.

        Raises:
            NotFoundError: If user not found.
            ValidationError: If current password is incorrect.
        """
        result = await self._db.execute(
            select(User).where(User.id == uuid.UUID(user_id))
        )
        user = result.scalar_one_or_none()

        if not user:
            raise NotFoundError("User", user_id)

        if not verify_password(current_password, user.hashed_password):
            raise ValidationError(
                message="Current password is incorrect",
                field_errors={"current_password": "Does not match"},
            )

        user.hashed_password = hash_password(new_password)
        logger.info("Password changed", user_id=user_id)

    # ── Private Helpers ──────────────────────────────────────────────────

    async def _get_or_create_tenant(self, name: str) -> Tenant:
        """Get existing tenant or create a new one."""
        result = await self._db.execute(
            select(Tenant).where(Tenant.name == name)
        )
        tenant = result.scalar_one_or_none()

        if not tenant:
            slug = name.lower().replace(" ", "-")
            tenant = Tenant(name=name, slug=slug, is_active=True)
            self._db.add(tenant)
            await self._db.flush()
            logger.info("Tenant created", tenant_name=name)

        return tenant

    async def _get_or_create_role(self, role_name: RoleName) -> Role:
        """Get existing role or create it with default permissions."""
        from app.core.constants import ROLE_PERMISSIONS

        result = await self._db.execute(
            select(Role).where(Role.name == role_name.value)
        )
        role = result.scalar_one_or_none()

        if not role:
            perms = ROLE_PERMISSIONS.get(role_name, set())
            role = Role(
                name=role_name.value,
                description=f"Default {role_name.value} role",
                permissions_csv=",".join(p.value for p in perms),
            )
            self._db.add(role)
            await self._db.flush()
            logger.info("Role created", role_name=role_name.value)

        return role

    def _create_tokens(self, user: User, role_name: str) -> TokenResponse:
        """Generate JWT access and refresh tokens."""
        settings = get_settings()
        access_token = create_access_token(
            subject=str(user.id),
            tenant_id=str(user.tenant_id),
            role=role_name,
        )
        refresh_token = create_refresh_token(
            subject=str(user.id),
            tenant_id=str(user.tenant_id),
        )
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.jwt_access_token_expire_minutes * 60,
        )

    def _build_user_response(self, user: User, role_name: str) -> UserResponse:
        """Build a UserResponse from a User model."""
        return UserResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            is_active=user.is_active,
            is_verified=user.is_verified,
            role_name=role_name,
            tenant_id=user.tenant_id,
            created_at=user.created_at,
        )
