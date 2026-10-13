"""OpenTelemetry instrumentation and Prometheus metrics definitions.

This module defines all application metrics and provides setup functions
for distributed tracing via OpenTelemetry (exported to Jaeger/OTLP).

Metrics are eagerly defined at module level so they can be imported and
used anywhere without initialization order concerns. The ``setup_telemetry``
function should be called once at app startup to configure trace exporting.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

try:
    from opentelemetry import trace
except ImportError:
    class _MockTrace:
        @staticmethod
        def get_tracer(*args: Any, **kwargs: Any) -> Any:
            class _MockTracer:
                def start_as_current_span(self, *a: Any, **kw: Any) -> Any:
                    import contextlib
                    return contextlib.nullcontext()
            return _MockTracer()

    trace = _MockTrace()  # type: ignore[assignment]

try:
    from prometheus_client import Counter, Gauge, Histogram, Info
except ImportError:
    class _MockMetric:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def labels(self, *args: Any, **kwargs: Any) -> Any:
            return self

        def inc(self, *args: Any, **kwargs: Any) -> None:
            pass

        def dec(self, *args: Any, **kwargs: Any) -> None:
            pass

        def set(self, *args: Any, **kwargs: Any) -> None:
            pass

        def observe(self, *args: Any, **kwargs: Any) -> None:
            pass

        def info(self, *args: Any, **kwargs: Any) -> None:
            pass

    Counter = Gauge = Histogram = Info = _MockMetric  # type: ignore[assignment,misc]

if TYPE_CHECKING:
    from fastapi import FastAPI


# ═════════════════════════════════════════════════════════════════════════
# Prometheus Metrics
# ═════════════════════════════════════════════════════════════════════════

APP_INFO = Info("app", "Application metadata")

# ── HTTP ─────────────────────────────────────────────────────────────────

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total number of HTTP requests received",
    ["method", "endpoint", "status_code"],
)

HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request processing duration in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# ── LLM ──────────────────────────────────────────────────────────────────

LLM_TOKENS_TOTAL = Counter(
    "llm_tokens_total",
    "Total LLM tokens consumed",
    ["provider", "model", "token_type"],
)

LLM_COST_DOLLARS = Counter(
    "llm_cost_dollars_total",
    "Cumulative LLM cost in USD",
    ["provider", "model"],
)

LLM_REQUEST_DURATION = Histogram(
    "llm_request_duration_seconds",
    "LLM API call duration in seconds",
    ["provider", "model"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

# ── Agents ───────────────────────────────────────────────────────────────

AGENT_EXECUTION_DURATION = Histogram(
    "agent_execution_duration_seconds",
    "Agent execution duration in seconds",
    ["agent_type", "model"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

AGENT_EXECUTIONS_TOTAL = Counter(
    "agent_executions_total",
    "Total agent executions",
    ["agent_type", "status"],
)

# ── Tools ────────────────────────────────────────────────────────────────

TOOL_EXECUTIONS_TOTAL = Counter(
    "tool_executions_total",
    "Total tool executions",
    ["tool_name", "status"],
)

TOOL_EXECUTION_DURATION = Histogram(
    "tool_execution_duration_seconds",
    "Tool execution duration in seconds",
    ["tool_name"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

# ── RAG ──────────────────────────────────────────────────────────────────

RAG_RETRIEVAL_DURATION = Histogram(
    "rag_retrieval_duration_seconds",
    "RAG semantic search duration in seconds",
    ["collection"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)

RAG_CHUNKS_RETRIEVED = Histogram(
    "rag_chunks_retrieved",
    "Number of chunks retrieved per RAG query",
    ["collection"],
    buckets=(1, 3, 5, 10, 15, 20, 30),
)

# ── WebSocket ────────────────────────────────────────────────────────────

ACTIVE_WEBSOCKET_CONNECTIONS = Gauge(
    "active_websocket_connections",
    "Number of currently active WebSocket connections",
)

# ── Celery Tasks ─────────────────────────────────────────────────────────

CELERY_TASKS_TOTAL = Counter(
    "celery_tasks_total",
    "Total Celery background tasks",
    ["task_name", "status"],
)

CELERY_TASK_DURATION = Histogram(
    "celery_task_duration_seconds",
    "Celery task execution duration in seconds",
    ["task_name"],
    buckets=(0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0),
)

# ── Documents ────────────────────────────────────────────────────────────

DOCUMENTS_PROCESSED_TOTAL = Counter(
    "documents_processed_total",
    "Total documents processed for RAG",
    ["document_type", "status"],
)

# ── Users ────────────────────────────────────────────────────────────────

ACTIVE_USERS = Gauge(
    "active_users",
    "Number of currently active users (based on recent activity)",
)


# ═════════════════════════════════════════════════════════════════════════
# OpenTelemetry Tracing Setup
# ═════════════════════════════════════════════════════════════════════════


def setup_telemetry(app: FastAPI, service_name: str, otlp_endpoint: str) -> None:
    """Initialize OpenTelemetry distributed tracing and instrument FastAPI.

    Configures a ``TracerProvider`` with an OTLP exporter that sends trace
    data to a collector (typically Jaeger). FastAPI is automatically
    instrumented so all incoming requests generate spans.

    Args:
        app: The FastAPI application instance to instrument.
        service_name: Service name for trace identification.
        otlp_endpoint: OTLP collector endpoint (e.g., ``http://jaeger:4317``).
    """
    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create(
            {
                "service.name": service_name,
                "service.version": "1.0.0",
            }
        )

        provider = TracerProvider(resource=resource)

        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

        trace.set_tracer_provider(provider)

        FastAPIInstrumentor.instrument_app(
            app,
            excluded_urls="health,readiness,metrics",
        )

        import structlog

        structlog.get_logger().info(
            "OpenTelemetry tracing initialized",
            service_name=service_name,
            otlp_endpoint=otlp_endpoint,
        )
    except ImportError:
        import structlog

        structlog.get_logger().warning(
            "OpenTelemetry SDK packages not installed — tracing is disabled. "
            "The application will continue to function normally without tracing."
        )
    except Exception as exc:
        import structlog

        structlog.get_logger().error(
            "Failed to initialize OpenTelemetry tracing",
            error=str(exc),
            exc_info=True,
        )


def get_tracer(name: str = "enterprise-ai-agent") -> trace.Tracer:
    """Get an OpenTelemetry tracer instance.

    If the SDK is not configured, this returns a no-op tracer from the
    ``opentelemetry-api`` package, so code using the tracer always works
    regardless of whether tracing is enabled.

    Args:
        name: Tracer name, typically the module's ``__name__``.

    Returns:
        An OpenTelemetry ``Tracer`` instance.
    """
    return trace.get_tracer(name)
