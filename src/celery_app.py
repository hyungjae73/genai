"""
Celery application configuration for Payment Compliance Monitor.

This module configures Celery for asynchronous task processing.
"""

import os
from celery import Celery
from celery.schedules import crontab


# Get Redis URL from environment
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Create Celery app
celery_app = Celery(
    'payment_compliance_monitor',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['src.tasks']
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
