"""Async SQLAlchemy session factory and database connection management.

Provides:
- Async engine creation with connection pooling
- Async session factory for request-scoped sessions
- ``get_db`` dependency for FastAPI route injection
- ``get_redis`` dependency for Redis connection (or in-memory fallback)

Usage in FastAPI routes::

    @router.get("/items")
    async def list_items(db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(Item))
        return result.scalars().all()
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Module-level singletons — initialized lazily
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_redis_pool: Any | None = None
_using_memory_cache: bool = False


# ── In-Memory Cache Fallback ─────────────────────────────────────────────

class InMemoryCache:
    """Minimal Redis-compatible in-memory cache for lite mode.

    Implements only the subset of Redis methods used by the application
    so it can serve as a drop-in replacement when Redis is unavailable.
    """

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._store[key] = value

    async def setex(self, key: str, seconds: int, value: str) -> None:
        self._store[key] = value

    async def incr(self, key: str) -> int:
        val = int(self._store.get(key, 0)) + 1
        self._store[key] = str(val)
        return val

    async def expire(self, key: str, seconds: int) -> None:
        pass  # No TTL in memory cache

    async def delete(self, *keys: str) -> None:
        for k in keys:
            self._store.pop(k, None)

    async def exists(self, key: str) -> int:
        return 1 if key in self._store else 0

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        self._store.clear()


# ── Database Engine ──────────────────────────────────────────────────────


def get_engine() -> AsyncEngine:
    """Get or create the async SQLAlchemy engine.

    The engine is created once and reused for the lifetime of the process.
    Connection pool settings are loaded from application configuration.

    Returns:
        The async SQLAlchemy engine.
    """
    global _engine  # noqa: PLW0603
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            echo=settings.database_echo,
            pool_pre_ping=True,
            pool_recycle=3600,
            connect_args={
                "server_settings": {
                    "application_name": settings.app_name,
                },
            },
        )
        logger.info(
            "Database engine created",
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the async session factory.

    Returns:
        An ``async_sessionmaker`` bound to the application engine.
    """
    global _session_factory  # noqa: PLW0603
    if _session_factory is None:
        engine = get_engine()
        _session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session.

    The session is automatically committed on success and rolled back
    on exception. It is always closed when the request completes.

    Yields:
        An ``AsyncSession`` scoped to the current request.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Redis / In-Memory Cache ──────────────────────────────────────────────


async def get_redis() -> AsyncGenerator[Any, None]:
    """FastAPI dependency that yields a Redis connection (or in-memory fallback).

    In lite mode, or if Redis is unreachable, returns an ``InMemoryCache``
    instance that implements the same interface.

    Yields:
        An async Redis client instance or InMemoryCache.
    """
    global _redis_pool, _using_memory_cache  # noqa: PLW0603
    if _redis_pool is None:
        settings = get_settings()
        if settings.lite_mode:
            _redis_pool = InMemoryCache()
            _using_memory_cache = True
            logger.info("Using in-memory cache (lite mode)")
        else:
            try:
                import redis.asyncio as aioredis

                _redis_pool = aioredis.from_url(
                    settings.redis_url,
                    password=settings.redis_password or None,
                    encoding="utf-8",
                    decode_responses=True,
                    max_connections=20,
                )
                # Test connectivity
                await _redis_pool.ping()
                _using_memory_cache = False
                logger.info("Redis connection pool created")
            except Exception as exc:
                logger.warning("Redis unavailable, falling back to in-memory cache", error=str(exc))
                _redis_pool = InMemoryCache()
                _using_memory_cache = True
    yield _redis_pool


async def close_db() -> None:
    """Close the database engine and dispose of the connection pool.

    Call this during application shutdown to cleanly release resources.
    """
    global _engine, _session_factory  # noqa: PLW0603
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database engine disposed")


async def close_redis() -> None:
    """Close the Redis connection pool (or in-memory cache).

    Call this during application shutdown.
    """
    global _redis_pool, _using_memory_cache  # noqa: PLW0603
    if _redis_pool is not None:
        await _redis_pool.close()
        _redis_pool = None
        _using_memory_cache = False
        logger.info("Cache connection closed")


async def check_db_connectivity() -> bool:
    """Test database connectivity for health checks.

    Returns:
        ``True`` if the database is reachable, ``False`` otherwise.
    """
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(
                __import__("sqlalchemy").text("SELECT 1")
            )
        return True
    except Exception:
        logger.error("Database connectivity check failed", exc_info=True)
        return False


async def check_redis_connectivity() -> bool:
    """Test Redis connectivity for health checks.

    In lite mode or when using in-memory cache, always returns True.

    Returns:
        ``True`` if Redis (or fallback) is reachable, ``False`` otherwise.
    """
    global _redis_pool, _using_memory_cache  # noqa: PLW0603

    settings = get_settings()
    if settings.lite_mode or _using_memory_cache:
        return True

    try:
        if _redis_pool is None:
            import redis.asyncio as aioredis

            _redis_pool = aioredis.from_url(
                settings.redis_url,
                password=settings.redis_password or None,
                encoding="utf-8",
                decode_responses=True,
            )
        pong = await _redis_pool.ping()
        return bool(pong)
    except Exception:
        logger.warning("Redis connectivity check failed", exc_info=True)
        return False
async def check_chromadb_connectivity() -> bool:
    """Test ChromaDB connectivity for health checks.

    Returns:
        ``True`` if ChromaDB is reachable, ``False`` otherwise.
    """
    try:
        import chromadb

        settings = get_settings()
        client = chromadb.HttpClient(
            host=settings.chromadb_host,
            port=settings.chromadb_port,
        )
        client.heartbeat()
        return True
    except Exception:
        logger.warning("ChromaDB connectivity check failed", exc_info=True)
        return False
