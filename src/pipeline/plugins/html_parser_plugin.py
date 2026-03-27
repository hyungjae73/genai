"""
HTMLParserPlugin — DataExtractor ステージ プラグイン。

構造化データが取得できないサイトで、既存の PaymentInfoExtractor を
フォールバックとして呼び出し、HTML から価格情報を抽出する。

Requirements: 8.1, 8.2, 8.3
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from src.pipeline.context import CrawlContext
from src.pipeline.plugin import CrawlPlugin

logger = logging.getLogger(__name__)


class HTMLParserPlugin(CrawlPlugin):
    """構造化データ未取得時のフォールバック HTML 解析プラグイン。

    StructuredDataPlugin が構造化データを取得できなかった場合
    (metadata に structureddata_empty: True が設定されている場合) に実行され、
    既存の PaymentInfoExtractor を使用して HTML から価格情報を抽出する。

    Requirements: 8.1, 8.2, 8.3
    """

    def __init__(self, extractor=None):
        """Initialize HTMLParserPlugin.

        Args:
            extractor: Optional PaymentInfoExtractor instance.
                       Defaults to creating a new instance. Useful for testing.
        """
        self._extractor = extractor

    def _get_extractor(self):
        """Lazy-load PaymentInfoExtractor to avoid import issues."""
        if self._extractor is None:
            from src.extractors.payment_info_extractor import PaymentInfoExtractor
            self._extractor = PaymentInfoExtractor()
        return self._extractor

    def should_run(self, ctx: CrawlContext) -> bool:
        """metadata に structureddata_empty: True がある場合に True を返す。"""
        return ctx.metadata.get("structureddata_empty") is True

    async def execute(self, ctx: CrawlContext) -> CrawlContext:
        """PaymentInfoExtractor を使用して HTML から価格情報を抽出する。

        Args:
            ctx: パイプライン共有コンテキスト

        Returns:
            extracted_data にフォールバック抽出結果を追記した CrawlContext
        """
        html = ctx.html_content or ""
        if not html:
            ctx.metadata["htmlparser_skipped"] = True
            return ctx

        try:
            extractor = self._get_extractor()
            extracted = extractor.extract_payment_info(html, ctx.url)

            # Build variant-style data from PaymentInfoExtractor results
            variants = self._convert_to_variants(extracted)

            if variants:
                existing = ctx.extracted_data.get("structured_price_data", {})
                existing_variants = existing.get("variants", [])
                existing_sources = existing.get("data_sources_used", [])

                all_variants = existing_variants + variants
                all_sources = list(set(existing_sources + ["html_fallback"]))

                product_name = (extracted.get("product_info") or {}).get("name") or existing.get("product_name")

                ctx.extracted_data["structured_price_data"] = {
                    "product_name": product_name,
                    "variants": all_variants,
                    "data_sources_used": all_sources,
                    "extraction_timestamp": datetime.now(timezone.utc).isoformat(),
                }

            ctx.metadata["htmlparser_extraction_source"] = extracted.get("extraction_source")
            ctx.metadata["htmlparser_price_count"] = len(variants)

        except Exception as e:
            error_msg = f"HTMLParserPlugin error: {str(e)}"
            logger.error("%s for url=%s", error_msg, ctx.url)
            ctx.errors.append({
                "plugin": self.name,
                "stage": "data_extractor",
                "error": error_msg,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        return ctx

    def _convert_to_variants(self, extracted: dict) -> list[dict[str, Any]]:
        """PaymentInfoExtractor の結果をバリアント形式に変換する。

        Args:
            extracted: PaymentInfoExtractor.extract_payment_info() の戻り値

        Returns:
            StructuredPriceData 互換のバリアントリスト
        """
        variants: list[dict[str, Any]] = []
        price_info = extracted.get("price_info", [])

        for i, price in enumerate(price_info):
            amount = price.get("amount")
            if amount is None:
                continue

            variant_name = price.get("product_name") or f"価格{i + 1}" if i > 0 else "デフォルト"

            variants.append({
                "variant_name": variant_name,
                "price": float(amount) if amount is not None else None,
                "compare_at_price": None,
                "currency": price.get("currency", ""),
                "sku": price.get("product_sku"),
                "data_source": "html_fallback",
                "options": {},
            })

        return variants
