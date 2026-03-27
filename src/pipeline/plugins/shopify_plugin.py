"""
ShopifyPlugin — DataExtractor ステージ プラグイン。

Shopify サイトの全バリアント価格を `/products/{handle}.json` エンドポイントから取得する。
HTML 内の Shopify 検出 → API リクエスト → バリアント価格抽出。

Requirements: 7.1, 7.2, 7.3, 7.4
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from src.pipeline.context import CrawlContext
from src.pipeline.plugin import CrawlPlugin

logger = logging.getLogger(__name__)

# Patterns to detect Shopify in HTML
SHOPIFY_PATTERNS = [
    re.compile(r"Shopify\.shop", re.IGNORECASE),
    re.compile(r"cdn\.shopify\.com", re.IGNORECASE),
]


class ShopifyPlugin(CrawlPlugin):
    """Shopify サイトの全バリアント価格を API から取得するプラグイン。

    HTML 内に Shopify.shop または cdn.shopify.com が検出された場合に実行され、
    `/products/{handle}.json` から全バリアントの価格情報を抽出する。

    Requirements: 7.1, 7.2, 7.3, 7.4
    """

    # Allow dependency injection for testing
    def __init__(self, http_fetcher=None):
        """Initialize ShopifyPlugin.

        Args:
            http_fetcher: Optional callable(url) -> dict for HTTP fetching.
                          Defaults to urllib-based fetcher. Useful for testing.
        """
        self._http_fetcher = http_fetcher or self._default_fetch

    def should_run(self, ctx: CrawlContext) -> bool:
        """html_content に Shopify.shop or cdn.shopify.com が含まれる場合に True を返す。"""
        if ctx.html_content is None:
            return False
        return any(pattern.search(ctx.html_content) for pattern in SHOPIFY_PATTERNS)

    async def execute(self, ctx: CrawlContext) -> CrawlContext:
        """Shopify product.json から全バリアント価格を取得する。

        Args:
            ctx: パイプライン共有コンテキスト

        Returns:
            extracted_data にバリアント価格を追記した CrawlContext
        """
        try:
            handle = self._extract_product_handle(ctx.url)
            if not handle:
                ctx.metadata["shopify_no_handle"] = True
                return ctx

            product_json_url = self._build_product_json_url(ctx.url, handle)
            ctx.metadata["shopify_api_url"] = product_json_url

            product_data = self._http_fetcher(product_json_url)
            variants = self._extract_variants(product_data)

            if variants:
                # Merge into extracted_data
                existing = ctx.extracted_data.get("structured_price_data", {})
                existing_variants = existing.get("variants", [])
                existing_sources = existing.get("data_sources_used", [])

                all_variants = existing_variants + variants
                all_sources = list(set(existing_sources + ["shopify_api"]))

                ctx.extracted_data["structured_price_data"] = {
                    "product_name": product_data.get("product", {}).get("title", existing.get("product_name")),
                    "variants": all_variants,
                    "data_sources_used": all_sources,
                    "extraction_timestamp": datetime.now(timezone.utc).isoformat(),
                }

            ctx.metadata["shopify_variants_count"] = len(variants)

        except HTTPError as e:
            error_msg = f"Shopify API HTTP error: {e.code}"
            logger.warning("%s for url=%s", error_msg, ctx.url)
            ctx.errors.append({
                "plugin": self.name,
                "stage": "data_extractor",
                "error": error_msg,
                "http_code": e.code,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            error_msg = f"ShopifyPlugin error: {str(e)}"
            logger.error("%s for url=%s", error_msg, ctx.url)
            ctx.errors.append({
                "plugin": self.name,
                "stage": "data_extractor",
                "error": error_msg,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        return ctx

    def _extract_product_handle(self, url: str) -> Optional[str]:
        """URL からプロダクトハンドルを抽出する。

        Shopify の URL パターン: /products/{handle} or /products/{handle}?variant=...
        """
        parsed = urlparse(url)
        path = parsed.path.rstrip("/")

        # Match /products/{handle}
        match = re.search(r"/products/([^/?#]+)", path)
        if match:
            return match.group(1)

        # Match /collections/.../products/{handle}
        match = re.search(r"/collections/[^/]+/products/([^/?#]+)", path)
        if match:
            return match.group(1)

        return None

    def _build_product_json_url(self, url: str, handle: str) -> str:
        """product.json の URL を構築する。"""
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        return f"{base}/products/{handle}.json"

    def _extract_variants(self, product_data: dict) -> list[dict[str, Any]]:
        """product.json レスポンスからバリアント情報を抽出する。

        Args:
            product_data: Shopify product.json のレスポンス dict

        Returns:
            バリアント情報のリスト
        """
        variants: list[dict[str, Any]] = []
        product = product_data.get("product", {})
        raw_variants = product.get("variants", [])

        for v in raw_variants:
            price = self._parse_price(v.get("price"))
            if price is None:
                continue

            variant = {
                "variant_name": v.get("title", "デフォルト"),
                "price": price,
                "compare_at_price": self._parse_price(v.get("compare_at_price")),
                "currency": "",  # Shopify API doesn't always include currency in variants
                "sku": v.get("sku"),
                "data_source": "shopify_api",
                "options": {},
            }

            # Extract option1-3
            for opt_key in ("option1", "option2", "option3"):
                opt_val = v.get(opt_key)
                if opt_val:
                    variant["options"][opt_key] = opt_val

            variants.append(variant)

        return variants

    def _parse_price(self, value: Any) -> Optional[float]:
        """価格値を float に変換する。"""
        if value is None:
            return None
        try:
            cleaned = str(value).replace(",", "").strip()
            return float(cleaned)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _default_fetch(url: str) -> dict:
        """urllib を使用した HTTP GET リクエスト。"""
        req = Request(url, headers={"Accept": "application/json", "User-Agent": "CrawlPipeline/1.0"})
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
