"""Multi-tenant context injection middleware.

Extracts the tenant ID from the authenticated user's JWT token and
binds it to the request state and structlog context. This enables
automatic tenant-scoped database queries downstream.

When multi-tenancy is disabled (single-tenant mode), all requests
use the configured default tenant.
"""

from __future__ import annotations

from typing import Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import get_settings

# Paths that don't require tenant context
TENANT_EXEMPT_PATHS: frozenset[str] = frozenset({
    "/health",
    "/readiness",
    "/metrics",
    "/seed",
})


class TenantMiddleware(BaseHTTPMiddleware):
    """Injects tenant context into every request.

    The tenant ID is extracted from the JWT token's ``tenant_id`` claim
    (set during authentication). If multi-tenancy is disabled, the
    default tenant is used for all requests.

    The tenant ID is stored in:
    1. ``request.state.tenant_id`` — for route handlers
    2. ``structlog.contextvars`` — for automatic log enrichment
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Extract and bind tenant context.

        Args:
            request: The incoming HTTP request.
            call_next: The next middleware or route handler.

        Returns:
            The response from downstream handlers.
        """
        if request.url.path in TENANT_EXEMPT_PATHS:
            return await call_next(request)

        settings = get_settings()

        if not settings.multi_tenant_enabled:
            # Single-tenant mode — use default tenant
            tenant_id = settings.default_tenant_name
        else:
            # Multi-tenant mode — extract from request state
            # (set by auth dependency after JWT decode)
            tenant_id = getattr(request.state, "tenant_id", settings.default_tenant_name)

        # Bind to request state for downstream access
        request.state.tenant_id = tenant_id

        # Bind to structlog context for automatic log enrichment
        structlog.contextvars.bind_contextvars(tenant_id=tenant_id)

        return await call_next(request)
