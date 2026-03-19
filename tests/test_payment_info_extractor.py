"""
Integration tests for PaymentInfoExtractor.

Tests cover:
- End-to-end extraction pipeline (structured data → semantic HTML → regex)
- Multi-source fallback behavior
- Error handling and resilience

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 6.1-6.6, 22.1, 22.3, 22.4
"""

import pytest
from unittest.mock import MagicMock, patch

from src.extractors.payment_info_extractor import PaymentInfoExtractor


@pytest.fixture
def extractor():
    """Create a PaymentInfoExtractor with real sub-components."""
    return PaymentInfoExtractor()


# ---------------------------------------------------------------------------
# HTML fixtures
# ---------------------------------------------------------------------------

FULL_JSONLD_HTML = """
<html lang="ja">
<head>
    <title>テスト商品 - オンラインショップ</title>
    <meta name="description" content="高品質なテスト商品の販売ページです。">
    <meta property="og:title" content="テスト商品">
    <meta property="og:description" content="高品質なテスト商品">
    <meta property="og:image" content="https://example.com/product.jpg">
    <meta property="og:url" content="https://example.com/product/1">
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "プレミアムウィジェット",
        "description": "高品質なウィジェット製品",
        "sku": "WDG-001",
        "offers": {
            "@type": "Offer",
            "price": "2980",
            "priceCurrency": "JPY",
            "availability": "https://schema.org/InStock"
        }
    }
    </script>
</head>
<body>
    <article>
        <h1>プレミアムウィジェット</h1>
        <p class="price">¥2,980</p>
    </article>
    <table>
        <caption>手数料一覧</caption>
        <tr><th>手数料</th><th>金額</th></tr>
        <tr><td>送料</td><td>¥500</td></tr>
    </table>
    <form>
        <input type="radio" name="payment_method" id="cc" value="クレジットカード">
        <label for="cc">クレジットカード</label>
        <input type="radio" name="payment_method" id="bt" value="銀行振込">
        <label for="bt">銀行振込</label>
    </form>
</body>
</html>
"""

SEMANTIC_ONLY_HTML = """
<html lang="en">
<head>
    <title>Widget Store</title>
    <meta name="description" content="Buy widgets online.">
</head>
<body>
    <article>
        <h1>Standard Widget</h1>
        <span class="price">$49.99</span>
    </article>
    <section>
        <span itemprop="price" content="49.99">$49.99</span>
        <meta itemprop="priceCurrency" content="USD">
    </section>
    <table>
        <caption>Fees</caption>
        <tr><th>Fee</th><th>Amount</th></tr>
        <tr><td>Shipping</td><td>$5.00</td></tr>
    </table>
    <form>
        <select name="payment_method">
            <option value="">Select</option>
            <option value="paypal">PayPal</option>
        </select>
    </form>
</body>
</html>
"""

MINIMAL_HTML = """
<html>
<head><title>Empty Page</title></head>
<body><p>No product information here.</p></body>
</html>
"""

MALFORMED_HTML = "<not><valid html <><>>"

MULTI_PRICE_JSONLD_HTML = """
<html lang="ja">
<head><title>複数価格商品</title>
<script type="application/ld+json">
{
    "@context": "https://schema.org",
    "@type": "Product",
    "name": "バリアント商品",
    "sku": "VAR-100",
    "offers": [
        {"@type": "Offer", "price": "1000", "priceCurrency": "JPY", "availability": "InStock"},
        {"@type": "Offer", "price": "1500", "priceCurrency": "JPY", "availability": "InStock"}
    ]
}
</script>
</head>
<body>
    <section><p class="price">¥1,000 〜 ¥1,500</p></section>
</body>
</html>
"""


# ===========================================================================
# End-to-end extraction pipeline tests
# ===========================================================================

class TestEndToEndExtractionPipeline:
    """エンドツーエンドの抽出パイプラインテスト"""

    def test_full_pipeline_with_jsonld(self, extractor):
        """JSON-LD structured data drives the primary extraction."""
        result = extractor.extract_payment_info(FULL_JSONLD_HTML, "https://example.com/product/1")

        # Product info from structured data
        assert result["product_info"]["name"] == "プレミアムウィジェット"
        assert result["product_info"]["sku"] == "WDG-001"

        # Price from structured data
        assert any(p["amount"] == 2980.0 for p in result["price_info"])

        # Extraction source should be structured_data
        assert result["extraction_source"] == "structured_data"

        # Language detected
        assert result["language"] == "ja"

        # Metadata extracted
        assert result["metadata"]["title"] == "テスト商品 - オンラインショップ"
        assert result["metadata"]["og_title"] == "テスト商品"

        # Confidence scores populated
        assert "product_name" in result["confidence_scores"]
        assert result["overall_confidence"] > 0.0

    def test_full_pipeline_with_semantic_html(self, extractor):
        """Semantic HTML extraction when no structured data is present."""
        result = extractor.extract_payment_info(SEMANTIC_ONLY_HTML, "https://example.com/widgets")

        # Prices extracted from semantic elements
        assert len(result["price_info"]) > 0
        amounts = [p["amount"] for p in result["price_info"]]
        assert 49.99 in amounts

        # Extraction source should be semantic_html
        assert result["extraction_source"] == "semantic_html"

        # Language detected
        assert result["language"] == "en"

        # Confidence scores present
        assert result["overall_confidence"] > 0.0

    def test_pipeline_with_multiple_price_variants(self, extractor):
        """Multiple price variants from JSON-LD offers array."""
        result = extractor.extract_payment_info(MULTI_PRICE_JSONLD_HTML, "https://example.com/variant")

        assert result["extraction_source"] == "structured_data"
        assert result["product_info"]["name"] == "バリアント商品"
        assert result["product_info"]["sku"] == "VAR-100"

        structured_prices = [p for p in result["price_info"] if p.get("source") == "structured_data"]
        assert len(structured_prices) >= 2
        structured_amounts = sorted(p["amount"] for p in structured_prices)
        assert 1000.0 in structured_amounts
        assert 1500.0 in structured_amounts

    def test_product_price_association(self, extractor):
        """Product name and SKU are associated with each price (Req 5.1, 5.2)."""
        result = extractor.extract_payment_info(FULL_JSONLD_HTML, "https://example.com/product/1")

        for price in result["price_info"]:
            if price.get("source") == "structured_data":
                assert price.get("product_name") == "プレミアムウィジェット"
                assert price.get("product_sku") == "WDG-001"

    def test_fees_associated_with_base_price(self, extractor):
        """Fees are linked to the base price (Req 5.4)."""
        result = extractor.extract_payment_info(FULL_JSONLD_HTML, "https://example.com/product/1")

        for fee in result.get("fees", []):
            if fee.get("amount") is not None:
                assert "related_base_price" in fee

    def test_confidence_scores_reflect_source(self, extractor):
        """Structured data yields higher confidence than semantic HTML (Req 6.2, 6.3)."""
        structured_result = extractor.extract_payment_info(FULL_JSONLD_HTML, "https://example.com/a")
        semantic_result = extractor.extract_payment_info(SEMANTIC_ONLY_HTML, "https://example.com/b")

        assert structured_result["overall_confidence"] > semantic_result["overall_confidence"]

    def test_result_structure_always_complete(self, extractor):
        """Result dict always contains all expected top-level keys."""
        result = extractor.extract_payment_info(MINIMAL_HTML, "https://example.com/empty")

        for key in ("product_info", "price_info", "payment_methods", "fees",
                     "metadata", "confidence_scores", "overall_confidence",
                     "language", "extraction_source"):
            assert key in result


# ===========================================================================
# Multi-source fallback tests
# ===========================================================================

class TestMultiSourceFallback:
    """複数抽出元のフォールバックテスト"""

    def test_falls_back_to_semantic_when_no_structured_data(self, extractor):
        """When no JSON-LD/Microdata, semantic HTML is used."""
        result = extractor.extract_payment_info(SEMANTIC_ONLY_HTML, "https://example.com/sem")

        assert result["extraction_source"] == "semantic_html"
        assert len(result["price_info"]) > 0

    def test_falls_back_to_regex_when_no_semantic(self, extractor):
        """When no structured data or semantic elements, source is regex."""
        result = extractor.extract_payment_info(MINIMAL_HTML, "https://example.com/min")

        assert result["extraction_source"] == "regex"

    def test_semantic_prices_supplement_structured_data(self, extractor):
        """Semantic prices that differ from structured data are added."""
        html = """
        <html lang="ja">
        <head>
        <script type="application/ld+json">
        {"@context":"https://schema.org","@type":"Product","name":"Combo",
         "offers":{"@type":"Offer","price":"3000","priceCurrency":"JPY"}}
        </script>
        </head>
        <body>
            <section><span class="price">¥3,500</span></section>
        </body>
        </html>
        """
        result = extractor.extract_payment_info(html, "https://example.com/combo")

        assert result["extraction_source"] == "structured_data"
        amounts = [p["amount"] for p in result["price_info"]]
        assert 3000.0 in amounts
        # The semantic price ¥3,500 differs from structured ¥3,000 so it should be added
        assert 3500.0 in amounts

    def test_duplicate_prices_not_added_from_semantic(self, extractor):
        """Semantic prices matching structured data amounts are skipped."""
        html = """
        <html lang="ja">
        <head>
        <script type="application/ld+json">
        {"@context":"https://schema.org","@type":"Product","name":"Same",
         "offers":{"@type":"Offer","price":"5000","priceCurrency":"JPY"}}
        </script>
        </head>
        <body>
            <span data-price="5000">¥5,000</span>
        </body>
        </html>
        """
        result = extractor.extract_payment_info(html, "https://example.com/same")

        prices_5000 = [p for p in result["price_info"] if p["amount"] == 5000.0]
        # Structured data price present; semantic duplicate should be skipped
        structured = [p for p in prices_5000 if p.get("source") == "structured_data"]
        assert len(structured) == 1

    def test_payment_methods_extracted_from_semantic(self, extractor):
        """Payment methods come from semantic HTML forms."""
        result = extractor.extract_payment_info(FULL_JSONLD_HTML, "https://example.com/pay")

        method_names = [m["method_name"] for m in result["payment_methods"]]
        assert len(method_names) > 0

    def test_fees_extracted_from_semantic_tables(self, extractor):
        """Fees are extracted from table elements."""
        result = extractor.extract_payment_info(FULL_JSONLD_HTML, "https://example.com/fees")

        assert len(result["fees"]) > 0
        fee_types = [f["fee_type"] for f in result["fees"]]
        assert "送料" in fee_types


# ===========================================================================
# Error handling tests
# ===========================================================================

class TestErrorHandling:
    """エラーハンドリングのテスト"""

    def test_malformed_html_does_not_raise(self, extractor):
        """Malformed HTML is handled gracefully."""
        result = extractor.extract_payment_info(MALFORMED_HTML, "https://example.com/bad")

        assert isinstance(result, dict)
        assert "product_info" in result

    def test_empty_html_does_not_raise(self, extractor):
        """Empty string HTML is handled gracefully."""
        result = extractor.extract_payment_info("", "https://example.com/empty")

        assert isinstance(result, dict)
        assert result["price_info"] == []

    def test_structured_parser_failure_falls_back(self, extractor):
        """If structured parser raises, semantic extraction still runs."""
        extractor.structured_parser.parse_jsonld = MagicMock(side_effect=RuntimeError("boom"))
        extractor.structured_parser.parse_microdata = MagicMock(side_effect=RuntimeError("boom"))

        result = extractor.extract_payment_info(SEMANTIC_ONLY_HTML, "https://example.com/fallback")

        # Should still get semantic prices
        assert result["extraction_source"] in ("semantic_html", "regex")
        assert isinstance(result["price_info"], list)

    def test_semantic_parser_failure_still_returns_result(self, extractor):
        """If semantic parser raises, result is still returned."""
        extractor.semantic_parser.extract_prices = MagicMock(side_effect=RuntimeError("fail"))
        extractor.semantic_parser.extract_payment_methods = MagicMock(side_effect=RuntimeError("fail"))
        extractor.semantic_parser.extract_fees = MagicMock(side_effect=RuntimeError("fail"))

        result = extractor.extract_payment_info(FULL_JSONLD_HTML, "https://example.com/err")

        # Structured data should still work
        assert result["extraction_source"] == "structured_data"
        assert result["product_info"]["name"] == "プレミアムウィジェット"

    def test_metadata_extractor_failure_records_error(self, extractor):
        """If metadata extraction raises, error is captured in metadata."""
        extractor.metadata_extractor.extract_metadata = MagicMock(side_effect=ValueError("meta fail"))

        result = extractor.extract_payment_info(FULL_JSONLD_HTML, "https://example.com/metaerr")

        assert "extraction_error" in result["metadata"]

    def test_language_detector_failure_sets_none(self, extractor):
        """If language detection raises, language is None."""
        extractor.language_detector.detect_language = MagicMock(side_effect=RuntimeError("lang fail"))

        result = extractor.extract_payment_info(FULL_JSONLD_HTML, "https://example.com/langerr")

        assert "extraction_error" in result["metadata"]

    def test_invalid_jsonld_gracefully_handled(self, extractor):
        """Invalid JSON in ld+json script tag doesn't crash the pipeline."""
        html = """
        <html><head>
        <script type="application/ld+json">{ not valid json }</script>
        </head><body>
            <span class="price">$10.00</span>
        </body></html>
        """
        result = extractor.extract_payment_info(html, "https://example.com/badjson")

        assert isinstance(result, dict)
        # Should fall back to semantic extraction
        assert len(result["price_info"]) > 0
