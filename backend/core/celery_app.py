from datetime import timedelta
from celery import Celery
from backend.config import settings

app = Celery(
    "rag_platform",
    broker=settings.REDIS_URL,
    backend=None,
    include=["backend.core.tasks", "backend.core.scheduler"],
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "daily-crawl": {
            "task": "backend.core.scheduler.daily_crawl",
            "schedule": timedelta(hours=24),
        },
    },
)
