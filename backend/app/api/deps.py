"""FastAPI dependency injection for routes.

Provides reusable ``Depends()`` callables for:
- Database sessions (``get_db``)
- Redis connections (``get_redis``)
- Current authenticated user (``get_current_user``)
- Current tenant context (``get_current_tenant``)
- Role-based access control (``require_role``, ``require_permission``)

Usage in route handlers::

    @router.get("/protected")
    async def protected_route(
        user: dict = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        return {"user_id": user["sub"]}
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.constants import ROLE_PERMISSIONS, Permission, RoleName
from app.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
)
from app.core.security import decode_access_token
from app.database.session import get_db as _get_db
from app.database.session import get_redis as _get_redis

# Re-export database dependencies for convenience
get_db = _get_db
get_redis = _get_redis


async def get_current_user(
    authorization: str | None = Header(None, alias="Authorization"),
) -> dict[str, Any]:
    """Extract and validate the current user from the JWT access token.

    Expects the ``Authorization`` header in the format ``Bearer <token>``.

    Args:
        authorization: The Authorization header value.

    Returns:
        Decoded JWT payload containing ``sub``, ``tenant_id``, ``role``, etc.

    Raises:
        AuthenticationError: If the token is missing, malformed, or invalid.
    """
    if not authorization:
        raise AuthenticationError("Authorization header is required")

    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":  # noqa: PLR2004
        raise AuthenticationError(
            "Authorization header must be in format: Bearer <token>"
        )

    token = parts[1]
    payload = decode_access_token(token)

    # Ensure required claims are present
    if not payload.get("sub"):
        raise AuthenticationError("Token is missing subject claim")

    return payload


async def get_current_tenant(
    request: Request,
    user: dict[str, Any] = Depends(get_current_user),
) -> str:
    """Extract the tenant ID from the authenticated user's token.

    Also sets the tenant ID on the request state for downstream
    middleware and database query filtering.

    Args:
        request: The current HTTP request.
        user: The decoded JWT payload (injected via ``get_current_user``).

    Returns:
        The tenant ID string.

    Raises:
        AuthenticationError: If no tenant ID is found in the token.
    """
    settings = get_settings()

    if not settings.multi_tenant_enabled:
        tenant_id = settings.default_tenant_name
    else:
        tenant_id = user.get("tenant_id")
        if not tenant_id:
            raise AuthenticationError("Token is missing tenant_id claim")

    request.state.tenant_id = tenant_id
    return tenant_id


def require_role(*roles: RoleName):
    """Create a dependency that enforces role-based access.

    Args:
        *roles: One or more role names that are allowed access.

    Returns:
        A FastAPI dependency function.

    Usage::

        @router.delete("/users/{user_id}")
        async def delete_user(
            user: dict = Depends(require_role(RoleName.ADMIN)),
        ):
            ...
    """

    async def _check_role(
        user: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        user_role = user.get("role", "")
        if user_role not in {r.value for r in roles}:
            raise AuthorizationError(
                message=f"This action requires one of these roles: {', '.join(r.value for r in roles)}",
            )
        return user

    return _check_role


def require_permission(permission: Permission):
    """Create a dependency that enforces a specific permission.

    Permissions are derived from the user's role via the
    ``ROLE_PERMISSIONS`` mapping in ``constants.py``.

    Args:
        permission: The required permission.

    Returns:
        A FastAPI dependency function.

    Usage::

        @router.post("/documents")
        async def upload_document(
            user: dict = Depends(require_permission(Permission.DOCUMENT_UPLOAD)),
        ):
            ...
    """

    async def _check_permission(
        user: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        user_role_str = user.get("role", "")
        try:
            user_role = RoleName(user_role_str)
        except ValueError:
            raise AuthorizationError(
                message=f"Unknown role: {user_role_str}",
            )

        role_perms = ROLE_PERMISSIONS.get(user_role, set())
        if permission not in role_perms:
            raise AuthorizationError(
                message=f"Missing required permission: {permission.value}",
                required_permission=permission.value,
            )
        return user

    return _check_permission


async def get_optional_user(
    authorization: str | None = Header(None, alias="Authorization"),
) -> dict[str, Any] | None:
    """Optionally extract the current user — returns ``None`` if no token.

    Useful for routes that work both authenticated and anonymously
    but provide additional features when authenticated.

    Args:
        authorization: The Authorization header value.

    Returns:
        Decoded JWT payload, or ``None`` if no valid token is provided.
    """
    if not authorization:
        return None

    try:
        return await get_current_user(authorization)
    except AuthenticationError:
        return None
