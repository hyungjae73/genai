"""
Structured Data Parser - JSON-LDおよびMicrodata形式の構造化データを解析するコンポーネント。

JSON-LD形式のscriptタグとMicrodata属性（itemscope/itemprop）を解析し、
schema.org Product/Offerプロパティを抽出します。
構造化データが利用可能な場合はHTML解析より優先されます。

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6
"""

import json
import logging
from typing import Any, List, Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class StructuredDataParser:
    """JSON-LDおよびMicrodataの構造化データを解析するクラス。"""

    def parse_jsonld(self, html: str) -> List[dict]:
        """
        HTML内のJSON-LDスクリプトタグを解析する。

        Args:
            html: HTML文字列

        Returns:
            JSON-LDオブジェクトのリスト
        """
        results: List[dict] = []
        try:
            soup = BeautifulSoup(html, "html.parser")
            scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
            for script in scripts:
                try:
                    text = script.string
                    if not text:
                        continue
                    data = json.loads(text)
                    if isinstance(data, list):
                        results.extend(data)
                    elif isinstance(data, dict):
                        # Handle @graph wrapper
                        if "@graph" in data:
                            graph = data["@graph"]
                            if isinstance(graph, list):
                                results.extend(graph)
                        else:
                            results.append(data)
                except json.JSONDecodeError as e:
                    logger.warning("Failed to parse JSON-LD: %s", e)
        except Exception as e:
            logger.error("Failed to parse HTML for JSON-LD: %s", e)
        return results

    def parse_microdata(self, html: str) -> List[dict]:
        """
        HTML内のMicrodata属性を解析する。

        Args:
            html: HTML文字列

        Returns:
            Microdataオブジェクトのリスト
        """
        results: List[dict] = []
        try:
            soup = BeautifulSoup(html, "html.parser")
            items = soup.find_all(attrs={"itemscope": True})
            for item in items:
                item_data = self._parse_microdata_item(item)
                if item_data:
                    results.append(item_data)
        except Exception as e:
            logger.error("Failed to parse HTML for Microdata: %s", e)
        return results

    def _parse_microdata_item(self, element) -> Optional[dict]:
        """単一のMicrodataアイテムを解析する。"""
        try:
            item_type = element.get("itemtype", "")
            data: dict[str, Any] = {"@type": item_type}

            props = element.find_all(attrs={"itemprop": True}, recursive=True)
            for prop in props:
                # Skip nested itemscope properties that belong to child items
                parent_scope = prop.find_parent(attrs={"itemscope": True})
                if parent_scope and parent_scope != element:
                    continue

                prop_name = prop.get("itemprop", "")
                if not prop_name:
                    continue

                if prop.has_attr("itemscope"):
                    value = self._parse_microdata_item(prop)
                elif prop.has_attr("content"):
                    value = prop["content"]
                elif prop.name == "meta":
                    value = prop.get("content", "")
                elif prop.name in ("a", "link"):
                    value = prop.get("href", "")
                elif prop.name == "img":
                    value = prop.get("src", "")
                elif prop.name in ("time", "data"):
                    value = prop.get("datetime", prop.get("value", prop.get_text(strip=True)))
                else:
                    value = prop.get_text(strip=True)

                data[prop_name] = value

            return data if len(data) > 1 else None
        except Exception as e:
            logger.warning("Failed to parse Microdata item: %s", e)
            return None

    def extract_product_info(self, structured_data: List[dict]) -> dict:
        """
        構造化データから商品情報を抽出する。

        schema.org Product/Offerプロパティを優先的に抽出します。

        Args:
            structured_data: JSON-LDまたはMicrodataから取得した構造化データのリスト

        Returns:
            商品情報を含む辞書
            {
                "name": str | None,
                "description": str | None,
                "sku": str | None,
                "prices": [{"amount": float, "currency": str, "availability": str}],
            }
        """
        result: dict[str, Any] = {
            "name": None,
            "description": None,
            "sku": None,
            "prices": [],
        }

        for item in structured_data:
            item_type = self._get_type(item)

            if self._is_product_type(item_type):
                result["name"] = result["name"] or item.get("name")
                result["description"] = result["description"] or item.get("description")
                result["sku"] = result["sku"] or item.get("sku")

                offers = item.get("offers")
                if offers:
                    self._extract_offers(offers, result["prices"])

            elif self._is_offer_type(item_type):
                self._extract_single_offer(item, result["prices"])

        return result

    def _get_type(self, item: dict) -> str:
        """構造化データアイテムの型を取得する。"""
        item_type = item.get("@type", "")
        if isinstance(item_type, list):
            item_type = item_type[0] if item_type else ""
        return str(item_type)

    def _is_product_type(self, item_type: str) -> bool:
        """Product型かどうかを判定する。"""
        return any(
            t in item_type.lower()
            for t in ["product", "http://schema.org/product", "https://schema.org/product"]
        )

    def _is_offer_type(self, item_type: str) -> bool:
        """Offer型かどうかを判定する。"""
        return any(
            t in item_type.lower()
            for t in ["offer", "http://schema.org/offer", "https://schema.org/offer"]
        )

    def _extract_offers(self, offers: Any, prices: list) -> None:
        """offersフィールドから価格情報を抽出する。"""
        if isinstance(offers, dict):
            offer_type = self._get_type(offers)
            if "aggregateoffer" in offer_type.lower():
                low = self._parse_price(offers.get("lowPrice"))
                high = self._parse_price(offers.get("highPrice"))
                currency = offers.get("priceCurrency", "")
                if low is not None:
                    prices.append({
                        "amount": low,
                        "currency": currency,
                        "availability": offers.get("availability", ""),
                        "price_type": "low_price",
                    })
                if high is not None:
                    prices.append({
                        "amount": high,
                        "currency": currency,
                        "availability": offers.get("availability", ""),
                        "price_type": "high_price",
                    })
            else:
                self._extract_single_offer(offers, prices)
        elif isinstance(offers, list):
            for offer in offers:
                if isinstance(offer, dict):
                    self._extract_single_offer(offer, prices)

    def _extract_single_offer(self, offer: dict, prices: list) -> None:
        """単一のOfferから価格情報を抽出する。"""
        price = self._parse_price(offer.get("price"))
        if price is not None:
            prices.append({
                "amount": price,
                "currency": offer.get("priceCurrency", ""),
                "availability": offer.get("availability", ""),
                "price_type": "base_price",
            })

    def _parse_price(self, value: Any) -> Optional[float]:
        """価格値をfloatに変換する。"""
        if value is None:
            return None
        try:
            cleaned = str(value).replace(",", "").strip()
            return float(cleaned)
        except (ValueError, TypeError):
            return None


# ------------------------------------------------------------------ #
# verification-flow-restructure 拡張
# 要件: 2.1-2.6, 3.1-3.4
# ------------------------------------------------------------------ #

import re
from dataclasses import dataclass, field
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


@dataclass
class VariantPrice:
    """単一バリアントの価格情報。"""
    variant_name: str
    price: float
    compare_at_price: Optional[float]
    currency: str
    sku: Optional[str]
    options: dict
    data_source: str  # "json_ld" | "shopify_api" | "microdata" | "open_graph"


@dataclass
class StructuredPriceData:
    """構造化データから抽出された全バリアント価格情報。"""
    product_name: Optional[str]
    variants: list  # list[VariantPrice]
    data_source: str
    raw_sources: dict = field(default_factory=dict)

    def is_empty(self) -> bool:
        return len(self.variants) == 0


# 優先順位: 低い数値 = 高い優先度
_SOURCE_PRIORITY = {
    "json_ld": 0,
    "shopify_api": 1,
    "microdata": 2,
    "open_graph": 3,
}

_SHOPIFY_PATTERNS = [
    re.compile(r"Shopify\.shop", re.IGNORECASE),
    re.compile(r"cdn\.shopify\.com", re.IGNORECASE),
]


class StructuredDataParserV2(StructuredDataParser):
    """StructuredDataParser の拡張版。Open Graph / Shopify / 統合メソッドを追加。

    要件: 2.1-2.6, 3.1-3.4
    """

    def parse_open_graph(self, html: str) -> dict:
        """Open Graph メタタグから価格情報を抽出する。

        対象プロパティ: og:price:amount, og:price:currency,
                        product:price:amount, product:price:currency

        要件: 2.3
        """
        result: dict[str, Any] = {}
        try:
            soup = BeautifulSoup(html, "html.parser")
            for prop in ("og:price:amount", "product:price:amount"):
                tag = soup.find("meta", attrs={"property": prop})
                if tag and tag.get("content"):
                    result["price"] = tag["content"]
                    break
            for prop in ("og:price:currency", "product:price:currency"):
                tag = soup.find("meta", attrs={"property": prop})
                if tag and tag.get("content"):
                    result["currency"] = tag["content"]
                    break
            # og:title as product name
            title_tag = soup.find("meta", attrs={"property": "og:title"})
            if title_tag and title_tag.get("content"):
                result["product_name"] = title_tag["content"]
        except Exception as e:
            logger.warning("Failed to parse Open Graph: %s", e)
        return result

    def _detect_shopify(self, html: str) -> bool:
        """HTML 内に Shopify マーカーが存在するか判定する。

        要件: 3.4
        """
        return any(p.search(html) for p in _SHOPIFY_PATTERNS)

    def fetch_shopify_product(self, url: str, html: str) -> Optional[dict]:
        """Shopify product.json からバリアント情報を取得する。

        Shopify サイトでない場合、または 404/403 の場合は None を返す。

        要件: 3.1, 3.2, 3.3
        """
        if not self._detect_shopify(html):
            return None

        handle = self._extract_product_handle(url)
        if not handle:
            logger.debug("Could not extract Shopify product handle from %s", url)
            return None

        parsed = urlparse(url)
        product_json_url = f"{parsed.scheme}://{parsed.netloc}/products/{handle}.json"

        try:
            req = Request(
                product_json_url,
                headers={"Accept": "application/json", "User-Agent": "VerificationService/1.0"},
            )
            with urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            logger.warning("Shopify product.json HTTP %s for %s", e.code, product_json_url)
            return None
        except Exception as e:
            logger.warning("Shopify product.json fetch failed for %s: %s", product_json_url, e)
            return None

    def _extract_product_handle(self, url: str) -> Optional[str]:
        """URL から Shopify プロダクトハンドルを抽出する。"""
        parsed = urlparse(url)
        path = parsed.path.rstrip("/")
        match = re.search(r"/products/([^/?#]+)", path)
        return match.group(1) if match else None

    def extract_all_variant_prices(self, html: str, url: str) -> StructuredPriceData:
        """全データソースから価格を抽出し、優先順位に基づいて統合する。

        優先順位: JSON-LD > Shopify API > Microdata > Open Graph

        要件: 2.1-2.6
        """
        raw_sources: dict[str, Any] = {}
        all_variants: dict[str, list] = {}  # source -> list[VariantPrice]
        product_name: Optional[str] = None

        # 1. JSON-LD
        try:
            jsonld_items = self.parse_jsonld(html)
            jsonld_variants = self._variants_from_jsonld(jsonld_items)
            if jsonld_variants:
                all_variants["json_ld"] = jsonld_variants
                raw_sources["json_ld"] = jsonld_items
                if not product_name:
                    product_name = self._product_name_from_jsonld(jsonld_items)
        except Exception as e:
            logger.warning("JSON-LD extraction failed: %s", e)

        # 2. Shopify API
        try:
            shopify_data = self.fetch_shopify_product(url, html)
            if shopify_data:
                shopify_variants = self._variants_from_shopify(shopify_data)
                if shopify_variants:
                    all_variants["shopify_api"] = shopify_variants
                    raw_sources["shopify_api"] = shopify_data
                    if not product_name:
                        product_name = shopify_data.get("product", {}).get("title")
        except Exception as e:
            logger.warning("Shopify extraction failed: %s", e)

        # 3. Microdata
        try:
            microdata_items = self.parse_microdata(html)
            microdata_variants = self._variants_from_microdata(microdata_items)
            if microdata_variants:
                all_variants["microdata"] = microdata_variants
                raw_sources["microdata"] = microdata_items
        except Exception as e:
            logger.warning("Microdata extraction failed: %s", e)

        # 4. Open Graph
        try:
            og_data = self.parse_open_graph(html)
            og_variants = self._variants_from_open_graph(og_data)
            if og_variants:
                all_variants["open_graph"] = og_variants
                raw_sources["open_graph"] = og_data
                if not product_name:
                    product_name = og_data.get("product_name")
        except Exception as e:
            logger.warning("Open Graph extraction failed: %s", e)

        return self._resolve_priority(all_variants, product_name, raw_sources)

    def _resolve_priority(
        self,
        all_variants: dict,
        product_name: Optional[str],
        raw_sources: dict,
    ) -> StructuredPriceData:
        """優先順位に基づいて最終的な StructuredPriceData を返す。

        要件: 2.5
        """
        for source in sorted(_SOURCE_PRIORITY, key=lambda s: _SOURCE_PRIORITY[s]):
            if source in all_variants and all_variants[source]:
                return StructuredPriceData(
                    product_name=product_name,
                    variants=all_variants[source],
                    data_source=source,
                    raw_sources=raw_sources,
                )
        return StructuredPriceData(
            product_name=product_name,
            variants=[],
            data_source="none",
            raw_sources=raw_sources,
        )

    # ------------------------------------------------------------------ #
    # 内部変換ヘルパー
    # ------------------------------------------------------------------ #

    def _variants_from_jsonld(self, items: list) -> list:
        """JSON-LD アイテムリストから VariantPrice リストを生成する。"""
        variants = []
        for item in items:
            item_type = self._get_type(item)
            if not self._is_product_type(item_type):
                continue
            product_name = item.get("name")
            offers = item.get("offers")
            if not offers:
                continue
            offer_list = offers if isinstance(offers, list) else [offers]
            for i, offer in enumerate(offer_list):
                if not isinstance(offer, dict):
                    continue
                price = self._parse_price(offer.get("price"))
                if price is None:
                    continue
                name = offer.get("name") or (product_name or f"variant_{i+1}")
                variants.append(VariantPrice(
                    variant_name=name,
                    price=price,
                    compare_at_price=None,
                    currency=offer.get("priceCurrency", ""),
                    sku=offer.get("sku"),
                    options={},
                    data_source="json_ld",
                ))
        return variants

    def _variants_from_shopify(self, product_data: dict) -> list:
        """Shopify product.json から VariantPrice リストを生成する。"""
        variants = []
        product = product_data.get("product", product_data)
        for v in product.get("variants", []):
            price = self._parse_price(v.get("price"))
            if price is None:
                continue
            compare = self._parse_price(v.get("compare_at_price"))
            options = {}
            for k in ("option1", "option2", "option3"):
                if v.get(k):
                    options[k] = v[k]
            variants.append(VariantPrice(
                variant_name=v.get("title", ""),
                price=price,
                compare_at_price=compare,
                currency="",  # Shopify API doesn't always include currency in variants
                sku=v.get("sku"),
                options=options,
                data_source="shopify_api",
            ))
        return variants

    def _variants_from_microdata(self, items: list) -> list:
        """Microdata アイテムリストから VariantPrice リストを生成する。"""
        variants = []
        for item in items:
            item_type = item.get("@type", "")
            if "product" not in item_type.lower():
                continue
            price_str = item.get("price") or item.get("offers", {}).get("price") if isinstance(item.get("offers"), dict) else None
            price = self._parse_price(price_str)
            if price is None:
                continue
            currency = item.get("priceCurrency") or (item.get("offers", {}).get("priceCurrency") if isinstance(item.get("offers"), dict) else "")
            variants.append(VariantPrice(
                variant_name=item.get("name", "variant"),
                price=price,
                compare_at_price=None,
                currency=currency or "",
                sku=item.get("sku"),
                options={},
                data_source="microdata",
            ))
        return variants

    def _variants_from_open_graph(self, og_data: dict) -> list:
        """Open Graph データから VariantPrice リストを生成する。"""
        price = self._parse_price(og_data.get("price"))
        if price is None:
            return []
        return [VariantPrice(
            variant_name=og_data.get("product_name", "default"),
            price=price,
            compare_at_price=None,
            currency=og_data.get("currency", ""),
            sku=None,
            options={},
            data_source="open_graph",
        )]

    def _product_name_from_jsonld(self, items: list) -> Optional[str]:
        """JSON-LD から商品名を取得する。"""
        for item in items:
            if self._is_product_type(self._get_type(item)):
                name = item.get("name")
                if name:
                    return str(name)
        return None
