"""
Integration tests for verification system.

Tests the complete verification workflow from OCR extraction to result storage.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from src.ocr_engine import OCREngine, OCRResult, OCRRegion
from src.verification_service import VerificationService, Discrepancy
from src.analyzer import ContentAnalyzer, PaymentInfo
from src.validator import ValidationEngine
from src.models import MonitoringSite, ContractCondition, CrawlResult, VerificationResult


@pytest.fixture
def sample_html_content():
    """Sample HTML content with payment information."""
    return """
    <html>
    <body>
        <h1>Payment Information</h1>
        <p>Price: $29.99</p>
        <p>Payment Method: Credit Card</p>
        <p>Fee: 3%</p>
    </body>
    </html>
    """


@pytest.fixture
def sample_ocr_text():
    """Sample OCR extracted text."""
    return """
    Payment Information
    Price: $29.99
    Additional Price: $39.99
    Payment Method: Credit Card
    Fee: 3%
    """


@pytest.fixture
def sample_contract_conditions():
    """Sample contract conditions."""
    return {
        'prices': {'USD': [29.99]},
        'payment_methods': {'allowed': ['credit_card'], 'required': []},
        'fees': {'percentage': [3.0]},
        'subscription_terms': None
    }


def test_ocr_engine_basic_extraction():
    """Test OCR engine can extract text from images."""
    ocr_engine = OCREngine()
    
    # Test with non-existent file (should return error)
    result = ocr_engine.extract_text(Path("nonexistent.png"))
    
    assert result.success is False
    assert result.error_message is not None
    assert "File not found" in result.error_message


def test_content_analyzer_extraction(sample_html_content):
    """Test content analyzer extracts payment info correctly."""
    analyzer = ContentAnalyzer()
    
    payment_info = analyzer.extract_payment_info(sample_html_content)
    
    assert payment_info is not None
    assert 'USD' in payment_info.prices
    assert 29.99 in payment_info.prices['USD']
    assert 'credit_card' in payment_info.payment_methods
    assert 'percentage' in payment_info.fees
    assert 3.0 in payment_info.fees['percentage']


def test_validation_engine(sample_html_content, sample_contract_conditions):
    """Test validation engine detects violations."""
    analyzer = ContentAnalyzer()
    validator = ValidationEngine()
    
    payment_info = analyzer.extract_payment_info(sample_html_content)
    validation_result = validator.validate_payment_info(
        payment_info,
        sample_contract_conditions
    )
    
    assert validation_result is not None
    assert validation_result.is_valid is True
    assert len(validation_result.violations) == 0


def test_comparison_logic():
    """Test comparison logic detects discrepancies."""
    html_data = PaymentInfo(
        prices={'USD': [29.99]},
        payment_methods=['credit_card'],
        fees={'percentage': [3.0]},
        subscription_terms=None,
        is_complete=True
    )
    
    ocr_data = PaymentInfo(
        prices={'USD': [29.99, 39.99]},  # Extra price in OCR
        payment_methods=['credit_card'],
        fees={'percentage': [3.0]},
        subscription_terms=None,
        is_complete=True
    )
    
    # Create mock verification service
    mock_analyzer = Mock()
    mock_validator = Mock()
    mock_ocr = Mock()
    mock_screenshot = Mock()
    mock_db = Mock()
    
    service = VerificationService(
        content_analyzer=mock_analyzer,
        validation_engine=mock_validator,
        ocr_engine=mock_ocr,
        screenshot_capture=mock_screenshot,
        db_session=mock_db
    )
    
    discrepancies = service._compare_payment_data(html_data, ocr_data)
    
    assert len(discrepancies) > 0
    assert any(d.field_name == 'prices.USD' for d in discrepancies)
    assert any(d.difference_type == 'mismatch' for d in discrepancies)


def test_discrepancy_severity():
    """Test discrepancy severity determination."""
    mock_analyzer = Mock()
    mock_validator = Mock()
    mock_ocr = Mock()
    mock_screenshot = Mock()
    mock_db = Mock()
    
    service = VerificationService(
        content_analyzer=mock_analyzer,
        validation_engine=mock_validator,
        ocr_engine=mock_ocr,
        screenshot_capture=mock_screenshot,
        db_session=mock_db
    )
    
    # Test severity levels
    assert service._determine_severity('prices.USD') == 'high'
    assert service._determine_severity('payment_methods') == 'high'
    assert service._determine_severity('fees.percentage') == 'medium'
    assert service._determine_severity('subscription_terms') == 'medium'
    assert service._determine_severity('other_field') == 'low'


def test_ocr_result_structure():
    """Test OCR result structure is correct."""
    result = OCRResult(
        full_text="Sample text",
        regions=[
            OCRRegion(
                text="Sample",
                confidence=0.95,
                bbox=(0, 0, 100, 20)
            )
        ],
        average_confidence=0.95,
        success=True,
        error_message=None
    )
    
    assert result.success is True
    assert result.full_text == "Sample text"
    assert len(result.regions) == 1
    assert result.regions[0].confidence == 0.95
    assert result.average_confidence == 0.95


def test_verification_data_serialization():
    """Test verification data can be serialized."""
    from src.verification_service import VerificationData
    
    data = VerificationData(
        html_payment_info={'prices': {'USD': [29.99]}},
        ocr_payment_info={'prices': {'USD': [29.99]}},
        html_validation={'is_valid': True, 'violations': []},
        ocr_validation={'is_valid': True, 'violations': []},
        discrepancies=[],
        screenshot_path='/path/to/screenshot.png',
        ocr_confidence=0.92,
        status='success',
        error_message=None
    )
    
    assert data.status == 'success'
    assert data.ocr_confidence == 0.92
    assert len(data.discrepancies) == 0


@pytest.mark.asyncio
async def test_verification_service_error_handling():
    """Test verification service handles errors gracefully."""
    mock_analyzer = Mock()
    mock_validator = Mock()
    mock_ocr = Mock()
    mock_screenshot = Mock()
    mock_db = Mock()
    
    # Mock database query to return None (site not found)
    mock_db.query.return_value.filter.return_value.first.return_value = None
    
    service = VerificationService(
        content_analyzer=mock_analyzer,
        validation_engine=mock_validator,
        ocr_engine=mock_ocr,
        screenshot_capture=mock_screenshot,
        db_session=mock_db
    )
    
    result = await service.run_verification(999)
    
    assert result.status == 'failure'
    assert result.error_message is not None
    assert 'not found' in result.error_message.lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
