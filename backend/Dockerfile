# =============================================================================
# Enterprise AI Agent — Backend Dockerfile
# Multi-stage build for minimal production image
# =============================================================================

# ── Stage 1: Dependency Builder ──────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install system dependencies required for building Python packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment for clean dependency isolation
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies (cached layer — only rebuilds when pyproject.toml changes)
COPY pyproject.toml ./
RUN mkdir -p app && \
    echo '"""Package init."""' > app/__init__.py && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir "." && \
    rm -rf app

# ── Stage 2: Production Runtime ─────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Install only runtime system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r appuser && \
    useradd -r -g appuser -d /app -s /sbin/nologin appuser

# Copy virtual environment from builder (contains all installed packages)
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

# Copy application source code
COPY ./app ./app
COPY ./alembic.ini ./alembic.ini

# Copy prompt templates (if they exist at build time)
COPY ./prompt[s] ./prompts

# Create directories and set ownership
RUN mkdir -p /app/uploads /app/logs && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Health check for Docker and orchestrators
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run with uvicorn — use --factory for the app factory pattern
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
