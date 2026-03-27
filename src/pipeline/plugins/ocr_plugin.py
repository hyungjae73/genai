"""
OCRPlugin — DataExtractor ステージ プラグイン。

スクリーンショットから OCR で視覚的証拠を抽出する。
ROI（関心領域）検出 → 切り出し → OCR 実行 → evidence_records に追加。

Requirements: 9.1, 9.2, 9.3, 9.4, 9.5
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from src.pipeline.context import CrawlContext
from src.pipeline.plugin import CrawlPlugin

logger = logging.getLogger(__name__)

# Price patterns for ROI detection (currency symbol + number)
PRICE_PATTERNS = [
    re.compile(r"[¥￥]\s*[\d,]+"),           # Japanese Yen
    re.compile(r"\$\s*[\d,]+\.?\d*"),         # US Dollar
    re.compile(r"€\s*[\d,]+\.?\d*"),          # Euro
    re.compile(r"£\s*[\d,]+\.?\d*"),          # British Pound
    re.compile(r"[\d,]+\s*円"),               # Japanese Yen (suffix)
    re.compile(r"[\d,]+\.?\d*\s*(?:USD|JPY|EUR|GBP)", re.IGNORECASE),
]


class OCRPlugin(CrawlPlugin):
    """スクリーンショットから OCR で証拠を抽出するプラグイン。

    各スクリーンショットから価格表示領域、注意書き領域、定期購入条件領域を
    ROI として検出し、OCR を実行して evidence_records に追加する。

    Requirements: 9.1, 9.2, 9.3, 9.4, 9.5
    """

    def __init__(self, ocr_engine=None, image_processor=None):
        """Initialize OCRPlugin.

        Args:
            ocr_engine: Optional OCREngine instance. Lazy-loaded if not provided.
            image_processor: Optional image processing callable for ROI cropping.
        """
        self._ocr_engine = ocr_engine
        self._image_processor = image_processor

    def _get_ocr_engine(self):
        """Lazy-load OCREngine to avoid import issues when libraries aren't installed."""
        if self._ocr_engine is None:
            try:
                from src.ocr_engine import OCREngine
                self._ocr_engine = OCREngine()
            except ImportError:
                logger.warning("OCREngine not available, OCR will be skipped")
                return None
        return self._ocr_engine

    def should_run(self, ctx: CrawlContext) -> bool:
        """screenshots が1件以上存在する場合に True を返す。"""
        return len(ctx.screenshots) >= 1

    async def execute(self, ctx: CrawlContext) -> CrawlContext:
        """スクリーンショットから OCR で証拠を抽出する。

        Args:
            ctx: パイプライン共有コンテキスト

        Returns:
            evidence_records に OCR 結果を追記した CrawlContext
        """
        ocr_engine = self._get_ocr_engine()
        if ocr_engine is None:
            ctx.errors.append({
                "plugin": self.name,
                "stage": "data_extractor",
                "error": "OCR engine not available",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return ctx

        total_processed = 0

        for screenshot in ctx.screenshots:
            try:
                image_path = Path(screenshot.image_path)
                processed = False
                last_error: Optional[str] = None

                # Detect ROIs in the screenshot
                rois = self._detect_rois(ocr_engine, image_path)

                if rois:
                    # Process each ROI
                    for roi in rois:
                        evidence = self._process_roi(
                            ocr_engine, image_path, roi, screenshot.variant_name
                        )
                        if evidence:
                            ctx.evidence_records.append(evidence)
                            total_processed += 1
                            processed = True
                else:
                    # No ROI detected: OCR on full screenshot (Req 9.4)
                    evidence = self._process_full_screenshot(
                        ocr_engine, image_path, screenshot.variant_name
                    )
                    if evidence:
                        ctx.evidence_records.append(evidence)
                        total_processed += 1
                        processed = True

                if not processed:
                    # Both ROI detection and full screenshot OCR failed
                    ctx.errors.append({
                        "plugin": self.name,
                        "stage": "data_extractor",
                        "error": f"OCR produced no results for {screenshot.image_path}",
                        "screenshot": screenshot.image_path,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

            except Exception as e:
                error_msg = f"OCR processing failed for {screenshot.image_path}: {str(e)}"
                logger.error(error_msg)
                ctx.errors.append({
                    "plugin": self.name,
                    "stage": "data_extractor",
                    "error": error_msg,
                    "screenshot": screenshot.image_path,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

        ctx.metadata["ocr_processed_count"] = total_processed
        ctx.metadata["ocr_screenshot_count"] = len(ctx.screenshots)

        return ctx

    def _detect_rois(
        self, ocr_engine, image_path: Path
    ) -> list[dict[str, Any]]:
        """スクリーンショットから ROI（関心領域）を検出する。

        テキストブロックの位置情報（bbox）と価格パターンのマッチングを使用。

        Args:
            ocr_engine: OCREngine instance
            image_path: スクリーンショットのパス

        Returns:
            検出された ROI のリスト。各 ROI は bbox と type を持つ。
        """
        rois: list[dict[str, Any]] = []

        try:
            # Run OCR to get text regions with bounding boxes
            result = ocr_engine.extract_text(image_path)
            if not result.success:
                return rois

            for region in result.regions:
                text = region.text
                bbox = region.bbox  # (x, y, width, height)

                # Check if region contains price patterns (Req 9.5)
                roi_type = self._classify_region(text)
                if roi_type:
                    rois.append({
                        "bbox": bbox,
                        "type": roi_type,
                        "text": text,
                        "confidence": region.confidence,
                    })

        except Exception as e:
            logger.warning("ROI detection failed for %s: %s", image_path, e)

        return rois

    def _classify_region(self, text: str) -> Optional[str]:
        """テキスト内容に基づいて ROI タイプを分類する。

        Returns:
            ROI タイプ: "price_display", "terms_notice", "subscription_condition", or None
        """
        if not text:
            return None

        # Price pattern matching (Req 9.5)
        for pattern in PRICE_PATTERNS:
            if pattern.search(text):
                return "price_display"

        # Terms/notice patterns
        terms_keywords = ["注意", "条件", "規約", "terms", "conditions", "notice", "注"]
        if any(kw in text.lower() for kw in terms_keywords):
            return "terms_notice"

        # Subscription patterns
        subscription_keywords = ["定期", "サブスク", "subscription", "recurring", "月額", "年額"]
        if any(kw in text.lower() for kw in subscription_keywords):
            return "subscription_condition"

        return None

    def _process_roi(
        self,
        ocr_engine,
        image_path: Path,
        roi: dict[str, Any],
        variant_name: str,
    ) -> Optional[dict[str, Any]]:
        """ROI を切り出して OCR を実行し、evidence_record を生成する。

        Args:
            ocr_engine: OCREngine instance
            image_path: 元画像のパス
            roi: ROI 情報 (bbox, type, text, confidence)
            variant_name: バリアント名

        Returns:
            evidence_record dict, or None if processing fails
        """
        try:
            roi_image_path = self._crop_roi(image_path, roi["bbox"])

            if roi_image_path:
                # OCR on cropped ROI image
                result = ocr_engine.extract_text(roi_image_path)
                ocr_text = result.full_text if result.success else roi.get("text", "")
                ocr_confidence = result.average_confidence if result.success else roi.get("confidence", 0.0)
            else:
                # Use text from initial detection
                ocr_text = roi.get("text", "")
                ocr_confidence = roi.get("confidence", 0.0)

            return {
                "variant_name": variant_name,
                "screenshot_path": str(image_path),
                "roi_image_path": str(roi_image_path) if roi_image_path else None,
                "ocr_text": ocr_text,
                "ocr_confidence": ocr_confidence,
                "evidence_type": roi.get("type", "general"),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.warning("ROI processing failed: %s", e)
            return None

    def _process_full_screenshot(
        self,
        ocr_engine,
        image_path: Path,
        variant_name: str,
    ) -> Optional[dict[str, Any]]:
        """スクリーンショット全体に OCR を実行する（ROI 未検出時）。

        Args:
            ocr_engine: OCREngine instance
            image_path: スクリーンショットのパス
            variant_name: バリアント名

        Returns:
            evidence_record dict, or None if processing fails
        """
        try:
            result = ocr_engine.extract_text(image_path)
            if not result.success:
                return None

            return {
                "variant_name": variant_name,
                "screenshot_path": str(image_path),
                "roi_image_path": None,
                "ocr_text": result.full_text,
                "ocr_confidence": result.average_confidence,
                "evidence_type": "general",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.warning("Full screenshot OCR failed for %s: %s", image_path, e)
            return None

    def _crop_roi(self, image_path: Path, bbox: tuple) -> Optional[Path]:
        """画像から ROI を切り出す。

        Args:
            image_path: 元画像のパス
            bbox: (x, y, width, height)

        Returns:
            切り出し画像のパス, or None if cropping fails
        """
        if self._image_processor:
            return self._image_processor(image_path, bbox)

        try:
            from PIL import Image

            img = Image.open(str(image_path))
            x, y, w, h = bbox

            # Add padding around the ROI for better OCR
            padding = 10
            left = max(0, x - padding)
            top = max(0, y - padding)
            right = min(img.width, x + w + padding)
            bottom = min(img.height, y + h + padding)

            cropped = img.crop((left, top, right, bottom))

            # Save cropped image
            roi_path = image_path.parent / f"{image_path.stem}_roi_{x}_{y}{image_path.suffix}"
            cropped.save(str(roi_path))

            return roi_path

        except ImportError:
            logger.warning("PIL not available for ROI cropping")
            return None
        except Exception as e:
            logger.warning("ROI cropping failed: %s", e)
            return None
