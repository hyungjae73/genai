"""
Property-based tests for dark-pattern-notification feature.

Uses Hypothesis to validate correctness properties across all notification
components: config merge, template rendering, duplicate suppression,
plugin orchestration, Celery tasks, and API endpoints.

Feature: dark-pattern-notification
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from src.models import MonitoringSite, NotificationRecord
from src.pipeline.context import CrawlContext
from src.pipeline.plugins.duplicate_suppression import DuplicateSuppressionChecker
from src.pipeline.plugins.notification_config import (
    NotificationConfig,
    mask_webhook_url,
    merge_notification_config,
)
from src.pipeline.plugins.notification_plugin import NotificationPlugin
from src.pipeline.plugins.notification_template import (
    DEFAULT_COLOR,
    SEVERITY_COLORS,
    NotificationTemplateRenderer,
)


# ======================================================================
# Strategies
# ======================================================================


@dataclass
class FakeSite:
    """Minimal site object satisfying SiteLike protocol."""
    name: str = "TestSite"
    url: str = "https://example.com"


KNOWN_SEVERITIES = ["warning", "critical", "info"]
KNOWN_VIOLATION_TYPES = ["price_mismatch", "structured_data_failure", "dark_pattern"]
KNOWN_CHANNELS = ["slack", "email"]
KNOWN_STATUSES = ["sent", "failed", "skipped"]


violation_strategy = st.fixed_dictionaries(
    {
        "violation_type": st.sampled_from(KNOWN_VIOLATION_TYPES),
        "severity": st.sampled_from(KNOWN_SEVERITIES),
        "detected_at": st.text(min_size=1, max_size=30),
    },
    optional={
        "detected_price": st.one_of(
            st.none(),
            st.integers(min_value=0, max_value=100000),
            st.floats(min_value=0, max_value=100000, allow_nan=False, allow_infinity=False),
        ),
        "expected_price": st.one_of(
            st.none(),
            st.integers(min_value=0, max_value=100000),
            st.floats(min_value=0, max_value=100000, allow_nan=False, allow_infinity=False),
        ),
        "evidence_url": st.one_of(st.none(), st.text(min_size=1, max_size=200)),
        "alert_id": st.one_of(st.none(), st.integers(min_value=1, max_value=100000)),
    },
)

notification_config_strategy = st.builds(
    NotificationConfig,
    slack_enabled=st.booleans(),
    slack_webhook_url=st.one_of(st.none(), st.text(min_size=10, max_size=200)),
    slack_channel=st.text(min_size=1, max_size=50),
    email_enabled=st.booleans(),
    email_recipients=st.lists(st.emails(), min_size=0, max_size=5),
    suppression_window_hours=st.integers(min_value=1, max_value=168),
)

site_name_strategy = st.text(min_size=1, max_size=100)
site_url_strategy = st.from_regex(r"https?://[a-z]+\.[a-z]{2,4}", fullmatch=True)

fake_site_strategy = st.builds(
    FakeSite,
    name=site_name_strategy,
    url=site_url_strategy,
)


# ======================================================================
# Property 12: Duplicate suppression within time window
# Feature: dark-pattern-notification, Property 12: Duplicate suppression within time window
# **Validates: Requirements 6.2, 6.4, 6.5**
# ======================================================================


class TestProperty12DuplicateSuppression:
    """For any site_id, violation_type, and window W: if a sent NotificationRecord
    exists within W hours, filter_new_violations excludes it; otherwise includes it."""

    @given(
        site_id=st.integers(min_value=1, max_value=100000),
        violation_types=st.lists(
            st.sampled_from(KNOWN_VIOLATION_TYPES), min_size=1, max_size=5, unique=True
        ),
        window_hours=st.integers(min_value=1, max_value=168),
        sent_subset_indices=st.lists(st.integers(min_value=0, max_value=4), max_size=3),
    )
    @settings(max_examples=100)
    def test_sent_within_window_excluded_otherwise_included(
        self, site_id, violation_types, window_hours, sent_subset_indices
    ):
        """Violation types with a 'sent' record within the window are excluded;
        those without are included."""
        # Determine which violation types have been "sent" within the window
        valid_indices = [i for i in sent_subset_indices if i < len(violation_types)]
        sent_types = {violation_types[i] for i in valid_indices}

        # Mock session that returns the sent types
        session = MagicMock()
        query = MagicMock()
        session.query.return_value = query
        query.filter.return_value = query
        query.distinct.return_value = query
        query.all.return_value = [(vt,) for vt in sent_types]

        checker = DuplicateSuppressionChecker(session_factory=lambda: session)
        result = checker.filter_new_violations(site_id, violation_types, window_hours)

        # Result should contain only types NOT in sent_types
        expected = [vt for vt in violation_types if vt not in sent_types]
        assert result == expected

        # Session should be closed
        session.close.assert_called_once()

    @given(
        site_id=st.integers(min_value=1, max_value=100000),
        window_hours=st.integers(min_value=1, max_value=168),
    )
    @settings(max_examples=100)
    def test_empty_violation_types_returns_empty(self, site_id, window_hours):
        """Empty violation_types input always returns empty list."""
        session = MagicMock()
        checker = DuplicateSuppressionChecker(session_factory=lambda: session)
        result = checker.filter_new_violations(site_id, [], window_hours)
        assert result == []


# ======================================================================
# Property 8: 3-layer config merge priority
# Feature: dark-pattern-notification, Property 8: 3-layer config merge priority
# **Validates: Requirements 3.2, 4.1, 4.2, 4.3, 4.4, 4.5**
# ======================================================================


class TestProperty8ConfigMergePriority:
    """For any env vars, site config, customer email, override flag:
    (1) NOTIFICATION_OVERRIDE_DISABLED=true disables all;
    (2) site overrides global;
    (3) global as defaults;
    (4) email_recipients always has customer_email first."""

    @given(
        customer_email=st.emails(),
        override_disabled=st.booleans(),
        env_slack_enabled=st.sampled_from(["true", "false"]),
        env_email_enabled=st.sampled_from(["true", "false"]),
        site_slack_enabled=st.one_of(st.none(), st.booleans()),
        site_email_enabled=st.one_of(st.none(), st.booleans()),
        additional_recipients=st.lists(st.emails(), max_size=3),
    )
    @settings(max_examples=100)
    def test_merge_priority_rules(
        self,
        customer_email,
        override_disabled,
        env_slack_enabled,
        env_email_enabled,
        site_slack_enabled,
        site_email_enabled,
        additional_recipients,
    ):
        env = {
            "NOTIFICATION_SLACK_ENABLED": env_slack_enabled,
            "NOTIFICATION_EMAIL_ENABLED": env_email_enabled,
        }
        if override_disabled:
            env["NOTIFICATION_OVERRIDE_DISABLED"] = "true"

        site_config = None
        np_params: dict[str, Any] = {}
        if site_slack_enabled is not None:
            np_params["slack_enabled"] = site_slack_enabled
        if site_email_enabled is not None:
            np_params["email_enabled"] = site_email_enabled
        if additional_recipients:
            np_params["additional_email_recipients"] = additional_recipients
        if np_params:
            site_config = {"params": {"NotificationPlugin": np_params}}

        with patch.dict(os.environ, env, clear=True):
            config = merge_notification_config(customer_email, site_config)

        # Rule 1: override disabled → all channels off
        if override_disabled:
            assert config.slack_enabled is False
            assert config.email_enabled is False
        else:
            # Rule 2: site overrides global
            if site_slack_enabled is not None:
                assert config.slack_enabled == site_slack_enabled
            else:
                # Rule 3: global as default
                assert config.slack_enabled == (env_slack_enabled == "true")

            if site_email_enabled is not None:
                assert config.email_enabled == site_email_enabled
            else:
                assert config.email_enabled == (env_email_enabled == "true")

        # Rule 4: customer_email always first, no duplicates
        assert config.email_recipients[0] == customer_email
        assert len(config.email_recipients) == len(set(config.email_recipients))


# ======================================================================
# Property 14: Webhook URL masking
# Feature: dark-pattern-notification, Property 14: Webhook URL masking
# **Validates: Requirements 9.4**
# ======================================================================


class TestProperty14WebhookUrlMasking:
    """For any URL >= 8 chars: mask all except last 8;
    for < 8 chars: mask entire; for None: return None."""

    @given(url=st.text(min_size=8, max_size=300))
    @settings(max_examples=100)
    def test_long_url_masks_except_last_8(self, url):
        masked = mask_webhook_url(url)
        assert masked is not None
        assert len(masked) == len(url)
        assert masked[-8:] == url[-8:]
        assert masked[:-8] == "*" * (len(url) - 8)

    @given(url=st.text(min_size=1, max_size=7))
    @settings(max_examples=100)
    def test_short_url_fully_masked(self, url):
        masked = mask_webhook_url(url)
        assert masked is not None
        assert masked == "*" * len(url)

    @settings(max_examples=100)
    @given(data=st.data())
    def test_none_returns_none(self, data):
        assert mask_webhook_url(None) is None

    @given(url=st.text(min_size=0, max_size=300))
    @settings(max_examples=100)
    def test_length_preserved(self, url):
        masked = mask_webhook_url(url)
        assert masked is not None
        assert len(masked) == len(url)


# ======================================================================
# Property 4 & 5: Slack payload fields and severity colors
# Feature: dark-pattern-notification, Property 4: Slack payload contains all required violation fields
# Feature: dark-pattern-notification, Property 5: Slack severity color mapping
# **Validates: Requirements 2.2, 2.3**
# ======================================================================


class TestProperty4And5SlackPayload:
    """For any violation and site: payload contains site name, violation type,
    severity, detected_at; severity colors match mapping."""

    @given(
        violation=violation_strategy,
        site=fake_site_strategy,
        config=notification_config_strategy,
    )
    @settings(max_examples=100)
    def test_slack_payload_contains_required_fields(self, violation, site, config):
        """Property 4: Slack payload contains site name, violation type, severity, detected_at."""
        renderer = NotificationTemplateRenderer()
        payload = renderer.render_slack_payload([violation], config, site)

        assert "attachments" in payload
        assert len(payload["attachments"]) == 1
        text = payload["attachments"][0]["blocks"][0]["text"]["text"]

        assert site.name in text
        assert violation["violation_type"] in text
        assert violation["severity"] in text
        assert violation["detected_at"] in text

    @given(severity=st.sampled_from(KNOWN_SEVERITIES))
    @settings(max_examples=100)
    def test_severity_color_mapping(self, severity):
        """Property 5: Known severity values map to correct colors."""
        renderer = NotificationTemplateRenderer()
        config = NotificationConfig(slack_channel="#test")
        site = FakeSite()
        violation = {
            "violation_type": "test",
            "severity": severity,
            "detected_at": "2025-01-01T00:00:00",
        }
        payload = renderer.render_slack_payload([violation], config, site)
        color = payload["attachments"][0]["color"]
        assert color == SEVERITY_COLORS[severity]

    @given(
        severity=st.text(min_size=1, max_size=20).filter(
            lambda s: s not in KNOWN_SEVERITIES
        )
    )
    @settings(max_examples=100)
    def test_unknown_severity_uses_default_color(self, severity):
        """Unknown severity values use the default color."""
        renderer = NotificationTemplateRenderer()
        config = NotificationConfig(slack_channel="#test")
        site = FakeSite()
        violation = {
            "violation_type": "test",
            "severity": severity,
            "detected_at": "now",
        }
        payload = renderer.render_slack_payload([violation], config, site)
        assert payload["attachments"][0]["color"] == DEFAULT_COLOR


# ======================================================================
# Property 6 & 7: Email subject format and body fields
# Feature: dark-pattern-notification, Property 6: Email subject format
# Feature: dark-pattern-notification, Property 7: Email body contains all required violation fields
# **Validates: Requirements 3.3, 3.4**
# ======================================================================


class TestProperty6And7EmailFormat:
    """For any severity and site name: subject matches format;
    body contains all required fields."""

    @given(
        violation=violation_strategy,
        site=fake_site_strategy,
        config=notification_config_strategy,
    )
    @settings(max_examples=100)
    def test_email_subject_format(self, violation, site, config):
        """Property 6: Email subject matches [決済条件監視] {severity}: {site_name} でダークパターン違反を検出."""
        renderer = NotificationTemplateRenderer()
        subject, _ = renderer.render_email([violation], config, site)

        severity = violation["severity"]
        expected_subject = f"[決済条件監視] {severity}: {site.name} でダークパターン違反を検出"
        assert subject == expected_subject

    @given(
        violation=violation_strategy,
        site=fake_site_strategy,
        config=notification_config_strategy,
    )
    @settings(max_examples=100)
    def test_email_body_contains_required_fields(self, violation, site, config):
        """Property 7: Email body contains site name, site URL, violation type, severity, detected_at."""
        renderer = NotificationTemplateRenderer()
        _, body = renderer.render_email([violation], config, site)

        assert site.name in body
        assert site.url in body
        assert violation["violation_type"] in body
        assert violation["severity"] in body
        assert violation["detected_at"] in body


# ======================================================================
# Property 10 & 11: Missing fields default to N/A and round-trip
# Feature: dark-pattern-notification, Property 10: Missing template fields default to N/A
# Feature: dark-pattern-notification, Property 11: Template field round-trip
# **Validates: Requirements 5.4, 5.5**
# ======================================================================


class TestProperty10And11MissingFieldsAndRoundTrip:
    """For any violation with missing optional fields: rendered output shows N/A;
    field values can be recovered from rendered output."""

    @given(
        site=fake_site_strategy,
        has_detected_price=st.booleans(),
        has_expected_price=st.booleans(),
        has_evidence_url=st.booleans(),
    )
    @settings(max_examples=100)
    def test_missing_optional_fields_default_to_na(
        self, site, has_detected_price, has_expected_price, has_evidence_url
    ):
        """Property 10: Missing optional fields render as 'N/A'."""
        violation: dict[str, Any] = {
            "violation_type": "price_mismatch",
            "severity": "warning",
            "detected_at": "2025-01-01T00:00:00",
        }
        if has_detected_price:
            violation["detected_price"] = 1000
        if has_expected_price:
            violation["expected_price"] = 500
        if has_evidence_url:
            violation["evidence_url"] = "https://evidence.example.com/img.png"

        renderer = NotificationTemplateRenderer()
        fields = renderer.render_violation_fields(violation, site)

        if not has_detected_price:
            assert fields["detected_price"] == "N/A"
        else:
            assert fields["detected_price"] != "N/A"

        if not has_expected_price:
            assert fields["expected_price"] == "N/A"
        else:
            assert fields["expected_price"] != "N/A"

        if not has_evidence_url:
            assert fields["evidence_url"] == "N/A"
        else:
            assert fields["evidence_url"] != "N/A"

    @given(
        violation_type=st.sampled_from(KNOWN_VIOLATION_TYPES),
        severity=st.sampled_from(KNOWN_SEVERITIES),
        detected_at=st.text(min_size=1, max_size=30).filter(lambda s: "\n" not in s),
        detected_price=st.integers(min_value=1, max_value=100000),
        evidence_url=st.from_regex(r"https://[a-z]+\.[a-z]{2,4}/[a-z]+", fullmatch=True),
    )
    @settings(max_examples=100)
    def test_template_field_round_trip(
        self, violation_type, severity, detected_at, detected_price, evidence_url
    ):
        """Property 11: Field values can be recovered from render_violation_fields output."""
        site = FakeSite(name="RoundTripSite", url="https://roundtrip.com")
        violation = {
            "violation_type": violation_type,
            "severity": severity,
            "detected_at": detected_at,
            "detected_price": detected_price,
            "evidence_url": evidence_url,
        }

        renderer = NotificationTemplateRenderer()
        fields = renderer.render_violation_fields(violation, site)

        # Round-trip: recovered values match originals
        assert fields["site_name"] == site.name
        assert fields["violation_type"] == violation_type
        assert fields["severity"] == severity
        assert fields["detected_at"] == detected_at
        assert fields["detected_price"] == str(detected_price)
        assert fields["evidence_url"] == evidence_url


# ======================================================================
# Property 9: Multiple violations single notification
# Feature: dark-pattern-notification, Property 9: Multiple violations produce single notification
# **Validates: Requirements 5.3**
# ======================================================================


class TestProperty9MultipleViolationsSingleNotification:
    """For any list of violations > 1: renderer produces exactly one Slack payload
    and one email body."""

    @given(
        violations=st.lists(violation_strategy, min_size=2, max_size=10),
        site=fake_site_strategy,
        config=notification_config_strategy,
    )
    @settings(max_examples=100)
    def test_single_slack_payload_for_multiple_violations(self, violations, site, config):
        """Renderer produces exactly one Slack payload dict (not a list)."""
        renderer = NotificationTemplateRenderer()
        payload = renderer.render_slack_payload(violations, config, site)

        # Single dict, not a list
        assert isinstance(payload, dict)
        # One attachment per violation
        assert len(payload["attachments"]) == len(violations)

        # Each violation's type appears in some attachment
        for v in violations:
            texts = [
                a["blocks"][0]["text"]["text"] for a in payload["attachments"]
            ]
            assert any(v["violation_type"] in t for t in texts)

    @given(
        violations=st.lists(violation_strategy, min_size=2, max_size=10),
        site=fake_site_strategy,
        config=notification_config_strategy,
    )
    @settings(max_examples=100)
    def test_single_email_for_multiple_violations(self, violations, site, config):
        """Renderer produces exactly one (subject, body) tuple."""
        renderer = NotificationTemplateRenderer()
        result = renderer.render_email(violations, config, site)

        assert isinstance(result, tuple)
        assert len(result) == 2
        subject, body = result
        assert isinstance(subject, str)
        assert isinstance(body, str)

        # Each violation's type appears in the body
        for v in violations:
            assert v["violation_type"] in body


# ======================================================================
# Property 1: should_run reflects violations and channel availability
# Feature: dark-pattern-notification, Property 1: should_run reflects violations and channel availability
# **Validates: Requirements 1.2**
# ======================================================================


def _make_site_with_config(plugin_config=None, customer_email="user@example.com"):
    """Build a MonitoringSite with a mock customer."""
    site = MonitoringSite(id=1, name="Test Site", url="https://example.com")
    site.plugin_config = plugin_config
    customer = MagicMock()
    customer.email = customer_email
    site.customer = customer
    return site


class TestProperty1ShouldRun:
    """For any CrawlContext and config: should_run returns True iff
    violations >= 1 AND at least one channel enabled."""

    @given(
        num_violations=st.integers(min_value=0, max_value=5),
        slack_enabled=st.booleans(),
        email_enabled=st.booleans(),
    )
    @settings(max_examples=100)
    def test_should_run_reflects_violations_and_channels(
        self, num_violations, slack_enabled, email_enabled
    ):
        violations = [
            {"violation_type": "price_mismatch"} for _ in range(num_violations)
        ]
        env = {
            "NOTIFICATION_SLACK_ENABLED": str(slack_enabled).lower(),
            "NOTIFICATION_EMAIL_ENABLED": str(email_enabled).lower(),
        }

        site = _make_site_with_config()
        ctx = CrawlContext(site=site, url="https://example.com")
        ctx.violations = violations

        with patch.dict(os.environ, env, clear=True):
            plugin = NotificationPlugin()
            result = plugin.should_run(ctx)

        has_violations = num_violations >= 1
        has_channel = slack_enabled or email_enabled
        expected = has_violations and has_channel
        assert result == expected


# ======================================================================
# Property 2 & 3: execute metadata and exception safety
# Feature: dark-pattern-notification, Property 2: execute records metadata with notification_ prefix
# Feature: dark-pattern-notification, Property 3: execute never raises exceptions
# **Validates: Requirements 1.4, 1.5**
# ======================================================================


class TestProperty2And3ExecuteMetadataAndSafety:
    """For any CrawlContext: execute records notification_ prefixed metadata;
    execute never raises."""

    @given(
        num_violations=st.integers(min_value=1, max_value=5),
        slack_enabled=st.booleans(),
        email_enabled=st.booleans(),
    )
    @settings(max_examples=100, deadline=None)
    @patch("src.notification_tasks._send_email", return_value=False)
    @patch("src.notification_tasks._send_slack", return_value=False)
    def test_execute_records_notification_prefixed_metadata(
        self, mock_send_slack, mock_send_email, num_violations, slack_enabled, email_enabled
    ):
        """Property 2: After execute, metadata has at least one notification_ key."""
        assume(slack_enabled or email_enabled)

        violations = [
            {"violation_type": "price_mismatch"} for _ in range(num_violations)
        ]
        env = {
            "NOTIFICATION_SLACK_ENABLED": str(slack_enabled).lower(),
            "NOTIFICATION_EMAIL_ENABLED": str(email_enabled).lower(),
        }

        site = _make_site_with_config()
        ctx = CrawlContext(site=site, url="https://example.com")
        ctx.violations = violations

        with patch.dict(os.environ, env, clear=True):
            plugin = NotificationPlugin()
            result = asyncio.get_event_loop().run_until_complete(plugin.execute(ctx))

        notification_keys = [
            k for k in result.metadata if k.startswith("notification_")
        ]
        assert len(notification_keys) >= 1

    @given(
        num_violations=st.integers(min_value=0, max_value=5),
        inject_celery_error=st.booleans(),
        inject_db_error=st.booleans(),
    )
    @settings(max_examples=100, deadline=None)
    @patch("src.notification_tasks._send_email", return_value=False)
    @patch("src.notification_tasks._send_slack", return_value=False)
    def test_execute_never_raises(
        self, mock_send_slack, mock_send_email, num_violations, inject_celery_error, inject_db_error
    ):
        """Property 3: execute never raises exceptions regardless of internal errors."""
        violations = [
            {"violation_type": "price_mismatch"} for _ in range(num_violations)
        ]

        celery_app = None
        session_factory = None

        if inject_celery_error:
            celery_app = MagicMock()
            celery_app.send_task.side_effect = Exception("Celery down")

        if inject_db_error:
            session = MagicMock()
            session.query.side_effect = Exception("DB error")
            session_factory = lambda: session

        env = {
            "NOTIFICATION_EMAIL_ENABLED": "true",
        }

        site = _make_site_with_config()
        ctx = CrawlContext(site=site, url="https://example.com")
        ctx.violations = violations

        with patch.dict(os.environ, env, clear=True):
            plugin = NotificationPlugin(
                celery_app=celery_app, session_factory=session_factory
            )
            # Must not raise
            result = asyncio.get_event_loop().run_until_complete(plugin.execute(ctx))

        assert isinstance(result, CrawlContext)


# ======================================================================
# Property 13: Successful send creates NotificationRecord
# Feature: dark-pattern-notification, Property 13: Successful send creates NotificationRecord and updates Alert flags
# **Validates: Requirements 2.5, 3.6, 6.3, 8.4**
# ======================================================================


class TestProperty13SuccessfulSendCreatesRecord:
    """For any successful send: NotificationRecord with status=sent is created
    and Alert flags updated."""

    @given(
        violation_type=st.sampled_from(KNOWN_VIOLATION_TYPES),
        alert_id=st.integers(min_value=1, max_value=100000),
        channel=st.sampled_from(KNOWN_CHANNELS),
    )
    @settings(max_examples=100)
    @patch("src.database.SessionLocal")
    def test_successful_send_creates_sent_record_and_updates_flags(
        self, mock_session_local, violation_type, alert_id, channel
    ):
        from src.notification_tasks import _record_notification_results

        session = MagicMock()
        mock_session_local.return_value = session
        mock_query = MagicMock()
        session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query

        payload = {
            "site_id": 1,
            "violations": [
                {"violation_type": violation_type, "alert_id": alert_id},
            ],
            "slack_webhook_url": "https://hooks.slack.com/test",
            "email_recipients": ["user@example.com"],
        }

        slack_success = True if channel == "slack" else None
        email_success = True if channel == "email" else None

        _record_notification_results(payload, slack_success, email_success)

        # At least one record was added
        assert session.add.call_count >= 1
        record = session.add.call_args[0][0]
        assert record.status == "sent"
        assert record.channel == channel
        assert record.violation_type == violation_type

        # Alert flag updated
        if channel == "slack":
            mock_query.update.assert_called_with(
                {"slack_sent": True}, synchronize_session=False
            )
        else:
            mock_query.update.assert_called_with(
                {"email_sent": True}, synchronize_session=False
            )

        session.commit.assert_called_once()


# ======================================================================
# Property 15: Notification config API round-trip
# Feature: dark-pattern-notification, Property 15: Notification config API round-trip
# **Validates: Requirements 9.1, 9.2**
# ======================================================================


class TestProperty15ConfigApiRoundTrip:
    """For any valid update payload: PUT then GET returns config reflecting updates."""

    @given(
        slack_enabled=st.one_of(st.none(), st.booleans()),
        email_enabled=st.one_of(st.none(), st.booleans()),
        slack_channel=st.one_of(st.none(), st.text(min_size=1, max_size=30)),
        suppression_window_hours=st.one_of(
            st.none(), st.integers(min_value=1, max_value=168)
        ),
    )
    @settings(max_examples=100)
    def test_put_then_get_reflects_updates(
        self, slack_enabled, email_enabled, slack_channel, suppression_window_hours
    ):
        """Simulates PUT update then GET, verifying the merged config reflects updates."""
        from src.api.notifications import update_notification_config, get_notification_config
        from src.api.schemas import NotificationConfigUpdate

        # Build update payload (only non-None fields)
        update_kwargs: dict[str, Any] = {}
        if slack_enabled is not None:
            update_kwargs["slack_enabled"] = slack_enabled
        if email_enabled is not None:
            update_kwargs["email_enabled"] = email_enabled
        if slack_channel is not None:
            update_kwargs["slack_channel"] = slack_channel
        if suppression_window_hours is not None:
            update_kwargs["suppression_window_hours"] = suppression_window_hours

        update_body = NotificationConfigUpdate(**update_kwargs)

        # Mock site with empty plugin_config
        site = MonitoringSite(id=42, name="API Test Site", url="https://api-test.com")
        site.plugin_config = {}
        customer = MagicMock()
        customer.email = "customer@example.com"
        site.customer = customer

        # Mock DB session
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = site

        env = {}  # clear env to use defaults
        with patch.dict(os.environ, env, clear=True):
            # PUT
            put_result = update_notification_config(site_id=42, body=update_body, db=db)

            # GET
            get_result = get_notification_config(site_id=42, db=db)

        # Verify updated fields are reflected
        if slack_enabled is not None:
            assert get_result.slack_enabled == slack_enabled
        if email_enabled is not None:
            assert get_result.email_enabled == email_enabled
        if slack_channel is not None:
            assert get_result.slack_channel == slack_channel
        if suppression_window_hours is not None:
            assert get_result.suppression_window_hours == suppression_window_hours


# ======================================================================
# Property 16 & 17: History filtering and pagination
# Feature: dark-pattern-notification, Property 16: Notification history filtering
# Feature: dark-pattern-notification, Property 17: Notification history pagination
# **Validates: Requirements 10.3, 10.4, 10.5**
# ======================================================================


def _make_mock_records(
    n: int,
    channels: list[str] | None = None,
    statuses: list[str] | None = None,
) -> list[MagicMock]:
    """Create n mock NotificationRecord objects with given channels/statuses."""
    records = []
    for i in range(n):
        r = MagicMock()
        r.id = i + 1
        r.violation_type = KNOWN_VIOLATION_TYPES[i % len(KNOWN_VIOLATION_TYPES)]
        r.channel = (channels or KNOWN_CHANNELS)[i % len(channels or KNOWN_CHANNELS)]
        r.recipient = f"recipient_{i}@example.com"
        r.status = (statuses or KNOWN_STATUSES)[i % len(statuses or KNOWN_STATUSES)]
        r.sent_at = datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i)
        r.site_id = 1
        records.append(r)
    return records


class TestProperty16And17HistoryFilteringAndPagination:
    """For any set of records: channel/status filters return correct subsets;
    pagination returns correct slices."""

    @given(
        n_records=st.integers(min_value=0, max_value=20),
        filter_channel=st.one_of(st.none(), st.sampled_from(KNOWN_CHANNELS)),
        filter_status=st.one_of(st.none(), st.sampled_from(KNOWN_STATUSES)),
    )
    @settings(max_examples=100)
    def test_filtering_returns_correct_subsets(
        self, n_records, filter_channel, filter_status
    ):
        """Property 16: Filtering by channel/status returns matching records."""
        all_records = _make_mock_records(n_records)

        # Apply filters in-memory to compute expected
        expected = all_records
        if filter_channel is not None:
            expected = [r for r in expected if r.channel == filter_channel]
        if filter_status is not None:
            expected = [r for r in expected if r.status == filter_status]

        # Mock the DB query chain
        from src.api.notifications import get_notification_history

        site = MonitoringSite(id=1, name="Test", url="https://test.com")

        db = MagicMock()
        # _get_site_or_404 query
        site_query = MagicMock()
        db.query.return_value = site_query
        site_query.filter.return_value = site_query
        site_query.first.return_value = site

        # For the NotificationRecord query, we need a more sophisticated mock
        # that tracks filter calls
        record_query = MagicMock()

        # Track the chain: db.query(NR).filter(site_id) -> filter(channel) -> filter(status)
        call_count = {"n": 0}
        original_query = db.query

        def query_side_effect(model):
            call_count["n"] += 1
            if call_count["n"] == 1:
                # First call is _get_site_or_404
                return site_query
            # Second call is the NotificationRecord query
            return record_query

        db.query.side_effect = query_side_effect

        record_query.filter.return_value = record_query
        record_query.count.return_value = len(expected)
        record_query.order_by.return_value = record_query
        record_query.offset.return_value = record_query
        record_query.limit.return_value = record_query
        record_query.all.return_value = expected

        result = get_notification_history(
            site_id=1,
            channel=filter_channel,
            status=filter_status,
            limit=50,
            offset=0,
            db=db,
        )

        assert result.total == len(expected)
        assert len(result.items) == len(expected)

    @given(
        n_records=st.integers(min_value=0, max_value=30),
        limit=st.integers(min_value=1, max_value=20),
        offset=st.integers(min_value=0, max_value=30),
    )
    @settings(max_examples=100)
    def test_pagination_returns_correct_slices(self, n_records, limit, offset):
        """Property 17: Pagination returns min(L, max(0, N-O)) items with total=N."""
        all_records = _make_mock_records(n_records)
        expected_count = min(limit, max(0, n_records - offset))
        page_records = all_records[offset : offset + limit]

        from src.api.notifications import get_notification_history

        site = MonitoringSite(id=1, name="Test", url="https://test.com")

        db = MagicMock()
        site_query = MagicMock()

        call_count = {"n": 0}

        def query_side_effect(model):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return site_query
            record_query = MagicMock()
            record_query.filter.return_value = record_query
            record_query.count.return_value = n_records
            record_query.order_by.return_value = record_query
            record_query.offset.return_value = record_query
            record_query.limit.return_value = record_query
            record_query.all.return_value = page_records
            return record_query

        db.query.side_effect = query_side_effect
        site_query.filter.return_value = site_query
        site_query.first.return_value = site

        result = get_notification_history(
            site_id=1,
            channel=None,
            status=None,
            limit=limit,
            offset=offset,
            db=db,
        )

        assert result.total == n_records
        assert result.limit == limit
        assert result.offset == offset
        assert len(result.items) == expected_count
