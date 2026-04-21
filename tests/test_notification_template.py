"""
Unit tests for NotificationTemplateRenderer.

Tests Slack payload generation, email rendering, severity color mapping,
missing field defaults, and multiple violation handling.

Requirements: 2.2, 2.3, 3.3, 3.4, 5.1, 5.2, 5.3, 5.4, 5.5
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.pipeline.plugins.notification_config import NotificationConfig
from src.pipeline.plugins.notification_template import (
    DEFAULT_COLOR,
    SEVERITY_COLORS,
    NotificationTemplateRenderer,
)


@dataclass
class FakeSite:
    """Minimal site object satisfying SiteLike protocol."""

    name: str = "テストサイト"
    url: str = "https://example.com"


@pytest.fixture
def renderer():
    return NotificationTemplateRenderer()


@pytest.fixture
def config():
    return NotificationConfig(
        slack_enabled=True,
        slack_webhook_url="https://hooks.slack.com/services/T00/B00/xxxx",
        slack_channel="#alerts",
        email_enabled=True,
        email_recipients=["user@example.com"],
    )


@pytest.fixture
def site():
    return FakeSite()


@pytest.fixture
def full_violation():
    return {
        "violation_type": "price_mismatch",
        "severity": "critical",
        "detected_at": "2025-01-15T10:30:00",
        "detected_price": 1980,
        "expected_price": 980,
        "evidence_url": "https://storage.example.com/evidence/123.png",
    }


@pytest.fixture
def minimal_violation():
    """Violation with only required fields."""
    return {
        "violation_type": "dark_pattern",
        "severity": "warning",
        "detected_at": "2025-01-15T11:00:00",
    }


# --- render_violation_fields ---


class TestRenderViolationFields:
    def test_full_violation_extracts_all_fields(self, renderer, site, full_violation):
        fields = renderer.render_violation_fields(full_violation, site)
        assert fields["site_name"] == "テストサイト"
        assert fields["site_url"] == "https://example.com"
        assert fields["violation_type"] == "price_mismatch"
        assert fields["severity"] == "critical"
        assert fields["detected_at"] == "2025-01-15T10:30:00"
        assert fields["detected_price"] == "1980"
        assert fields["expected_price"] == "980"
        assert fields["evidence_url"] == "https://storage.example.com/evidence/123.png"

    def test_missing_optional_fields_default_to_na(self, renderer, site, minimal_violation):
        fields = renderer.render_violation_fields(minimal_violation, site)
        assert fields["detected_price"] == "N/A"
        assert fields["expected_price"] == "N/A"
        assert fields["evidence_url"] == "N/A"

    def test_empty_violation_all_na(self, renderer, site):
        fields = renderer.render_violation_fields({}, site)
        assert fields["violation_type"] == "N/A"
        assert fields["severity"] == "N/A"
        assert fields["detected_at"] == "N/A"
        assert fields["detected_price"] == "N/A"
        assert fields["expected_price"] == "N/A"
        assert fields["evidence_url"] == "N/A"
        # site fields still come from site object
        assert fields["site_name"] == "テストサイト"
        assert fields["site_url"] == "https://example.com"


# --- render_slack_payload ---


class TestRenderSlackPayload:
    def test_slack_payload_contains_required_fields(
        self, renderer, config, site, full_violation
    ):
        payload = renderer.render_slack_payload([full_violation], config, site)
        assert "attachments" in payload
        assert len(payload["attachments"]) == 1
        text = payload["attachments"][0]["blocks"][0]["text"]["text"]
        assert "テストサイト" in text
        assert "price_mismatch" in text
        assert "critical" in text
        assert "2025-01-15T10:30:00" in text

    def test_slack_payload_includes_optional_fields_when_present(
        self, renderer, config, site, full_violation
    ):
        payload = renderer.render_slack_payload([full_violation], config, site)
        text = payload["attachments"][0]["blocks"][0]["text"]["text"]
        assert "1980" in text
        assert "https://storage.example.com/evidence/123.png" in text

    def test_slack_payload_omits_optional_fields_when_missing(
        self, renderer, config, site, minimal_violation
    ):
        payload = renderer.render_slack_payload([minimal_violation], config, site)
        text = payload["attachments"][0]["blocks"][0]["text"]["text"]
        assert "N/A" not in text
        assert "検出価格" not in text
        assert "証拠URL" not in text

    def test_severity_color_warning(self, renderer, config, site):
        violation = {"violation_type": "test", "severity": "warning", "detected_at": "now"}
        payload = renderer.render_slack_payload([violation], config, site)
        assert payload["attachments"][0]["color"] == "#FFA500"

    def test_severity_color_critical(self, renderer, config, site):
        violation = {"violation_type": "test", "severity": "critical", "detected_at": "now"}
        payload = renderer.render_slack_payload([violation], config, site)
        assert payload["attachments"][0]["color"] == "#FF0000"

    def test_severity_color_info(self, renderer, config, site):
        violation = {"violation_type": "test", "severity": "info", "detected_at": "now"}
        payload = renderer.render_slack_payload([violation], config, site)
        assert payload["attachments"][0]["color"] == "#0000FF"

    def test_unknown_severity_uses_default_color(self, renderer, config, site):
        violation = {"violation_type": "test", "severity": "unknown", "detected_at": "now"}
        payload = renderer.render_slack_payload([violation], config, site)
        assert payload["attachments"][0]["color"] == DEFAULT_COLOR

    def test_slack_channel_from_config(self, renderer, config, site, full_violation):
        config.slack_channel = "#custom-channel"
        payload = renderer.render_slack_payload([full_violation], config, site)
        assert payload["channel"] == "#custom-channel"


# --- render_email ---


class TestRenderEmail:
    def test_email_subject_format(self, renderer, config, site, full_violation):
        subject, _ = renderer.render_email([full_violation], config, site)
        assert subject == "[決済条件監視] critical: テストサイト でダークパターン違反を検出"

    def test_email_subject_uses_worst_severity(self, renderer, config, site):
        violations = [
            {"violation_type": "a", "severity": "info", "detected_at": "now"},
            {"violation_type": "b", "severity": "critical", "detected_at": "now"},
            {"violation_type": "c", "severity": "warning", "detected_at": "now"},
        ]
        subject, _ = renderer.render_email(violations, config, site)
        assert "[決済条件監視] critical:" in subject

    def test_email_body_contains_required_fields(
        self, renderer, config, site, full_violation
    ):
        _, body = renderer.render_email([full_violation], config, site)
        assert "テストサイト" in body
        assert "https://example.com" in body
        assert "price_mismatch" in body
        assert "critical" in body
        assert "2025-01-15T10:30:00" in body

    def test_email_body_contains_optional_fields_when_present(
        self, renderer, config, site, full_violation
    ):
        _, body = renderer.render_email([full_violation], config, site)
        assert "1980" in body
        assert "980" in body
        assert "https://storage.example.com/evidence/123.png" in body

    def test_email_body_shows_na_for_missing_fields(
        self, renderer, config, site, minimal_violation
    ):
        _, body = renderer.render_email([minimal_violation], config, site)
        assert "N/A" in body


# --- Multiple violations ---


class TestMultipleViolations:
    def test_slack_multiple_violations_single_payload(self, renderer, config, site):
        violations = [
            {"violation_type": "price_mismatch", "severity": "critical", "detected_at": "t1"},
            {"violation_type": "dark_pattern", "severity": "warning", "detected_at": "t2"},
            {"violation_type": "structured_data_failure", "severity": "info", "detected_at": "t3"},
        ]
        payload = renderer.render_slack_payload(violations, config, site)
        # Single payload dict, not a list
        assert isinstance(payload, dict)
        # One attachment per violation
        assert len(payload["attachments"]) == 3
        # Each violation's details appear
        texts = [a["blocks"][0]["text"]["text"] for a in payload["attachments"]]
        assert any("price_mismatch" in t for t in texts)
        assert any("dark_pattern" in t for t in texts)
        assert any("structured_data_failure" in t for t in texts)

    def test_email_multiple_violations_single_email(self, renderer, config, site):
        violations = [
            {"violation_type": "price_mismatch", "severity": "critical", "detected_at": "t1"},
            {"violation_type": "dark_pattern", "severity": "warning", "detected_at": "t2"},
        ]
        subject, body = renderer.render_email(violations, config, site)
        # Single subject/body tuple
        assert isinstance(subject, str)
        assert isinstance(body, str)
        # Both violations appear in body
        assert "price_mismatch" in body
        assert "dark_pattern" in body
        assert "2件" in body
