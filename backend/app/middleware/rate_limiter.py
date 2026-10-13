"""Redis-based sliding window rate limiter middleware.

Implements a fixed-window rate limiting strategy using Redis INCR with TTL.
Each client (identified by IP or user ID) is allowed a configurable number
of requests per time window. When exceeded, a 429 response is returned.

The rate limiter runs as ASGI middleware so it applies to all routes
before they reach the application. Health and metrics endpoints are
excluded by default.
"""

from __future__ import annotations

import time
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Endpoints excluded from rate limiting
EXCLUDED_PATHS: frozenset[str] = frozenset({
    "/health",
    "/readiness",
    "/metrics",
})


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding window rate limiter using Redis.

    Each client gets ``max_requests`` requests per ``window_seconds``
    time window. The client is identified by:
    1. The ``X-Forwarded-For`` header (if behind a proxy)
    2. The client's IP address

    When the rate limit is exceeded, a JSON 429 response is returned
    with a ``Retry-After`` header indicating when the client can retry.
    """

    def __init__(self, app: Any, redis: Any = None) -> None:
        super().__init__(app)
        self._redis = redis
        settings = get_settings()
        self._max_requests = settings.rate_limit_requests
        self._window_seconds = settings.rate_limit_window_seconds

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Process the request through the rate limiter.

        Args:
            request: The incoming HTTP request.
            call_next: The next middleware or route handler.

        Returns:
            The response, or a 429 JSON response if rate limited.
        """
        # Skip rate limiting for health/metrics endpoints
        if request.url.path in EXCLUDED_PATHS:
            return await call_next(request)

        # Skip if Redis is not configured
        if self._redis is None:
            return await call_next(request)

        client_id = _get_client_identifier(request)
        window_key = f"ratelimit:{client_id}:{int(time.time()) // self._window_seconds}"

        try:
            pipe = self._redis.pipeline()
            pipe.incr(window_key)
            pipe.expire(window_key, self._window_seconds)
            results = await pipe.execute()
            request_count = results[0]

            if request_count > self._max_requests:
                retry_after = self._window_seconds - (int(time.time()) % self._window_seconds)
                logger.warning(
                    "Rate limit exceeded",
                    client_id=client_id,
                    request_count=request_count,
                    max_requests=self._max_requests,
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": "Too many requests",
                            "details": {
                                "retry_after_seconds": retry_after,
                                "limit": self._max_requests,
                                "window_seconds": self._window_seconds,
                            },
                        }
                    },
                    headers={"Retry-After": str(retry_after)},
                )

            # Add rate limit headers to successful responses
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(self._max_requests)
            response.headers["X-RateLimit-Remaining"] = str(
                max(0, self._max_requests - request_count)
            )
            response.headers["X-RateLimit-Window"] = str(self._window_seconds)
            return response

        except Exception:
            # If Redis is down, allow the request through (fail-open)
            logger.error("Rate limiter Redis error — failing open", exc_info=True)
            return await call_next(request)


def _get_client_identifier(request: Request) -> str:
    """Extract client identifier for rate limiting.

    Uses X-Forwarded-For header if present (proxy environments),
    otherwise falls back to the direct client IP.

    Args:
        request: The incoming HTTP request.

    Returns:
        A string identifying the client.
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
