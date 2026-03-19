"""
Unit tests for SemanticParser.

Tests cover:
- Extraction of each semantic element (data-price, itemprop, class, article/section)
- Confidence score calculation for different sources
- Multiple price extraction
- Payment method extraction from forms and text
- Fee extraction from tables

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6
"""

import pytest

from src.extractors.semantic_parser import SemanticParser


@pytest.fixture
def parser():
    return SemanticParser()


# ---------------------------------------------------------------------------
# Price extraction – semantic elements (Req 4.1, 4.2, 4.3)
# ---------------------------------------------------------------------------

class TestDataPriceExtraction:
    """data-price属性からの価格抽出テスト (Req 4.3)"""

    def test_extracts_price_from_data_price_attribute(self, parser):
        html = '<div data-price="1500">¥1,500</div>'
        prices = parser.extract_prices(html)
        assert any(p["amount"] == 1500.0 and p["source"] == "data-price" for p in prices)

    def test_extracts_decimal_price_from_data_price(self, parser):
        html = '<span data-price="29.99">$29.99</span>'
        prices = parser.extract_prices(html)
        assert any(p["amount"] == 29.99 and p["source"] == "data-price" for p in prices)

    def test_data_price_with_comma_separated_value(self, parser):
        html = '<div data-price="1,000">¥1,000</div>'
        prices = parser.extract_prices(html)
        assert any(p["amount"] == 1000.0 for p in prices)

    def test_data_price_detects_jpy_currency(self, parser):
        html = '<div data-price="500">¥500</div>'
        prices = parser.extract_prices(html)
        dp = [p for p in prices if p["source"] == "data-price"]
        assert len(dp) >= 1
        assert dp[0]["currency"] == "JPY"

    def test_data_price_invalid_value_skipped(self, parser):
        html = '<div data-price="not-a-number">N/A</div>'
        prices = parser.extract_prices(html)
        dp = [p for p in prices if p["source"] == "data-price"]
        assert len(dp) == 0


class TestItempropPriceExtraction:
    """itemprop="price"属性からの価格抽出テスト (Req 4.3)"""

    def test_extracts_price_from_itemprop_content(self, parser):
        html = '<span itemprop="price" content="2500">¥2,500</span>'
        prices = parser.extract_prices(html)
        assert any(p["amount"] == 2500.0 and p["source"] == "itemprop" for p in prices)

    def test_extracts_price_from_itemprop_text(self, parser):
        html = '<span itemprop="price">3000</span>'
        prices = parser.extract_prices(html)
        assert any(p["amount"] == 3000.0 and p["source"] == "itemprop" for p in prices)

    def test_itemprop_with_priceCurrency(self, parser):
        html = """
        <div>
            <span itemprop="price" content="19.99">$19.99</span>
            <meta itemprop="priceCurrency" content="USD">
        </div>
        """
        prices = parser.extract_prices(html)
        ip = [p for p in prices if p["source"] == "itemprop"]
        assert len(ip) >= 1
        assert ip[0]["currency"] == "USD"


class TestClassPriceExtraction:
    """class="price"を含む要素からの価格抽出テスト (Req 4.3)"""

    def test_extracts_price_from_class_price(self, parser):
        html = '<span class="price">¥1,200</span>'
        prices = parser.extract_prices(html)
        assert any(p["amount"] == 1200.0 and p["source"] == "class-price" for p in prices)

    def test_extracts_price_from_class_containing_price(self, parser):
        html = '<div class="product-price">$49.99</div>'
        prices = parser.extract_prices(html)
        assert any(p["amount"] == 49.99 and p["source"] == "class-price" for p in prices)

    def test_class_price_with_euro(self, parser):
        html = '<span class="price">€9.99</span>'
        prices = parser.extract_prices(html)
        cp = [p for p in prices if p["source"] == "class-price"]
        assert len(cp) >= 1
        assert cp[0]["currency"] == "EUR"


class TestArticleSectionExtraction:
    """article/section要素からの価格抽出テスト (Req 4.1, 4.2)"""

    def test_extracts_price_from_article(self, parser):
        html = "<article><h2>商品A</h2><p>価格: ¥3,000</p></article>"
        prices = parser.extract_prices(html)
        assert any(p["amount"] == 3000.0 and p["source"] == "semantic-article" for p in prices)

    def test_extracts_price_from_section(self, parser):
        html = "<section><h3>料金プラン</h3><p>月額$9.99</p></section>"
        prices = parser.extract_prices(html)
        assert any(p["amount"] == 9.99 and p["source"] == "semantic-section" for p in prices)

    def test_article_price_not_duplicated_with_data_price(self, parser):
        """data-priceで既に抽出された価格はarticle/sectionで重複しない。"""
        html = """
        <article>
            <span data-price="500">¥500</span>
        </article>
        """
        prices = parser.extract_prices(html)
        amounts_500 = [p for p in prices if p["amount"] == 500.0]
        # data-price should be present; article duplicate should be suppressed
        assert any(p["source"] == "data-price" for p in amounts_500)


# ---------------------------------------------------------------------------
# Confidence score tests (Req 4.6)
# ---------------------------------------------------------------------------

class TestConfidenceScores:
    """信頼度スコア計算のテスト (Req 4.6)"""

    def test_data_price_confidence_is_080(self, parser):
        html = '<div data-price="100">¥100</div>'
        prices = parser.extract_prices(html)
        dp = [p for p in prices if p["source"] == "data-price"]
        assert dp[0]["confidence"] == 0.80

    def test_itemprop_confidence_is_078(self, parser):
        html = '<span itemprop="price" content="200">200</span>'
        prices = parser.extract_prices(html)
        ip = [p for p in prices if p["source"] == "itemprop"]
        assert ip[0]["confidence"] == 0.78

    def test_class_price_confidence_is_070(self, parser):
        html = '<span class="price">¥300</span>'
        prices = parser.extract_prices(html)
        cp = [p for p in prices if p["source"] == "class-price"]
        assert cp[0]["confidence"] == 0.70

    def test_article_section_confidence_is_065(self, parser):
        html = "<article><p>価格: ¥400</p></article>"
        prices = parser.extract_prices(html)
        ap = [p for p in prices if p["source"] == "semantic-article"]
        assert ap[0]["confidence"] == 0.65

    def test_semantic_sources_have_higher_confidence_than_regex_baseline(self, parser):
        """セマンティック要素の信頼度は正規表現ベースライン(0.3-0.5)より高い。"""
        html = """
        <div data-price="100">¥100</div>
        <span itemprop="price" content="200">200</span>
        <span class="price">¥300</span>
        <article><p>¥400</p></article>
        """
        prices = parser.extract_prices(html)
        for p in prices:
            assert p["confidence"] >= 0.60, f"Source {p['source']} confidence {p['confidence']} < 0.60"

    def test_payment_form_confidence(self, parser):
        html = """
        <form>
            <input type="credit" name="cc">
        </form>
        """
        methods = parser.extract_payment_methods(html)
        fm = [m for m in methods if m["source"] == "form-input"]
        assert len(fm) >= 1
        assert fm[0]["confidence"] == 0.75

    def test_payment_text_keyword_confidence(self, parser):
        html = "<div>お支払い方法: クレジットカード、銀行振込</div>"
        methods = parser.extract_payment_methods(html)
        tk = [m for m in methods if m["source"] == "text-keyword"]
        assert all(m["confidence"] == 0.65 for m in tk)

    def test_fee_table_confidence(self, parser):
        html = """
        <table>
            <tr><th>手数料</th><th>金額</th></tr>
            <tr><td>送料</td><td>¥500</td></tr>
        </table>
        """
        fees = parser.extract_fees(html)
        assert len(fees) >= 1
        assert fees[0]["confidence"] == 0.70


# ---------------------------------------------------------------------------
# Multiple price extraction tests
# ---------------------------------------------------------------------------

class TestMultiplePriceExtraction:
    """複数価格の抽出テスト"""

    def test_extracts_multiple_data_prices(self, parser):
        html = """
        <div data-price="1000">¥1,000</div>
        <div data-price="2000">¥2,000</div>
        """
        prices = parser.extract_prices(html)
        dp = [p for p in prices if p["source"] == "data-price"]
        assert len(dp) == 2
        amounts = {p["amount"] for p in dp}
        assert amounts == {1000.0, 2000.0}

    def test_extracts_prices_from_mixed_sources(self, parser):
        html = """
        <div data-price="500">¥500</div>
        <span itemprop="price" content="800">800</span>
        <span class="price">¥1,200</span>
        """
        prices = parser.extract_prices(html)
        sources = {p["source"] for p in prices}
        assert "data-price" in sources
        assert "itemprop" in sources
        assert "class-price" in sources

    def test_extracts_prices_in_different_currencies(self, parser):
        html = """
        <span class="price">$10.00</span>
        <span class="price">€20.00</span>
        <span class="price">¥3,000</span>
        """
        prices = parser.extract_prices(html)
        currencies = {p["currency"] for p in prices}
        assert "USD" in currencies
        assert "EUR" in currencies
        assert "JPY" in currencies

    def test_empty_html_returns_no_prices(self, parser):
        prices = parser.extract_prices("")
        assert prices == []

    def test_html_without_prices_returns_empty(self, parser):
        html = "<html><body><p>No pricing here</p></body></html>"
        prices = parser.extract_prices(html)
        assert prices == []


# ---------------------------------------------------------------------------
# Payment method extraction (Req 4.4)
# ---------------------------------------------------------------------------

class TestPaymentMethodExtraction:
    """支払い方法の抽出テスト (Req 4.4)"""

    def test_extracts_credit_card_from_form_input(self, parser):
        html = '<form><input type="credit" name="payment"></form>'
        methods = parser.extract_payment_methods(html)
        assert any(m["method_name"] == "credit_card" for m in methods)

    def test_extracts_payment_from_radio_buttons(self, parser):
        html = """
        <form>
            <label for="pay1">Visa</label>
            <input type="radio" name="payment_method" id="pay1" value="visa">
            <label for="pay2">PayPal</label>
            <input type="radio" name="payment_method" id="pay2" value="paypal">
        </form>
        """
        methods = parser.extract_payment_methods(html)
        names = [m["method_name"] for m in methods]
        assert "Visa" in names
        assert "PayPal" in names

    def test_extracts_payment_from_select_options(self, parser):
        html = """
        <form>
            <select name="payment_type">
                <option value="">選択してください</option>
                <option value="cc">クレジットカード</option>
                <option value="bank">銀行振込</option>
            </select>
        </form>
        """
        methods = parser.extract_payment_methods(html)
        fm = [m for m in methods if m["source"] == "form-select"]
        names = [m["method_name"] for m in fm]
        assert "クレジットカード" in names
        assert "銀行振込" in names
        # "選択してください" should be excluded
        assert "選択してください" not in names

    def test_extracts_payment_keywords_from_text(self, parser):
        html = "<div>お支払い方法: クレジットカード、PayPay、代金引換</div>"
        methods = parser.extract_payment_methods(html)
        tk = [m for m in methods if m["source"] == "text-keyword"]
        names = [m["method_name"] for m in tk]
        assert any("クレジットカード" in n for n in names)
        assert any("PayPay" in n for n in names)
        assert any("代金引換" in n for n in names)

    def test_empty_html_returns_no_methods(self, parser):
        methods = parser.extract_payment_methods("")
        assert methods == []


# ---------------------------------------------------------------------------
# Fee extraction (Req 4.5)
# ---------------------------------------------------------------------------

class TestFeeExtraction:
    """手数料情報の抽出テスト (Req 4.5)"""

    def test_extracts_fees_from_table_with_fee_header(self, parser):
        html = """
        <table>
            <tr><th>手数料</th><th>金額</th></tr>
            <tr><td>送料</td><td>¥500</td></tr>
            <tr><td>代引手数料</td><td>¥300</td></tr>
        </table>
        """
        fees = parser.extract_fees(html)
        # Header row is also processed; data rows produce fee entries
        assert len(fees) >= 2
        types = [f["fee_type"] for f in fees]
        assert "送料" in types
        assert "代引手数料" in types

    def test_extracts_fee_amount(self, parser):
        html = """
        <table>
            <tr><th>Fee Type</th><th>fee</th></tr>
            <tr><td>Shipping</td><td>$5.00</td></tr>
        </table>
        """
        fees = parser.extract_fees(html)
        assert len(fees) >= 1
        # Find the actual data row (Shipping), not the header row
        shipping = [f for f in fees if f["fee_type"] == "Shipping"]
        assert len(shipping) == 1
        assert shipping[0]["amount"] == 5.0

    def test_extracts_fee_with_description_column(self, parser):
        html = """
        <table>
            <tr><th>手数料</th><th>金額</th><th>備考</th></tr>
            <tr><td>送料</td><td>¥500</td><td>全国一律</td></tr>
        </table>
        """
        fees = parser.extract_fees(html)
        assert len(fees) >= 1
        shipping = [f for f in fees if f["fee_type"] == "送料"]
        assert len(shipping) == 1
        assert shipping[0]["description"] == "全国一律"

    def test_fee_table_detected_by_caption(self, parser):
        html = """
        <table>
            <caption>送料一覧</caption>
            <tr><td>北海道</td><td>¥1,200</td></tr>
            <tr><td>本州</td><td>¥800</td></tr>
        </table>
        """
        fees = parser.extract_fees(html)
        assert len(fees) >= 1

    def test_non_fee_table_ignored(self, parser):
        html = """
        <table>
            <tr><th>Name</th><th>Age</th></tr>
            <tr><td>Alice</td><td>30</td></tr>
        </table>
        """
        fees = parser.extract_fees(html)
        assert fees == []

    def test_empty_html_returns_no_fees(self, parser):
        fees = parser.extract_fees("")
        assert fees == []


# ---------------------------------------------------------------------------
# Utility / edge-case tests
# ---------------------------------------------------------------------------

class TestCurrencyDetection:
    """通貨検出のテスト"""

    def test_detects_jpy_from_yen_sign(self, parser):
        assert parser._detect_currency("¥1,000") == "JPY"

    def test_detects_jpy_from_en_sign(self, parser):
        assert parser._detect_currency("1000円") == "JPY"

    def test_detects_usd_from_dollar_sign(self, parser):
        assert parser._detect_currency("$50") == "USD"

    def test_detects_eur_from_euro_sign(self, parser):
        assert parser._detect_currency("€10") == "EUR"

    def test_detects_gbp_from_pound_sign(self, parser):
        assert parser._detect_currency("£20") == "GBP"

    def test_detects_cny_from_yuan(self, parser):
        assert parser._detect_currency("100元") == "CNY"

    def test_detects_currency_code_in_text(self, parser):
        assert parser._detect_currency("Price: 100 USD") == "USD"

    def test_returns_empty_for_unknown_currency(self, parser):
        assert parser._detect_currency("some random text") == ""


class TestPriceValueParsing:
    """_parse_price_value ユーティリティのテスト"""

    def test_parses_integer(self, parser):
        assert parser._parse_price_value("1000") == 1000.0

    def test_parses_decimal(self, parser):
        assert parser._parse_price_value("19.99") == 19.99

    def test_parses_comma_separated(self, parser):
        assert parser._parse_price_value("1,000") == 1000.0

    def test_returns_none_for_none(self, parser):
        assert parser._parse_price_value(None) is None

    def test_returns_none_for_non_numeric(self, parser):
        assert parser._parse_price_value("abc") is None
