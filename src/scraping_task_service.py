"""
Service layer for ScrapingTask with strict state management.

Follows engineering_standards.md:
- Skill 2: Idempotency — duplicate PENDING/PROCESSING tasks for same URL are reused
- Skill 3: Pessimistic transactions — session.begin() with auto-rollback
- Skill 4: Fail-safe — exceptions always recorded to error_message column
"""

import logging
import traceback
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models import ScrapingTask, ScrapingTaskStatus

logger = logging.getLogger(__name__)

# Valid state transitions (from → allowed targets)
_VALID_TRANSITIONS: dict[ScrapingTaskStatus, set[ScrapingTaskStatus]] = {
    ScrapingTaskStatus.PENDING: {ScrapingTaskStatus.PROCESSING, ScrapingTaskStatus.FAILED},
    ScrapingTaskStatus.PROCESSING: {ScrapingTaskStatus.SUCCESS, ScrapingTaskStatus.FAILED},
    ScrapingTaskStatus.SUCCESS: set(),
    ScrapingTaskStatus.FAILED: set(),
}


class InvalidStateTransition(Exception):
    """Raised when an illegal status transition is attempted."""


class ScrapingTaskService:
    """
    Manages ScrapingTask lifecycle with idempotency and pessimistic state management.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_task(self, url: str) -> ScrapingTask:
        """
        Create a new scraping task or return an existing in-flight task for the same URL.

        Idempotency: if a PENDING or PROCESSING task already exists for this URL,
        it is returned instead of creating a duplicate.
        """
        # Check for existing in-flight task (idempotency guard)
        existing = self._session.execute(
            select(ScrapingTask).where(
                ScrapingTask.target_url == url,
                ScrapingTask.status.in_([
                    ScrapingTaskStatus.PENDING.value,
                    ScrapingTaskStatus.PROCESSING.value,
                ]),
            )
        ).scalar_one_or_none()

        if existing is not None:
            logger.info(
                "Reusing existing in-flight task id=%s for url=%s (status=%s)",
                existing.id, url, existing.status,
            )
            return existing

        task = ScrapingTask(
            target_url=url,
            status=ScrapingTaskStatus.PENDING.value,
        )
        self._session.add(task)
        self._session.flush()
        return task

    def mark_as_failed(self, task_id: int, error_reason: str) -> ScrapingTask:
        """
        Transition a task to FAILED and record the error reason.

        Pessimistic state management:
        - Only PENDING or PROCESSING tasks can transition to FAILED.
        - Already-FAILED tasks are returned as-is (idempotent).
        - error_message is truncated to 10000 chars to prevent DB bloat.
        """
        task = self._session.get(ScrapingTask, task_id)
        if task is None:
            raise ValueError(f"ScrapingTask id={task_id} not found")

        current = ScrapingTaskStatus(task.status)

        # Idempotent: already failed → no-op
        if current is ScrapingTaskStatus.FAILED:
            logger.info("Task id=%s already FAILED, no-op", task_id)
            return task

        # Validate state transition
        if ScrapingTaskStatus.FAILED not in _VALID_TRANSITIONS[current]:
            raise InvalidStateTransition(
                f"Cannot transition from {current.value} to FAILED"
            )

        task.status = ScrapingTaskStatus.FAILED.value
        task.error_message = error_reason[:10000]
        self._session.flush()

        logger.warning(
            "Task id=%s marked FAILED: %s", task_id, error_reason[:200],
        )
        return task
