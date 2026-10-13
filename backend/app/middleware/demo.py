"""Demo mode middleware — per-IP rate limiting and daily token budget.

Enabled when DEMO_MODE=true. Protects the live demo from abuse:
- Per-IP request rate limiting (sliding window, in-memory)
- Daily token budget cap across all demo users
- Demo-specific headers in responses
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings

logger = structlog.get_logger("demo")


class DemoRateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP rate limiter for demo mode.

    Uses a simple in-memory sliding window counter.
    Not suitable for multi-process deployments — but fine for a
    single-instance demo on Render/Railway.
    """

    def __init__(self, app: Any) -> None:
        super().__init__(app)
        # IP → list of request timestamps
        self._requests: dict[str, list[float]] = defaultdict(list)
        # Daily token counter (resets daily)
        self._daily_tokens: int = 0
        self._daily_reset_date: str = ""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        settings = get_settings()
        if not settings.demo_mode:
            return await call_next(request)

        # Skip rate limiting for health/metrics/static
        path = request.url.path
        if path in {"/health", "/readiness", "/metrics"} or path.startswith("/assets"):
            return await call_next(request)

        # Get client IP
        client_ip = self._get_client_ip(request)

        # Check per-IP rate limit
        now = time.time()
        window = settings.demo_rate_limit_window_seconds
        max_requests = settings.demo_rate_limit_per_ip

        # Clean old entries and count recent requests
        self._requests[client_ip] = [
            ts for ts in self._requests[client_ip]
            if now - ts < window
        ]

        if len(self._requests[client_ip]) >= max_requests:
            logger.warning("Demo rate limit hit", client_ip=client_ip)
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "DEMO_RATE_LIMIT",
                        "message": f"Demo rate limit: max {max_requests} requests per {window}s. "
                                   "Deploy your own instance for unlimited access.",
                        "details": {"retry_after_seconds": window},
                    }
                },
            )

        self._requests[client_ip].append(now)

        # Check daily token budget (only for chat endpoints)
        if "/chat/message" in path:
            today = time.strftime("%Y-%m-%d")
            if today != self._daily_reset_date:
                self._daily_tokens = 0
                self._daily_reset_date = today

            if self._daily_tokens >= settings.demo_daily_token_budget:
                logger.warning("Demo daily token budget exhausted")
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "DEMO_TOKEN_BUDGET",
                            "message": "Daily demo token budget exhausted. "
                                       "Budget resets at midnight UTC. "
                                       "Deploy your own instance for unlimited access.",
                            "details": {
                                "daily_budget": settings.demo_daily_token_budget,
                                "tokens_used": self._daily_tokens,
                            },
                        }
                    },
                )

        response = await call_next(request)

        # Track tokens from chat responses
        if "/chat/message" in path and response.status_code == 200:
            # Approximate token tracking from response headers
            # (actual tracking happens in chat_service)
            self._daily_tokens += 500  # Rough estimate per request

        # Add demo mode headers
        response.headers["X-Demo-Mode"] = "true"
        remaining = max(0, max_requests - len(self._requests[client_ip]))
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP, respecting X-Forwarded-For for proxied deployments."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def add_tokens(self, count: int) -> None:
        """Add tokens to the daily counter (called by chat service)."""
        self._daily_tokens += count

    @property
    def daily_tokens_used(self) -> int:
        return self._daily_tokens


# Global instance for token tracking from chat service
_demo_middleware: DemoRateLimitMiddleware | None = None


def get_demo_middleware() -> DemoRateLimitMiddleware | None:
    return _demo_middleware


def set_demo_middleware(middleware: DemoRateLimitMiddleware) -> None:
    global _demo_middleware  # noqa: PLW0603
    _demo_middleware = middleware
