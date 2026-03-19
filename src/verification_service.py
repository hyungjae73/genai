"""
Verification Service for Payment Compliance Monitor.

This module orchestrates multi-source verification workflow including
HTML extraction, OCR extraction, comparison, and validation.
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from src.analyzer import ContentAnalyzer, PaymentInfo
from src.validator import ValidationEngine, ValidationResult
from src.ocr_engine import OCREngine
from src.screenshot_capture import ScreenshotCapture
from src.models import MonitoringSite, ContractCondition, VerificationResult


@dataclass
class Discrepancy:
    """Represents a difference between HTML and OCR data."""
    field_name: str
    html_value: Any
    ocr_value: Any
    difference_type: str  # 'missing', 'mismatch', 'extra'
    severity: str  # 'low', 'medium', 'high'


@dataclass
class VerificationData:
    """Complete verification data from all sources."""
    html_payment_info: dict
    ocr_payment_info: dict
    html_validation: dict
    ocr_validation: dict
    discrepancies: list[dict]
    screenshot_path: str
    ocr_confidence: float
    status: str  # 'success', 'partial_failure', 'failure'
    error_message: Optional[str] = None


class VerificationService:
    """Orchestrates verification workflow."""
    
    def __init__(
        self,
        content_analyzer: ContentAnalyzer,
        validation_engine: ValidationEngine,
        ocr_engine: OCREngine,
        screenshot_capture: ScreenshotCapture,
        db_session: Session
    ):
        """Initialize with required dependencies."""
        self.content_analyzer = content_analyzer
        self.validation_engine = validation_engine
        self.ocr_engine = ocr_engine
        self.screenshot_capture = screenshot_capture
        self.db_session = db_session
    
    async def run_verification(self, site_id: int) -> VerificationData:
        """
        Run complete verification for a site.
        
        Steps:
        1. Fetch site and contract from database
        2. Extract HTML data using ContentAnalyzer
        3. Capture screenshot using ScreenshotCapture
        4. Extract OCR data from screenshot
        5. Compare HTML and OCR data
        6. Validate both against contract
        7. Store results in database
        
        Args:
            site_id: Site to verify
            
        Returns:
            VerificationData with all results
        """
        try:
            # Step 1: Fetch site and contract
            site = self.db_session.query(MonitoringSite).filter(
                MonitoringSite.id == site_id
            ).first()
            
            if not site:
                return VerificationData(
                    html_payment_info={},
                    ocr_payment_info={},
                    html_validation={},
                    ocr_validation={},
                    discrepancies=[],
                    screenshot_path="",
                    ocr_confidence=0.0,
                    status="failure",
                    error_message=f"Site with id {site_id} not found"
                )
            
            # Get current contract conditions
            contract = self.db_session.query(ContractCondition).filter(
                ContractCondition.site_id == site_id,
                ContractCondition.is_current == True
            ).first()
            
            if not contract:
                return VerificationData(
                    html_payment_info={},
                    ocr_payment_info={},
                    html_validation={},
                    ocr_validation={},
                    discrepancies=[],
                    screenshot_path="",
                    ocr_confidence=0.0,
                    status="failure",
                    error_message=f"No contract conditions found for site {site_id}"
                )
            
            # Prepare contract conditions dict
            contract_conditions = {
                'prices': contract.prices,
                'payment_methods': contract.payment_methods,
                'fees': contract.fees,
                'subscription_terms': contract.subscription_terms
            }
            
            # Step 2: Extract HTML data
            # Get latest crawl result
            from src.models import CrawlResult
            latest_crawl = self.db_session.query(CrawlResult).filter(
                CrawlResult.site_id == site_id
            ).order_by(CrawlResult.crawled_at.desc()).first()
            
            if not latest_crawl:
                return VerificationData(
                    html_payment_info={},
                    ocr_payment_info={},
                    html_validation={},
                    ocr_validation={},
                    discrepancies=[],
                    screenshot_path="",
                    ocr_confidence=0.0,
                    status="failure",
                    error_message=f"No crawl results found for site {site_id}"
                )
            
            html_payment_info = self.content_analyzer.extract_payment_info(
                latest_crawl.html_content
            )
            
            # Step 3: Capture screenshot
            try:
                screenshot_path = await self.screenshot_capture.capture_screenshot(
                    url=site.url,
                    site_id=site_id,
                    screenshot_type="verification"
                )
            except Exception as e:
                return VerificationData(
                    html_payment_info=asdict(html_payment_info),
                    ocr_payment_info={},
                    html_validation={},
                    ocr_validation={},
                    discrepancies=[],
                    screenshot_path="",
                    ocr_confidence=0.0,
                    status="partial_failure",
                    error_message=f"Screenshot capture failed: {str(e)}"
                )
            
            # Step 4: Extract OCR data
            ocr_result = self.ocr_engine.extract_text(screenshot_path)
            
            if not ocr_result.success:
                return VerificationData(
                    html_payment_info=asdict(html_payment_info),
                    ocr_payment_info={},
                    html_validation={},
                    ocr_validation={},
                    discrepancies=[],
                    screenshot_path=str(screenshot_path),
                    ocr_confidence=0.0,
                    status="partial_failure",
                    error_message=f"OCR extraction failed: {ocr_result.error_message}"
                )
            
            ocr_payment_info = self._extract_payment_from_ocr(ocr_result.full_text)
            
            # Step 5: Compare HTML and OCR data
            discrepancies = self._compare_payment_data(html_payment_info, ocr_payment_info)
            
            # Step 6: Validate both against contract
            html_validation = self.validation_engine.validate_payment_info(
                html_payment_info,
                contract_conditions
            )
            
            ocr_validation = self.validation_engine.validate_payment_info(
                ocr_payment_info,
                contract_conditions
            )
            
            # Step 7: Store results in database
            verification_result = VerificationResult(
                site_id=site_id,
                html_data=asdict(html_payment_info),
                ocr_data=asdict(ocr_payment_info),
                html_violations=self._serialize_violations(html_validation, 'html'),
                ocr_violations=self._serialize_violations(ocr_validation, 'ocr'),
                discrepancies={'items': [asdict(d) for d in discrepancies]},
                screenshot_path=str(screenshot_path),
                ocr_confidence=ocr_result.average_confidence,
                status='success',
                error_message=None,
                created_at=datetime.utcnow()
            )
            
            self.db_session.add(verification_result)
            self.db_session.commit()
            
            return VerificationData(
                html_payment_info=asdict(html_payment_info),
                ocr_payment_info=asdict(ocr_payment_info),
                html_validation=self._serialize_validation_result(html_validation),
                ocr_validation=self._serialize_validation_result(ocr_validation),
                discrepancies=[asdict(d) for d in discrepancies],
                screenshot_path=str(screenshot_path),
                ocr_confidence=ocr_result.average_confidence,
                status='success',
                error_message=None
            )
        
        except Exception as e:
            # Handle unexpected errors
            return VerificationData(
                html_payment_info={},
                ocr_payment_info={},
                html_validation={},
                ocr_validation={},
                discrepancies=[],
                screenshot_path="",
                ocr_confidence=0.0,
                status="failure",
                error_message=f"Verification failed: {str(e)}"
            )
    
    def _extract_payment_from_ocr(self, ocr_text: str) -> PaymentInfo:
        """
        Extract payment information from OCR text.
        Uses same patterns as ContentAnalyzer.
        
        Args:
            ocr_text: Text extracted from OCR
            
        Returns:
            PaymentInfo object
        """
        # Reuse ContentAnalyzer's extraction logic
        # Wrap OCR text in minimal HTML structure
        html_wrapper = f"<html><body>{ocr_text}</body></html>"
        return self.content_analyzer.extract_payment_info(html_wrapper)
    
    def _compare_payment_data(
        self,
        html_data: PaymentInfo,
        ocr_data: PaymentInfo
    ) -> list[Discrepancy]:
        """
        Compare HTML and OCR payment data field by field.
        
        Args:
            html_data: Payment info from HTML
            ocr_data: Payment info from OCR
            
        Returns:
            List of discrepancies
        """
        discrepancies = []
        
        # Compare prices
        discrepancies.extend(
            self._compare_field('prices', html_data.prices, ocr_data.prices)
        )
        
        # Compare payment methods
        discrepancies.extend(
            self._compare_field('payment_methods', html_data.payment_methods, ocr_data.payment_methods)
        )
        
        # Compare fees
        discrepancies.extend(
            self._compare_field('fees', html_data.fees, ocr_data.fees)
        )
        
        # Compare subscription terms
        discrepancies.extend(
            self._compare_field('subscription_terms', html_data.subscription_terms, ocr_data.subscription_terms)
        )
        
        return discrepancies
    
    def _compare_field(
        self,
        field_name: str,
        html_value: Any,
        ocr_value: Any
    ) -> list[Discrepancy]:
        """
        Compare a specific field between HTML and OCR data.
        
        Args:
            field_name: Name of the field
            html_value: Value from HTML
            ocr_value: Value from OCR
            
        Returns:
            List of discrepancies for this field
        """
        discrepancies = []
        
        # Handle None values
        if html_value is None and ocr_value is None:
            return discrepancies
        
        if html_value is None and ocr_value is not None:
            discrepancies.append(Discrepancy(
                field_name=field_name,
                html_value=None,
                ocr_value=ocr_value,
                difference_type='missing',
                severity=self._determine_severity(field_name)
            ))
            return discrepancies
        
        if html_value is not None and ocr_value is None:
            discrepancies.append(Discrepancy(
                field_name=field_name,
                html_value=html_value,
                ocr_value=None,
                difference_type='missing',
                severity=self._determine_severity(field_name)
            ))
            return discrepancies
        
        # Compare values
        if isinstance(html_value, dict) and isinstance(ocr_value, dict):
            # Compare dictionaries (e.g., prices, fees)
            all_keys = set(html_value.keys()) | set(ocr_value.keys())
            for key in all_keys:
                html_sub = html_value.get(key)
                ocr_sub = ocr_value.get(key)
                
                if html_sub != ocr_sub:
                    discrepancies.append(Discrepancy(
                        field_name=f"{field_name}.{key}",
                        html_value=html_sub,
                        ocr_value=ocr_sub,
                        difference_type='mismatch',
                        severity=self._determine_severity(field_name)
                    ))
        
        elif isinstance(html_value, list) and isinstance(ocr_value, list):
            # Compare lists (e.g., payment_methods)
            html_set = set(html_value)
            ocr_set = set(ocr_value)
            
            if html_set != ocr_set:
                discrepancies.append(Discrepancy(
                    field_name=field_name,
                    html_value=html_value,
                    ocr_value=ocr_value,
                    difference_type='mismatch',
                    severity=self._determine_severity(field_name)
                ))
        
        else:
            # Direct comparison
            if html_value != ocr_value:
                discrepancies.append(Discrepancy(
                    field_name=field_name,
                    html_value=html_value,
                    ocr_value=ocr_value,
                    difference_type='mismatch',
                    severity=self._determine_severity(field_name)
                ))
        
        return discrepancies
    
    def _determine_severity(self, field_name: str) -> str:
        """
        Determine severity level based on field name.
        
        Args:
            field_name: Name of the field
            
        Returns:
            Severity level: 'low', 'medium', or 'high'
        """
        if 'price' in field_name.lower():
            return 'high'
        elif 'payment_method' in field_name.lower():
            return 'high'
        elif 'fee' in field_name.lower():
            return 'medium'
        elif 'subscription' in field_name.lower():
            return 'medium'
        else:
            return 'low'
    
    def _serialize_violations(self, validation_result: ValidationResult, data_source: str) -> dict:
        """
        Serialize validation violations with data source attribution.
        
        Args:
            validation_result: Validation result
            data_source: 'html' or 'ocr'
            
        Returns:
            Dictionary of violations
        """
        violations = []
        for violation in validation_result.violations:
            violations.append({
                'violation_type': violation.violation_type,
                'severity': violation.severity,
                'field_name': violation.field_name,
                'expected_value': violation.expected_value,
                'actual_value': violation.actual_value,
                'message': violation.message,
                'data_source': data_source
            })
        
        return {'items': violations}
    
    def _serialize_validation_result(self, validation_result: ValidationResult) -> dict:
        """
        Serialize validation result to dictionary.
        
        Args:
            validation_result: Validation result
            
        Returns:
            Dictionary representation
        """
        return {
            'is_valid': validation_result.is_valid,
            'violations': [
                {
                    'violation_type': v.violation_type,
                    'severity': v.severity,
                    'field_name': v.field_name,
                    'expected_value': v.expected_value,
                    'actual_value': v.actual_value,
                    'message': v.message
                }
                for v in validation_result.violations
            ]
        }
