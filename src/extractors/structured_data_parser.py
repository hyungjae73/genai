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
