"""
Semantic Parser - セマンティックHTML要素から支払い情報を抽出するコンポーネント。

article要素、section要素、data-price属性、itemprop="price"、class="price"、
form要素、table要素などのセマンティックHTML要素を解析し、
商品情報、価格情報、支払い方法、手数料を抽出します。

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6
"""

import logging
import re
from typing import Any, List, Optional

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

# Multi-language price patterns
PRICE_PATTERNS = [
    # Japanese: ¥1,000 / 1,000円 / 1000円
    re.compile(r"[¥￥]\s*([\d,]+(?:\.\d+)?)", re.UNICODE),
    re.compile(r"([\d,]+(?:\.\d+)?)\s*円", re.UNICODE),
    # English: $10.00 / USD 10.00
    re.compile(r"\$\s*([\d,]+(?:\.\d+)?)", re.UNICODE),
    re.compile(r"USD\s*([\d,]+(?:\.\d+)?)", re.UNICODE | re.IGNORECASE),
    # Euro: €9.99 / EUR 9.99
    re.compile(r"€\s*([\d,]+(?:\.\d+)?)", re.UNICODE),
    re.compile(r"EUR\s*([\d,]+(?:\.\d+)?)", re.UNICODE | re.IGNORECASE),
    # Chinese: ¥100 / 100元 / CNY 100
    re.compile(r"([\d,]+(?:\.\d+)?)\s*元", re.UNICODE),
    re.compile(r"CNY\s*([\d,]+(?:\.\d+)?)", re.UNICODE | re.IGNORECASE),
    # Generic number with currency code
    re.compile(r"([\d,]+(?:\.\d+)?)\s*(?:JPY|USD|EUR|GBP|CNY)", re.UNICODE | re.IGNORECASE),
]

# Currency detection from text context
CURRENCY_INDICATORS = {
    "¥": "JPY",
    "￥": "JPY",
    "円": "JPY",
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "元": "CNY",
}


class SemanticParser:
    """セマンティックHTML要素から支払い情報を抽出するクラス。"""

    def extract_prices(self, html: str) -> List[dict]:
        """
        HTMLから価格情報を抽出する。

        data-price属性、itemprop="price"、class="price"属性、
        article/section要素内の価格パターンを検索します。

        Args:
            html: HTML文字列

        Returns:
            価格情報のリスト
            [{"amount": float, "currency": str, "source": str, "context": str, "confidence": float}]
        """
        prices: List[dict] = []
        try:
            soup = BeautifulSoup(html, "html.parser")
            self._extract_from_data_price(soup, prices)
            self._extract_from_itemprop_price(soup, prices)
            self._extract_from_class_price(soup, prices)
            self._extract_from_article_sections(soup, prices)
        except Exception as e:
            logger.error("Failed to extract prices from HTML: %s", e)
        return prices

    def extract_payment_methods(self, html: str) -> List[dict]:
        """
        HTMLから支払い方法を抽出する。

        form要素とinput type属性から支払い方法を検出します。

        Args:
            html: HTML文字列

        Returns:
            支払い方法のリスト
            [{"method_name": str, "source": str, "confidence": float}]
        """
        methods: List[dict] = []
        try:
            soup = BeautifulSoup(html, "html.parser")
            self._extract_payment_from_forms(soup, methods)
            self._extract_payment_from_text(soup, methods)
        except Exception as e:
            logger.error("Failed to extract payment methods: %s", e)
        return methods

    def extract_fees(self, html: str) -> List[dict]:
        """
        HTMLから手数料情報を抽出する。

        table要素から手数料関連の情報を検索します。

        Args:
            html: HTML文字列

        Returns:
            手数料情報のリスト
            [{"fee_type": str, "amount": float | None, "currency": str, "description": str, "confidence": float}]
        """
        fees: List[dict] = []
        try:
            soup = BeautifulSoup(html, "html.parser")
            self._extract_fees_from_tables(soup, fees)
        except Exception as e:
            logger.error("Failed to extract fees: %s", e)
        return fees

    # --- Price extraction helpers ---

    def _extract_from_data_price(self, soup: BeautifulSoup, prices: List[dict]) -> None:
        """data-price属性から価格を抽出する。"""
        elements = soup.find_all(attrs={"data-price": True})
        for el in elements:
            value = self._parse_price_value(el["data-price"])
            if value is not None:
                context = self._get_context_text(el)
                prices.append({
                    "amount": value,
                    "currency": self._detect_currency(context),
                    "source": "data-price",
                    "context": context,
                    "confidence": 0.80,
                })

    def _extract_from_itemprop_price(self, soup: BeautifulSoup, prices: List[dict]) -> None:
        """itemprop="price"属性から価格を抽出する。"""
        elements = soup.find_all(attrs={"itemprop": "price"})
        for el in elements:
            raw = el.get("content") or el.get_text(strip=True)
            value = self._parse_price_value(raw)
            if value is not None:
                context = self._get_context_text(el)
                # Check for currency in sibling itemprop
                currency = self._detect_currency(context)
                currency_el = soup.find(attrs={"itemprop": "priceCurrency"})
                if currency_el:
                    currency = currency_el.get("content", currency_el.get_text(strip=True)) or currency
                prices.append({
                    "amount": value,
                    "currency": currency,
                    "source": "itemprop",
                    "context": context,
                    "confidence": 0.78,
                })

    def _extract_from_class_price(self, soup: BeautifulSoup, prices: List[dict]) -> None:
        """class="price"を含む要素から価格を抽出する。"""
        elements = soup.find_all(class_=re.compile(r"\bprice\b", re.IGNORECASE))
        for el in elements:
            text = el.get_text(strip=True)
            extracted = self._extract_price_from_text(text)
            if extracted:
                amount, currency = extracted
                prices.append({
                    "amount": amount,
                    "currency": currency,
                    "source": "class-price",
                    "context": text[:200],
                    "confidence": 0.70,
                })

    def _extract_from_article_sections(self, soup: BeautifulSoup, prices: List[dict]) -> None:
        """article/section要素内から価格パターンを抽出する。"""
        for tag_name in ("article", "section"):
            elements = soup.find_all(tag_name)
            for el in elements:
                text = el.get_text(strip=True)
                extracted = self._extract_price_from_text(text)
                if extracted:
                    amount, currency = extracted
                    # Avoid duplicates from more specific selectors
                    if not any(p["amount"] == amount for p in prices):
                        prices.append({
                            "amount": amount,
                            "currency": currency,
                            "source": f"semantic-{tag_name}",
                            "context": text[:200],
                            "confidence": 0.65,
                        })

    # --- Payment method extraction helpers ---

    def _extract_payment_from_forms(self, soup: BeautifulSoup, methods: List[dict]) -> None:
        """form要素とinput typeから支払い方法を抽出する。"""
        forms = soup.find_all("form")
        for form in forms:
            # Check for credit card inputs
            cc_inputs = form.find_all("input", attrs={"type": re.compile(r"(credit|card|payment)", re.IGNORECASE)})
            if cc_inputs:
                methods.append({
                    "method_name": "credit_card",
                    "source": "form-input",
                    "confidence": 0.75,
                })

            # Check for radio/select payment options
            radios = form.find_all("input", attrs={"type": "radio", "name": re.compile(r"payment", re.IGNORECASE)})
            for radio in radios:
                label = self._find_label_for(soup, radio)
                if label:
                    methods.append({
                        "method_name": label,
                        "source": "form-radio",
                        "confidence": 0.75,
                    })

            selects = form.find_all("select", attrs={"name": re.compile(r"payment", re.IGNORECASE)})
            for select in selects:
                options = select.find_all("option")
                for option in options:
                    text = option.get_text(strip=True)
                    if text and text.lower() not in ("", "select", "選択してください"):
                        methods.append({
                            "method_name": text,
                            "source": "form-select",
                            "confidence": 0.70,
                        })

    def _extract_payment_from_text(self, soup: BeautifulSoup, methods: List[dict]) -> None:
        """テキストコンテンツから支払い方法キーワードを検出する。"""
        payment_keywords = {
            # Japanese
            "クレジットカード": "credit_card",
            "銀行振込": "bank_transfer",
            "コンビニ決済": "convenience_store",
            "代金引換": "cash_on_delivery",
            "電子マネー": "e_money",
            "PayPay": "paypay",
            # English
            "credit card": "credit_card",
            "debit card": "debit_card",
            "bank transfer": "bank_transfer",
            "paypal": "paypal",
            "apple pay": "apple_pay",
            "google pay": "google_pay",
            # Chinese
            "信用卡": "credit_card",
            "银行转账": "bank_transfer",
            "支付宝": "alipay",
            "微信支付": "wechat_pay",
        }

        text = soup.get_text()
        seen = set()
        for keyword, method_id in payment_keywords.items():
            if keyword.lower() in text.lower() and method_id not in seen:
                seen.add(method_id)
                methods.append({
                    "method_name": keyword,
                    "source": "text-keyword",
                    "confidence": 0.65,
                })

    # --- Fee extraction helpers ---

    def _extract_fees_from_tables(self, soup: BeautifulSoup, fees: List[dict]) -> None:
        """table要素から手数料情報を抽出する。"""
        fee_keywords = [
            "手数料", "送料", "配送料", "shipping", "fee", "charge",
            "delivery", "handling", "税", "tax", "运费", "手续费",
        ]

        tables = soup.find_all("table")
        for table in tables:
            headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
            # Check if table is fee-related
            is_fee_table = any(
                any(kw in header for kw in fee_keywords)
                for header in headers
            )
            if not is_fee_table:
                # Also check caption or surrounding text
                caption = table.find("caption")
                if caption:
                    caption_text = caption.get_text(strip=True).lower()
                    is_fee_table = any(kw in caption_text for kw in fee_keywords)

            if not is_fee_table:
                continue

            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) >= 2:
                    fee_type = cells[0].get_text(strip=True)
                    fee_text = cells[1].get_text(strip=True)
                    extracted = self._extract_price_from_text(fee_text)
                    amount = extracted[0] if extracted else None
                    currency = extracted[1] if extracted else ""
                    description = cells[2].get_text(strip=True) if len(cells) > 2 else ""

                    fees.append({
                        "fee_type": fee_type,
                        "amount": amount,
                        "currency": currency,
                        "description": description,
                        "confidence": 0.70,
                    })

    # --- Utility methods ---

    def _parse_price_value(self, raw: Any) -> Optional[float]:
        """生の値をfloatに変換する。"""
        if raw is None:
            return None
        try:
            cleaned = str(raw).replace(",", "").strip()
            return float(cleaned)
        except (ValueError, TypeError):
            return None

    def _extract_price_from_text(self, text: str) -> Optional[tuple]:
        """テキストから価格パターンを抽出する。(amount, currency)のタプルを返す。"""
        for pattern in PRICE_PATTERNS:
            match = pattern.search(text)
            if match:
                try:
                    amount = float(match.group(1).replace(",", ""))
                    currency = self._detect_currency(text)
                    return (amount, currency)
                except (ValueError, IndexError):
                    continue
        return None

    def _detect_currency(self, text: str) -> str:
        """テキストから通貨を検出する。"""
        for indicator, currency in CURRENCY_INDICATORS.items():
            if indicator in text:
                return currency

        # Check for currency codes
        for code in ("JPY", "USD", "EUR", "GBP", "CNY"):
            if code in text.upper():
                return code

        return ""

    def _get_context_text(self, element: Tag) -> str:
        """要素の周辺テキストコンテキストを取得する。"""
        parent = element.parent
        if parent:
            return parent.get_text(strip=True)[:200]
        return element.get_text(strip=True)[:200]

    def _find_label_for(self, soup: BeautifulSoup, input_el: Tag) -> Optional[str]:
        """input要素に対応するlabelテキストを取得する。"""
        input_id = input_el.get("id")
        if input_id:
            label = soup.find("label", attrs={"for": input_id})
            if label:
                return label.get_text(strip=True)
        # Check for wrapping label
        parent = input_el.parent
        if parent and parent.name == "label":
            return parent.get_text(strip=True)
        # Use value attribute as fallback
        value = input_el.get("value")
        if value:
            return value
        return None
