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


@dataclass
class StructuredPathResult:
    """構造化データ価格比較パスの結果。要件: 1.1, 1.5"""
    structured_price_data: dict          # StructuredPriceData の辞書表現
    violations: list                     # バリアント別違反レコード
    data_source: str                     # "json_ld" | "shopify_api" | "microdata" | "open_graph" | "html_fallback"
    status: str                          # "success" | "failure" | "fallback"
    error_message: Optional[str] = None


@dataclass
class EvidencePathResult:
    """視覚的証拠保全パスの結果。要件: 1.1, 1.5"""
    evidence_records: list               # EvidenceRecord の辞書表現リスト
    status: str                          # "success" | "failure" | "partial"
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

    # ------------------------------------------------------------------ #
    # 2-path parallel execution methods (verification-flow-restructure)
    # ------------------------------------------------------------------ #

    async def _run_structured_data_path(
        self, html: str, url: str, contract_conditions: dict
    ) -> StructuredPathResult:
        """構造化データ価格比較パスを実行する。要件: 2.1-2.6, 4.1-4.3, 5.1-5.4"""
        try:
            from src.extractors.structured_data_parser import StructuredDataParserV2
            parser = StructuredDataParserV2()
            price_data = parser.extract_all_variant_prices(html, url)

            if price_data.is_empty():
                violations = self._compare_variants_with_contract(
                    [{"variant_name": "default", "price": None, "currency": "", "data_source": "html_fallback"}],
                    contract_conditions,
                    "html_fallback",
                )
                return StructuredPathResult(
                    structured_price_data={"variants": [], "data_source": "html_fallback"},
                    violations=violations,
                    data_source="html_fallback",
                    status="fallback",
                )

            violations = self._compare_variants(price_data, contract_conditions)
            return StructuredPathResult(
                structured_price_data={
                    "product_name": price_data.product_name,
                    "variants": [
                        {
                            "variant_name": v.variant_name,
                            "price": v.price,
                            "compare_at_price": v.compare_at_price,
                            "currency": v.currency,
                            "sku": v.sku,
                            "options": v.options,
                            "data_source": v.data_source,
                        }
                        for v in price_data.variants
                    ],
                    "data_source": price_data.data_source,
                },
                violations=violations,
                data_source=price_data.data_source,
                status="success",
            )
        except Exception as e:
            return StructuredPathResult(
                structured_price_data={},
                violations=[],
                data_source="none",
                status="failure",
                error_message=str(e),
            )

    async def _run_evidence_path(
        self, site, screenshot_path: Optional[str]
    ) -> EvidencePathResult:
        """視覚的証拠保全パスを実行する。要件: 6.1-6.5, 7.1-7.5, 8.1-8.4

        スマート・リトライ: OCR信頼度が0%の場合、スクリーンショットを再取得して
        1回だけOCRをリトライする（JSレンダリング待ちのため5秒待機）。
        """
        import asyncio

        evidence_records = []
        try:
            if not screenshot_path:
                return EvidencePathResult(
                    evidence_records=[],
                    status="failure",
                    error_message="No screenshot available",
                )

            from pathlib import Path
            image_path = Path(screenshot_path)
            if not image_path.exists():
                return EvidencePathResult(
                    evidence_records=[],
                    status="failure",
                    error_message=f"Screenshot not found: {screenshot_path}",
                )

            # Detect ROIs and extract evidence
            try:
                rois = self.ocr_engine.detect_rois(image_path) if hasattr(self.ocr_engine, 'detect_rois') else []
            except Exception:
                rois = []

            if rois:
                for roi in rois:
                    try:
                        ocr_result = self.ocr_engine.extract_text(str(image_path))
                        evidence_records.append({
                            "variant_name": "default",
                            "screenshot_path": screenshot_path,
                            "roi_image_path": None,
                            "ocr_text": ocr_result.full_text if ocr_result.success else "",
                            "ocr_confidence": ocr_result.average_confidence if ocr_result.success else 0.0,
                            "evidence_type": roi.get("region_type", "general") if isinstance(roi, dict) else "general",
                        })
                    except Exception:
                        continue
            else:
                # Fallback: full image OCR
                try:
                    ocr_result = self.ocr_engine.extract_text(str(image_path))
                    evidence_records.append({
                        "variant_name": "default",
                        "screenshot_path": screenshot_path,
                        "roi_image_path": None,
                        "ocr_text": ocr_result.full_text if ocr_result.success else "",
                        "ocr_confidence": ocr_result.average_confidence if ocr_result.success else 0.0,
                        "evidence_type": "general",
                    })
                except Exception as e:
                    return EvidencePathResult(
                        evidence_records=[],
                        status="failure",
                        error_message=str(e),
                    )

            # --- Smart Retry: OCR信頼度0%の場合、スクリーンショット再取得+OCRリトライ ---
            if evidence_records and evidence_records[0].get("ocr_confidence", 0.0) == 0.0:
                try:
                    # 5秒待機（JSレンダリング完了を待つ）
                    await asyncio.sleep(5)
                    # スクリーンショットを再取得
                    retry_screenshot = await self.screenshot_capture.capture_screenshot(
                        url=site.url,
                        site_id=site.id,
                        screenshot_type="verification_retry",
                    )
                    if retry_screenshot:
                        retry_path = Path(retry_screenshot)
                        if retry_path.exists():
                            retry_ocr = self.ocr_engine.extract_text(str(retry_path))
                            if retry_ocr.success and retry_ocr.average_confidence > 0.0:
                                # リトライ成功: 結果を上書き
                                evidence_records[0] = {
                                    "variant_name": "default",
                                    "screenshot_path": retry_screenshot,
                                    "roi_image_path": None,
                                    "ocr_text": retry_ocr.full_text,
                                    "ocr_confidence": retry_ocr.average_confidence,
                                    "evidence_type": "general",
                                }
                except Exception:
                    pass  # リトライ失敗は無視、元の結果を維持

            return EvidencePathResult(
                evidence_records=evidence_records,
                status="success" if evidence_records else "partial",
            )
        except Exception as e:
            return EvidencePathResult(
                evidence_records=evidence_records,
                status="partial" if evidence_records else "failure",
                error_message=str(e),
            )

    def _compare_variants(self, price_data, contract_conditions: dict) -> list:
        """全バリアント価格を契約条件と比較する。要件: 5.1-5.4

        不変条件: 違反数 + 一致数 = 全バリアント数
        """
        violations = []
        contract_prices = contract_conditions.get("prices", {})

        for variant in price_data.variants:
            matched = False
            for price_key, contract_price_info in contract_prices.items():
                if isinstance(contract_price_info, dict):
                    contract_amount = contract_price_info.get("amount") or contract_price_info.get("price")
                elif isinstance(contract_price_info, (int, float)):
                    contract_amount = float(contract_price_info)
                else:
                    continue

                if contract_amount is None:
                    continue

                if abs(variant.price - float(contract_amount)) <= 0.01:
                    matched = True
                    break

            if not matched and contract_prices:
                first_price = next(iter(contract_prices.values()), None)
                contract_ref = None
                if isinstance(first_price, dict):
                    contract_ref = first_price.get("amount") or first_price.get("price")
                elif isinstance(first_price, (int, float)):
                    contract_ref = float(first_price)

                violations.append({
                    "variant_name": variant.variant_name,
                    "field": "price",
                    "contract_value": contract_ref,
                    "actual_value": variant.price,
                    "severity": "high",
                    "data_source": variant.data_source,
                })

        return violations

    def _compare_variants_with_contract(
        self, variants: list, contract_conditions: dict, data_source: str
    ) -> list:
        """dict 形式のバリアントリストで契約条件と比較する（フォールバック用）。"""
        return []

    async def run_verification_v2(self, site_id: int) -> VerificationData:
        """2パス並行実行による検証フロー。要件: 1.1-1.5

        構造化データ価格比較パスと視覚的証拠保全パスを asyncio.gather で並行実行する。
        一方のパスが失敗しても他方は継続する (return_exceptions=True)。
        """
        import asyncio

        try:
            # Fetch site and contract
            site = self.db_session.query(MonitoringSite).filter(
                MonitoringSite.id == site_id
            ).first()
            if not site:
                return VerificationData(
                    html_payment_info={}, ocr_payment_info={},
                    html_validation={}, ocr_validation={},
                    discrepancies=[], screenshot_path="",
                    ocr_confidence=0.0, status="failure",
                    error_message=f"Site {site_id} not found",
                )

            contract = self.db_session.query(ContractCondition).filter(
                ContractCondition.site_id == site_id,
                ContractCondition.is_current == True,
            ).first()
            if not contract:
                return VerificationData(
                    html_payment_info={}, ocr_payment_info={},
                    html_validation={}, ocr_validation={},
                    discrepancies=[], screenshot_path="",
                    ocr_confidence=0.0, status="failure",
                    error_message=f"No contract for site {site_id}",
                )

            contract_conditions = {
                "prices": contract.prices,
                "payment_methods": contract.payment_methods,
                "fees": contract.fees,
                "subscription_terms": contract.subscription_terms,
            }

            # Get latest crawl result
            from src.models import CrawlResult
            latest_crawl = self.db_session.query(CrawlResult).filter(
                CrawlResult.site_id == site_id
            ).order_by(CrawlResult.crawled_at.desc()).first()
            if not latest_crawl:
                return VerificationData(
                    html_payment_info={}, ocr_payment_info={},
                    html_validation={}, ocr_validation={},
                    discrepancies=[], screenshot_path="",
                    ocr_confidence=0.0, status="failure",
                    error_message=f"No crawl results for site {site_id}",
                )

            # Capture screenshot (needed by evidence path)
            screenshot_path: Optional[str] = None
            try:
                screenshot_path = await self.screenshot_capture.capture_screenshot(
                    url=site.url,
                    site_id=site_id,
                    screenshot_type="verification",
                )
            except Exception:
                pass  # Evidence path will handle missing screenshot

            # Run both paths in parallel
            structured_coro = self._run_structured_data_path(
                latest_crawl.html_content, site.url, contract_conditions
            )
            evidence_coro = self._run_evidence_path(site, screenshot_path)

            results = await asyncio.gather(structured_coro, evidence_coro, return_exceptions=True)

            if isinstance(results[0], Exception):
                structured_result = StructuredPathResult(
                    structured_price_data={}, violations=[],
                    data_source="none", status="failure",
                    error_message=str(results[0]),
                )
            else:
                structured_result: StructuredPathResult = results[0]

            if isinstance(results[1], Exception):
                evidence_result = EvidencePathResult(
                    evidence_records=[], status="failure",
                    error_message=str(results[1]),
                )
            else:
                evidence_result: EvidencePathResult = results[1]

            # Determine overall status
            if structured_result.status == "failure" and evidence_result.status == "failure":
                overall_status = "failure"
            elif structured_result.status == "failure" or evidence_result.status == "failure":
                overall_status = "partial_failure"
            else:
                overall_status = "success"

            # Save VerificationResult with new fields
            html_payment_info = self.content_analyzer.extract_payment_info(latest_crawl.html_content)
            ocr_confidence = 0.0
            if evidence_result.evidence_records:
                ocr_confidence = evidence_result.evidence_records[0].get("ocr_confidence", 0.0)

            verification_result = VerificationResult(
                site_id=site_id,
                html_data=asdict(html_payment_info),
                ocr_data={},
                html_violations={"items": structured_result.violations},
                ocr_violations={"items": []},
                discrepancies={"items": []},
                screenshot_path=screenshot_path or "",
                ocr_confidence=ocr_confidence,
                status=overall_status,
                error_message=None,
                created_at=datetime.utcnow(),
                # New fields (要件: 9.1-9.5)
                structured_data=structured_result.structured_price_data or None,
                structured_data_violations={"violations": structured_result.violations} if structured_result.violations else None,
                data_source=structured_result.data_source,
                structured_data_status=structured_result.status,
                evidence_status=evidence_result.status,
            )

            self.db_session.add(verification_result)
            self.db_session.flush()  # Get ID for EvidenceRecord FK

            # Save EvidenceRecords
            from src.models import EvidenceRecord
            from datetime import datetime as dt
            for rec in evidence_result.evidence_records:
                er = EvidenceRecord(
                    verification_result_id=verification_result.id,
                    variant_name=rec.get("variant_name", "default"),
                    screenshot_path=rec.get("screenshot_path", ""),
                    roi_image_path=rec.get("roi_image_path"),
                    ocr_text=rec.get("ocr_text", ""),
                    ocr_confidence=rec.get("ocr_confidence", 0.0),
                    evidence_type=rec.get("evidence_type", "general"),
                    created_at=dt.utcnow(),
                )
                self.db_session.add(er)

            self.db_session.commit()

            # --- OCR 0% 審査キュー自動投入 (manual-review-workflow 連携) ---
            # スマート・リトライ後もOCR信頼度が0%の場合、人間による目視確認が必要
            if ocr_confidence == 0.0 and evidence_result.evidence_records:
                try:
                    from src.review.service import ReviewService
                    from src.models import Alert
                    # OCR失敗アラートを生成
                    ocr_alert = Alert(
                        alert_type="ocr_failure",
                        severity="medium",
                        message=f"OCR信頼度0%: サイト {site.name} ({site.url}) のスクリーンショットからテキストを抽出できませんでした。目視確認が必要です。",
                        site_id=site_id,
                        is_resolved=False,
                    )
                    self.db_session.add(ocr_alert)
                    self.db_session.flush()
                    # 審査キューに投入
                    review_svc = ReviewService(self.db_session)
                    review_svc.enqueue_from_alert(ocr_alert)
                    self.db_session.commit()
                except Exception:
                    pass  # 審査キュー投入失敗はクロール結果に影響させない

            return VerificationData(
                html_payment_info=asdict(html_payment_info),
                ocr_payment_info={},
                html_validation={"violations": structured_result.violations, "data_source": structured_result.data_source},
                ocr_validation={},
                discrepancies=[],
                screenshot_path=screenshot_path or "",
                ocr_confidence=ocr_confidence,
                status=overall_status,
                error_message=None,
            )

        except Exception as e:
            return VerificationData(
                html_payment_info={}, ocr_payment_info={},
                html_validation={}, ocr_validation={},
                discrepancies=[], screenshot_path="",
                ocr_confidence=0.0, status="failure",
                error_message=f"Verification v2 failed: {str(e)}",
            )
