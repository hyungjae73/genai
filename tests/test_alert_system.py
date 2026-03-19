"""
Unit tests for AlertSystem.

Tests the alert notification system with mocked external services.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.alert_system import AlertSystem, NotificationConfig, AlertResult
from src.validator import Violation


@pytest.fixture
def sample_violation():
    """Create a sample violation for testing."""
    return Violation(
        violation_type='price',
        severity='high',
        field_name='prices.JPY',
        expected_value=1000.0,
        actual_value=2000.0,
        message='Price mismatch: expected 1000.0, found 2000.0'
    )


@pytest.fixture
def sample_site_info():
    """Create sample site information for testing."""
    return {
        'company_name': 'Test Company',
        'domain': 'test.com',
        'target_url': 'https://test.com/payment'
    }


@pytest.fixture
def notification_config():
    """Create notification configuration for testing."""
    return NotificationConfig(
        email_recipients=['admin@example.com', 'compliance@example.com'],
        slack_webhook_url='https://hooks.slack.com/services/TEST/WEBHOOK',
        slack_channel='#alerts'
    )


class TestAlertSystem:
    """Test suite for AlertSystem."""
    
    @pytest.mark.asyncio
    async def test_send_alert_success(
        self,
        sample_violation,
        sample_site_info,
        notification_config
    ):
        """Test successful alert sending."""
        alert_system = AlertSystem()
        
        result = await alert_system.send_alert(
            violation=sample_violation,
            site_info=sample_site_info,
            notification_config=notification_config,
            alert_id=1
        )
        
        assert isinstance(result, AlertResult)
        assert result.alert_id == 1
        assert result.email_sent is True
        assert result.slack_sent is True
        assert result.email_error is None
        assert result.slack_error is None
    
    @pytest.mark.asyncio
    async def test_send_alert_email_only(
        self,
        sample_violation,
        sample_site_info
    ):
        """Test alert sending with email only."""
        config = NotificationConfig(
            email_recipients=['admin@example.com']
        )
        
        alert_system = AlertSystem()
        
        result = await alert_system.send_alert(
            violation=sample_violation,
            site_info=sample_site_info,
            notification_config=config,
            alert_id=2
        )
        
        assert result.email_sent is True
        assert result.slack_sent is False
    
    @pytest.mark.asyncio
    async def test_send_alert_slack_only(
        self,
        sample_violation,
        sample_site_info
    ):
        """Test alert sending with Slack only."""
        config = NotificationConfig(
            email_recipients=[],
            slack_webhook_url='https://hooks.slack.com/services/TEST'
        )
        
        alert_system = AlertSystem()
        
        result = await alert_system.send_alert(
            violation=sample_violation,
            site_info=sample_site_info,
            notification_config=config,
            alert_id=3
        )
        
        assert result.email_sent is False
        assert result.slack_sent is True
    
    def test_format_alert_message(
        self,
        sample_violation,
        sample_site_info
    ):
        """Test alert message formatting."""
        alert_system = AlertSystem()
        
        message = alert_system._format_alert_message(
            violation=sample_violation,
            site_info=sample_site_info
        )
        
        assert 'Payment Compliance Violation Detected' in message
        assert 'Test Company' in message
        assert 'test.com' in message
        assert 'price' in message
        assert 'HIGH' in message  # Severity is uppercase in the message
        assert '1000.0' in message
        assert '2000.0' in message
    
    def test_get_alert_subject_high_priority(
        self,
        sample_violation,
        sample_site_info
    ):
        """Test alert subject for high priority violation."""
        alert_system = AlertSystem()
        
        subject = alert_system._get_alert_subject(
            violation=sample_violation,
            site_info=sample_site_info
        )
        
        assert 'URGENT' in subject
        assert 'Test Company' in subject
    
    def test_get_alert_subject_normal_priority(
        self,
        sample_site_info
    ):
        """Test alert subject for normal priority violation."""
        violation = Violation(
            violation_type='payment_method',
            severity='medium',
            field_name='payment_methods',
            expected_value='credit_card',
            actual_value='paypal',
            message='Unauthorized payment method'
        )
        
        alert_system = AlertSystem()
        
        subject = alert_system._get_alert_subject(
            violation=violation,
            site_info=sample_site_info
        )
        
        assert 'URGENT' not in subject
        assert 'Test Company' in subject
    
    def test_is_high_priority(self):
        """Test high priority detection."""
        alert_system = AlertSystem()
        
        high_violation = Violation(
            violation_type='price',
            severity='high',
            field_name='prices.JPY',
            expected_value=1000.0,
            actual_value=2000.0,
            message='Price mismatch'
        )
        
        medium_violation = Violation(
            violation_type='fee',
            severity='medium',
            field_name='fees',
            expected_value=3.0,
            actual_value=5.0,
            message='Fee mismatch'
        )
        
        assert alert_system._is_high_priority(high_violation) is True
        assert alert_system._is_high_priority(medium_violation) is False
    
    @pytest.mark.asyncio
    async def test_send_email_with_retry_success(self):
        """Test email sending with successful first attempt."""
        alert_system = AlertSystem()
        
        success, error, retry_count = await alert_system._send_email_with_retry(
            recipients=['test@example.com'],
            subject='Test Alert',
            message='Test message',
            is_urgent=False
        )
        
        assert success is True
        assert error is None
        assert retry_count == 0
    
    @pytest.mark.asyncio
    async def test_send_email_with_retry_failure(self):
        """Test email sending with retry on failure."""
        alert_system = AlertSystem(max_retries=2, retry_delay=0.01)
        
        # Mock _send_email to always fail
        with patch.object(alert_system, '_send_email', side_effect=Exception('Send failed')):
            success, error, retry_count = await alert_system._send_email_with_retry(
                recipients=['test@example.com'],
                subject='Test Alert',
                message='Test message',
                is_urgent=False
            )
            
            assert success is False
            assert error is not None
            assert retry_count == 2
    
    @pytest.mark.asyncio
    async def test_send_slack_with_retry_success(self):
        """Test Slack sending with successful first attempt."""
        alert_system = AlertSystem()
        
        success, error, retry_count = await alert_system._send_slack_with_retry(
            webhook_url='https://hooks.slack.com/test',
            message='Test message',
            channel='#test',
            is_urgent=False
        )
        
        assert success is True
        assert error is None
        assert retry_count == 0
    
    @pytest.mark.asyncio
    async def test_send_slack_with_retry_failure(self):
        """Test Slack sending with retry on failure."""
        alert_system = AlertSystem(max_retries=2, retry_delay=0.01)
        
        # Mock _send_slack to always fail
        with patch.object(alert_system, '_send_slack', side_effect=Exception('Send failed')):
            success, error, retry_count = await alert_system._send_slack_with_retry(
                webhook_url='https://hooks.slack.com/test',
                message='Test message',
                channel='#test',
                is_urgent=False
            )
            
            assert success is False
            assert error is not None
            assert retry_count == 2
    
    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        """Test exponential backoff in retry logic."""
        alert_system = AlertSystem(max_retries=3, retry_delay=0.1)
        
        # Mock _send_email to fail twice then succeed
        call_count = 0
        
        async def mock_send_email(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception('Temporary failure')
            return True
        
        with patch.object(alert_system, '_send_email', side_effect=mock_send_email):
            success, error, retry_count = await alert_system._send_email_with_retry(
                recipients=['test@example.com'],
                subject='Test',
                message='Test',
                is_urgent=False
            )
            
            assert success is True
            assert retry_count == 2  # Failed twice before succeeding
            assert call_count == 3
