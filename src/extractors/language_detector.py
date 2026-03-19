"""
Language Detector - 多言語対応の言語検出と多言語パターンマッチングコンポーネント。

html lang属性およびmetaタグから言語を検出し、
日本語・英語・中国語の価格パターン、通貨記号/コード、支払い方法名を認識します。

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5
"""

import logging
import re
from typing import Dict, List, Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class LanguageDetector:
    """言語検出と多言語パターンマッチングを提供するクラス。"""

    def detect_language(self, html: str) -> Optional[str]:
        """
        HTMLから言語を検出する。

        html lang属性を優先し、metaタグにフォールバックします。

        Args:
            html: HTML文字列

        Returns:
            言語コード (例: "ja", "en", "zh") またはNone
        """
        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception as e:
            logger.error("Failed to parse HTML for language detection: %s", e)
            return None

        lang = self._detect_from_html_lang(soup)
        if lang:
            return lang

        lang = self._detect_from_meta(soup)
        if lang:
            return lang

        return None

    def _detect_from_html_lang(self, soup: BeautifulSoup) -> Optional[str]:
        """html lang属性から言語を検出する。"""
        try:
            html_tag = soup.find("html")
            if html_tag and html_tag.get("lang"):
                return self._normalize_lang(html_tag["lang"])
        except Exception as e:
            logger.warning("Failed to detect language from html tag: %s", e)
        return None

    def _detect_from_meta(self, soup: BeautifulSoup) -> Optional[str]:
        """metaタグから言語を検出する。"""
        try:
            # http-equiv="content-language"
            meta = soup.find("meta", attrs={"http-equiv": "content-language"})
            if meta and meta.get("content"):
                return self._normalize_lang(meta["content"])

            # og:locale
            meta = soup.find("meta", attrs={"property": "og:locale"})
            if meta and meta.get("content"):
                return self._normalize_lang(meta["content"])
        except Exception as e:
            logger.warning("Failed to detect language from meta tags: %s", e)
        return None

    def _normalize_lang(self, lang: str) -> str:
        """言語コードを正規化する (例: "ja-JP" -> "ja")。"""
        lang = lang.strip().lower()
        # Handle locale formats: ja_JP, ja-JP, zh_CN, zh-CN
        lang = lang.replace("_", "-")
        return lang.split("-")[0]


# ============================================================
# Multi-language pattern definitions
# ============================================================

# --- Price patterns per language ---

PRICE_PATTERNS: Dict[str, List[re.Pattern]] = {
    "ja": [
        re.compile(r"[¥￥]\s*([\d,]+(?:\.\d+)?)", re.UNICODE),
        re.compile(r"([\d,]+(?:\.\d+)?)\s*円", re.UNICODE),
        re.compile(r"([\d,]+(?:\.\d+)?)\s*JPY", re.UNICODE | re.IGNORECASE),
    ],
    "en": [
        re.compile(r"\$\s*([\d,]+(?:\.\d{1,2})?)", re.UNICODE),
        re.compile(r"USD\s*([\d,]+(?:\.\d{1,2})?)", re.UNICODE | re.IGNORECASE),
        re.compile(r"£\s*([\d,]+(?:\.\d{1,2})?)", re.UNICODE),
        re.compile(r"GBP\s*([\d,]+(?:\.\d{1,2})?)", re.UNICODE | re.IGNORECASE),
        re.compile(r"€\s*([\d,]+(?:\.\d{1,2})?)", re.UNICODE),
        re.compile(r"EUR\s*([\d,]+(?:\.\d{1,2})?)", re.UNICODE | re.IGNORECASE),
    ],
    "zh": [
        re.compile(r"[¥￥]\s*([\d,]+(?:\.\d+)?)", re.UNICODE),
        re.compile(r"([\d,]+(?:\.\d+)?)\s*元", re.UNICODE),
        re.compile(r"CNY\s*([\d,]+(?:\.\d+)?)", re.UNICODE | re.IGNORECASE),
        re.compile(r"RMB\s*([\d,]+(?:\.\d+)?)", re.UNICODE | re.IGNORECASE),
    ],
}

# --- Currency symbols/codes per language ---

CURRENCY_SYMBOLS: Dict[str, Dict[str, str]] = {
    "ja": {
        "¥": "JPY",
        "￥": "JPY",
        "円": "JPY",
        "JPY": "JPY",
    },
    "en": {
        "$": "USD",
        "USD": "USD",
        "£": "GBP",
        "GBP": "GBP",
        "€": "EUR",
        "EUR": "EUR",
    },
    "zh": {
        "¥": "CNY",
        "￥": "CNY",
        "元": "CNY",
        "CNY": "CNY",
        "RMB": "CNY",
    },
}

# --- Payment method names per language ---

PAYMENT_METHOD_NAMES: Dict[str, Dict[str, str]] = {
    "ja": {
        "クレジットカード": "credit_card",
        "デビットカード": "debit_card",
        "銀行振込": "bank_transfer",
        "コンビニ決済": "convenience_store",
        "代金引換": "cash_on_delivery",
        "電子マネー": "e_money",
        "PayPay": "paypay",
        "楽天ペイ": "rakuten_pay",
        "d払い": "d_payment",
        "au PAY": "au_pay",
    },
    "en": {
        "credit card": "credit_card",
        "debit card": "debit_card",
        "bank transfer": "bank_transfer",
        "wire transfer": "wire_transfer",
        "paypal": "paypal",
        "apple pay": "apple_pay",
        "google pay": "google_pay",
        "cash on delivery": "cash_on_delivery",
    },
    "zh": {
        "信用卡": "credit_card",
        "借记卡": "debit_card",
        "银行转账": "bank_transfer",
        "支付宝": "alipay",
        "微信支付": "wechat_pay",
        "货到付款": "cash_on_delivery",
        "京东支付": "jd_pay",
    },
}


def get_price_patterns(language: Optional[str] = None) -> List[re.Pattern]:
    """
    指定言語の価格パターンを取得する。言語未指定時は全言語のパターンを返す。

    Args:
        language: 言語コード ("ja", "en", "zh") またはNone

    Returns:
        正規表現パターンのリスト
    """
    if language and language in PRICE_PATTERNS:
        return PRICE_PATTERNS[language]
    # Return all patterns
    all_patterns = []
    for patterns in PRICE_PATTERNS.values():
        all_patterns.extend(patterns)
    return all_patterns


def get_currency_symbols(language: Optional[str] = None) -> Dict[str, str]:
    """
    指定言語の通貨記号/コードマッピングを取得する。

    Args:
        language: 言語コード またはNone

    Returns:
        通貨記号/コード -> 通貨コードの辞書
    """
    if language and language in CURRENCY_SYMBOLS:
        return CURRENCY_SYMBOLS[language]
    merged: Dict[str, str] = {}
    for symbols in CURRENCY_SYMBOLS.values():
        merged.update(symbols)
    return merged


def get_payment_method_names(language: Optional[str] = None) -> Dict[str, str]:
    """
    指定言語の支払い方法名マッピングを取得する。

    Args:
        language: 言語コード またはNone

    Returns:
        支払い方法名 -> 正規化IDの辞書
    """
    if language and language in PAYMENT_METHOD_NAMES:
        return PAYMENT_METHOD_NAMES[language]
    merged: Dict[str, str] = {}
    for names in PAYMENT_METHOD_NAMES.values():
        merged.update(names)
    return merged
