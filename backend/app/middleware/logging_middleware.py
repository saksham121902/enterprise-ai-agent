"""Request/response logging middleware with structured context.

Logs every HTTP request with:
- Method, path, status code
- Processing time
- Request ID (generated or from X-Request-ID header)
- Client IP
- User agent

The request ID is added to structlog's context variables so all
subsequent log entries within the request include it automatically.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.telemetry import HTTP_REQUEST_DURATION, HTTP_REQUESTS_TOTAL

# Paths excluded from detailed request logging (too noisy)
QUIET_PATHS: frozenset[str] = frozenset({
    "/health",
    "/readiness",
    "/metrics",
})


class LoggingMiddleware(BaseHTTPMiddleware):
    """Structured HTTP request/response logging middleware.

    Generates a unique request ID for each request (or uses the
    incoming ``X-Request-ID`` header) and binds it to structlog's
    context variables for automatic inclusion in all log entries.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Log the request and response with timing and context.

        Args:
            request: The incoming HTTP request.
            call_next: The next middleware or route handler.

        Returns:
            The response with added tracing headers.
        """
        # Generate or extract request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # Bind request context to structlog for this request's lifetime
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        start_time = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            process_time = time.perf_counter() - start_time
            _log_request(request, 500, process_time, request_id)
            HTTP_REQUESTS_TOTAL.labels(
                method=request.method,
                endpoint=_normalize_path(request.url.path),
                status_code="500",
            ).inc()
            HTTP_REQUEST_DURATION.labels(
                method=request.method,
                endpoint=_normalize_path(request.url.path),
            ).observe(process_time)
            raise

        process_time = time.perf_counter() - start_time

        # Add tracing headers to response
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{process_time:.4f}"

        # Log and record metrics
        _log_request(request, response.status_code, process_time, request_id)

        normalized_path = _normalize_path(request.url.path)
        HTTP_REQUESTS_TOTAL.labels(
            method=request.method,
            endpoint=normalized_path,
            status_code=str(response.status_code),
        ).inc()
        HTTP_REQUEST_DURATION.labels(
            method=request.method,
            endpoint=normalized_path,
        ).observe(process_time)

        return response


def _log_request(
    request: Request,
    status_code: int,
    process_time: float,
    request_id: str,
) -> None:
    """Emit a structured log entry for the request.

    Quiet paths (health, metrics) are logged at DEBUG level to
    avoid noise. All other requests are logged at INFO level.

    Args:
        request: The HTTP request.
        status_code: The response status code.
        process_time: Request processing duration in seconds.
        request_id: The unique request identifier.
    """
    log = structlog.get_logger("http")
    log_data: dict[str, Any] = {
        "status_code": status_code,
        "process_time_ms": round(process_time * 1000, 2),
        "client_ip": request.client.host if request.client else "unknown",
    }

    if request.url.path in QUIET_PATHS:
        log.debug("HTTP request", **log_data)
    elif status_code >= 500:
        log.error("HTTP request failed", **log_data)
    elif status_code >= 400:
        log.warning("HTTP client error", **log_data)
    else:
        log.info("HTTP request", **log_data)


def _normalize_path(path: str) -> str:
    """Normalize URL path for metric labels.

    Replaces UUID-like segments and numeric IDs with placeholders
    to prevent metric cardinality explosion.

    Args:
        path: The raw URL path.

    Returns:
        Normalized path string suitable for metric labels.
    """
    parts = path.strip("/").split("/")
    normalized: list[str] = []
    for part in parts:
        # Replace UUIDs
        if len(part) == 36 and part.count("-") == 4:
            normalized.append("{id}")
        # Replace numeric IDs
        elif part.isdigit():
            normalized.append("{id}")
        else:
            normalized.append(part)
    return "/" + "/".join(normalized) if normalized else "/"
