"""
StructuredDataPlugin — DataExtractor ステージ プラグイン。

HTML 構造化データ（JSON-LD, Open Graph, Microdata）から価格情報を抽出する。
優先順位: JSON-LD > Shopify API > Microdata > Open Graph

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

from bs4 import BeautifulSoup

from src.pipeline.context import CrawlContext
from src.pipeline.plugin import CrawlPlugin

logger = logging.getLogger(__name__)

# Priority order: lower number = higher priority
SOURCE_PRIORITY = {
    "json_ld": 0,
    "shopify_api": 1,
    "microdata": 2,
    "open_graph": 3,
}


class StructuredDataPlugin(CrawlPlugin):
    """HTML 構造化データから価格情報を抽出するプラグイン。

    JSON-LD, Open Graph, Microdata の3つのデータソースから価格を抽出し、
    StructuredPriceData 形式で ctx.extracted_data に格納する。

    優先順位: JSON-LD > Shopify API > Microdata > Open Graph
    同一商品の価格が複数ソースから取得された場合、優先度の高いソースを採用する。
    """

    def should_run(self, ctx: CrawlContext) -> bool:
        """html_content が存在する場合に True を返す。"""
        return ctx.html_content is not None

    async def execute(self, ctx: CrawlContext) -> CrawlContext:
        """構造化データから価格情報を抽出する。

        Args:
            ctx: パイプライン共有コンテキスト

        Returns:
            extracted_data に StructuredPriceData を追記した CrawlContext
        """
        html = ctx.html_content or ""

        try:
            soup = BeautifulSoup(html, "html.parser")

            # Extract from each source
            jsonld_variants = self._extract_from_jsonld(soup)
            microdata_variants = self._extract_from_microdata(soup)
            og_variants = self._extract_from_open_graph(soup)

            # Collect product name from any source
            product_name = (
                self._get_product_name_jsonld(soup)
                or self._get_product_name_microdata(soup)
                or self._get_product_name_og(soup)
            )

            # Merge variants with priority deduplication
            all_variants = jsonld_variants + microdata_variants + og_variants
            merged_variants = self._merge_by_priority(all_variants)

            data_sources_used = sorted(
                {v["data_source"] for v in merged_variants},
                key=lambda s: SOURCE_PRIORITY.get(s, 99),
            )

            if merged_variants:
                ctx.extracted_data["structured_price_data"] = {
                    "product_name": product_name,
                    "variants": merged_variants,
                    "data_sources_used": data_sources_used,
                    "extraction_timestamp": datetime.now(timezone.utc).isoformat(),
                }
            else:
                ctx.metadata["structureddata_empty"] = True

        except Exception as e:
            logger.error("StructuredDataPlugin failed: %s", e)
            ctx.errors.append({
                "plugin": self.name,
                "stage": "data_extractor",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            ctx.metadata["structureddata_empty"] = True

        return ctx

    # ------------------------------------------------------------------
    # JSON-LD extraction
    # ------------------------------------------------------------------

    def _extract_from_jsonld(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """JSON-LD スクリプトタグから価格バリアントを抽出する。"""
        variants: list[dict[str, Any]] = []
        scripts = soup.find_all("script", attrs={"type": "application/ld+json"})

        for script in scripts:
            try:
                text = script.string
                if not text:
                    continue
                data = json.loads(text)
                items = self._flatten_jsonld(data)
                for item in items:
                    variants.extend(self._extract_offers_from_item(item, "json_ld"))
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning("JSON-LD parse error: %s", e)

        return variants

    def _flatten_jsonld(self, data: Any) -> list[dict]:
        """JSON-LD データをフラットなアイテムリストに変換する。"""
        if isinstance(data, list):
            result = []
            for item in data:
                result.extend(self._flatten_jsonld(item))
            return result
        if isinstance(data, dict):
            if "@graph" in data:
                return self._flatten_jsonld(data["@graph"])
            return [data]
        return []

    def _extract_offers_from_item(
        self, item: dict, data_source: str
    ) -> list[dict[str, Any]]:
        """schema.org Product/Offer アイテムからバリアントを抽出する。"""
        variants: list[dict[str, Any]] = []
        item_type = self._get_schema_type(item)

        if self._is_product_type(item_type):
            offers = item.get("offers")
            if offers:
                variants.extend(
                    self._parse_offers(offers, data_source, item.get("name"))
                )
        elif self._is_offer_type(item_type):
            variant = self._parse_single_offer(item, data_source)
            if variant:
                variants.append(variant)

        return variants

    def _parse_offers(
        self, offers: Any, data_source: str, product_name: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """offers フィールドからバリアントリストを生成する。"""
        variants: list[dict[str, Any]] = []

        if isinstance(offers, dict):
            offer_type = self._get_schema_type(offers)
            if "aggregateoffer" in offer_type.lower():
                # AggregateOffer: lowPrice / highPrice
                for price_key, label in [("lowPrice", "最低価格"), ("highPrice", "最高価格")]:
                    price = self._parse_price(offers.get(price_key))
                    if price is not None:
                        variants.append({
                            "variant_name": label,
                            "price": price,
                            "compare_at_price": None,
                            "currency": offers.get("priceCurrency", ""),
                            "sku": None,
                            "data_source": data_source,
                            "options": {},
                        })
            else:
                variant = self._parse_single_offer(
                    offers, data_source, product_name
                )
                if variant:
                    variants.append(variant)
        elif isinstance(offers, list):
            for i, offer in enumerate(offers):
                if isinstance(offer, dict):
                    variant = self._parse_single_offer(
                        offer, data_source, product_name
                    )
                    if variant:
                        variants.append(variant)

        return variants

    def _parse_single_offer(
        self,
        offer: dict,
        data_source: str,
        product_name: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """単一の Offer から variant dict を生成する。"""
        price = self._parse_price(offer.get("price"))
        if price is None:
            return None

        variant_name = offer.get("name") or product_name or "デフォルト"
        return {
            "variant_name": variant_name,
            "price": price,
            "compare_at_price": self._parse_price(offer.get("compare_at_price")),
            "currency": offer.get("priceCurrency", ""),
            "sku": offer.get("sku"),
            "data_source": data_source,
            "options": {},
        }

    # ------------------------------------------------------------------
    # Microdata extraction
    # ------------------------------------------------------------------

    def _extract_from_microdata(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """Microdata 属性から価格バリアントを抽出する。"""
        variants: list[dict[str, Any]] = []

        items = soup.find_all(attrs={"itemscope": True})
        for item in items:
            item_type = item.get("itemtype", "")
            if not self._is_product_type(item_type) and not self._is_offer_type(item_type):
                continue

            if self._is_product_type(item_type):
                # Find nested offers
                offer_elements = item.find_all(
                    attrs={"itemtype": re.compile(r"schema\.org/(Offer|AggregateOffer)", re.I)}
                )
                if offer_elements:
                    for offer_el in offer_elements:
                        variant = self._parse_microdata_offer(offer_el)
                        if variant:
                            variants.append(variant)
                else:
                    # Price directly on product
                    variant = self._parse_microdata_offer(item)
                    if variant:
                        variants.append(variant)
            elif self._is_offer_type(item_type):
                # Skip if this is a child of a product we already processed
                parent = item.find_parent(attrs={"itemscope": True})
                if parent and self._is_product_type(parent.get("itemtype", "")):
                    continue
                variant = self._parse_microdata_offer(item)
                if variant:
                    variants.append(variant)

        return variants

    def _parse_microdata_offer(self, element) -> Optional[dict[str, Any]]:
        """Microdata 要素から variant dict を生成する。"""
        price_el = element.find(attrs={"itemprop": "price"})
        if not price_el:
            return None

        price_value = price_el.get("content") or price_el.get_text(strip=True)
        price = self._parse_price(price_value)
        if price is None:
            return None

        currency_el = element.find(attrs={"itemprop": "priceCurrency"})
        currency = ""
        if currency_el:
            currency = currency_el.get("content") or currency_el.get_text(strip=True)

        name_el = element.find(attrs={"itemprop": "name"})
        variant_name = "デフォルト"
        if name_el:
            variant_name = name_el.get("content") or name_el.get_text(strip=True) or "デフォルト"

        return {
            "variant_name": variant_name,
            "price": price,
            "compare_at_price": None,
            "currency": currency,
            "sku": None,
            "data_source": "microdata",
            "options": {},
        }

    # ------------------------------------------------------------------
    # Open Graph extraction
    # ------------------------------------------------------------------

    def _extract_from_open_graph(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """Open Graph メタタグから価格バリアントを抽出する。"""
        variants: list[dict[str, Any]] = []

        price_amount = self._get_og_content(soup, "product:price:amount")
        if price_amount is None:
            price_amount = self._get_og_content(soup, "og:price:amount")

        price = self._parse_price(price_amount)
        if price is None:
            return variants

        currency = (
            self._get_og_content(soup, "product:price:currency")
            or self._get_og_content(soup, "og:price:currency")
            or ""
        )

        product_name = self._get_og_content(soup, "og:title") or "デフォルト"

        variants.append({
            "variant_name": product_name,
            "price": price,
            "compare_at_price": None,
            "currency": currency,
            "sku": None,
            "data_source": "open_graph",
            "options": {},
        })

        return variants

    def _get_og_content(self, soup: BeautifulSoup, property_name: str) -> Optional[str]:
        """Open Graph メタタグの content 属性を取得する。"""
        tag = soup.find("meta", attrs={"property": property_name})
        if tag and tag.get("content"):
            return tag["content"]
        return None

    # ------------------------------------------------------------------
    # Product name helpers
    # ------------------------------------------------------------------

    def _get_product_name_jsonld(self, soup: BeautifulSoup) -> Optional[str]:
        """JSON-LD から商品名を取得する。"""
        scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
        for script in scripts:
            try:
                text = script.string
                if not text:
                    continue
                data = json.loads(text)
                items = self._flatten_jsonld(data)
                for item in items:
                    if self._is_product_type(self._get_schema_type(item)):
                        name = item.get("name")
                        if name:
                            return str(name)
            except (json.JSONDecodeError, TypeError) as e:
                logger.debug("JSON-LD parse failed for product name: %s", e)
        return None

    def _get_product_name_microdata(self, soup: BeautifulSoup) -> Optional[str]:
        """Microdata から商品名を取得する。"""
        products = soup.find_all(
            attrs={"itemtype": re.compile(r"schema\.org/Product", re.I)}
        )
        for product in products:
            name_el = product.find(attrs={"itemprop": "name"})
            if name_el:
                name = name_el.get("content") or name_el.get_text(strip=True)
                if name:
                    return name
        return None

    def _get_product_name_og(self, soup: BeautifulSoup) -> Optional[str]:
        """Open Graph から商品名を取得する。"""
        return self._get_og_content(soup, "og:title")

    # ------------------------------------------------------------------
    # Priority merge
    # ------------------------------------------------------------------

    def _merge_by_priority(
        self, variants: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """同一バリアント名の価格を優先順位でマージする。

        同じ variant_name + price の組み合わせが複数ソースにある場合、
        優先度の高いソースのみ残す。
        """
        seen: dict[tuple, dict[str, Any]] = {}

        for variant in variants:
            key = (variant["variant_name"], variant["price"])
            existing = seen.get(key)
            if existing is None:
                seen[key] = variant
            else:
                existing_priority = SOURCE_PRIORITY.get(
                    existing["data_source"], 99
                )
                new_priority = SOURCE_PRIORITY.get(variant["data_source"], 99)
                if new_priority < existing_priority:
                    seen[key] = variant

        return list(seen.values())

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    def _get_schema_type(self, item: dict) -> str:
        """schema.org の @type を取得する。"""
        item_type = item.get("@type", "")
        if isinstance(item_type, list):
            item_type = item_type[0] if item_type else ""
        return str(item_type)

    def _is_product_type(self, type_str: str) -> bool:
        """Product 型かどうかを判定する。"""
        return "product" in type_str.lower() and "offer" not in type_str.lower()

    def _is_offer_type(self, type_str: str) -> bool:
        """Offer 型かどうかを判定する。"""
        return "offer" in type_str.lower()

    def _parse_price(self, value: Any) -> Optional[float]:
        """価格値を float に変換する。"""
        if value is None:
            return None
        try:
            cleaned = str(value).replace(",", "").replace("¥", "").replace("$", "").replace("€", "").strip()
            return float(cleaned)
        except (ValueError, TypeError):
            return None
