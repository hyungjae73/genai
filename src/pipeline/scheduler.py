"""
Crawl scheduler for pipeline architecture.

Celery Beat periodic execution that fetches due CrawlSchedule records,
dispatches them via BatchDispatcher, and updates next_crawl_at.

Requirements: 19.1-19.5, 22.2-22.4
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Callable, Optional, Protocol

from src.pipeline.dispatcher import BatchDispatcher

logger = logging.getLogger(__name__)


class DBSession(Protocol):
    """Protocol for database session dependency injection."""

    def query(self, *args: Any) -> Any:
        ...

    def commit(self) -> None:
        ...

    def rollback(self) -> None:
        ...

    def close(self) -> None:
        ...


class CrawlScheduler:
    """
    Celery Beat scheduler for crawl pipeline.

    Fetches CrawlSchedule records where next_crawl_at <= now,
    dispatches them via BatchDispatcher, and updates next_crawl_at.

    Supports USE_PIPELINE env var for new/legacy flow switching.

    Args:
        dispatcher: BatchDispatcher instance for task dispatch.
        session_factory: Callable that returns a DB session.
        max_tasks_per_run: Maximum tasks to dispatch per run (default 500).
        use_pipeline: Override for USE_PIPELINE env var (None = read from env).
        legacy_task_func: Callable for legacy crawl_all_sites task dispatch.
    """

    def __init__(
        self,
        dispatcher: Optional[BatchDispatcher] = None,
        session_factory: Optional[Callable] = None,
        max_tasks_per_run: int = 500,
        use_pipeline: Optional[bool] = None,
        legacy_task_func: Optional[Callable] = None,
    ):
        self._dispatcher = dispatcher or BatchDispatcher()
        self._session_factory = session_factory
        self._max_tasks_per_run = max_tasks_per_run
        self._legacy_task_func = legacy_task_func

        # Resolve USE_PIPELINE: explicit param > env var > default False
        if use_pipeline is not None:
            self._use_pipeline = use_pipeline
        else:
            self._use_pipeline = os.environ.get("USE_PIPELINE", "false").lower() == "true"

    @property
    def use_pipeline(self) -> bool:
        return self._use_pipeline

    @property
    def max_tasks_per_run(self) -> int:
        return self._max_tasks_per_run

    def run_scheduled_crawls(self, now: Optional[datetime] = None) -> int:
        """
        Execute scheduled crawls.

        1. If USE_PIPELINE is False, dispatch via legacy task and return.
        2. Fetch CrawlSchedule where next_crawl_at <= now.
        3. Dispatch via BatchDispatcher (sorted by priority, limited).
        4. Update next_crawl_at for dispatched schedules.

        Args:
            now: Current time override for testing (default: datetime.utcnow()).

        Returns:
            Number of tasks dispatched.
        """
        if not self._use_pipeline:
            return self._dispatch_legacy()

        return self._dispatch_pipeline(now)

    def _dispatch_legacy(self) -> int:
        """Dispatch via legacy crawl_all_sites task."""
        if self._legacy_task_func is not None:
            try:
                self._legacy_task_func()
                logger.info("Dispatched legacy crawl_all_sites task")
                return 1
            except Exception as e:
                logger.error("Failed to dispatch legacy task: %s", e)
                return 0
        else:
            logger.warning("No legacy task function configured, skipping")
            return 0

    def _dispatch_pipeline(self, now: Optional[datetime] = None) -> int:
        """Dispatch via new pipeline using BatchDispatcher."""
        if self._session_factory is None:
            logger.error("No session_factory configured for pipeline dispatch")
            return 0

        if now is None:
            now = datetime.utcnow()

        session = self._session_factory()
        try:
            from src.models import CrawlSchedule

            # Fetch due schedules, limited to max_tasks_per_run
            due_schedules = (
                session.query(CrawlSchedule)
                .filter(CrawlSchedule.next_crawl_at <= now)
                .limit(self._max_tasks_per_run)
                .all()
            )

            if not due_schedules:
                logger.info("No due schedules found")
                return 0

            # Dispatch via BatchDispatcher
            dispatched = self._dispatcher.dispatch(due_schedules)

            # Update next_crawl_at for dispatched schedules
            for schedule in due_schedules[:dispatched]:
                schedule.next_crawl_at = now + timedelta(minutes=schedule.interval_minutes)

            session.commit()

            logger.info(
                "Pipeline dispatch: %d/%d schedules dispatched",
                dispatched,
                len(due_schedules),
            )
            return dispatched

        except Exception as e:
            session.rollback()
            logger.error("Pipeline dispatch failed: %s", e)
            return 0
        finally:
            session.close()
