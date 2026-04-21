"""
Unit tests for notification_config module.

Tests NotificationConfig dataclass, merge_notification_config, and mask_webhook_url.
Requirements: 3.2, 4.1, 4.2, 4.3, 4.4, 4.5, 9.4
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from src.pipeline.plugins.notification_config import (
    NotificationConfig,
    mask_webhook_url,
    merge_notification_config,
)


class TestNotificationConfigDefaults:
    """NotificationConfig dataclass default values."""

    def test_defaults(self):
        config = NotificationConfig()
        assert config.slack_enabled is False
        assert config.slack_webhook_url is None
        assert config.slack_channel == "#alerts"
        assert config.email_enabled is True
        assert config.email_recipients == []
        assert config.suppression_window_hours == 24


class TestMergeNotificationConfig:
    """merge_notification_config pure function tests."""

    @patch.dict(os.environ, {}, clear=True)
    def test_defaults_from_env(self):
        """Global env defaults when no env vars or site config."""
        config = merge_notification_config("user@example.com")
        assert config.slack_enabled is False
        assert config.slack_webhook_url is None
        assert config.slack_channel == "#alerts"
        assert config.email_enabled is True
        assert config.email_recipients == ["user@example.com"]
        assert config.suppression_window_hours == 24

    @patch.dict(os.environ, {
        "NOTIFICATION_SLACK_WEBHOOK_URL": "https://hooks.slack.com/test",
        "NOTIFICATION_SLACK_CHANNEL": "#custom",
        "NOTIFICATION_EMAIL_ENABLED": "false",
        "NOTIFICATION_SLACK_ENABLED": "true",
        "NOTIFICATION_SUPPRESSION_WINDOW_HOURS": "48",
    }, clear=True)
    def test_env_vars_applied(self):
        """Environment variables override defaults."""
        config = merge_notification_config("user@example.com")
        assert config.slack_enabled is True
        assert config.slack_webhook_url == "https://hooks.slack.com/test"
        assert config.slack_channel == "#custom"
        assert config.email_enabled is False
        assert config.suppression_window_hours == 48

    @patch.dict(os.environ, {
        "NOTIFICATION_SLACK_ENABLED": "false",
        "NOTIFICATION_EMAIL_ENABLED": "true",
    }, clear=True)
    def test_site_config_overrides_env(self):
        """Site plugin_config overrides global env vars."""
        site_config = {
            "params": {
                "NotificationPlugin": {
                    "slack_enabled": True,
                    "slack_channel": "#site-alerts",
                    "email_enabled": False,
                    "slack_webhook_url": "https://hooks.slack.com/site",
                    "suppression_window_hours": 12,
                }
            }
        }
        config = merge_notification_config("user@example.com", site_config)
        assert config.slack_enabled is True
        assert config.slack_channel == "#site-alerts"
        assert config.email_enabled is False
        assert config.slack_webhook_url == "https://hooks.slack.com/site"
        assert config.suppression_window_hours == 12

    @patch.dict(os.environ, {
        "NOTIFICATION_OVERRIDE_DISABLED": "true",
        "NOTIFICATION_SLACK_ENABLED": "true",
        "NOTIFICATION_EMAIL_ENABLED": "true",
    }, clear=True)
    def test_override_disabled_disables_all(self):
        """NOTIFICATION_OVERRIDE_DISABLED=true disables all channels."""
        site_config = {
            "params": {
                "NotificationPlugin": {
                    "slack_enabled": True,
                    "email_enabled": True,
                }
            }
        }
        config = merge_notification_config("user@example.com", site_config)
        assert config.slack_enabled is False
        assert config.email_enabled is False

    @patch.dict(os.environ, {}, clear=True)
    def test_email_recipients_deduplication(self):
        """Customer email + additional_email_recipients, deduplicated."""
        site_config = {
            "params": {
                "NotificationPlugin": {
                    "additional_email_recipients": [
                        "extra@example.com",
                        "user@example.com",  # duplicate of customer email
                        "another@example.com",
                    ]
                }
            }
        }
        config = merge_notification_config("user@example.com", site_config)
        assert config.email_recipients == [
            "user@example.com",
            "extra@example.com",
            "another@example.com",
        ]

    @patch.dict(os.environ, {}, clear=True)
    def test_customer_email_first_in_recipients(self):
        """Customer email is always first in email_recipients."""
        site_config = {
            "params": {
                "NotificationPlugin": {
                    "additional_email_recipients": ["first@example.com"]
                }
            }
        }
        config = merge_notification_config("customer@example.com", site_config)
        assert config.email_recipients[0] == "customer@example.com"

    @patch.dict(os.environ, {}, clear=True)
    def test_none_site_config(self):
        """None site_config uses only env defaults."""
        config = merge_notification_config("user@example.com", None)
        assert config.email_recipients == ["user@example.com"]
        assert config.slack_enabled is False

    @patch.dict(os.environ, {}, clear=True)
    def test_empty_site_config(self):
        """Empty site_config dict uses only env defaults."""
        config = merge_notification_config("user@example.com", {})
        assert config.email_recipients == ["user@example.com"]

    @patch.dict(os.environ, {}, clear=True)
    def test_site_config_missing_notification_plugin_key(self):
        """Site config without NotificationPlugin key uses env defaults."""
        site_config = {"params": {"OtherPlugin": {"key": "value"}}}
        config = merge_notification_config("user@example.com", site_config)
        assert config.slack_enabled is False
        assert config.email_enabled is True


class TestMaskWebhookUrl:
    """mask_webhook_url helper tests."""

    def test_none_returns_none(self):
        assert mask_webhook_url(None) is None

    def test_long_url_masks_except_last_8(self):
        url = "https://hooks.slack.com/services/T00/B00/xxxx1234"
        masked = mask_webhook_url(url)
        assert masked is not None
        assert masked.endswith("xxxx1234")
        assert masked[: len(masked) - 8] == "*" * (len(url) - 8)

    def test_exactly_8_chars(self):
        url = "12345678"
        masked = mask_webhook_url(url)
        assert masked == "12345678"

    def test_less_than_8_chars(self):
        url = "short"
        masked = mask_webhook_url(url)
        assert masked == "*****"

    def test_empty_string(self):
        masked = mask_webhook_url("")
        assert masked == ""
