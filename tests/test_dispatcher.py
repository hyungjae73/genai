"""
Unit tests for BatchDispatcher.

Tests priority sorting, Celery task dispatch, and batch limits.
Requirements: 17.1, 17.2, 19.3
"""

from unittest.mock import MagicMock, call

import pytest

from src.pipeline.dispatcher import BatchDispatcher, map_priority, PRIORITY_MAP


class FakeSchedule:
    """Minimal CrawlSchedule-like object for testing."""

    def __init__(self, site_id: int, priority: str = "normal"):
        self.site_id = site_id
        self.priority = priority


class TestMapPriority:
    """Tests for priority string to Celery integer mapping."""

    def test_high_maps_to_0(self):
        assert map_priority("high") == 0

    def test_normal_maps_to_5(self):
        assert map_priority("normal") == 5

    def test_low_maps_to_9(self):
        assert map_priority("low") == 9

    def test_unknown_defaults_to_normal(self):
        assert map_priority("unknown") == 5

    def test_priority_map_has_three_entries(self):
        assert set(PRIORITY_MAP.keys()) == {"high", "normal", "low"}


class TestBatchDispatcher:
    """Tests for BatchDispatcher dispatch logic."""

    def test_empty_schedules_returns_zero(self):
        dispatcher = BatchDispatcher()
        assert dispatcher.dispatch([]) == 0

    def test_dispatches_all_schedules(self):
        mock_celery = MagicMock()
        dispatcher = BatchDispatcher(celery_app=mock_celery)

        schedules = [FakeSchedule(1, "high"), FakeSchedule(2, "normal")]
        count = dispatcher.dispatch(schedules)

        assert count == 2
        assert mock_celery.send_task.call_count == 2

    def test_sorts_by_priority(self):
        mock_celery = MagicMock()
        dispatcher = BatchDispatcher(celery_app=mock_celery)

        schedules = [
            FakeSchedule(3, "low"),
            FakeSchedule(1, "high"),
            FakeSchedule(2, "normal"),
        ]
        dispatcher.dispatch(schedules)

        # Verify dispatch order: high (site 1) -> normal (site 2) -> low (site 3)
        calls = mock_celery.send_task.call_args_list
        assert calls[0] == call(
            "src.tasks.crawl_and_validate_site",
            kwargs={"site_id": 1},
            priority=0,
        )
        assert calls[1] == call(
            "src.tasks.crawl_and_validate_site",
            kwargs={"site_id": 2},
            priority=5,
        )
        assert calls[2] == call(
            "src.tasks.crawl_and_validate_site",
            kwargs={"site_id": 3},
            priority=9,
        )

    def test_respects_max_tasks_per_run(self):
        mock_celery = MagicMock()
        dispatcher = BatchDispatcher(celery_app=mock_celery, max_tasks_per_run=2)

        schedules = [FakeSchedule(i, "normal") for i in range(5)]
        count = dispatcher.dispatch(schedules)

        assert count == 2
        assert mock_celery.send_task.call_count == 2

    def test_default_batch_size(self):
        dispatcher = BatchDispatcher()
        assert dispatcher.batch_size == 100

    def test_default_max_tasks_per_run(self):
        dispatcher = BatchDispatcher()
        assert dispatcher.max_tasks_per_run == 500

    def test_celery_send_task_error_continues(self):
        """Dispatch continues even if one send_task fails."""
        mock_celery = MagicMock()
        mock_celery.send_task.side_effect = [Exception("fail"), None]

        dispatcher = BatchDispatcher(celery_app=mock_celery)
        schedules = [FakeSchedule(1, "normal"), FakeSchedule(2, "normal")]
        count = dispatcher.dispatch(schedules)

        # First fails, second succeeds
        assert count == 1

    def test_dispatch_without_celery_app(self):
        """Dispatch counts tasks even without a real Celery app."""
        dispatcher = BatchDispatcher(celery_app=None)
        schedules = [FakeSchedule(1, "high"), FakeSchedule(2, "low")]
        count = dispatcher.dispatch(schedules)
        assert count == 2

    def test_celery_priority_passed_correctly(self):
        """Celery task priority matches the mapped value."""
        mock_celery = MagicMock()
        dispatcher = BatchDispatcher(celery_app=mock_celery)

        dispatcher.dispatch([FakeSchedule(1, "high")])
        mock_celery.send_task.assert_called_once_with(
            "src.tasks.crawl_and_validate_site",
            kwargs={"site_id": 1},
            priority=0,
        )
