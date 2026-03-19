"""
Property-based tests for Verification Result Persistence.

Tests universal properties for database storage of verification results.
Feature: verification-comparison-system
"""

import asyncio

import pytest
from unittest.mock import MagicMock, AsyncMock, call
from datetime import datetime
from pathlib import Path

from hypothesis import given, strategies as st, settings, HealthCheck
from dataclasses import asdict

from src.analyzer import ContentAnalyzer, PaymentInfo
from src.validator import ValidationResult, Violation
from src.ocr_engine import OCRResult, OCRRegion
from src.verification_service import VerificationService, VerificationData
from src.models import VerificationResult as VerificationResultModel


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

@st.composite
def payment_info_strategy(draw):
    """Generate random PaymentInfo objects."""
    prices = {}
    if draw(st.booleans()):
        currency = draw(st.sampled_from(['USD', 'JPY', 'EUR']))
        amounts = draw(st.lists(
            st.floats(min_value=0.01, max_value=99999, allow_nan=False, allow_infinity=False),
            min_size=1, max_size=3,
        ))
        prices[currency] = amounts

    methods = draw(st.lists(
        st.sampled_from(['credit_card', 'bank_transfer', 'paypal', 'cash_on_delivery']),
        unique=True, max_size=3,
    ))

    fees = {}
    if draw(st.booleans()):
        fees['percentage'] = draw(st.lists(
            st.floats(min_value=0.1, max_value=30, allow_nan=False, allow_infinity=False),
            min_size=1, max_size=2,
        ))

    sub_terms = None
    if draw(st.booleans()):
        sub_terms = {
            'has_commitment': draw(st.booleans()),
            'has_cancellation_policy': draw(st.booleans()),
        }

    return PaymentInfo(
        prices=prices,
        payment_methods=methods,
        fees=fees,
        subscription_terms=sub_terms,
    )


def _build_mocked_service(site_id, site_url, html_payment_info, ocr_payment_info,
                          contract_conditions, ocr_confidence=0.95, violations=None):
    """Build a VerificationService with fully mocked dependencies for persistence tests."""
    db_session = MagicMock()

    mock_site = MagicMock()
    mock_site.id = site_id
    mock_site.url = site_url

    mock_contract = MagicMock()
    mock_contract.site_id = site_id
    mock_contract.is_current = True
    mock_contract.prices = contract_conditions.get('prices', {})
    mock_contract.payment_methods = contract_conditions.get('payment_methods', {})
    mock_contract.fees = contract_conditions.get('fees', {})
    mock_contract.subscription_terms = contract_conditions.get('subscription_terms')

    mock_crawl = MagicMock()
    mock_crawl.site_id = site_id
    mock_crawl.html_content = "<html><body>Price: $29.99</body></html>"

    def query_side_effect(model):
        q = MagicMock()
        f = MagicMock()
        q.filter.return_value = f
        if model.__name__ == 'MonitoringSite':
            f.first.return_value = mock_site
        elif model.__name__ == 'ContractCondition':
            f.first.return_value = mock_contract
        elif model.__name__ == 'CrawlResult':
            order = MagicMock()
            f.order_by.return_value = order
            order.first.return_value = mock_crawl
        return q

    db_session.query.side_effect = query_side_effect

    content_analyzer = MagicMock()
    content_analyzer.extract_payment_info.side_effect = [html_payment_info, ocr_payment_info]

    screenshot_capture = MagicMock()
    screenshot_capture.capture_screenshot = AsyncMock(
        return_value=Path("/tmp/test_screenshot.png")
    )

    ocr_engine = MagicMock()
    ocr_engine.extract_text.return_value = OCRResult(
        full_text="Price: $29.99",
        regions=[OCRRegion(text="Price: $29.99", confidence=ocr_confidence, bbox=(0, 0, 100, 20))],
        average_confidence=ocr_confidence,
        success=True,
        error_message=None,
    )

    validation_engine = MagicMock()
    if violations:
        validation_engine.validate_payment_info.return_value = ValidationResult(
            is_valid=False,
            violations=violations,
            payment_info=html_payment_info,
            contract_conditions=contract_conditions,
        )
    else:
        validation_engine.validate_payment_info.return_value = ValidationResult(
            is_valid=True,
            violations=[],
            payment_info=html_payment_info,
            contract_conditions=contract_conditions,
        )

    service = VerificationService(
        content_analyzer=content_analyzer,
        validation_engine=validation_engine,
        ocr_engine=ocr_engine,
        screenshot_capture=screenshot_capture,
        db_session=db_session,
    )

    return service, db_session


# ===========================================================================
# Property 14: Verification Result Persistence  (Task 11.2)
# ===========================================================================

class TestVerificationResultPersistence:
    """Property 14: Verification Result Persistence."""

    # Feature: verification-comparison-system, Property 14: Verification Result Persistence
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    @given(
        site_id=st.integers(min_value=1, max_value=10000),
        data=st.data(),
    )
    def test_property_verification_result_persistence(self, site_id, data):
        """
        Property 14: Verification Result Persistence

        For any completed verification, a database record should be created
        via db_session.add() and db_session.commit().

        **Validates: Requirements 5.1**
        """
        html_info = data.draw(payment_info_strategy(), label="html_info")
        ocr_info = data.draw(payment_info_strategy(), label="ocr_info")
        site_url = data.draw(
            st.from_regex(r'https://[a-z]{3,10}\.(com|org|net)', fullmatch=True),
            label="site_url",
        )

        contract_conditions = {
            'prices': {'USD': [29.99]},
            'payment_methods': {'allowed': ['credit_card']},
            'fees': {'percentage': [3.0]},
            'subscription_terms': None,
        }

        service, db_session = _build_mocked_service(
            site_id, site_url, html_info, ocr_info, contract_conditions
        )

        result = asyncio.get_event_loop().run_until_complete(
            service.run_verification(site_id)
        )

        # Verify db_session.add was called (record created)
        assert db_session.add.called, (
            "db_session.add() must be called to persist the verification result"
        )

        # Verify db_session.commit was called (record saved)
        assert db_session.commit.called, (
            "db_session.commit() must be called to save the verification result"
        )

        # Verify the added object is a VerificationResult
        added_obj = db_session.add.call_args[0][0]
        assert hasattr(added_obj, 'site_id'), "Persisted object must have site_id"
        assert added_obj.site_id == site_id, (
            f"Persisted site_id={added_obj.site_id} != expected {site_id}"
        )
        assert added_obj.status == 'success', (
            f"Expected status='success', got '{added_obj.status}'"
        )


# ===========================================================================
# Property 15: Complete Result Storage  (Task 11.3)
# ===========================================================================

class TestCompleteResultStorage:
    """Property 15: Complete Result Storage."""

    # Feature: verification-comparison-system, Property 15: Complete Result Storage
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    @given(
        site_id=st.integers(min_value=1, max_value=10000),
        ocr_confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        data=st.data(),
    )
    def test_property_complete_result_storage(self, site_id, ocr_confidence, data):
        """
        Property 15: Complete Result Storage

        For any completed verification, the stored result should include all
        required fields: html_data, ocr_data, discrepancies, html_violations,
        ocr_violations, screenshot_path, ocr_confidence, status.

        **Validates: Requirements 5.2, 5.3, 5.4**
        """
        html_info = data.draw(payment_info_strategy(), label="html_info")
        ocr_info = data.draw(payment_info_strategy(), label="ocr_info")
        site_url = data.draw(
            st.from_regex(r'https://[a-z]{3,10}\.(com|org|net)', fullmatch=True),
            label="site_url",
        )

        contract_conditions = {
            'prices': {'USD': [29.99]},
            'payment_methods': {'allowed': ['credit_card']},
            'fees': {},
            'subscription_terms': None,
        }

        service, db_session = _build_mocked_service(
            site_id, site_url, html_info, ocr_info, contract_conditions,
            ocr_confidence=ocr_confidence,
        )

        result = asyncio.get_event_loop().run_until_complete(
            service.run_verification(site_id)
        )

        assert db_session.add.called, "db_session.add() must be called"
        stored = db_session.add.call_args[0][0]

        # All required fields must be present
        required_attrs = [
            'site_id', 'html_data', 'ocr_data', 'discrepancies',
            'html_violations', 'ocr_violations', 'screenshot_path',
            'ocr_confidence', 'status', 'created_at',
        ]
        for attr in required_attrs:
            assert hasattr(stored, attr), f"Stored result missing required field: {attr}"

        # html_data and ocr_data should be dicts
        assert isinstance(stored.html_data, dict), f"html_data must be dict, got {type(stored.html_data)}"
        assert isinstance(stored.ocr_data, dict), f"ocr_data must be dict, got {type(stored.ocr_data)}"

        # discrepancies should be a dict with 'items' key
        assert isinstance(stored.discrepancies, dict), f"discrepancies must be dict"
        assert 'items' in stored.discrepancies, "discrepancies must have 'items' key"

        # violations should be dicts with 'items' key
        assert isinstance(stored.html_violations, dict), "html_violations must be dict"
        assert 'items' in stored.html_violations, "html_violations must have 'items' key"
        assert isinstance(stored.ocr_violations, dict), "ocr_violations must be dict"
        assert 'items' in stored.ocr_violations, "ocr_violations must have 'items' key"

        # screenshot_path should be a non-empty string
        assert isinstance(stored.screenshot_path, str) and len(stored.screenshot_path) > 0, (
            f"screenshot_path must be non-empty string, got {stored.screenshot_path!r}"
        )

        # ocr_confidence should match
        assert stored.ocr_confidence == ocr_confidence, (
            f"Expected ocr_confidence={ocr_confidence}, got {stored.ocr_confidence}"
        )


# ===========================================================================
# Property 16: Error Message Storage  (Task 11.4)
# ===========================================================================

class TestErrorMessageStorage:
    """Property 16: Error Message Storage."""

    # Feature: verification-comparison-system, Property 16: Error Message Storage
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    @given(site_id=st.integers(min_value=1, max_value=10000))
    def test_property_error_message_storage_screenshot_failure(self, site_id):
        """
        Property 16: Error Message Storage (screenshot failure)

        For any verification that fails during screenshot capture,
        the result should include an error_message describing the failure.

        **Validates: Requirements 5.5**
        """
        db_session = MagicMock()
        mock_site = MagicMock()
        mock_site.id = site_id
        mock_site.url = f"https://example-{site_id}.com"

        mock_contract = MagicMock()
        mock_contract.site_id = site_id
        mock_contract.is_current = True
        mock_contract.prices = {}
        mock_contract.payment_methods = {}
        mock_contract.fees = {}
        mock_contract.subscription_terms = None

        mock_crawl = MagicMock()
        mock_crawl.site_id = site_id
        mock_crawl.html_content = "<html><body>test</body></html>"

        def query_side_effect(model):
            q = MagicMock()
            f = MagicMock()
            q.filter.return_value = f
            if model.__name__ == 'MonitoringSite':
                f.first.return_value = mock_site
            elif model.__name__ == 'ContractCondition':
                f.first.return_value = mock_contract
            elif model.__name__ == 'CrawlResult':
                order = MagicMock()
                f.order_by.return_value = order
                order.first.return_value = mock_crawl
            return q

        db_session.query.side_effect = query_side_effect

        content_analyzer = MagicMock()
        content_analyzer.extract_payment_info.return_value = PaymentInfo(
            prices={}, payment_methods=[], fees={}, subscription_terms=None,
        )

        screenshot_capture = MagicMock()
        screenshot_capture.capture_screenshot = AsyncMock(
            side_effect=Exception("Screenshot capture timeout")
        )

        service = VerificationService(
            content_analyzer=content_analyzer,
            validation_engine=MagicMock(),
            ocr_engine=MagicMock(),
            screenshot_capture=screenshot_capture,
            db_session=db_session,
        )

        result = asyncio.get_event_loop().run_until_complete(
            service.run_verification(site_id)
        )

        # Result should indicate failure
        assert result.status in ('partial_failure', 'failure'), (
            f"Expected partial_failure or failure status, got '{result.status}'"
        )

        # Error message must be present and non-empty
        assert result.error_message is not None, "error_message must not be None for failed verifications"
        assert len(result.error_message) > 0, "error_message must not be empty"
        assert "screenshot" in result.error_message.lower() or "Screenshot" in result.error_message, (
            f"error_message should mention screenshot failure: {result.error_message}"
        )

    # Feature: verification-comparison-system, Property 16: Error Message Storage
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    @given(site_id=st.integers(min_value=1, max_value=10000))
    def test_property_error_message_storage_site_not_found(self, site_id):
        """
        Property 16: Error Message Storage (site not found)

        For any verification where the site does not exist,
        the result should include an error_message.

        **Validates: Requirements 5.5**
        """
        db_session = MagicMock()

        def query_side_effect(model):
            q = MagicMock()
            f = MagicMock()
            q.filter.return_value = f
            f.first.return_value = None
            return q

        db_session.query.side_effect = query_side_effect

        service = VerificationService(
            content_analyzer=MagicMock(),
            validation_engine=MagicMock(),
            ocr_engine=MagicMock(),
            screenshot_capture=MagicMock(),
            db_session=db_session,
        )

        result = asyncio.get_event_loop().run_until_complete(
            service.run_verification(site_id)
        )

        assert result.status == 'failure', f"Expected failure, got '{result.status}'"
        assert result.error_message is not None, "error_message must not be None"
        assert len(result.error_message) > 0, "error_message must not be empty"
