"""FastAPI application factory.

Creates and configures the FastAPI application with all middleware,
exception handlers, health endpoints, and lifecycle management.

The application uses the factory pattern (``create_app()``) to support:
- Multiple configurations (dev, test, prod)
- Clean testing with fresh app instances
- Uvicorn's ``--factory`` flag for production deployment

Usage::

    # Development
    uvicorn app.main:create_app --factory --reload

    # Production (via Dockerfile CMD)
    uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from app.api.v1.router import router as v1_router
from app.core.config import Settings, get_settings
from app.core.exceptions import AppException
from app.core.logging import setup_logging
from app.core.telemetry import APP_INFO, setup_telemetry
from app.database.session import (
    check_db_connectivity,
    check_redis_connectivity,
    close_db,
    close_redis,
)
from app.middleware.logging_middleware import LoggingMiddleware
from app.middleware.tenant import TenantMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifecycle manager.

    Handles initialization on startup and cleanup on shutdown.
    Database connections, Redis pools, and external clients are
    initialized here and cleaned up when the app shuts down.

    Args:
        app: The FastAPI application instance.
    """
    logger = structlog.get_logger("lifespan")
    settings = get_settings()

    logger.info(
        "Starting application",
        app_name=settings.app_name,
        environment=settings.environment,
        version=settings.app_version,
        lite_mode=settings.lite_mode,
        demo_mode=settings.demo_mode,
    )

    # Publish app metadata to Prometheus
    APP_INFO.info(
        {
            "version": settings.app_version,
            "environment": settings.environment,
        }
    )

    # Initialize OpenTelemetry tracing (skip in lite mode unless explicitly enabled)
    if settings.jaeger_enabled and not settings.lite_mode:
        setup_telemetry(
            app=app,
            service_name=settings.app_name.lower().replace(" ", "-"),
            otlp_endpoint=settings.otlp_endpoint,
        )

    # Initialize LangSmith tracing if configured
    if settings.langsmith_tracing_enabled and settings.langsmith_api_key:
        import os
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
    # Auto-seed database in demo/lite mode on startup (vital for platforms without shell access like Render free tier)
    if settings.demo_mode or settings.lite_mode:
        try:
            from app.seed import seed_database

            logger.info("Auto-seeding demo database on startup...")
            await seed_database()
            logger.info("Demo database auto-seeding completed")
        except Exception as exc:
            logger.warning("Auto-seeding skipped or already applied", error=str(exc))

    logger.info("Application startup complete")

    yield

    # Shutdown phase — clean up resources
    logger.info("Shutting down — cleaning up resources")
    await close_db()
    await close_redis()
    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    This is the main entry point called by Uvicorn. It:
    1. Configures structured logging
    2. Creates the FastAPI instance with OpenAPI docs
    3. Registers global exception handlers
    4. Attaches middleware (logging, tenant, rate limit, CORS)
    5. Registers API v1 router and health/observability endpoints

    Returns:
        A fully configured ``FastAPI`` application instance.
    """
    settings = get_settings()

    # Logging must be configured before anything else
    setup_logging(
        log_level=settings.log_level,
        log_format=settings.log_format,
        app_name=settings.app_name,
    )

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Production-ready Enterprise AI Operations Agent with multi-agent "
            "orchestration, RAG, knowledge graphs, and workflow automation."
        ),
        docs_url=f"{settings.api_v1_prefix}/docs",
        redoc_url=f"{settings.api_v1_prefix}/redoc",
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
    )

    _register_exception_handlers(app)
    _register_middleware(app, settings)
    _register_routers(app, settings)
    _register_health_routes(app, settings)

    return app


# ── Exception Handlers ───────────────────────────────────────────────────


def _register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers for consistent error responses."""

    @app.exception_handler(AppException)
    async def app_exception_handler(
        request: Request, exc: AppException
    ) -> ORJSONResponse:
        """Handle all ``AppException`` subclasses with structured JSON responses."""
        structlog.get_logger().error(
            "Application error",
            error_code=exc.error_code,
            status_code=exc.status_code,
            message=exc.message,
            path=str(request.url),
            method=request.method,
        )
        return ORJSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> ORJSONResponse:
        """Catch-all for unexpected exceptions — returns a generic 500."""
        structlog.get_logger().exception(
            "Unhandled exception",
            path=str(request.url),
            method=request.method,
            error_type=type(exc).__name__,
        )
        return ORJSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                    "details": {},
                }
            },
        )


# ── Middleware ────────────────────────────────────────────────────────────


def _register_middleware(app: FastAPI, settings: Settings) -> None:
    """Register middleware stack.

    Middleware is executed in reverse registration order (last registered
    = first executed). Order matters:

    1. CORS (outermost — handles preflight)
    2. Logging (generates request ID, logs request/response)
    3. Tenant (injects tenant context)
    4. Rate limiting (applied after auth context is available)
    """
    # Demo mode rate limiter (per-IP + token budget)
    if settings.demo_mode:
        from app.middleware.demo import DemoRateLimitMiddleware, set_demo_middleware

        demo_mw = DemoRateLimitMiddleware(app)
        app.add_middleware(DemoRateLimitMiddleware)
        set_demo_middleware(demo_mw)

    # Tenant context injection
    app.add_middleware(TenantMiddleware)

    # Request logging with request ID generation and Prometheus metrics
    app.add_middleware(LoggingMiddleware)

    # CORS — must be outermost middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=r"https://.*\.onrender\.com|http://.*",
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Process-Time"],
    )


# ── Routers ──────────────────────────────────────────────────────────────


def _register_routers(app: FastAPI, settings: Settings) -> None:
    """Register API routers and WebSocket endpoints."""
    app.include_router(
        v1_router,
        prefix=settings.api_v1_prefix,
    )

    _register_websocket_routes(app)


# ── WebSocket Routes ─────────────────────────────────────────────────────


def _register_websocket_routes(app: FastAPI) -> None:
    """Register WebSocket endpoint for real-time communication."""
    from app.api.websocket import ws_manager
    from app.core.security import decode_access_token

    @app.websocket("/ws/{room_id}")
    async def websocket_endpoint(
        websocket: WebSocket,
        room_id: str,
        token: str = Query(default=""),
    ) -> None:
        """WebSocket connection endpoint.

        Authenticates via ``token`` query parameter (JWT), then joins
        the specified room for real-time event streaming.
        """
        # Authenticate
        try:
            if not token:
                await websocket.close(code=4001, reason="Token required")
                return
            payload = decode_access_token(token)
            user_id = payload.get("sub", "")
        except Exception:
            await websocket.close(code=4003, reason="Invalid token")
            return

        # Connect and join rooms
        await ws_manager.connect(websocket, room_id)
        if user_id:
            await ws_manager.join_room(websocket, f"user:{user_id}")

        try:
            while True:
                data = await websocket.receive_json()
                event_type = data.get("event", "message")
                event_data = data.get("data", {})

                # Relay messages to the room
                await ws_manager.send_to_room(
                    room_id,
                    event=event_type,
                    data={"user_id": user_id, **event_data},
                )
        except WebSocketDisconnect:
            await ws_manager.disconnect(websocket)
        except Exception:
            await ws_manager.disconnect(websocket)


# ── Health & Observability Routes ────────────────────────────────────────


def _register_health_routes(app: FastAPI, settings: Settings) -> None:
    """Register health check and observability endpoints."""

    @app.get("/health", tags=["Health"], summary="Liveness probe")
    async def health_check() -> dict[str, str]:
        """Basic liveness check — returns 200 if the process is running."""
        return {
            "status": "healthy",
            "version": settings.app_version,
            "environment": settings.environment,
        }

    @app.api_route("/seed", methods=["GET", "POST"], tags=["Health"], summary="Idempotent database seed endpoint")
    async def trigger_seed_endpoint() -> dict[str, str]:
        """Trigger database seeding on platforms without shell access."""
        from app.seed import seed_database

        try:
            await seed_database()
            return {"status": "success", "message": "Database seeded successfully"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    @app.get("/readiness", tags=["Health"], summary="Readiness probe")
    async def readiness_check() -> dict[str, object]:
        """Readiness probe for deployment orchestrators and load balancers.

        Verifies connectivity to PostgreSQL and ChromaDB.
        In lite mode, Redis, Celery, Neo4j, and Jaeger are marked as disabled.
        Returns 200 if required dependencies are reachable, 503 otherwise.
        """
        from app.database.session import check_chromadb_connectivity

        db_ok = await check_db_connectivity()
        chroma_ok = await check_chromadb_connectivity()

        dependencies: dict[str, str] = {
            "postgresql": "connected" if db_ok else "unavailable",
            "chromadb": "connected" if chroma_ok else "unavailable",
        }

        if settings.lite_mode:
            dependencies["redis"] = "disabled (lite mode)"
            dependencies["celery"] = "disabled (lite mode)"
            dependencies["neo4j"] = "disabled (lite mode)"
            dependencies["jaeger_tracing"] = "disabled (lite mode)"
            is_ready = db_ok  # ChromaDB failure won't bring down basic app, but db is required
        else:
            redis_ok = await check_redis_connectivity()
            dependencies["redis"] = "connected" if redis_ok else "unavailable"
            dependencies["celery"] = "active"
            dependencies["neo4j"] = "active"
            dependencies["jaeger_tracing"] = "active"
            is_ready = db_ok and redis_ok

        status = "ready" if is_ready else "degraded"
        status_code = 200 if status == "ready" else 503

        result: dict[str, object] = {
            "status": status,
            "mode": "lite" if settings.lite_mode else "full",
            "demo_mode": settings.demo_mode,
            "dependencies": dependencies,
        }

        if status_code == 503:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=503, content=result)  # type: ignore[return-value]

        return result

    @app.get("/metrics", tags=["Observability"], summary="Prometheus metrics")
    async def prometheus_metrics() -> Response:
        """Expose Prometheus metrics in OpenMetrics text format."""
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )
