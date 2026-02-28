from celery import Celery
from helpers.config import get_settings

settings = get_settings()

celery_app = Celery(
    "rose_blanche",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["tasks.ingestion_tasks"],
)

# ── Celery configuration ──
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    result_expires=3600,  # results expire after 1 hour
    worker_prefetch_multiplier=1,  # one task at a time (heavy embedding work)
    worker_max_tasks_per_child=10,  # restart worker after 10 tasks (memory safety)
    task_acks_late=True,  # acknowledge after completion (retry on crash)

    # ── Celery Beat schedule ──
    beat_schedule={
        "health-check-every-5-minutes": {
            "task": "tasks.ingestion_tasks.health_check",
            "schedule": 300.0,  # every 5 minutes
        },
        "auto-reingest-daily": {
            "task": "tasks.ingestion_tasks.scheduled_reingest",
            "schedule": 86400.0,  # every 24 hours
            "kwargs": {"chunk_size": 500, "overlap_size": 50},
        },
    },
)
