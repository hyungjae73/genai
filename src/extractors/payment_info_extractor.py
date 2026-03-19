"""
Payment Info Extractor - 統合抽出エンジン。

MetadataExtractor、StructuredDataParser、SemanticParserを統合し、
抽出パイプライン（構造化データ → セマンティックHTML → 正規表現）を実行します。
商品と価格の関連付け、複数価格バリアントの処理、基本価格と追加手数料の関連付けを行います。

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 7.1-7.7, 22.1, 22.3, 22.4, 22.5, 22.6
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.extractors.confidence_calculator import ConfidenceCalculator
from src.extractors.language_detector import LanguageDetector
from src.extractors.metadata_extractor import MetadataExtractor
from src.extractors.semantic_parser import SemanticParser
from src.extractors.structured_data_parser import StructuredDataParser

logger = logging.getLogger(__name__)

# Maximum DB write retries with exponential backoff
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1  # seconds


class PaymentInfoExtractor:
    """
    統合抽出エンジン。

    複数のパーサーを統合し、構造化データ → セマンティックHTML → 正規表現の
    優先順位で支払い情報を抽出します。
    """

    def __init__(
        self,
        metadata_extractor: Optional[MetadataExtractor] = None,
        structured_parser: Optional[StructuredDataParser] = None,
        semantic_parser: Optional[SemanticParser] = None,
        confidence_calculator: Optional[ConfidenceCalculator] = None,
        language_detector: Optional[LanguageDetector] = None,
    ):
        self.metadata_extractor = metadata_extractor or MetadataExtractor()
        self.structured_parser = structured_parser or StructuredDataParser()
        self.semantic_parser = semantic_parser or SemanticParser()
        self.confidence_calculator = confidence_calculator or ConfidenceCalculator()
        self.language_detector = language_detector or LanguageDetector()

    def extract_payment_info(self, html: str, url: str) -> dict:
        """
        HTMLから支払い情報を抽出する。

        抽出パイプライン: 構造化データ → セマンティックHTML → 正規表現

        Args:
            html: HTML文字列
            url: ページURL

        Returns:
            抽出された支払い情報の辞書
        """
        result: Dict[str, Any] = {
            "product_info": {},
            "price_info": [],
            "payment_methods": [],
            "fees": [],
            "metadata": {},
            "confidence_scores": {},
            "overall_confidence": 0.0,
            "language": None,
            "extraction_source": None,
        }

        extraction_start = time.monotonic()

        try:
            # Step 1: Detect language
            result["language"] = self.language_detector.detect_language(html)

            # Step 2: Extract metadata
            result["metadata"] = self.metadata_extractor.extract_metadata(html)

            # Step 3: Pipeline - structured data first, then semantic, then regex
            extraction_source = self._run_extraction_pipeline(html, result)
            result["extraction_source"] = extraction_source

            # Step 4: Associate products with prices
            self._associate_products_and_prices(result)

            # Step 5: Associate base prices with fees
            self._associate_prices_and_fees(result)

            # Step 6: Calculate confidence scores
            self._calculate_confidence_scores(result, extraction_source)

        except Exception as e:
            logger.error(
                "Payment info extraction failed for url=%s: %s", url, e
            )
            result["metadata"]["extraction_error"] = str(e)

        elapsed = time.monotonic() - extraction_start
        logger.info(
            "Payment info extraction completed in %.2fs for url=%s (target <3s, Req 19.5)",
            elapsed, url,
        )
        if elapsed > 3.0:
            logger.warning(
                "Extraction exceeded 3s target: %.2fs for url=%s",
                elapsed, url,
            )

        return result

    def _run_extraction_pipeline(self, html: str, result: dict) -> str:
        """
        抽出パイプラインを実行する。

        構造化データ → セマンティックHTML の順で試行し、
        各段階で得られたデータをマージする。

        Returns:
            主要な抽出元 ("structured_data", "semantic_html", "regex")
        """
        primary_source = "regex"

        # --- Phase 1: Structured data (highest priority) ---
        try:
            jsonld_data = self.structured_parser.parse_jsonld(html)
            microdata = self.structured_parser.parse_microdata(html)
            all_structured = jsonld_data + microdata

            if all_structured:
                product_info = self.structured_parser.extract_product_info(
                    all_structured
                )
                if product_info.get("name") or product_info.get("prices"):
                    primary_source = "structured_data"
                    result["product_info"] = {
                        "name": product_info.get("name"),
                        "description": product_info.get("description"),
                        "sku": product_info.get("sku"),
                    }
                    for price in product_info.get("prices", []):
                        result["price_info"].append({
                            "amount": price.get("amount"),
                            "currency": price.get("currency", ""),
                            "price_type": price.get("price_type", "base_price"),
                            "condition": price.get("availability", ""),
                            "source": "structured_data",
                        })
        except Exception as e:
            logger.warning("Structured data extraction failed: %s", e)

        # --- Phase 2: Semantic HTML ---
        try:
            semantic_prices = self.semantic_parser.extract_prices(html)
            for sp in semantic_prices:
                # Avoid duplicates: skip if same amount already from structured data
                if not any(
                    p["amount"] == sp["amount"] and p["source"] == "structured_data"
                    for p in result["price_info"]
                ):
                    result["price_info"].append({
                        "amount": sp["amount"],
                        "currency": sp.get("currency", ""),
                        "price_type": "base_price",
                        "condition": sp.get("context", "")[:100],
                        "source": "semantic_html",
                    })
                    if primary_source == "regex":
                        primary_source = "semantic_html"

            # Extract payment methods from semantic HTML
            semantic_methods = self.semantic_parser.extract_payment_methods(html)
            for sm in semantic_methods:
                if not any(
                    m["method_name"] == sm["method_name"]
                    for m in result["payment_methods"]
                ):
                    result["payment_methods"].append({
                        "method_name": sm["method_name"],
                        "provider": None,
                        "processing_fee": None,
                        "fee_type": None,
                        "source": "semantic_html",
                    })

            # Extract fees from semantic HTML
            semantic_fees = self.semantic_parser.extract_fees(html)
            for sf in semantic_fees:
                result["fees"].append({
                    "fee_type": sf.get("fee_type", ""),
                    "amount": sf.get("amount"),
                    "currency": sf.get("currency", ""),
                    "description": sf.get("description", ""),
                    "source": "semantic_html",
                })
        except Exception as e:
            logger.warning("Semantic HTML extraction failed: %s", e)

        return primary_source

    def _associate_products_and_prices(self, result: dict) -> None:
        """商品と価格を関連付ける (Req 5.1, 5.2, 5.3)."""
        product_name = (result.get("product_info") or {}).get("name")
        product_sku = (result.get("product_info") or {}).get("sku")

        for price in result.get("price_info", []):
            if product_name:
                price["product_name"] = product_name
            if product_sku:
                price["product_sku"] = product_sku

    def _associate_prices_and_fees(self, result: dict) -> None:
        """基本価格と追加手数料を関連付ける (Req 5.4)."""
        base_prices = [
            p for p in result.get("price_info", [])
            if p.get("price_type") == "base_price"
        ]
        for fee in result.get("fees", []):
            if base_prices:
                fee["related_base_price"] = base_prices[0].get("amount")

    def _calculate_confidence_scores(self, result: dict, primary_source: str) -> None:
        """信頼度スコアを計算する (Req 6.1-6.6)."""
        scores: Dict[str, float] = {}

        # Product info confidence
        product_info = result.get("product_info") or {}
        if product_info.get("name"):
            scores["product_name"] = self.confidence_calculator.calculate_confidence_score(
                primary_source, "product_name", product_info["name"]
            )
        if product_info.get("description"):
            scores["product_description"] = self.confidence_calculator.calculate_confidence_score(
                primary_source, "product_description", product_info["description"]
            )
        if product_info.get("sku"):
            scores["sku"] = self.confidence_calculator.calculate_confidence_score(
                primary_source, "sku", product_info["sku"]
            )

        # Price info confidence - use the source of each price
        for i, price in enumerate(result.get("price_info", [])):
            source = price.get("source", primary_source)
            key = f"price_{i}" if i > 0 else "base_price"
            scores[key] = self.confidence_calculator.calculate_confidence_score(
                source, "base_price", price.get("amount")
            )
            currency_key = f"currency_{i}" if i > 0 else "currency"
            if price.get("currency"):
                scores[currency_key] = self.confidence_calculator.calculate_confidence_score(
                    source, "currency", price["currency"]
                )

        # Payment methods confidence
        if result.get("payment_methods"):
            method_sources = [m.get("source", primary_source) for m in result["payment_methods"]]
            best_source = method_sources[0] if method_sources else primary_source
            scores["payment_methods"] = self.confidence_calculator.calculate_confidence_score(
                best_source, "payment_methods", result["payment_methods"]
            )

        # Fees confidence
        if result.get("fees"):
            fee_sources = [f.get("source", primary_source) for f in result["fees"]]
            best_source = fee_sources[0] if fee_sources else primary_source
            scores["fees"] = self.confidence_calculator.calculate_confidence_score(
                best_source, "fees", result["fees"]
            )

        result["confidence_scores"] = scores
        result["overall_confidence"] = self.confidence_calculator.calculate_overall_score(scores)

    def save_extracted_info(
        self,
        session,
        crawl_result_id: int,
        site_id: int,
        extracted_data: dict,
    ) -> Optional[int]:
        """
        抽出結果をデータベースに永続化する。

        DB書き込み失敗時は最大3回、指数バックオフで再試行する。

        Args:
            session: SQLAlchemy Session
            crawl_result_id: クロール結果ID
            site_id: サイトID
            extracted_data: extract_payment_info() の戻り値

        Returns:
            保存されたレコードのID、失敗時はNone
        """
        from src.models import ExtractedPaymentInfo

        record = ExtractedPaymentInfo(
            crawl_result_id=crawl_result_id,
            site_id=site_id,
            product_info=extracted_data.get("product_info") or {},
            price_info=extracted_data.get("price_info") or [],
            payment_methods=extracted_data.get("payment_methods") or [],
            fees=extracted_data.get("fees") or [],
            extraction_metadata=extracted_data.get("metadata") or {},
            confidence_scores=extracted_data.get("confidence_scores") or {},
            overall_confidence_score=extracted_data.get("overall_confidence", 0.0),
            status="completed",
            language=extracted_data.get("language"),
            extracted_at=datetime.utcnow(),
        )

        last_error: Optional[Exception] = None
        for attempt in range(MAX_RETRIES):
            try:
                session.add(record)
                session.flush()
                logger.info(
                    "Saved extracted payment info: id=%d, crawl_result_id=%d, site_id=%d",
                    record.id, crawl_result_id, site_id,
                )
                return record.id
            except Exception as e:
                last_error = e
                session.rollback()
                delay = RETRY_BASE_DELAY * (2 ** attempt)  # 1s, 2s, 4s
                logger.warning(
                    "DB write failed (attempt %d/%d) for crawl_result_id=%d: %s. "
                    "Retrying in %ds...",
                    attempt + 1, MAX_RETRIES, crawl_result_id, e, delay,
                )
                if attempt < MAX_RETRIES - 1:
                    time.sleep(delay)

        # All retries exhausted - save a failed record
        logger.error(
            "DB write failed after %d retries for crawl_result_id=%d: %s",
            MAX_RETRIES, crawl_result_id, last_error,
        )
        self._save_failed_record(
            session, crawl_result_id, site_id, str(last_error)
        )
        return None

    def _save_failed_record(
        self,
        session,
        crawl_result_id: int,
        site_id: int,
        error_message: str,
    ) -> None:
        """抽出完全失敗時にfailedステータスのレコードを保存する (Req 22.3, 22.4)."""
        from src.models import ExtractedPaymentInfo

        try:
            failed_record = ExtractedPaymentInfo(
                crawl_result_id=crawl_result_id,
                site_id=site_id,
                product_info={},
                price_info=[],
                payment_methods=[],
                fees=[],
                extraction_metadata={"error": error_message},
                confidence_scores={},
                overall_confidence_score=0.0,
                status="failed",
                language=None,
                extracted_at=datetime.utcnow(),
            )
            session.add(failed_record)
            session.flush()
            logger.info(
                "Saved failed extraction record for crawl_result_id=%d",
                crawl_result_id,
            )
        except Exception as e:
            logger.error(
                "Failed to save failed record for crawl_result_id=%d: %s",
                crawl_result_id, e,
            )

    def extract_and_save(
        self,
        session,
        html: str,
        url: str,
        crawl_result_id: int,
        site_id: int,
    ) -> Optional[int]:
        """
        抽出と永続化を一括で実行する便利メソッド。

        Args:
            session: SQLAlchemy Session
            html: HTML文字列
            url: ページURL
            crawl_result_id: クロール結果ID
            site_id: サイトID

        Returns:
            保存されたレコードのID、失敗時はNone
        """
        try:
            extracted_data = self.extract_payment_info(html, url)
        except Exception as e:
            logger.error(
                "Extraction failed for site_id=%d, crawl_result_id=%d, url=%s: %s",
                site_id, crawl_result_id, url, e,
            )
            self._save_failed_record(session, crawl_result_id, site_id, str(e))
            return None

        return self.save_extracted_info(
            session, crawl_result_id, site_id, extracted_data
        )
