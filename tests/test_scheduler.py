"""
Unit tests for CrawlScheduler.

Tests USE_PIPELINE flow switching, schedule fetching, dispatch, and next_crawl_at updates.
Requirements: 19.1-19.5, 22.2-22.4
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, call

import pytest

from src.pipeline.scheduler import CrawlScheduler
from src.pipeline.dispatcher import BatchDispatcher


class FakeSchedule:
    """Minimal CrawlSchedule-like object for testing."""

    def __init__(self, site_id: int, priority: str, next_crawl_at: datetime, interval_minutes: int = 1440):
        self.site_id = site_id
        self.priority = priority
        self.next_crawl_at = next_crawl_at
        self.interval_minutes = interval_minutes


class TestCrawlSchedulerUsePipeline:
    """Tests for USE_PIPELINE env var flow switching."""

    def test_use_pipeline_false_by_default(self):
        """USE_PIPELINE defaults to False."""
        scheduler = CrawlScheduler()
        assert scheduler.use_pipeline is False

    def test_use_pipeline_explicit_true(self):
        """Explicit use_pipeline=True overrides env."""
        scheduler = CrawlScheduler(use_pipeline=True)
        assert scheduler.use_pipeline is True

    def test_use_pipeline_explicit_false(self):
        """Explicit use_pipeline=False overrides env."""
        scheduler = CrawlScheduler(use_pipeline=False)
        assert scheduler.use_pipeline is False

    @patch.dict("os.environ", {"USE_PIPELINE": "true"})
    def test_use_pipeline_from_env_true(self):
        """USE_PIPELINE=true from env sets use_pipeline to True."""
        scheduler = CrawlScheduler()
        assert scheduler.use_pipeline is True

    @patch.dict("os.environ", {"USE_PIPELINE": "false"})
    def test_use_pipeline_from_env_false(self):
        """USE_PIPELINE=false from env sets use_pipeline to False."""
        scheduler = CrawlScheduler()
        assert scheduler.use_pipeline is False

    @patch.dict("os.environ", {"USE_PIPELINE": "True"})
    def test_use_pipeline_case_insensitive(self):
        """USE_PIPELINE env var is case-insensitive."""
        scheduler = CrawlScheduler()
        assert scheduler.use_pipeline is True


class TestCrawlSchedulerLegacy:
    """Tests for legacy flow dispatch."""

    def test_legacy_dispatch_calls_task_func(self):
        """When USE_PIPELINE=false, legacy task function is called."""
        mock_legacy = MagicMock()
        scheduler = CrawlScheduler(
            use_pipeline=False,
            legacy_task_func=mock_legacy,
        )

        result = scheduler.run_scheduled_crawls()

        mock_legacy.assert_called_once()
        assert result == 1

    def test_legacy_dispatch_no_func_returns_zero(self):
        """When no legacy function configured, returns 0."""
        scheduler = CrawlScheduler(use_pipeline=False)
        result = scheduler.run_scheduled_crawls()
        assert result == 0

    def test_legacy_dispatch_error_returns_zero(self):
        """When legacy function raises, returns 0."""
        mock_legacy = MagicMock(side_effect=Exception("fail"))
        scheduler = CrawlScheduler(
            use_pipeline=False,
            legacy_task_func=mock_legacy,
        )

        result = scheduler.run_scheduled_crawls()
        assert result == 0


class TestCrawlSchedulerPipeline:
    """Tests for new pipeline dispatch."""

    def _make_session_factory(self, schedules):
        """Create a mock session factory that returns given schedules."""
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_limit = MagicMock()

        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.limit.return_value = mock_limit
        mock_limit.all.return_value = schedules

        return lambda: mock_session, mock_session

    def test_pipeline_dispatches_due_schedules(self):
        """Pipeline mode dispatches due schedules via BatchDispatcher."""
        now = datetime(2024, 1, 15, 10, 0, 0)
        schedules = [
            FakeSchedule(1, "high", now - timedelta(hours=1)),
            FakeSchedule(2, "normal", now - timedelta(minutes=30)),
        ]

        mock_dispatcher = MagicMock(spec=BatchDispatcher)
        mock_dispatcher.dispatch.return_value = 2

        factory, session = self._make_session_factory(schedules)

        scheduler = CrawlScheduler(
            dispatcher=mock_dispatcher,
            session_factory=factory,
            use_pipeline=True,
        )

        result = scheduler.run_scheduled_crawls(now=now)

        assert result == 2
        mock_dispatcher.dispatch.assert_called_once_with(schedules)
        session.commit.assert_called_once()

    def test_pipeline_updates_next_crawl_at(self):
        """After dispatch, next_crawl_at is updated to now + interval_minutes."""
        now = datetime(2024, 1, 15, 10, 0, 0)
        schedule = FakeSchedule(1, "normal", now - timedelta(hours=1), interval_minutes=60)

        mock_dispatcher = MagicMock(spec=BatchDispatcher)
        mock_dispatcher.dispatch.return_value = 1

        factory, session = self._make_session_factory([schedule])

        scheduler = CrawlScheduler(
            dispatcher=mock_dispatcher,
            session_factory=factory,
            use_pipeline=True,
        )

        scheduler.run_scheduled_crawls(now=now)

        expected_next = now + timedelta(minutes=60)
        assert schedule.next_crawl_at == expected_next

    def test_pipeline_no_due_schedules(self):
        """Returns 0 when no schedules are due."""
        mock_dispatcher = MagicMock(spec=BatchDispatcher)
        factory, session = self._make_session_factory([])

        scheduler = CrawlScheduler(
            dispatcher=mock_dispatcher,
            session_factory=factory,
            use_pipeline=True,
        )

        result = scheduler.run_scheduled_crawls()
        assert result == 0
        mock_dispatcher.dispatch.assert_not_called()

    def test_pipeline_no_session_factory(self):
        """Returns 0 when no session_factory is configured."""
        scheduler = CrawlScheduler(use_pipeline=True, session_factory=None)
        result = scheduler.run_scheduled_crawls()
        assert result == 0

    def test_pipeline_db_error_rollback(self):
        """DB errors cause rollback and return 0."""
        mock_session = MagicMock()
        mock_session.query.side_effect = Exception("DB error")

        scheduler = CrawlScheduler(
            session_factory=lambda: mock_session,
            use_pipeline=True,
        )

        result = scheduler.run_scheduled_crawls()
        assert result == 0
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()

    def test_default_max_tasks_per_run(self):
        """Default max_tasks_per_run is 500."""
        scheduler = CrawlScheduler()
        assert scheduler.max_tasks_per_run == 500
