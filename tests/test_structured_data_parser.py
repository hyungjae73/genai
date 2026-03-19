"""
Unit tests for StructuredDataParser.

Tests cover:
- JSON-LDパースのテスト
- Microdataパースのテスト
- フォールバック動作のテスト (extract_product_info)
- エラーハンドリングのテスト

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6
"""

import pytest

from src.extractors.structured_data_parser import StructuredDataParser


@pytest.fixture
def parser():
    return StructuredDataParser()


# ---------------------------------------------------------------------------
# JSON-LD parsing tests (Req 3.1, 3.4, 3.5)
# ---------------------------------------------------------------------------

class TestParseJsonLD:
    """JSON-LDパースのテスト"""

    def test_parses_single_product_jsonld(self, parser):
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Product", "name": "Widget", "sku": "W123"}
        </script>
        </head><body></body></html>
        """
        results = parser.parse_jsonld(html)
        assert len(results) == 1
        assert results[0]["@type"] == "Product"
        assert results[0]["name"] == "Widget"
        assert results[0]["sku"] == "W123"

    def test_parses_jsonld_array(self, parser):
        html = """
        <html><head>
        <script type="application/ld+json">
        [{"@type": "Product", "name": "A"}, {"@type": "Offer", "price": "10"}]
        </script>
        </head><body></body></html>
        """
        results = parser.parse_jsonld(html)
        assert len(results) == 2

    def test_parses_jsonld_with_graph(self, parser):
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@graph": [{"@type": "Product", "name": "G1"}, {"@type": "Product", "name": "G2"}]}
        </script>
        </head><body></body></html>
        """
        results = parser.parse_jsonld(html)
        assert len(results) == 2
        assert results[0]["name"] == "G1"
        assert results[1]["name"] == "G2"

    def test_parses_multiple_jsonld_scripts(self, parser):
        html = """
        <html><head>
        <script type="application/ld+json">{"@type": "Product", "name": "First"}</script>
        <script type="application/ld+json">{"@type": "Offer", "price": "500"}</script>
        </head><body></body></html>
        """
        results = parser.parse_jsonld(html)
        assert len(results) == 2

    def test_ignores_non_jsonld_scripts(self, parser):
        html = """
        <html><head>
        <script type="text/javascript">var x = 1;</script>
        <script type="application/ld+json">{"@type": "Product", "name": "Only"}</script>
        </head><body></body></html>
        """
        results = parser.parse_jsonld(html)
        assert len(results) == 1
        assert results[0]["name"] == "Only"

    def test_returns_empty_for_no_jsonld(self, parser):
        html = "<html><head></head><body></body></html>"
        results = parser.parse_jsonld(html)
        assert results == []

    def test_skips_empty_script_tag(self, parser):
        html = """
        <html><head>
        <script type="application/ld+json"></script>
        </head><body></body></html>
        """
        results = parser.parse_jsonld(html)
        assert results == []

    def test_skips_invalid_json_and_continues(self, parser):
        html = """
        <html><head>
        <script type="application/ld+json">{not valid json}</script>
        <script type="application/ld+json">{"@type": "Product", "name": "Valid"}</script>
        </head><body></body></html>
        """
        results = parser.parse_jsonld(html)
        assert len(results) == 1
        assert results[0]["name"] == "Valid"

    def test_parses_product_with_offers(self, parser):
        html = """
        <html><head>
        <script type="application/ld+json">
        {
            "@type": "Product",
            "name": "Laptop",
            "sku": "LAP-001",
            "description": "A great laptop",
            "offers": {
                "@type": "Offer",
                "price": "999.99",
                "priceCurrency": "USD",
                "availability": "InStock"
            }
        }
        </script>
        </head><body></body></html>
        """
        results = parser.parse_jsonld(html)
        assert len(results) == 1
        assert results[0]["offers"]["price"] == "999.99"
        assert results[0]["offers"]["priceCurrency"] == "USD"


# ---------------------------------------------------------------------------
# Microdata parsing tests (Req 3.2)
# ---------------------------------------------------------------------------

class TestParseMicrodata:
    """Microdataパースのテスト"""

    def test_parses_simple_microdata_item(self, parser):
        html = """
        <html><body>
        <div itemscope itemtype="http://schema.org/Product">
            <span itemprop="name">Test Product</span>
        </div>
        </body></html>
        """
        results = parser.parse_microdata(html)
        assert len(results) == 1
        assert results[0]["@type"] == "http://schema.org/Product"
        assert results[0]["name"] == "Test Product"

    def test_parses_microdata_with_content_attribute(self, parser):
        html = """
        <html><body>
        <div itemscope itemtype="http://schema.org/Product">
            <meta itemprop="sku" content="SKU-999">
            <span itemprop="name">Item</span>
        </div>
        </body></html>
        """
        results = parser.parse_microdata(html)
        assert len(results) == 1
        assert results[0]["sku"] == "SKU-999"

    def test_parses_microdata_link_href(self, parser):
        html = """
        <html><body>
        <div itemscope itemtype="http://schema.org/Product">
            <span itemprop="name">Linked</span>
            <a itemprop="url" href="https://example.com/product">Link</a>
        </div>
        </body></html>
        """
        results = parser.parse_microdata(html)
        assert results[0]["url"] == "https://example.com/product"

    def test_parses_microdata_img_src(self, parser):
        html = """
        <html><body>
        <div itemscope itemtype="http://schema.org/Product">
            <span itemprop="name">Image Product</span>
            <img itemprop="image" src="https://example.com/img.png">
        </div>
        </body></html>
        """
        results = parser.parse_microdata(html)
        assert results[0]["image"] == "https://example.com/img.png"

    def test_parses_nested_microdata_item(self, parser):
        html = """
        <html><body>
        <div itemscope itemtype="http://schema.org/Product">
            <span itemprop="name">Nested Product</span>
            <div itemprop="offers" itemscope itemtype="http://schema.org/Offer">
                <span itemprop="price">1500</span>
                <meta itemprop="priceCurrency" content="JPY">
            </div>
        </div>
        </body></html>
        """
        results = parser.parse_microdata(html)
        # The top-level item should have a nested offers dict
        assert len(results) >= 1
        top = results[0]
        assert top["@type"] == "http://schema.org/Product"
        assert isinstance(top["offers"], dict)
        assert top["offers"]["price"] == "1500"
        assert top["offers"]["priceCurrency"] == "JPY"

    def test_returns_empty_for_no_microdata(self, parser):
        html = "<html><body><p>No microdata here</p></body></html>"
        results = parser.parse_microdata(html)
        assert results == []

    def test_skips_itemscope_with_no_properties(self, parser):
        html = """
        <html><body>
        <div itemscope itemtype="http://schema.org/Thing"></div>
        </body></html>
        """
        results = parser.parse_microdata(html)
        # Item with only @type and no other props returns None
        assert results == []

    def test_parses_multiple_microdata_items(self, parser):
        html = """
        <html><body>
        <div itemscope itemtype="http://schema.org/Product">
            <span itemprop="name">Product A</span>
        </div>
        <div itemscope itemtype="http://schema.org/Product">
            <span itemprop="name">Product B</span>
        </div>
        </body></html>
        """
        results = parser.parse_microdata(html)
        assert len(results) == 2
        names = {r["name"] for r in results}
        assert names == {"Product A", "Product B"}

    def test_parses_time_element_datetime(self, parser):
        html = """
        <html><body>
        <div itemscope itemtype="http://schema.org/Product">
            <span itemprop="name">Timed</span>
            <time itemprop="releaseDate" datetime="2024-01-15">Jan 15</time>
        </div>
        </body></html>
        """
        results = parser.parse_microdata(html)
        assert results[0]["releaseDate"] == "2024-01-15"


# ---------------------------------------------------------------------------
# extract_product_info / fallback tests (Req 3.3, 3.4, 3.5)
# ---------------------------------------------------------------------------

class TestExtractProductInfo:
    """フォールバック動作のテスト - extract_product_info"""

    def test_extracts_product_name_and_description(self, parser):
        data = [{"@type": "Product", "name": "Gadget", "description": "Cool gadget", "sku": "G-1"}]
        result = parser.extract_product_info(data)
        assert result["name"] == "Gadget"
        assert result["description"] == "Cool gadget"
        assert result["sku"] == "G-1"

    def test_extracts_offer_price(self, parser):
        data = [
            {
                "@type": "Product",
                "name": "Phone",
                "offers": {
                    "@type": "Offer",
                    "price": "799",
                    "priceCurrency": "USD",
                    "availability": "InStock",
                },
            }
        ]
        result = parser.extract_product_info(data)
        assert result["name"] == "Phone"
        assert len(result["prices"]) == 1
        assert result["prices"][0]["amount"] == 799.0
        assert result["prices"][0]["currency"] == "USD"

    def test_extracts_multiple_offers_from_list(self, parser):
        data = [
            {
                "@type": "Product",
                "name": "Multi",
                "offers": [
                    {"@type": "Offer", "price": "100", "priceCurrency": "JPY"},
                    {"@type": "Offer", "price": "200", "priceCurrency": "JPY"},
                ],
            }
        ]
        result = parser.extract_product_info(data)
        assert len(result["prices"]) == 2
        amounts = [p["amount"] for p in result["prices"]]
        assert 100.0 in amounts
        assert 200.0 in amounts

    def test_extracts_aggregate_offer(self, parser):
        data = [
            {
                "@type": "Product",
                "name": "Range",
                "offers": {
                    "@type": "AggregateOffer",
                    "lowPrice": "50",
                    "highPrice": "150",
                    "priceCurrency": "EUR",
                },
            }
        ]
        result = parser.extract_product_info(data)
        assert len(result["prices"]) == 2
        types = {p["price_type"] for p in result["prices"]}
        assert "low_price" in types
        assert "high_price" in types
        amounts = {p["amount"] for p in result["prices"]}
        assert 50.0 in amounts
        assert 150.0 in amounts

    def test_extracts_standalone_offer(self, parser):
        data = [{"@type": "Offer", "price": "300", "priceCurrency": "GBP", "availability": "InStock"}]
        result = parser.extract_product_info(data)
        assert len(result["prices"]) == 1
        assert result["prices"][0]["amount"] == 300.0
        assert result["prices"][0]["currency"] == "GBP"

    def test_returns_empty_for_no_product_or_offer(self, parser):
        data = [{"@type": "Organization", "name": "Acme Corp"}]
        result = parser.extract_product_info(data)
        assert result["name"] is None
        assert result["prices"] == []

    def test_returns_empty_for_empty_list(self, parser):
        result = parser.extract_product_info([])
        assert result["name"] is None
        assert result["description"] is None
        assert result["sku"] is None
        assert result["prices"] == []

    def test_first_product_name_wins(self, parser):
        data = [
            {"@type": "Product", "name": "First"},
            {"@type": "Product", "name": "Second"},
        ]
        result = parser.extract_product_info(data)
        assert result["name"] == "First"

    def test_handles_type_as_list(self, parser):
        data = [{"@type": ["Product", "IndividualProduct"], "name": "ListType"}]
        result = parser.extract_product_info(data)
        assert result["name"] == "ListType"

    def test_handles_price_with_commas(self, parser):
        data = [{"@type": "Offer", "price": "1,299.99", "priceCurrency": "USD"}]
        result = parser.extract_product_info(data)
        assert result["prices"][0]["amount"] == 1299.99

    def test_skips_offer_without_price(self, parser):
        data = [{"@type": "Offer", "priceCurrency": "USD"}]
        result = parser.extract_product_info(data)
        assert result["prices"] == []

    def test_handles_schema_org_url_type(self, parser):
        data = [{"@type": "https://schema.org/Product", "name": "URL Type"}]
        result = parser.extract_product_info(data)
        assert result["name"] == "URL Type"


# ---------------------------------------------------------------------------
# Error handling tests (Req 3.6)
# ---------------------------------------------------------------------------

class TestErrorHandling:
    """エラーハンドリングのテスト"""

    def test_jsonld_returns_empty_on_empty_html(self, parser):
        assert parser.parse_jsonld("") == []

    def test_jsonld_returns_empty_on_malformed_html(self, parser):
        assert parser.parse_jsonld("<not><valid><<<html") == []

    def test_microdata_returns_empty_on_empty_html(self, parser):
        assert parser.parse_microdata("") == []

    def test_microdata_returns_empty_on_malformed_html(self, parser):
        assert parser.parse_microdata("<broken<>html") == []

    def test_extract_product_info_handles_missing_fields(self, parser):
        data = [{"@type": "Product"}]
        result = parser.extract_product_info(data)
        assert result["name"] is None
        assert result["description"] is None
        assert result["sku"] is None
        assert result["prices"] == []

    def test_parse_price_returns_none_for_non_numeric(self, parser):
        data = [{"@type": "Offer", "price": "free", "priceCurrency": "USD"}]
        result = parser.extract_product_info(data)
        assert result["prices"] == []

    def test_parse_price_returns_none_for_none(self, parser):
        assert parser._parse_price(None) is None

    def test_parse_price_handles_string_with_spaces(self, parser):
        assert parser._parse_price("  42.5  ") == 42.5

    def test_jsonld_invalid_json_does_not_raise(self, parser):
        html = """
        <html><head>
        <script type="application/ld+json">{invalid}</script>
        </head><body></body></html>
        """
        # Should not raise, just return empty
        results = parser.parse_jsonld(html)
        assert results == []

    def test_aggregate_offer_with_only_low_price(self, parser):
        data = [
            {
                "@type": "Product",
                "name": "Partial",
                "offers": {
                    "@type": "AggregateOffer",
                    "lowPrice": "25",
                    "priceCurrency": "USD",
                },
            }
        ]
        result = parser.extract_product_info(data)
        assert len(result["prices"]) == 1
        assert result["prices"][0]["price_type"] == "low_price"

    def test_aggregate_offer_with_only_high_price(self, parser):
        data = [
            {
                "@type": "Product",
                "name": "Partial High",
                "offers": {
                    "@type": "AggregateOffer",
                    "highPrice": "75",
                    "priceCurrency": "EUR",
                },
            }
        ]
        result = parser.extract_product_info(data)
        assert len(result["prices"]) == 1
        assert result["prices"][0]["price_type"] == "high_price"
