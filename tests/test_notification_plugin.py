"""
Unit tests for NotificationPlugin and DuplicateSuppressionChecker.

Tests should_run, execute metadata recording, error handling,
and duplicate suppression filtering.

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 6.1, 6.2, 6.4, 6.5
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.models import MonitoringSite, NotificationRecord
from src.pipeline.context import CrawlContext
from src.pipeline.plugins.duplicate_suppression import DuplicateSuppressionChecker
from src.pipeline.plugins.notification_plugin import NotificationPlugin


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_site(plugin_config=None, customer_email="user@example.com"):
    """Build a MonitoringSite with a mock customer."""
    site = MonitoringSite(id=1, name="Test Site", url="https://example.com")
    site.plugin_config = plugin_config
    customer = MagicMock()
    customer.email = customer_email
    site.customer = customer
    return site


def _make_ctx(violations=None, plugin_config=None, customer_email="user@example.com"):
    """Build a CrawlContext with violations and optional config."""
    site = _make_site(plugin_config=plugin_config, customer_email=customer_email)
    ctx = CrawlContext(site=site, url="https://example.com")
    if violations:
        ctx.violations = violations
    return ctx


# ------------------------------------------------------------------
# should_run (Req 1.2)
# ------------------------------------------------------------------


class TestShouldRun:
    @patch.dict(os.environ, {"NOTIFICATION_EMAIL_ENABLED": "true"}, clear=True)
    def test_returns_true_with_violations_and_channel_enabled(self):
        ctx = _make_ctx(violations=[{"violation_type": "price_mismatch"}])
        plugin = NotificationPlugin()
        assert plugin.should_run(ctx) is True

    @patch.dict(os.environ, {"NOTIFICATION_EMAIL_ENABLED": "true"}, clear=True)
    def test_returns_false_with_no_violations(self):
        ctx = _make_ctx(violations=[])
        plugin = NotificationPlugin()
        assert plugin.should_run(ctx) is False

    @patch.dict(os.environ, {
        "NOTIFICATION_EMAIL_ENABLED": "false",
        "NOTIFICATION_SLACK_ENABLED": "false",
    }, clear=True)
    def test_returns_false_when_all_channels_disabled(self):
        ctx = _make_ctx(violations=[{"violation_type": "price_mismatch"}])
        plugin = NotificationPlugin()
        assert plugin.should_run(ctx) is False

    @patch.dict(os.environ, {
        "NOTIFICATION_SLACK_ENABLED": "true",
        "NOTIFICATION_EMAIL_ENABLED": "false",
    }, clear=True)
    def test_returns_true_with_only_slack_enabled(self):
        ctx = _make_ctx(violations=[{"violation_type": "price_mismatch"}])
        plugin = NotificationPlugin()
        assert plugin.should_run(ctx) is True

    @patch.dict(os.environ, {
        "NOTIFICATION_OVERRIDE_DISABLED": "true",
        "NOTIFICATION_EMAIL_ENABLED": "true",
    }, clear=True)
    def test_returns_false_when_override_disabled(self):
        ctx = _make_ctx(violations=[{"violation_type": "price_mismatch"}])
        plugin = NotificationPlugin()
        assert plugin.should_run(ctx) is False


# ------------------------------------------------------------------
# execute — metadata recording (Req 1.4)
# ------------------------------------------------------------------


class TestExecuteMetadata:
    @pytest.mark.asyncio
    @patch.dict(os.environ, {"NOTIFICATION_EMAIL_ENABLED": "true"}, clear=True)
    async def test_records_notification_sent_metadata(self):
        ctx = _make_ctx(violations=[{"violation_type": "price_mismatch"}])
        plugin = NotificationPlugin()
        result = await plugin.execute(ctx)

        assert result.metadata["notification_sent"] is True
        assert "notification_channels" in result.metadata
        assert "notification_violation_count" in result.metadata

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"NOTIFICATION_EMAIL_ENABLED": "true"}, clear=True)
    async def test_metadata_keys_have_notification_prefix(self):
        ctx = _make_ctx(violations=[{"violation_type": "price_mismatch"}])
        plugin = NotificationPlugin()
        result = await plugin.execute(ctx)

        notification_keys = [
            k for k in result.metadata if k.startswith("notification_")
        ]
        assert len(notification_keys) >= 1

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"NOTIFICATION_EMAIL_ENABLED": "true"}, clear=True)
    async def test_preserves_existing_metadata(self):
        ctx = _make_ctx(violations=[{"violation_type": "price_mismatch"}])
        ctx.metadata["existing_key"] = "value"
        plugin = NotificationPlugin()
        result = await plugin.execute(ctx)

        assert result.metadata["existing_key"] == "value"

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"NOTIFICATION_EMAIL_ENABLED": "true"}, clear=True)
    async def test_records_channels_in_metadata(self):
        ctx = _make_ctx(violations=[{"violation_type": "price_mismatch"}])
        plugin = NotificationPlugin()
        result = await plugin.execute(ctx)

        assert "email" in result.metadata["notification_channels"]


# ------------------------------------------------------------------
# execute — never raises exceptions (Req 1.5)
# ------------------------------------------------------------------


class TestExecuteNeverRaises:
    @pytest.mark.asyncio
    @patch.dict(os.environ, {"NOTIFICATION_EMAIL_ENABLED": "true"}, clear=True)
    async def test_does_not_raise_on_celery_failure(self):
        celery_app = MagicMock()
        celery_app.send_task.side_effect = Exception("Celery down")
        ctx = _make_ctx(violations=[{"violation_type": "price_mismatch"}])
        plugin = NotificationPlugin(celery_app=celery_app)

        # Should not raise
        result = await plugin.execute(ctx)
        assert isinstance(result, CrawlContext)

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"NOTIFICATION_EMAIL_ENABLED": "true"}, clear=True)
    async def test_does_not_raise_on_db_failure(self):
        session = MagicMock()
        session.query.side_effect = Exception("DB error")
        ctx = _make_ctx(violations=[{"violation_type": "price_mismatch"}])
        plugin = NotificationPlugin(session_factory=lambda: session)

        result = await plugin.execute(ctx)
        assert isinstance(result, CrawlContext)

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"NOTIFICATION_EMAIL_ENABLED": "true"}, clear=True)
    async def test_appends_error_on_failure(self):
        celery_app = MagicMock()
        celery_app.send_task.side_effect = Exception("Celery down")
        ctx = _make_ctx(violations=[{"violation_type": "price_mismatch"}])
        plugin = NotificationPlugin(celery_app=celery_app)

        result = await plugin.execute(ctx)
        error_messages = [e["error"] for e in result.errors]
        assert any("Celery" in msg for msg in error_messages)

    @pytest.mark.asyncio
    async def test_does_not_raise_on_config_resolution_error(self):
        """Even if config resolution fails entirely, execute catches it."""
        site = MonitoringSite(id=1, name="Test", url="https://example.com")
        # No customer attribute at all — will cause AttributeError
        ctx = CrawlContext(site=site, url="https://example.com")
        ctx.violations = [{"violation_type": "price_mismatch"}]
        plugin = NotificationPlugin()

        result = await plugin.execute(ctx)
        assert isinstance(result, CrawlContext)


# ------------------------------------------------------------------
# execute — Celery submission and sync fallback (Req 8.1, 8.5)
# ------------------------------------------------------------------


class TestCelerySubmission:
    @pytest.mark.asyncio
    @patch.dict(os.environ, {"NOTIFICATION_EMAIL_ENABLED": "true"}, clear=True)
    async def test_submits_to_celery_when_available(self):
        celery_app = MagicMock()
        ctx = _make_ctx(violations=[{"violation_type": "price_mismatch"}])
        plugin = NotificationPlugin(celery_app=celery_app)

        await plugin.execute(ctx)
        celery_app.send_task.assert_called_once()
        call_args = celery_app.send_task.call_args
        assert call_args[0][0] == "src.notification_tasks.send_notification"
        assert call_args[1]["queue"] == "notification"

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"NOTIFICATION_EMAIL_ENABLED": "true"}, clear=True)
    async def test_records_error_on_celery_failure(self):
        celery_app = MagicMock()
        celery_app.send_task.side_effect = Exception("Connection refused")
        ctx = _make_ctx(violations=[{"violation_type": "price_mismatch"}])
        plugin = NotificationPlugin(celery_app=celery_app)

        result = await plugin.execute(ctx)
        assert any("Celery submit failed" in e["error"] for e in result.errors)


# ------------------------------------------------------------------
# execute — duplicate suppression integration (Req 6.1, 6.2)
# ------------------------------------------------------------------


class TestDuplicateSuppression:
    @pytest.mark.asyncio
    @patch.dict(os.environ, {"NOTIFICATION_EMAIL_ENABLED": "true"}, clear=True)
    async def test_suppresses_already_sent_violations(self):
        """Violations already sent within window are suppressed."""
        session = MagicMock()
        query = MagicMock()
        session.query.return_value = query
        query.filter.return_value = query
        query.distinct.return_value = query
        # Simulate that "price_mismatch" was already sent
        query.all.return_value = [("price_mismatch",)]

        ctx = _make_ctx(violations=[
            {"violation_type": "price_mismatch"},
            {"violation_type": "dark_pattern"},
        ])
        plugin = NotificationPlugin(session_factory=lambda: session)
        result = await plugin.execute(ctx)

        # dark_pattern should still be sent, price_mismatch suppressed
        assert result.metadata.get("notification_sent") is True
        assert result.metadata.get("notification_violation_count") == 1

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"NOTIFICATION_EMAIL_ENABLED": "true"}, clear=True)
    async def test_all_suppressed_records_status(self):
        """When all violations are suppressed, status is all_suppressed."""
        session = MagicMock()
        query = MagicMock()
        session.query.return_value = query
        query.filter.return_value = query
        query.distinct.return_value = query
        query.all.return_value = [("price_mismatch",)]

        ctx = _make_ctx(violations=[{"violation_type": "price_mismatch"}])
        plugin = NotificationPlugin(session_factory=lambda: session)
        result = await plugin.execute(ctx)

        assert result.metadata.get("notification_status") == "all_suppressed"
        assert result.metadata.get("notification_sent") is False


# ------------------------------------------------------------------
# DuplicateSuppressionChecker unit tests (Req 6.2, 6.4, 6.5)
# ------------------------------------------------------------------


class TestDuplicateSuppressionChecker:
    def test_returns_all_when_no_existing_records(self):
        session = MagicMock()
        query = MagicMock()
        session.query.return_value = query
        query.filter.return_value = query
        query.distinct.return_value = query
        query.all.return_value = []

        checker = DuplicateSuppressionChecker(session_factory=lambda: session)
        result = checker.filter_new_violations(
            site_id=1,
            violation_types=["price_mismatch", "dark_pattern"],
            window_hours=24,
        )
        assert result == ["price_mismatch", "dark_pattern"]

    def test_filters_out_existing_sent_records(self):
        session = MagicMock()
        query = MagicMock()
        session.query.return_value = query
        query.filter.return_value = query
        query.distinct.return_value = query
        query.all.return_value = [("price_mismatch",)]

        checker = DuplicateSuppressionChecker(session_factory=lambda: session)
        result = checker.filter_new_violations(
            site_id=1,
            violation_types=["price_mismatch", "dark_pattern"],
            window_hours=24,
        )
        assert result == ["dark_pattern"]

    def test_returns_empty_for_empty_input(self):
        session = MagicMock()
        checker = DuplicateSuppressionChecker(session_factory=lambda: session)
        result = checker.filter_new_violations(
            site_id=1,
            violation_types=[],
            window_hours=24,
        )
        assert result == []

    def test_closes_session_after_query(self):
        session = MagicMock()
        query = MagicMock()
        session.query.return_value = query
        query.filter.return_value = query
        query.distinct.return_value = query
        query.all.return_value = []

        checker = DuplicateSuppressionChecker(session_factory=lambda: session)
        checker.filter_new_violations(
            site_id=1,
            violation_types=["price_mismatch"],
            window_hours=24,
        )
        session.close.assert_called_once()

    def test_closes_session_on_error(self):
        session = MagicMock()
        session.query.side_effect = Exception("DB error")

        checker = DuplicateSuppressionChecker(session_factory=lambda: session)
        with pytest.raises(Exception, match="DB error"):
            checker.filter_new_violations(
                site_id=1,
                violation_types=["price_mismatch"],
                window_hours=24,
            )
        session.close.assert_called_once()


# ------------------------------------------------------------------
# Plugin name
# ------------------------------------------------------------------


class TestPluginName:
    def test_name(self):
        plugin = NotificationPlugin()
        assert plugin.name == "NotificationPlugin"
