"""
Celery application configuration for Payment Compliance Monitor.

This module configures Celery for asynchronous task processing,
including queue definitions for the crawl pipeline architecture.

Requirements: 16.1, 16.2, 16.4, 16.5
"""

import logging
import os

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_init
from kombu import Queue

logger = logging.getLogger(__name__)

# Get Redis URL from environment
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# ---------------------------------------------------------------------------
# Queue definitions for pipeline architecture (Req 16.1)
# ---------------------------------------------------------------------------
PIPELINE_QUEUES = (
    Queue('celery', routing_key='celery'),       # default queue
    Queue('crawl', routing_key='crawl'),         # PageFetcher — Playwright + BrowserPool
    Queue('extract', routing_key='extract'),     # DataExtractor — CPU optimized
    Queue('validate', routing_key='validate'),   # Validator — CPU optimized
    Queue('report', routing_key='report'),       # Reporter — DB/Storage I/O
    Queue('notification', routing_key='notification'),  # Notification — Slack/Email
)

# Task routing rules (Req 16.2)
PIPELINE_TASK_ROUTES = {
    'src.pipeline_tasks.crawl_task': {'queue': 'crawl'},
    'src.pipeline_tasks.extract_task': {'queue': 'extract'},
    'src.pipeline_tasks.validate_task': {'queue': 'validate'},
    'src.pipeline_tasks.report_task': {'queue': 'report'},
    'src.pipeline_tasks.perform_login': {'queue': 'crawl'},
    'src.notification_tasks.send_notification': {'queue': 'notification'},
    'src.pipeline.vlm_tasks.classify_page_vlm': {'queue': 'extract'},
}

# Create Celery app
celery_app = Celery(
    'payment_compliance_monitor',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['src.tasks', 'src.pipeline_tasks', 'src.notification_tasks', 'src.pipeline.vlm_tasks'],
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes
    task_soft_time_limit=240,  # 4 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    # Pipeline queue configuration
    task_queues=PIPELINE_QUEUES,
    task_routes=PIPELINE_TASK_ROUTES,
)

# Celery Beat schedule (periodic tasks)
celery_app.conf.beat_schedule = {
    'daily-crawling': {
        'task': 'src.tasks.crawl_all_sites',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2:00 AM
    },
    'weekly-fake-site-scan': {
        'task': 'src.tasks.scan_all_fake_sites',
        'schedule': crontab(hour=3, minute=0, day_of_week=1),  # Monday at 3:00 AM
    },
    'monthly-cleanup': {
        'task': 'src.tasks.cleanup_old_data',
        'schedule': crontab(hour=4, minute=0, day_of_month=1),  # 1st of month at 4:00 AM
    },
}

# Conditionally add pipeline scheduler beat entry
if os.getenv('USE_PIPELINE', 'false').lower() == 'true':
    celery_app.conf.beat_schedule['pipeline-scheduled-crawls'] = {
        'task': 'src.pipeline_tasks.run_scheduled_crawls_task',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    }


# ---------------------------------------------------------------------------
# Worker initialization signal — crawl queue workers init BrowserPool (Req 16.4, 16.5)
# ---------------------------------------------------------------------------

# Global BrowserPool instance for crawl workers
_browser_pool = None


def get_browser_pool():
    """Get the global BrowserPool instance (available on crawl workers only)."""
    return _browser_pool


@worker_init.connect
def _on_worker_init(sender=None, **kwargs):
    """Initialize Playwright + BrowserPool on crawl-queue workers.

    Only crawl workers need Playwright. extract/validate workers skip this.
    The worker's queues are inspected to determine if this is a crawl worker.
    """
    global _browser_pool

    # Determine which queues this worker is consuming from
    queues = set()
    if hasattr(sender, 'queues') and sender.queues:
        queues = {q.name if hasattr(q, 'name') else str(q) for q in sender.queues}

    if 'crawl' not in queues:
        logger.info(
            "Non-crawl worker (queues=%s): skipping BrowserPool initialization",
            queues,
        )
    else:
        logger.info("Crawl worker detected (queues=%s): initializing BrowserPool", queues)

        try:
            import asyncio
            from src.pipeline.browser_pool import BrowserPool

            max_instances = int(os.getenv('BROWSER_POOL_SIZE', '3'))
            pool = BrowserPool(max_instances=max_instances)

            loop = asyncio.new_event_loop()
            loop.run_until_complete(pool.initialize())

            _browser_pool = pool
            logger.info("BrowserPool initialized with %d instances", max_instances)
        except Exception as e:
            logger.error("Failed to initialize BrowserPool: %s", e)
            _browser_pool = None

    # OpenTelemetry Celery instrumentation (all workers)
    try:
        from src.core.telemetry import instrument_celery
        otel_service = os.getenv("OTEL_SERVICE_NAME", "payment-compliance-worker")
        instrument_celery(otel_service)
    except Exception as e:
        logger.warning("Failed to instrument Celery with OpenTelemetry: %s", e)
