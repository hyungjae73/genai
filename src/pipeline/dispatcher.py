"""
Batch dispatcher for crawl pipeline.

Sorts CrawlSchedule records by priority and dispatches them as Celery tasks.

Requirements: 17.1, 17.2, 19.3
"""

import logging
from typing import Any, Callable, Optional, Protocol

logger = logging.getLogger(__name__)


# Priority mapping: crawl_priority string -> Celery task priority integer
PRIORITY_MAP: dict[str, int] = {
    "high": 0,
    "normal": 5,
    "low": 9,
}


def map_priority(crawl_priority: str) -> int:
    """
    Map crawl_priority string to Celery task priority integer.

    Args:
        crawl_priority: One of 'high', 'normal', 'low'.

    Returns:
        Celery priority value (0=highest, 9=lowest).
    """
    return PRIORITY_MAP.get(crawl_priority, PRIORITY_MAP["normal"])


class CeleryApp(Protocol):
    """Protocol for Celery app dependency injection."""

    def send_task(self, name: str, args: Any = None, kwargs: Any = None, priority: int = 0, **options: Any) -> Any:
        ...


class BatchDispatcher:
    """
    Dispatches CrawlSchedule records as Celery tasks sorted by priority.

    Args:
        celery_app: Celery application instance (or mock).
        task_name: Name of the Celery task to dispatch.
        batch_size: Maximum number of tasks per batch (default 100).
        max_tasks_per_run: Maximum total tasks per scheduler run (default 500).
    """

    def __init__(
        self,
        celery_app: Optional[Any] = None,
        task_name: str = "src.tasks.crawl_and_validate_site",
        batch_size: int = 100,
        max_tasks_per_run: int = 500,
    ):
        self._celery_app = celery_app
        self._task_name = task_name
        self._batch_size = batch_size
        self._max_tasks_per_run = max_tasks_per_run

    @property
    def batch_size(self) -> int:
        return self._batch_size

    @property
    def max_tasks_per_run(self) -> int:
        return self._max_tasks_per_run

    def dispatch(self, schedules: list) -> int:
        """
        Sort schedules by priority and dispatch as Celery tasks.

        Args:
            schedules: List of CrawlSchedule-like objects with `site_id` and `priority`.

        Returns:
            Number of tasks dispatched.
        """
        if not schedules:
            return 0

        # Sort by priority: high (0) first, then normal (5), then low (9)
        sorted_schedules = sorted(
            schedules,
            key=lambda s: map_priority(getattr(s, "priority", "normal")),
        )

        # Limit to max_tasks_per_run
        limited = sorted_schedules[: self._max_tasks_per_run]

        dispatched = 0
        for schedule in limited:
            priority_str = getattr(schedule, "priority", "normal")
            celery_priority = map_priority(priority_str)
            site_id = getattr(schedule, "site_id", None)

            if site_id is None:
                logger.warning("Schedule missing site_id, skipping: %s", schedule)
                continue

            if self._celery_app is not None:
                try:
                    self._celery_app.send_task(
                        self._task_name,
                        kwargs={"site_id": site_id},
                        priority=celery_priority,
                    )
                except Exception as e:
                    logger.error("Failed to dispatch task for site_id=%d: %s", site_id, e)
                    continue

            dispatched += 1

        logger.info(
            "Dispatched %d/%d tasks (max_per_run=%d)",
            dispatched,
            len(schedules),
            self._max_tasks_per_run,
        )
        return dispatched
