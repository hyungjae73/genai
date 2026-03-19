"""
Unit tests for Verification Service error handling.

Tests specific error scenarios including screenshot failures, OCR failures,
partial_failure status, and various failure conditions.

Requirements: 3.1, 3.2, 3.3, 5.5
"""

import asyncio

import pytest
from unittest.mock import MagicMock, AsyncMock
from pathlib import Path
from dataclasses import asdict

from src.analyzer import ContentAnalyzer, PaymentInfo
from src.validator import ValidationEngine, ValidationResult
from src.ocr_engine import OCRResult, OCRRegion
from src.verification_service import VerificationService, VerificationData


def _make_query_side_effect(site=None, contract=None, crawl=None):
    """Helper to build a db_session.query side_effect for run_verification."""
    def query_side_effect(model):
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_query.filter.return_value = mock_filter

        if model.__name__ == "MonitoringSite":
            mock_filter.first.return_value = site
        elif model.__name__ == "ContractCondition":
            mock_filter.first.return_value = contract
        elif model.__name__ == "CrawlResult":
            mock_order = MagicMock()
            mock_filter.order_by.return_value = mock_order
            mock_order.first.return_value = crawl
        return mock_query
    return query_side_effect


def _make_mock_site(site_id=1, url="https://example.com"):
    site = MagicMock()
    site.id = site_id
    site.url = url
    return site


def _make_mock_contract(site_id=1):
    contract = MagicMock()
    contract.site_id = site_id
    contract.is_current = True
    contract.prices = {"USD": [29.99]}
    contract.payment_methods = ["credit_card"]
    contract.fees = {"percentage": [3.0]}
    contract.subscription_terms = None
    return contract


def _make_mock_crawl(site_id=1):
    crawl = MagicMock()
    crawl.site_id = site_id
    crawl.html_content = "<html><body><p>Price: $29.99</p></body></html>"
    return crawl


def _make_service(db_session, screenshot_capture=None, ocr_engine=None,
                  content_analyzer=None, validation_engine=None):
    """Create a VerificationService with sensible mock defaults."""
    if content_analyzer is None:
        content_analyzer = MagicMock()
        content_analyzer.extract_payment_info.return_value = PaymentInfo(
            prices={"USD": [29.99]},
            payment_methods=["credit_card"],
            fees={"percentage": [3.0]},
            subscription_terms=None,
        )

    if validation_engine is None:
        validation_engine = MagicMock()
        validation_engine.validate_payment_info.return_value = ValidationResult(
            is_valid=True,
            violations=[],
            payment_info=PaymentInfo(
                prices={"USD": [29.99]},
                payment_methods=["credit_card"],
                fees={"percentage": [3.0]},
                subscription_terms=None,
            ),
            contract_conditions={"prices": {"USD": [29.99]}},
        )

    if screenshot_capture is None:
        screenshot_capture = MagicMock()
        screenshot_capture.capture_screenshot = AsyncMock(
            return_value=Path("/tmp/test_screenshot.png")
        )

    if ocr_engine is None:
        ocr_engine = MagicMock()
        ocr_engine.extract_text.return_value = OCRResult(
            full_text="Price: $29.99",
            regions=[OCRRegion(text="Price: $29.99", confidence=0.95, bbox=(0, 0, 100, 20))],
            average_confidence=0.95,
            success=True,
            error_message=None,
        )

    return VerificationService(
        content_analyzer=content_analyzer,
        validation_engine=validation_engine,
        ocr_engine=ocr_engine,
        screenshot_capture=screenshot_capture,
        db_session=db_session,
    )


class TestVerificationServiceErrorHandling:
    """Unit tests for verification service error handling paths."""

    def test_screenshot_failure_returns_partial_failure(self):
        """
        When screenshot capture raises an exception, the service should return
        status='partial_failure' with an error message containing
        'Screenshot capture failed'.

        **Validates: Requirements 3.2, 5.5**
        """
        db_session = MagicMock()
        db_session.query.side_effect = _make_query_side_effect(
            site=_make_mock_site(),
            contract=_make_mock_contract(),
            crawl=_make_mock_crawl(),
        )

        screenshot_capture = MagicMock()
        screenshot_capture.capture_screenshot = AsyncMock(
            side_effect=Exception("Browser crashed")
        )

        service = _make_service(db_session, screenshot_capture=screenshot_capture)
        result = asyncio.get_event_loop().run_until_complete(
            service.run_verification(1)
        )

        assert result.status == "partial_failure"
        assert "Screenshot capture failed" in result.error_message
        assert result.ocr_payment_info == {}
        assert result.screenshot_path == ""

    def test_ocr_failure_returns_partial_failure(self):
        """
        When OCR extraction returns success=False, the service should return
        status='partial_failure' with an error message containing
        'OCR extraction failed'.

        **Validates: Requirements 3.3, 5.5**
        """
        db_session = MagicMock()
        db_session.query.side_effect = _make_query_side_effect(
            site=_make_mock_site(),
            contract=_make_mock_contract(),
            crawl=_make_mock_crawl(),
        )

        ocr_engine = MagicMock()
        ocr_engine.extract_text.return_value = OCRResult(
            full_text="",
            regions=[],
            average_confidence=0.0,
            success=False,
            error_message="OCR error: Tesseract not found",
        )

        service = _make_service(db_session, ocr_engine=ocr_engine)
        result = asyncio.get_event_loop().run_until_complete(
            service.run_verification(1)
        )

        assert result.status == "partial_failure"
        assert "OCR extraction failed" in result.error_message
        assert result.ocr_payment_info == {}

    def test_site_not_found_returns_failure(self):
        """
        When the site is not found in the database, the service should return
        status='failure' with an error message containing 'not found'.

        **Validates: Requirements 3.1, 5.5**
        """
        db_session = MagicMock()
        db_session.query.side_effect = _make_query_side_effect(
            site=None,
            contract=None,
            crawl=None,
        )

        service = _make_service(db_session)
        result = asyncio.get_event_loop().run_until_complete(
            service.run_verification(999)
        )

        assert result.status == "failure"
        assert "not found" in result.error_message
        assert "999" in result.error_message

    def test_no_contract_returns_failure(self):
        """
        When the site exists but has no contract conditions, the service should
        return status='failure' with an error message containing
        'No contract conditions'.

        **Validates: Requirements 3.1, 5.5**
        """
        db_session = MagicMock()
        db_session.query.side_effect = _make_query_side_effect(
            site=_make_mock_site(),
            contract=None,
            crawl=None,
        )

        service = _make_service(db_session)
        result = asyncio.get_event_loop().run_until_complete(
            service.run_verification(1)
        )

        assert result.status == "failure"
        assert "No contract conditions" in result.error_message

    def test_no_crawl_results_returns_failure(self):
        """
        When the site and contract exist but there are no crawl results,
        the service should return status='failure' with an error message
        containing 'No crawl results'.

        **Validates: Requirements 3.1, 5.5**
        """
        db_session = MagicMock()
        db_session.query.side_effect = _make_query_side_effect(
            site=_make_mock_site(),
            contract=_make_mock_contract(),
            crawl=None,
        )

        service = _make_service(db_session)
        result = asyncio.get_event_loop().run_until_complete(
            service.run_verification(1)
        )

        assert result.status == "failure"
        assert "No crawl results" in result.error_message

    def test_unexpected_error_returns_failure(self):
        """
        When an unexpected exception occurs during verification (e.g., in
        content_analyzer), the service should catch it and return
        status='failure' with an error message containing 'Verification failed'.

        **Validates: Requirements 3.1, 5.5**
        """
        db_session = MagicMock()
        db_session.query.side_effect = _make_query_side_effect(
            site=_make_mock_site(),
            contract=_make_mock_contract(),
            crawl=_make_mock_crawl(),
        )

        content_analyzer = MagicMock()
        content_analyzer.extract_payment_info.side_effect = RuntimeError(
            "Unexpected internal error"
        )

        service = _make_service(db_session, content_analyzer=content_analyzer)
        result = asyncio.get_event_loop().run_until_complete(
            service.run_verification(1)
        )

        assert result.status == "failure"
        assert "Verification failed" in result.error_message
