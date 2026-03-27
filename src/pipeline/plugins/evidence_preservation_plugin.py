"""
EvidencePreservationPlugin — Validator ステージ プラグイン。

evidence_records に evidence_type を分類し、全必須フィールドを設定する。
同一パイプライン実行の全レコードを同一 VerificationResult に関連付ける。

Requirements: 11.1, 11.2, 11.3, 11.4
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from src.pipeline.context import CrawlContext
from src.pipeline.plugin import CrawlPlugin

logger = logging.getLogger(__name__)

# Evidence type classification patterns
PRICE_PATTERNS = [
    re.compile(r"[¥$€£]\s*[\d,]+", re.IGNORECASE),
    re.compile(r"[\d,]+\s*円", re.IGNORECASE),
    re.compile(r"price", re.IGNORECASE),
    re.compile(r"料金|価格", re.IGNORECASE),
]

TERMS_PATTERNS = [
    re.compile(r"注意|注記|ご注意", re.IGNORECASE),
    re.compile(r"terms|conditions|notice", re.IGNORECASE),
    re.compile(r"利用規約|約款", re.IGNORECASE),
]

SUBSCRIPTION_PATTERNS = [
    re.compile(r"定期|サブスク|subscription", re.IGNORECASE),
    re.compile(r"自動更新|auto.?renew", re.IGNORECASE),
    re.compile(r"月額|年額|monthly|annual", re.IGNORECASE),
    re.compile(r"解約|cancel", re.IGNORECASE),
]


class EvidencePreservationPlugin(CrawlPlugin):
    """証拠レコードに evidence_type を分類し必須フィールドを設定するプラグイン。

    各 evidence_record に対して:
    - evidence_type を分類 (price_display, terms_notice, subscription_condition, general)
    - 全必須フィールドを設定
    - 同一パイプライン実行の全レコードを同一 verification_result_id に関連付け

    Requirements: 11.1, 11.2, 11.3, 11.4
    """

    def __init__(self, verification_result_id: int | None = None):
        """Initialize EvidencePreservationPlugin.

        Args:
            verification_result_id: Optional fixed verification_result_id.
                                     If None, generates a temporary ID.
        """
        self._verification_result_id = verification_result_id

    def should_run(self, ctx: CrawlContext) -> bool:
        """evidence_records が1件以上存在する場合に True を返す。"""
        return len(ctx.evidence_records) >= 1

    async def execute(self, ctx: CrawlContext) -> CrawlContext:
        """各 evidence_record に evidence_type と必須フィールドを設定する。

        Args:
            ctx: パイプライン共有コンテキスト

        Returns:
            evidence_records を更新した CrawlContext
        """
        try:
            # Use provided ID or generate a temporary one
            verification_result_id = self._verification_result_id
            if verification_result_id is None:
                # Use a temporary ID; the actual DB ID will be set by DBStoragePlugin
                verification_result_id = ctx.metadata.get(
                    "evidencepreservation_verification_result_id",
                    hash(f"{ctx.site.id}_{datetime.now(timezone.utc).isoformat()}") % (10**9),
                )

            now = datetime.now(timezone.utc)
            processed_records = []

            for record in ctx.evidence_records:
                processed = self._process_record(
                    record, verification_result_id, now
                )
                processed_records.append(processed)

            ctx.evidence_records = processed_records

            ctx.metadata["evidencepreservation_verification_result_id"] = verification_result_id
            ctx.metadata["evidencepreservation_record_count"] = len(processed_records)

        except Exception as e:
            logger.error("EvidencePreservationPlugin failed: %s", e)
            ctx.errors.append({
                "plugin": self.name,
                "stage": "validator",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        return ctx

    def _process_record(
        self,
        record: dict[str, Any],
        verification_result_id: int,
        now: datetime,
    ) -> dict[str, Any]:
        """Process a single evidence record, setting all required fields.

        Args:
            record: The raw evidence record dict
            verification_result_id: Shared verification result ID
            now: Current timestamp

        Returns:
            Processed record with all required fields set
        """
        ocr_text = record.get("ocr_text", "")
        evidence_type = self._classify_evidence_type(ocr_text)

        return {
            "verification_result_id": verification_result_id,
            "variant_name": record.get("variant_name", "unknown"),
            "screenshot_path": record.get("screenshot_path", ""),
            "roi_image_path": record.get("roi_image_path"),
            "ocr_text": ocr_text,
            "ocr_confidence": record.get("ocr_confidence", 0.0),
            "evidence_type": evidence_type,
            "created_at": record.get("created_at", now.isoformat()),
        }

    def _classify_evidence_type(self, ocr_text: str) -> str:
        """Classify the evidence type based on OCR text content.

        Classification priority:
        1. subscription_condition — subscription/auto-renewal terms
        2. terms_notice — terms, conditions, notices
        3. price_display — price-related content
        4. general — default fallback

        Args:
            ocr_text: The OCR-extracted text

        Returns:
            One of: 'price_display', 'terms_notice', 'subscription_condition', 'general'
        """
        if not ocr_text:
            return "general"

        # Check subscription patterns first (most specific)
        if any(p.search(ocr_text) for p in SUBSCRIPTION_PATTERNS):
            return "subscription_condition"

        # Check terms/notice patterns
        if any(p.search(ocr_text) for p in TERMS_PATTERNS):
            return "terms_notice"

        # Check price patterns
        if any(p.search(ocr_text) for p in PRICE_PATTERNS):
            return "price_display"

        return "general"
