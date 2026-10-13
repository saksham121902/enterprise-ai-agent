"""Celery application factory and task configuration.

Creates the Celery instance with:
- RabbitMQ broker + Redis result backend
- Multiple named queues (documents, embeddings, reports, emails)
- Dead Letter Queue (DLQ) for failed tasks
- Retry policies with exponential backoff
- Task serialization and result expiry settings

Usage::

    # Start worker:
    celery -A app.workers.celery_app worker --loglevel=info

    # Start beat scheduler:
    celery -A app.workers.celery_app beat --loglevel=info
"""

from __future__ import annotations

from celery import Celery

from app.core.config import get_settings
from app.core.constants import (
    CELERY_QUEUE_DEFAULT,
    CELERY_QUEUE_DOCUMENTS,
    CELERY_QUEUE_EMAILS,
    CELERY_QUEUE_EMBEDDINGS,
    CELERY_QUEUE_REPORTS,
    TASK_DLQ_ROUTING_KEY,
    TASK_MAX_RETRIES,
    TASK_RETRY_BACKOFF,
)

settings = get_settings()

celery_app = Celery(
    "enterprise_ai_agent",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Result management
    result_expires=3600,  # Results expire after 1 hour
    result_extended=True,

    # Worker settings
    worker_prefetch_multiplier=1,  # Fair distribution
    worker_max_tasks_per_child=200,  # Restart worker after 200 tasks (memory leak prevention)
    worker_max_memory_per_child=256_000,  # 256MB memory limit per worker child

    # Task execution
    task_acks_late=True,  # Acknowledge after execution (not before)
    task_reject_on_worker_lost=True,  # Requeue if worker crashes

    # Retry defaults
    task_default_retry_delay=TASK_RETRY_BACKOFF,
    task_max_retries=TASK_MAX_RETRIES,

    # Rate limiting
    task_default_rate_limit="100/m",

    # Queue configuration
    task_default_queue=CELERY_QUEUE_DEFAULT,
    task_queues={
        CELERY_QUEUE_DEFAULT: {
            "exchange": CELERY_QUEUE_DEFAULT,
            "routing_key": CELERY_QUEUE_DEFAULT,
        },
        CELERY_QUEUE_DOCUMENTS: {
            "exchange": CELERY_QUEUE_DOCUMENTS,
            "routing_key": CELERY_QUEUE_DOCUMENTS,
        },
        CELERY_QUEUE_EMBEDDINGS: {
            "exchange": CELERY_QUEUE_EMBEDDINGS,
            "routing_key": CELERY_QUEUE_EMBEDDINGS,
        },
        CELERY_QUEUE_REPORTS: {
            "exchange": CELERY_QUEUE_REPORTS,
            "routing_key": CELERY_QUEUE_REPORTS,
        },
        CELERY_QUEUE_EMAILS: {
            "exchange": CELERY_QUEUE_EMAILS,
            "routing_key": CELERY_QUEUE_EMAILS,
        },
        # Dead Letter Queue for permanently failed tasks
        TASK_DLQ_ROUTING_KEY: {
            "exchange": TASK_DLQ_ROUTING_KEY,
            "routing_key": TASK_DLQ_ROUTING_KEY,
        },
    },

    # Task routing
    task_routes={
        "app.workers.tasks.document_tasks.*": {"queue": CELERY_QUEUE_DOCUMENTS},
        "app.workers.tasks.embedding_tasks.*": {"queue": CELERY_QUEUE_EMBEDDINGS},
        "app.workers.tasks.report_tasks.*": {"queue": CELERY_QUEUE_REPORTS},
        "app.workers.tasks.email_tasks.*": {"queue": CELERY_QUEUE_EMAILS},
    },

    # Beat schedule (periodic tasks)
    beat_schedule={
        "cleanup-expired-tokens": {
            "task": "app.workers.tasks.maintenance_tasks.cleanup_expired_tokens",
            "schedule": 3600.0,  # Every hour
        },
        "aggregate-daily-costs": {
            "task": "app.workers.tasks.maintenance_tasks.aggregate_daily_costs",
            "schedule": 86400.0,  # Once per day
        },
    },
)

# Auto-discover tasks in the workers/tasks/ directory
celery_app.autodiscover_tasks(["app.workers.tasks"])
