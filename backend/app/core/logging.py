"""Structured logging configuration using structlog.

Provides JSON-formatted logs in production and colorized console output
in development. All log entries automatically include:

- ISO 8601 timestamps
- Log level
- Logger name
- Context variables (request ID, tenant ID, etc.) via ``structlog.contextvars``

Usage::

    from app.core.logging import get_logger

    logger = get_logger(__name__)
    logger.info("Processing document", document_id="abc-123", size_bytes=4096)
"""

from __future__ import annotations

import logging
import sys
from typing import Any

try:
    import structlog
except ImportError:
    structlog = None  # type: ignore[assignment]


class _StdlibLoggerWrapper:
    """Fallback logger wrapper mimicking structlog API using standard logging."""

    def __init__(self, name: str | None = None, **context: Any) -> None:
        self._logger = logging.getLogger(name or "app")
        self._context = context

    def bind(self, **kwargs: Any) -> _StdlibLoggerWrapper:
        new_ctx = {**self._context, **kwargs}
        return _StdlibLoggerWrapper(self._logger.name, **new_ctx)

    def _fmt(self, msg: str, kw: dict[str, Any]) -> str:
        from app.core.guardrails import redact_pii
        ctx = {**self._context, **kw}
        raw = f"{msg} | {ctx}" if ctx else msg
        return redact_pii(raw)

    def info(self, msg: str, **kwargs: Any) -> None:
        self._logger.info(self._fmt(msg, kwargs))

    def warning(self, msg: str, **kwargs: Any) -> None:
        self._logger.warning(self._fmt(msg, kwargs))

    def error(self, msg: str, **kwargs: Any) -> None:
        self._logger.error(self._fmt(msg, kwargs))

    def debug(self, msg: str, **kwargs: Any) -> None:
        self._logger.debug(self._fmt(msg, kwargs))

    def exception(self, msg: str, **kwargs: Any) -> None:
        self._logger.exception(self._fmt(msg, kwargs))


def setup_logging(
    log_level: str = "INFO",
    log_format: str = "json",
    app_name: str = "enterprise-ai-agent",
) -> None:
    """Configure structured logging for the entire application.

    This should be called once at startup, before any other module logs.

    Args:
        log_level: Minimum log level (``DEBUG``, ``INFO``, ``WARNING``,
            ``ERROR``, ``CRITICAL``).
        log_format: Output format — ``json`` for production (machine-parseable),
            ``console`` for development (colorized, human-readable).
        app_name: Application name included in every log entry.
    """
    # Shared processors applied to every log entry
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.ExtraAdder(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if log_format == "json":
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True, pad_event=50)

    # Configure structlog
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Bridge standard library logging to structlog
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    root_handler = logging.StreamHandler(sys.stdout)
    root_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(root_handler)
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Suppress noisy third-party loggers
    noisy_loggers = [
        "uvicorn.access",
        "uvicorn.error",
        "sqlalchemy.engine",
        "httpx",
        "httpcore",
        "chromadb",
        "neo4j",
        "celery",
        "celery.worker",
        "celery.app.trace",
        "amqp",
        "opentelemetry",
    ]
    for noisy in noisy_loggers:
        logging.getLogger(noisy).setLevel(logging.WARNING)

    structlog.get_logger().info(
        "Logging configured",
        log_level=log_level,
        log_format=log_format,
        app_name=app_name,
    )


def get_logger(
    name: str | None = None,
    **initial_context: Any,
) -> Any:
    """Get a structured logger instance with optional initial context."""
    if structlog is None:
        return _StdlibLoggerWrapper(name, **initial_context)

    log: Any = structlog.get_logger(name)
    if initial_context:
        log = log.bind(**initial_context)
    return log
