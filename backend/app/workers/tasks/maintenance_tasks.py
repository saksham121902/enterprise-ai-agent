"""Background maintenance tasks (scheduled via Celery Beat)."""

from __future__ import annotations

from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task(name="app.workers.tasks.maintenance_tasks.cleanup_expired_tokens")
def cleanup_expired_tokens() -> dict[str, str]:
    """Remove expired refresh tokens and session data.

    Scheduled to run every hour via Celery Beat.
    """
    logger.info("Running expired token cleanup")
    # Implementation will be added when Redis token blacklisting is built
    return {"status": "completed", "task": "cleanup_expired_tokens"}


@shared_task(name="app.workers.tasks.maintenance_tasks.aggregate_daily_costs")
def aggregate_daily_costs() -> dict[str, str]:
    """Aggregate daily LLM cost data for the analytics dashboard.

    Scheduled to run once per day via Celery Beat.
    """
    logger.info("Running daily cost aggregation")
    # Implementation will be added when analytics is built
    return {"status": "completed", "task": "aggregate_daily_costs"}
