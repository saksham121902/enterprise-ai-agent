"""Centralized application configuration using Pydantic Settings.

All configuration values are loaded from environment variables with sensible
defaults for local development. In production, values should be set via
environment variables, Docker secrets, or a secrets management system.

Configuration is accessed via the ``get_settings()`` singleton factory.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

try:
    from pydantic import BaseModel, Field, field_validator
    try:
        from pydantic_settings import BaseSettings, SettingsConfigDict
    except ImportError:
        class BaseSettings(BaseModel):  # type: ignore[no-redef]
            """Fallback BaseSettings when pydantic-settings is not installed."""
            model_config = {"extra": "allow"}

        def SettingsConfigDict(**kwargs: Any) -> dict[str, Any]:  # type: ignore[no-redef]
            return kwargs
except ImportError:
    class BaseModel:  # type: ignore[no-redef]
        def __init__(self, **kwargs: Any) -> None:
            for k, v in kwargs.items():
                setattr(self, k, v)

    class BaseSettings(BaseModel):  # type: ignore[no-redef]
        pass

    def Field(default: Any = None, **kwargs: Any) -> Any:  # type: ignore[no-redef]
        return default

    def field_validator(*args: Any, **kwargs: Any) -> Any:  # type: ignore[no-redef]
        def decorator(fn: Any) -> Any:
            return fn
        return decorator

    def SettingsConfigDict(**kwargs: Any) -> dict[str, Any]:  # type: ignore[no-redef]
        return kwargs


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Uses Pydantic Settings to validate and type-check all configuration.
    Values can be overridden via ``.env`` file or environment variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────
    app_name: str = "Enterprise AI Agent"
    app_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = False
    secret_key: str = "change-this-to-a-random-secret-in-production"
    api_v1_prefix: str = "/api/v1"
    allowed_hosts: list[str] = Field(default=["*"])

    # ── Lite Mode ────────────────────────────────────────────────────────
    # When True, the app runs with only FastAPI + PostgreSQL + ChromaDB.
    # Redis, Celery, Neo4j, Jaeger are not required.
    lite_mode: bool = False

    # ── Demo Mode ────────────────────────────────────────────────────────
    # When True, enables demo login, per-IP rate limiting, and token budget.
    demo_mode: bool = False
    demo_daily_token_budget: int = 50000
    demo_rate_limit_per_ip: int = 20
    demo_rate_limit_window_seconds: int = 60

    # ── Database (PostgreSQL) ────────────────────────────────────────────
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/enterprise_ai"
    )
    database_pool_size: int = 20
    database_max_overflow: int = 10
    database_echo: bool = False

    # ── Redis ────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    redis_password: str = ""

    # ── Celery ───────────────────────────────────────────────────────────
    celery_broker_url: str = "amqp://guest:guest@localhost:5672//"
    celery_result_backend: str = "redis://localhost:6379/1"

    # ── ChromaDB ─────────────────────────────────────────────────────────
    chromadb_host: str = "localhost"
    chromadb_port: int = 8001

    # ── Neo4j ────────────────────────────────────────────────────────────
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "enterprise_ai_neo4j"

    # ── JWT Authentication ───────────────────────────────────────────────
    jwt_secret_key: str = "change-this-to-a-random-jwt-secret-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # ── LLM Providers ───────────────────────────────────────────────────
    llm_primary_provider: str = "openai"
    llm_fallback_providers: list[str] = Field(default=["anthropic", "google"])

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-small"

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    # Google
    google_api_key: str = ""
    google_model: str = "gemini-2.0-flash"

    # Azure OpenAI
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_deployment: str = ""
    azure_openai_api_version: str = "2024-02-01"

    # Ollama (Local)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"

    # ── Secrets Management ───────────────────────────────────────────────
    secrets_provider: str = "env"
    vault_url: str = ""
    vault_token: str = ""
    vault_mount_point: str = "secret"
    aws_region: str = ""
    aws_secret_name: str = ""
    azure_vault_url: str = ""

    # ── Multi-Tenant ─────────────────────────────────────────────────────
    default_tenant_name: str = "default"
    multi_tenant_enabled: bool = False

    # ── CORS ─────────────────────────────────────────────────────────────
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"]
    )
    cors_allow_credentials: bool = True

    # ── Rate Limiting ────────────────────────────────────────────────────
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60

    # ── File Upload ──────────────────────────────────────────────────────
    upload_dir: str = "./uploads"
    max_upload_size_mb: int = 50
    allowed_upload_extensions: list[str] = Field(
        default=[".pdf", ".docx", ".txt", ".xlsx", ".csv"]
    )

    # ── Observability ────────────────────────────────────────────────────
    otlp_endpoint: str = "http://localhost:4317"
    prometheus_enabled: bool = True
    jaeger_enabled: bool = False
    log_level: str = "INFO"
    log_format: str = "console"

    # ── LangSmith / Tracing (optional) ───────────────────────────────────
    langsmith_api_key: str = ""
    langsmith_project: str = "enterprise-ai-agent"
    langsmith_tracing_enabled: bool = False

    # ── Email ────────────────────────────────────────────────────────────
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@enterprise-ai.local"

    # ── Derived Properties ───────────────────────────────────────────────

    @property
    def sync_database_url(self) -> str:
        """Database URL with synchronous driver, used by Alembic migrations."""
        return self.database_url.replace("+asyncpg", "+psycopg2")

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"

    @property
    def is_testing(self) -> bool:
        """Check if running in test environment."""
        return self.environment == "testing"

    @property
    def upload_path(self) -> Path:
        """Resolved upload directory path, created if needed."""
        path = Path(self.upload_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def max_upload_size_bytes(self) -> int:
        """Maximum upload size in bytes."""
        return self.max_upload_size_mb * 1024 * 1024

    # ── Validators ───────────────────────────────────────────────────────

    @field_validator(
        "cors_origins",
        "llm_fallback_providers",
        "allowed_upload_extensions",
        "allowed_hosts",
        mode="before",
    )
    @classmethod
    def parse_json_list(cls, v: Any) -> list[str]:
        """Parse JSON-encoded lists from environment variables.

        Supports both JSON arrays (``["a","b"]``) and comma-separated
        strings (``a,b``) for convenience.
        """
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            return [item.strip() for item in v.split(",") if item.strip()]
        return v  # type: ignore[return-value]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get the cached application settings singleton.

    Settings are loaded once from environment and cached for the lifetime
    of the process. Call this function to access configuration anywhere
    in the application.

    Returns:
        The application Settings instance.
    """
    return Settings()
