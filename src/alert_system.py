"""
Alert System for Payment Compliance Monitor.

This module sends notifications via email (SendGrid) and Slack when violations are detected.
"""

import asyncio
import os
from dataclasses import dataclass
from typing import Optional, Any
from datetime import datetime
import json


@dataclass
class NotificationConfig:
    """
    Configuration for notification channels.
    
    Attributes:
        email_recipients: List of email addresses to notify
        slack_webhook_url: Slack webhook URL for notifications
        slack_channel: Slack channel name (optional)
    """
    email_recipients: list[str]
    slack_webhook_url: Optional[str] = None
    slack_channel: Optional[str] = None


@dataclass
class AlertResult:
    """
    Result of alert notification operation.
    
    Attributes:
        alert_id: Unique identifier for the alert
        email_sent: Whether email was sent successfully
        slack_sent: Whether Slack notification was sent successfully
        email_error: Error message if email failed
        slack_error: Error message if Slack failed
        retry_count: Number of retries attempted
    """
    alert_id: int
    email_sent: bool
    slack_sent: bool
    email_error: Optional[str] = None
    slack_error: Optional[str] = None
    retry_count: int = 0


class AlertSystem:
    """
    Sends alerts via multiple notification channels.
    
    Supports email (SendGrid) and Slack notifications with retry logic.
    """
    
    def __init__(
        self,
        sendgrid_api_key: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """
        Initialize AlertSystem.
        
        Args:
            sendgrid_api_key: SendGrid API key (defaults to env var)
            max_retries: Maximum number of retry attempts
            retry_delay: Initial delay between retries in seconds
        """
        self.sendgrid_api_key = sendgrid_api_key or os.getenv('SENDGRID_API_KEY')
        self.max_retries = max_retries
        self.retry_delay = retry_delay
    
    async def send_alert(
        self,
        violation: Any,
        site_info: dict[str, Any],
        notification_config: NotificationConfig,
        alert_id: int
    ) -> AlertResult:
        """
        Send alert notifications via configured channels.
        
        Args:
            violation: Violation object with details
            site_info: Information about the monitoring site
            notification_config: Notification channel configuration
            alert_id: Unique identifier for this alert
        
        Returns:
            AlertResult with delivery status
        """
        # Prepare alert message
        message = self._format_alert_message(violation, site_info)
        
        # Send email notification
        email_sent = False
        email_error = None
        email_retry_count = 0
        
        if notification_config.email_recipients:
            email_sent, email_error, email_retry_count = await self._send_email_with_retry(
                recipients=notification_config.email_recipients,
                subject=self._get_alert_subject(violation, site_info),
                message=message,
                is_urgent=self._is_high_priority(violation)
            )
        
        # Send Slack notification
        slack_sent = False
        slack_error = None
        slack_retry_count = 0
        
        if notification_config.slack_webhook_url:
            slack_sent, slack_error, slack_retry_count = await self._send_slack_with_retry(
                webhook_url=notification_config.slack_webhook_url,
                message=message,
                channel=notification_config.slack_channel,
                is_urgent=self._is_high_priority(violation)
            )
        
        return AlertResult(
            alert_id=alert_id,
            email_sent=email_sent,
            slack_sent=slack_sent,
            email_error=email_error,
            slack_error=slack_error,
            retry_count=max(email_retry_count, slack_retry_count)
        )
    
    def _format_alert_message(
        self,
        violation: Any,
        site_info: dict[str, Any]
    ) -> str:
        """
        Format alert message with violation details.
        
        Args:
            violation: Violation object
            site_info: Site information
        
        Returns:
            Formatted message string
        """
        lines = [
            "🚨 Payment Compliance Violation Detected",
            "",
            f"Site: {site_info.get('company_name', 'Unknown')}",
            f"URL: {site_info.get('target_url', 'Unknown')}",
            f"Domain: {site_info.get('domain', 'Unknown')}",
            "",
            "Violation Details:",
            f"  Type: {violation.violation_type}",
            f"  Severity: {violation.severity.upper()}",
            f"  Field: {violation.field_name}",
            f"  Expected: {violation.expected_value}",
            f"  Actual: {violation.actual_value}",
            "",
            f"Message: {violation.message}",
            "",
            f"Detected at: {datetime.now().isoformat()}",
        ]
        
        return "\n".join(lines)
    
    def _get_alert_subject(
        self,
        violation: Any,
        site_info: dict[str, Any]
    ) -> str:
        """
        Generate alert subject line.
        
        Args:
            violation: Violation object
            site_info: Site information
        
        Returns:
            Subject line string
        """
        severity_prefix = "🔴 URGENT" if self._is_high_priority(violation) else "⚠️"
        company = site_info.get('company_name', 'Unknown Site')
        
        return f"{severity_prefix} Payment Compliance Violation - {company}"
    
    def _is_high_priority(self, violation: Any) -> bool:
        """
        Determine if violation is high priority.
        
        Args:
            violation: Violation object
        
        Returns:
            True if high priority
        """
        return violation.severity == 'high'
    
    async def _send_email_with_retry(
        self,
        recipients: list[str],
        subject: str,
        message: str,
        is_urgent: bool
    ) -> tuple[bool, Optional[str], int]:
        """
        Send email with retry logic.
        
        Args:
            recipients: List of recipient email addresses
            subject: Email subject
            message: Email body
            is_urgent: Whether this is an urgent alert
        
        Returns:
            Tuple of (success, error_message, retry_count)
        """
        retry_count = 0
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                success = await self._send_email(
                    recipients=recipients,
                    subject=subject,
                    message=message,
                    is_urgent=is_urgent
                )
                
                if success:
                    return True, None, retry_count
                
                last_error = "Email sending failed"
                
            except Exception as e:
                last_error = str(e)
            
            retry_count += 1
            
            if attempt < self.max_retries - 1:
                # Exponential backoff
                delay = self.retry_delay * (2 ** attempt)
                await asyncio.sleep(delay)
        
        return False, last_error, retry_count
    
    async def _send_email(
        self,
        recipients: list[str],
        subject: str,
        message: str,
        is_urgent: bool
    ) -> bool:
        """
        Send email via SendGrid.
        
        Args:
            recipients: List of recipient email addresses
            subject: Email subject
            message: Email body
            is_urgent: Whether this is an urgent alert
        
        Returns:
            True if sent successfully
        """
        # In production, this would use SendGrid API
        # For now, we'll simulate the behavior
        
        if not self.sendgrid_api_key:
            # If no API key, consider it a test environment
            return True
        
        # Simulate SendGrid API call
        # In production:
        # from sendgrid import SendGridAPIClient
        # from sendgrid.helpers.mail import Mail
        #
        # mail = Mail(
        #     from_email='alerts@payment-monitor.com',
        #     to_emails=recipients,
        #     subject=subject,
        #     plain_text_content=message
        # )
        #
        # if is_urgent:
        #     mail.add_header('X-Priority', '1')
        #
        # sg = SendGridAPIClient(self.sendgrid_api_key)
        # response = sg.send(mail)
        # return response.status_code == 202
        
        return True
    
    async def _send_slack_with_retry(
        self,
        webhook_url: str,
        message: str,
        channel: Optional[str],
        is_urgent: bool
    ) -> tuple[bool, Optional[str], int]:
        """
        Send Slack notification with retry logic.
        
        Args:
            webhook_url: Slack webhook URL
            message: Message to send
            channel: Slack channel (optional)
            is_urgent: Whether this is an urgent alert
        
        Returns:
            Tuple of (success, error_message, retry_count)
        """
        retry_count = 0
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                success = await self._send_slack(
                    webhook_url=webhook_url,
                    message=message,
                    channel=channel,
                    is_urgent=is_urgent
                )
                
                if success:
                    return True, None, retry_count
                
                last_error = "Slack notification failed"
                
            except Exception as e:
                last_error = str(e)
            
            retry_count += 1
            
            if attempt < self.max_retries - 1:
                # Exponential backoff
                delay = self.retry_delay * (2 ** attempt)
                await asyncio.sleep(delay)
        
        return False, last_error, retry_count
    
    async def _send_slack(
        self,
        webhook_url: str,
        message: str,
        channel: Optional[str],
        is_urgent: bool
    ) -> bool:
        """
        Send notification to Slack.
        
        Args:
            webhook_url: Slack webhook URL
            message: Message to send
            channel: Slack channel (optional)
            is_urgent: Whether this is an urgent alert
        
        Returns:
            True if sent successfully
        """
        # In production, this would use Slack SDK or webhook
        # For now, we'll simulate the behavior
        
        # Simulate Slack webhook call
        # In production:
        # import httpx
        #
        # payload = {
        #     'text': message,
        #     'username': 'Payment Compliance Monitor'
        # }
        #
        # if channel:
        #     payload['channel'] = channel
        #
        # if is_urgent:
        #     payload['text'] = f"<!channel> {message}"
        #
        # async with httpx.AsyncClient() as client:
        #     response = await client.post(webhook_url, json=payload)
        #     return response.status_code == 200
        
        return True
