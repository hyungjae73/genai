"""
Celery notification tasks for sending Slack and email notifications.

Implements a 2-layer retry strategy:
- HTTP-level: _send_slack() / _send_email() retry up to 3 times with exponential backoff (1s, 2s, 4s)
- Celery task-level: send_notification retries up to 3 times with 60s delay

After successful send: creates NotificationRecord with status='sent', updates Alert flags.
On failure after all retries: creates NotificationRecord with status='failed'.

Requirements: 2.4, 2.5, 3.5, 3.6, 6.3, 8.1, 8.2, 8.3, 8.4
"""

from __future__ import annotations

import logging
import os
import smtplib
import time
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import httpx

from src.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="src.notification_tasks.send_notification",
    queue="notification",
    max_retries=3,
    default_retry_delay=60,
)
def send_notification(self, payload: dict[str, Any]) -> dict[str, Any]:
    """Send Slack/email notifications and record results.

    Args:
        payload: Notification payload containing:
            - site_id: int
            - violations: list[dict]
            - slack_enabled: bool
            - slack_payload: dict | None
            - slack_webhook_url: str | None
            - email_enabled: bool
            - email_subject: str | None
            - email_body: str | None
            - email_recipients: list[str]

    Returns:
        dict with send results for each channel
    """
    site_id = payload.get("site_id")
    results: dict[str, Any] = {"site_id": site_id}

    slack_success = None
    email_success = None

    # Send Slack notification
    if payload.get("slack_enabled") and payload.get("slack_webhook_url"):
        slack_success = _send_slack(
            payload["slack_webhook_url"],
            payload["slack_payload"],
        )
        results["slack"] = "sent" if slack_success else "failed"

    # Send email notification
    if payload.get("email_enabled") and payload.get("email_recipients"):
        email_success = _send_email(
            payload["email_recipients"],
            payload.get("email_subject", ""),
            payload.get("email_body", ""),
        )
        results["email"] = "sent" if email_success else "failed"

    # If any channel failed, retry via Celery
    any_failed = (slack_success is False) or (email_success is False)
    if any_failed:
        try:
            self.retry()
        except self.MaxRetriesExceededError:
            logger.error(
                "send_notification max retries exceeded for site_id=%s", site_id
            )

    # Record results in DB
    try:
        _record_notification_results(payload, slack_success, email_success)
    except Exception as e:
        logger.error("Failed to record notification results: %s", e)

    return results


def _send_slack(webhook_url: str, payload: dict) -> bool:
    """Send Slack webhook POST with up to 3 retries (1s, 2s, 4s exponential backoff).

    Args:
        webhook_url: Slack Incoming Webhook URL
        payload: Slack Block Kit payload

    Returns:
        True if send succeeded, False otherwise
    """
    for attempt in range(3):
        try:
            resp = httpx.post(webhook_url, json=payload, timeout=10)
            if resp.status_code == 200:
                return True
            logger.warning(
                "Slack webhook returned %d on attempt %d",
                resp.status_code,
                attempt + 1,
            )
        except httpx.HTTPError as e:
            logger.warning("Slack webhook error on attempt %d: %s", attempt + 1, e)
        if attempt < 2:
            time.sleep(2**attempt)  # 1s, 2s, 4s
    return False


def _send_email(recipients: list[str], subject: str, body: str) -> bool:
    """Send email via SMTP with up to 3 retries (1s, 2s, 4s exponential backoff).

    Args:
        recipients: List of email addresses
        subject: Email subject
        body: Email body (plain text)

    Returns:
        True if send succeeded, False otherwise
    """
    smtp_host = os.environ.get("SMTP_HOST", "localhost")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_password = os.environ.get("SMTP_PASSWORD", "")
    from_addr = os.environ.get("SMTP_FROM", "noreply@payment-monitor.local")

    for attempt in range(3):
        try:
            msg = MIMEMultipart()
            msg["From"] = from_addr
            msg["To"] = ", ".join(recipients)
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain", "utf-8"))

            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                if smtp_user and smtp_password:
                    server.starttls()
                    server.login(smtp_user, smtp_password)
                server.sendmail(from_addr, recipients, msg.as_string())
            return True
        except Exception as e:
            logger.warning("Email send error on attempt %d: %s", attempt + 1, e)
        if attempt < 2:
            time.sleep(2**attempt)  # 1s, 2s, 4s
    return False


def _record_notification_results(
    payload: dict[str, Any],
    slack_success: bool | None,
    email_success: bool | None,
) -> None:
    """Create NotificationRecord entries and update Alert flags.

    Args:
        payload: Original notification payload
        slack_success: True/False/None for Slack channel
        email_success: True/False/None for email channel
    """
    from src.database import SessionLocal
    from src.models import Alert, NotificationRecord

    session = SessionLocal()
    try:
        site_id = payload.get("site_id")
        violations = payload.get("violations", [])
        now = datetime.now(timezone.utc)

        # Collect alert_ids from violations for flag updates
        alert_ids: list[int] = []
        for v in violations:
            aid = v.get("alert_id")
            if aid is not None:
                alert_ids.append(aid)

        # Create NotificationRecord for Slack
        if slack_success is not None:
            status = "sent" if slack_success else "failed"
            webhook_url = payload.get("slack_webhook_url", "")
            for v in violations:
                record = NotificationRecord(
                    site_id=site_id,
                    alert_id=v.get("alert_id"),
                    violation_type=v.get("violation_type", "unknown"),
                    channel="slack",
                    recipient=webhook_url,
                    status=status,
                    sent_at=now,
                )
                session.add(record)

            # Update Alert.slack_sent flags
            if slack_success and alert_ids:
                session.query(Alert).filter(
                    Alert.id.in_(alert_ids)
                ).update({"slack_sent": True}, synchronize_session=False)

        # Create NotificationRecord for email
        if email_success is not None:
            status = "sent" if email_success else "failed"
            recipients = payload.get("email_recipients", [])
            recipient_str = ", ".join(recipients)
            for v in violations:
                record = NotificationRecord(
                    site_id=site_id,
                    alert_id=v.get("alert_id"),
                    violation_type=v.get("violation_type", "unknown"),
                    channel="email",
                    recipient=recipient_str,
                    status=status,
                    sent_at=now,
                )
                session.add(record)

            # Update Alert.email_sent flags
            if email_success and alert_ids:
                session.query(Alert).filter(
                    Alert.id.in_(alert_ids)
                ).update({"email_sent": True}, synchronize_session=False)

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
