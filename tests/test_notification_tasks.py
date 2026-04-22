"""
Unit tests for notification_tasks module.

Tests _send_slack retries, _send_email retries,
send_notification creating NotificationRecord on success,
and send_notification updating Alert flags on success.

Requirements: 2.4, 2.5, 3.5, 3.6, 6.3, 8.1, 8.2, 8.3, 8.4
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.notification_tasks import _send_slack, _send_email, _record_notification_results


# ------------------------------------------------------------------
# _send_slack retries on failure (Req 2.4)
# ------------------------------------------------------------------


class TestSendSlackRetries:
    @patch("src.notification_tasks.httpx.post")
    def test_returns_true_on_first_success(self, mock_post):
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        mock_post.return_value = resp

        result = _send_slack("https://hooks.slack.com/test", {"text": "hi"})

        assert result is True
        mock_post.assert_called_once()

    @patch("src.notification_tasks.httpx.post")
    def test_retries_on_5xx_then_succeeds(self, mock_post):
        import httpx

        fail_resp = MagicMock()
        fail_resp.status_code = 500
        fail_resp.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Server Error",
                request=httpx.Request("POST", "https://hooks.slack.com/test"),
                response=MagicMock(status_code=500),
            )
        )
        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.raise_for_status = MagicMock()
        mock_post.side_effect = [fail_resp, ok_resp]

        result = _send_slack("https://hooks.slack.com/test", {"text": "hi"})

        assert result is True
        assert mock_post.call_count == 2

    @patch("src.notification_tasks.httpx.post")
    def test_retries_on_connection_error_then_succeeds(self, mock_post):
        import httpx as _httpx

        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.raise_for_status = MagicMock()
        mock_post.side_effect = [
            OSError("connection error"),
            ok_resp,
        ]

        result = _send_slack("https://hooks.slack.com/test", {"text": "hi"})

        assert result is True
        assert mock_post.call_count == 2

    @patch("src.notification_tasks.httpx.post")
    def test_returns_false_after_3_failures(self, mock_post):
        mock_post.side_effect = OSError("down")

        result = _send_slack("https://hooks.slack.com/test", {"text": "hi"})

        assert result is False
        assert mock_post.call_count == 3

    @patch("src.notification_tasks.httpx.post")
    def test_does_not_retry_on_4xx(self, mock_post):
        import httpx

        resp_403 = MagicMock()
        resp_403.status_code = 403
        resp_403.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Forbidden",
                request=httpx.Request("POST", "https://hooks.slack.com/test"),
                response=MagicMock(status_code=403),
            )
        )
        mock_post.return_value = resp_403

        result = _send_slack("https://hooks.slack.com/test", {"text": "hi"})

        assert result is False
        assert mock_post.call_count == 1


# ------------------------------------------------------------------
# _send_email retries on failure (Req 3.5)
# ------------------------------------------------------------------


class TestSendEmailRetries:
    @patch("src.notification_tasks.smtplib.SMTP")
    def test_returns_true_on_first_success(self, mock_smtp_cls):
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = _send_email(["user@example.com"], "Subject", "Body")

        assert result is True

    @patch("src.notification_tasks.smtplib.SMTP")
    def test_retries_on_smtp_error_then_succeeds(self, mock_smtp_cls):
        mock_server = MagicMock()
        # First call raises, second succeeds
        call_count = {"n": 0}

        def side_effect(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise ConnectionRefusedError("SMTP down")
            return mock_server

        mock_smtp_cls.return_value.__enter__ = MagicMock(side_effect=side_effect)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = _send_email(["user@example.com"], "Subject", "Body")

        assert result is True

    @patch("src.notification_tasks.smtplib.SMTP")
    def test_returns_false_after_3_failures(self, mock_smtp_cls):
        mock_smtp_cls.return_value.__enter__ = MagicMock(
            side_effect=ConnectionRefusedError("SMTP down")
        )
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = _send_email(["user@example.com"], "Subject", "Body")

        assert result is False


# ------------------------------------------------------------------
# _record_notification_results — creates NotificationRecord (Req 6.3, 2.5, 3.6)
# ------------------------------------------------------------------


class TestRecordNotificationResults:
    @patch("src.database.SessionLocal")
    def test_creates_slack_notification_record_on_success(self, mock_session_local):
        session = MagicMock()
        mock_session_local.return_value = session

        payload = {
            "site_id": 1,
            "violations": [
                {"violation_type": "price_mismatch", "alert_id": 10},
            ],
            "slack_webhook_url": "https://hooks.slack.com/test",
            "email_recipients": [],
        }

        _record_notification_results(payload, slack_success=True, email_success=None)

        # Should add a NotificationRecord
        assert session.add.call_count == 1
        record = session.add.call_args[0][0]
        assert record.site_id == 1
        assert record.channel == "slack"
        assert record.status == "sent"
        assert record.violation_type == "price_mismatch"
        assert record.alert_id == 10
        session.commit.assert_called_once()

    @patch("src.database.SessionLocal")
    def test_creates_email_notification_record_on_success(self, mock_session_local):
        session = MagicMock()
        mock_session_local.return_value = session

        payload = {
            "site_id": 1,
            "violations": [
                {"violation_type": "dark_pattern", "alert_id": 20},
            ],
            "slack_webhook_url": "",
            "email_recipients": ["user@example.com"],
        }

        _record_notification_results(payload, slack_success=None, email_success=True)

        assert session.add.call_count == 1
        record = session.add.call_args[0][0]
        assert record.channel == "email"
        assert record.status == "sent"
        assert record.recipient == "user@example.com"
        session.commit.assert_called_once()

    @patch("src.database.SessionLocal")
    def test_creates_failed_record_on_failure(self, mock_session_local):
        session = MagicMock()
        mock_session_local.return_value = session

        payload = {
            "site_id": 1,
            "violations": [
                {"violation_type": "price_mismatch", "alert_id": 10},
            ],
            "slack_webhook_url": "https://hooks.slack.com/test",
            "email_recipients": [],
        }

        _record_notification_results(payload, slack_success=False, email_success=None)

        record = session.add.call_args[0][0]
        assert record.status == "failed"

    @patch("src.database.SessionLocal")
    def test_updates_alert_slack_sent_flag(self, mock_session_local):
        session = MagicMock()
        mock_session_local.return_value = session
        mock_query = MagicMock()
        session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query

        payload = {
            "site_id": 1,
            "violations": [
                {"violation_type": "price_mismatch", "alert_id": 10},
            ],
            "slack_webhook_url": "https://hooks.slack.com/test",
            "email_recipients": [],
        }

        _record_notification_results(payload, slack_success=True, email_success=None)

        # Alert.slack_sent should be updated
        mock_query.update.assert_called_once_with(
            {"slack_sent": True}, synchronize_session=False
        )

    @patch("src.database.SessionLocal")
    def test_updates_alert_email_sent_flag(self, mock_session_local):
        session = MagicMock()
        mock_session_local.return_value = session
        mock_query = MagicMock()
        session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query

        payload = {
            "site_id": 1,
            "violations": [
                {"violation_type": "dark_pattern", "alert_id": 20},
            ],
            "slack_webhook_url": "",
            "email_recipients": ["user@example.com"],
        }

        _record_notification_results(payload, slack_success=None, email_success=True)

        mock_query.update.assert_called_once_with(
            {"email_sent": True}, synchronize_session=False
        )

    @patch("src.database.SessionLocal")
    def test_does_not_update_flags_when_no_alert_ids(self, mock_session_local):
        session = MagicMock()
        mock_session_local.return_value = session

        payload = {
            "site_id": 1,
            "violations": [
                {"violation_type": "price_mismatch"},  # no alert_id
            ],
            "slack_webhook_url": "https://hooks.slack.com/test",
            "email_recipients": [],
        }

        _record_notification_results(payload, slack_success=True, email_success=None)

        # Should add record but not call query for Alert update
        assert session.add.call_count == 1
        session.query.assert_not_called()

    @patch("src.database.SessionLocal")
    def test_creates_records_for_multiple_violations(self, mock_session_local):
        session = MagicMock()
        mock_session_local.return_value = session

        payload = {
            "site_id": 1,
            "violations": [
                {"violation_type": "price_mismatch", "alert_id": 10},
                {"violation_type": "dark_pattern", "alert_id": 20},
            ],
            "slack_webhook_url": "https://hooks.slack.com/test",
            "email_recipients": ["user@example.com"],
        }

        _record_notification_results(payload, slack_success=True, email_success=True)

        # 2 violations × 2 channels = 4 records
        assert session.add.call_count == 4

    @patch("src.database.SessionLocal")
    def test_rollback_on_db_error(self, mock_session_local):
        session = MagicMock()
        mock_session_local.return_value = session
        session.commit.side_effect = Exception("DB error")

        payload = {
            "site_id": 1,
            "violations": [{"violation_type": "price_mismatch"}],
            "slack_webhook_url": "https://hooks.slack.com/test",
            "email_recipients": [],
        }

        with pytest.raises(Exception, match="DB error"):
            _record_notification_results(payload, slack_success=True, email_success=None)

        session.rollback.assert_called_once()
        session.close.assert_called_once()

    @patch("src.database.SessionLocal")
    def test_session_always_closed(self, mock_session_local):
        session = MagicMock()
        mock_session_local.return_value = session

        payload = {
            "site_id": 1,
            "violations": [{"violation_type": "price_mismatch"}],
            "slack_webhook_url": "",
            "email_recipients": [],
        }

        _record_notification_results(payload, slack_success=None, email_success=None)

        session.close.assert_called_once()
