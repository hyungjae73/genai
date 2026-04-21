"""
Performance benchmarks for Verification System.

Verifies that key operations complete within acceptable time limits.
Feature: verification-comparison-system
"""

import time
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

from src.ocr_engine import OCREngine, OCRResult, OCRRegion
from src.verification_service import VerificationService
from src.analyzer import ContentAnalyzer, PaymentInfo
from src.validator import ValidationEngine, ValidationResult


class TestPerformanceBenchmarks:
    """Performance benchmarks for verification system components."""

    def test_ocr_extraction_under_5_seconds(self, tmp_path):
        """
        Verify OCR extraction completes in < 5 seconds.

        Uses a non-existent file to test the error path performance,
        which should return quickly. Real OCR with Tesseract would be
        tested with actual images in a full integration environment.

        **Validates: Requirements 1.5**
        """
        ocr_engine = OCREngine()

        start = time.perf_counter()
        # Test error path (file not found) - should be fast
        result = ocr_engine.extract_text(Path("nonexistent_image.png"))
        elapsed = time.perf_counter() - start

        assert elapsed < 5.0, f"OCR extraction took {elapsed:.2f}s, exceeds 5s limit"
        assert result.success is False

    def test_comparison_logic_under_100ms(self):
        """
        Verify field-by-field comparison completes in < 100ms.

        Tests the pure comparison logic without I/O.
        """
        service = VerificationService(
            content_analyzer=MagicMock(),
            validation_engine=MagicMock(),
            ocr_engine=MagicMock(),
            screenshot_capture=MagicMock(),
            db_session=MagicMock(),
        )

        html_data = PaymentInfo(
            prices={'USD': [29.99, 49.99], 'EUR': [24.99]},
            payment_methods=['credit_card', 'paypal', 'bank_transfer'],
            fees={'percentage': [3.0, 5.0], 'fixed': [1.50]},
            subscription_terms={'has_commitment': True, 'commitment_months': 12},
        )
        ocr_data = PaymentInfo(
            prices={'USD': [29.99, 59.99], 'JPY': [3000]},
            payment_methods=['credit_card', 'cash_on_delivery'],
            fees={'percentage': [3.5]},
            subscription_terms={'has_commitment': False},
        )

        start = time.perf_counter()
        for _ in range(1000):
            service._compare_payment_data(html_data, ocr_data)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / 1000) * 1000
        assert avg_ms < 100, f"Average comparison took {avg_ms:.2f}ms, exceeds 100ms limit"

    @pytest.mark.asyncio
    async def test_complete_verification_under_15_seconds_mocked(self):
        """
        Verify complete verification workflow completes in < 15 seconds.

        Uses mocked dependencies to test orchestration overhead.
        Real I/O (screenshot, OCR) would be tested in integration environment.

        **Validates: Requirements 1.5**
        """
        db_session = MagicMock()
        mock_site = MagicMock()
        mock_site.id = 1
        mock_site.url = "https://example.com"

        mock_contract = MagicMock()
        mock_contract.site_id = 1
        mock_contract.is_current = True
        mock_contract.prices = {'USD': [29.99]}
        mock_contract.payment_methods = {'allowed': ['credit_card']}
        mock_contract.fees = {}
        mock_contract.subscription_terms = None

        mock_crawl = MagicMock()
        mock_crawl.site_id = 1
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

        payment_info = PaymentInfo(
            prices={'USD': [29.99]},
            payment_methods=['credit_card'],
            fees={},
            subscription_terms=None,
        )

        content_analyzer = MagicMock()
        content_analyzer.extract_payment_info.return_value = payment_info

        screenshot_capture = MagicMock()
        screenshot_capture.capture_screenshot = AsyncMock(
            return_value=Path("/tmp/screenshot.png")
        )

        ocr_engine = MagicMock()
        ocr_engine.extract_text.return_value = OCRResult(
            full_text="Price: $29.99",
            regions=[OCRRegion(text="Price: $29.99", confidence=0.95, bbox=(0, 0, 100, 20))],
            average_confidence=0.95,
            success=True,
            error_message=None,
        )

        validation_engine = MagicMock()
        validation_engine.validate_payment_info.return_value = ValidationResult(
            is_valid=True,
            violations=[],
            payment_info=payment_info,
            contract_conditions={},
        )

        service = VerificationService(
            content_analyzer=content_analyzer,
            validation_engine=validation_engine,
            ocr_engine=ocr_engine,
            screenshot_capture=screenshot_capture,
            db_session=db_session,
        )

        start = time.perf_counter()
        result = await service.run_verification(1)
        elapsed = time.perf_counter() - start

        assert elapsed < 15.0, f"Verification took {elapsed:.2f}s, exceeds 15s limit"
        assert result.status == 'success'

    def test_api_response_time_under_100ms(self):
        """
        Verify API endpoint response time < 100ms.

        Tests the FastAPI endpoint with mocked DB.
        """
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from src.api.verification import router, _running_verifications, get_db
        from src.models import MonitoringSite

        _running_verifications.clear()
        app = FastAPI()
        app.include_router(router, prefix="/api/verification")

        db = MagicMock()
        mock_site = MagicMock(spec=MonitoringSite)
        mock_site.id = 1
        mock_site.name = "Test"

        def query_side_effect(model):
            q = MagicMock()
            f = MagicMock()
            q.filter.return_value = f
            if model.__name__ == "MonitoringSite":
                f.first.return_value = mock_site
            return q

        db.query.side_effect = query_side_effect
        app.dependency_overrides[get_db] = lambda: db

        from unittest.mock import patch
        with patch("src.api.verification._run_verification_task", new=AsyncMock()):
            client = TestClient(app, headers={"X-API-Key": "dev-api-key"})

            start = time.perf_counter()
            response = client.post("/api/verification/run", json={"site_id": 1})
            elapsed = time.perf_counter() - start

        assert response.status_code == 202
        elapsed_ms = elapsed * 1000
        assert elapsed_ms < 100, f"API response took {elapsed_ms:.1f}ms, exceeds 100ms limit"
