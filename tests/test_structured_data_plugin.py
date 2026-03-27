"""
Unit tests for StructuredDataPlugin.

Feature: crawl-pipeline-architecture
Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6
"""

import json

import pytest

from src.models import MonitoringSite
from src.pipeline.context import CrawlContext
from src.pipeline.plugins.structured_data_plugin import StructuredDataPlugin


@pytest.fixture
def plugin():
    return StructuredDataPlugin()


@pytest.fixture
def ctx():
    site = MonitoringSite(id=1, name="Test Site", url="https://example.com")
    return CrawlContext(site=site, url="https://example.com")


# ------------------------------------------------------------------
# should_run
# ------------------------------------------------------------------


class TestShouldRun:
    """should_run() は html_content が存在する場合に True を返す。"""

    def test_returns_true_when_html_content_exists(self, plugin, ctx):
        ctx.html_content = "<html></html>"
        assert plugin.should_run(ctx) is True

    def test_returns_false_when_html_content_is_none(self, plugin, ctx):
        ctx.html_content = None
        assert plugin.should_run(ctx) is False

    def test_returns_true_for_empty_string(self, plugin, ctx):
        ctx.html_content = ""
        assert plugin.should_run(ctx) is True


# ------------------------------------------------------------------
# JSON-LD extraction (Req 6.1)
# ------------------------------------------------------------------


class TestJsonLDExtraction:
    """JSON-LD から schema.org Product/Offer の価格を抽出する。"""

    @pytest.mark.asyncio
    async def test_extracts_single_product_offer(self, plugin, ctx):
        """Req 6.1: JSON-LD Product with single Offer."""
        ctx.html_content = """
        <html><head>
        <script type="application/ld+json">
        {
            "@type": "Product",
            "name": "テスト商品",
            "offers": {
                "@type": "Offer",
                "price": "1980",
                "priceCurrency": "JPY"
            }
        }
        </script>
        </head></html>
        """
        result = await plugin.execute(ctx)
        spd = result.extracted_data["structured_price_data"]
        assert spd["product_name"] == "テスト商品"
        assert len(spd["variants"]) == 1
        assert spd["variants"][0]["price"] == 1980.0
        assert spd["variants"][0]["currency"] == "JPY"
        assert spd["variants"][0]["data_source"] == "json_ld"

    @pytest.mark.asyncio
    async def test_extracts_multiple_offers(self, plugin, ctx):
        """Req 6.1: JSON-LD Product with multiple Offers."""
        ctx.html_content = """
        <html><head>
        <script type="application/ld+json">
        {
            "@type": "Product",
            "name": "テスト商品",
            "offers": [
                {"@type": "Offer", "price": "1980", "priceCurrency": "JPY", "name": "Sサイズ"},
                {"@type": "Offer", "price": "2480", "priceCurrency": "JPY", "name": "Lサイズ"}
            ]
        }
        </script>
        </head></html>
        """
        result = await plugin.execute(ctx)
        spd = result.extracted_data["structured_price_data"]
        assert len(spd["variants"]) == 2
        prices = {v["variant_name"]: v["price"] for v in spd["variants"]}
        assert prices["Sサイズ"] == 1980.0
        assert prices["Lサイズ"] == 2480.0

    @pytest.mark.asyncio
    async def test_extracts_aggregate_offer(self, plugin, ctx):
        """Req 6.1: JSON-LD AggregateOffer with lowPrice/highPrice."""
        ctx.html_content = """
        <html><head>
        <script type="application/ld+json">
        {
            "@type": "Product",
            "name": "テスト商品",
            "offers": {
                "@type": "AggregateOffer",
                "lowPrice": "980",
                "highPrice": "2980",
                "priceCurrency": "JPY"
            }
        }
        </script>
        </head></html>
        """
        result = await plugin.execute(ctx)
        spd = result.extracted_data["structured_price_data"]
        assert len(spd["variants"]) == 2
        prices = {v["variant_name"]: v["price"] for v in spd["variants"]}
        assert prices["最低価格"] == 980.0
        assert prices["最高価格"] == 2980.0

    @pytest.mark.asyncio
    async def test_handles_graph_wrapper(self, plugin, ctx):
        """JSON-LD @graph wrapper."""
        ctx.html_content = """
        <html><head>
        <script type="application/ld+json">
        {
            "@graph": [
                {
                    "@type": "Product",
                    "name": "Graph商品",
                    "offers": {"@type": "Offer", "price": "3000", "priceCurrency": "JPY"}
                }
            ]
        }
        </script>
        </head></html>
        """
        result = await plugin.execute(ctx)
        spd = result.extracted_data["structured_price_data"]
        assert spd["product_name"] == "Graph商品"
        assert spd["variants"][0]["price"] == 3000.0

    @pytest.mark.asyncio
    async def test_handles_invalid_jsonld_gracefully(self, plugin, ctx):
        """Invalid JSON-LD should not crash, should continue."""
        ctx.html_content = """
        <html><head>
        <script type="application/ld+json">{ invalid json }</script>
        <script type="application/ld+json">
        {"@type": "Product", "name": "Valid", "offers": {"@type": "Offer", "price": "500", "priceCurrency": "JPY"}}
        </script>
        </head></html>
        """
        result = await plugin.execute(ctx)
        spd = result.extracted_data["structured_price_data"]
        assert len(spd["variants"]) == 1
        assert spd["variants"][0]["price"] == 500.0

    @pytest.mark.asyncio
    async def test_data_source_is_json_ld(self, plugin, ctx):
        """Req 6.3: Each price has data_source field."""
        ctx.html_content = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Product", "name": "P", "offers": {"@type": "Offer", "price": "100", "priceCurrency": "JPY"}}
        </script>
        </head></html>
        """
        result = await plugin.execute(ctx)
        for v in result.extracted_data["structured_price_data"]["variants"]:
            assert v["data_source"] == "json_ld"

    @pytest.mark.asyncio
    async def test_data_sources_used_field(self, plugin, ctx):
        """data_sources_used lists all sources."""
        ctx.html_content = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Product", "name": "P", "offers": {"@type": "Offer", "price": "100", "priceCurrency": "JPY"}}
        </script>
        </head></html>
        """
        result = await plugin.execute(ctx)
        spd = result.extracted_data["structured_price_data"]
        assert "json_ld" in spd["data_sources_used"]


# ------------------------------------------------------------------
# Open Graph extraction (Req 6.2)
# ------------------------------------------------------------------


class TestOpenGraphExtraction:
    """Open Graph メタタグから価格情報を抽出する。"""

    @pytest.mark.asyncio
    async def test_extracts_product_price(self, plugin, ctx):
        """Req 6.2: Open Graph product:price:amount."""
        ctx.html_content = """
        <html><head>
        <meta property="og:title" content="OG商品" />
        <meta property="product:price:amount" content="1500" />
        <meta property="product:price:currency" content="JPY" />
        </head></html>
        """
        result = await plugin.execute(ctx)
        spd = result.extracted_data["structured_price_data"]
        assert len(spd["variants"]) == 1
        assert spd["variants"][0]["price"] == 1500.0
        assert spd["variants"][0]["currency"] == "JPY"
        assert spd["variants"][0]["data_source"] == "open_graph"

    @pytest.mark.asyncio
    async def test_extracts_og_price_amount(self, plugin, ctx):
        """Req 6.2: og:price:amount fallback."""
        ctx.html_content = """
        <html><head>
        <meta property="og:title" content="OG商品2" />
        <meta property="og:price:amount" content="2000" />
        <meta property="og:price:currency" content="USD" />
        </head></html>
        """
        result = await plugin.execute(ctx)
        spd = result.extracted_data["structured_price_data"]
        assert spd["variants"][0]["price"] == 2000.0
        assert spd["variants"][0]["currency"] == "USD"

    @pytest.mark.asyncio
    async def test_no_og_price_returns_empty(self, plugin, ctx):
        """No OG price tags should not produce variants."""
        ctx.html_content = """
        <html><head>
        <meta property="og:title" content="No Price" />
        </head></html>
        """
        result = await plugin.execute(ctx)
        assert result.metadata.get("structureddata_empty") is True


# ------------------------------------------------------------------
# Microdata extraction (Req 6.2)
# ------------------------------------------------------------------


class TestMicrodataExtraction:
    """Microdata 属性から価格情報を抽出する。"""

    @pytest.mark.asyncio
    async def test_extracts_product_microdata(self, plugin, ctx):
        """Req 6.2: Microdata Product with Offer."""
        ctx.html_content = """
        <html><body>
        <div itemscope itemtype="https://schema.org/Product">
            <span itemprop="name">Microdata商品</span>
            <div itemscope itemtype="https://schema.org/Offer">
                <meta itemprop="price" content="1200" />
                <meta itemprop="priceCurrency" content="JPY" />
            </div>
        </div>
        </body></html>
        """
        result = await plugin.execute(ctx)
        spd = result.extracted_data["structured_price_data"]
        assert len(spd["variants"]) == 1
        assert spd["variants"][0]["price"] == 1200.0
        assert spd["variants"][0]["data_source"] == "microdata"

    @pytest.mark.asyncio
    async def test_extracts_price_from_text(self, plugin, ctx):
        """Microdata price from element text content."""
        ctx.html_content = """
        <html><body>
        <div itemscope itemtype="https://schema.org/Product">
            <span itemprop="name">テスト</span>
            <div itemscope itemtype="https://schema.org/Offer">
                <span itemprop="price">3,500</span>
                <meta itemprop="priceCurrency" content="JPY" />
            </div>
        </div>
        </body></html>
        """
        result = await plugin.execute(ctx)
        spd = result.extracted_data["structured_price_data"]
        assert spd["variants"][0]["price"] == 3500.0


# ------------------------------------------------------------------
# Priority deduplication (Req 6.4)
# ------------------------------------------------------------------


class TestPriorityDeduplication:
    """複数ソースの同一価格は優先順位で重複排除する。"""

    @pytest.mark.asyncio
    async def test_jsonld_wins_over_og(self, plugin, ctx):
        """Req 6.4: JSON-LD > Open Graph."""
        ctx.html_content = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Product", "name": "商品A", "offers": {"@type": "Offer", "price": "1000", "priceCurrency": "JPY", "name": "商品A"}}
        </script>
        <meta property="og:title" content="商品A" />
        <meta property="product:price:amount" content="1000" />
        <meta property="product:price:currency" content="JPY" />
        </head></html>
        """
        result = await plugin.execute(ctx)
        spd = result.extracted_data["structured_price_data"]
        # Same name + price should be deduplicated, JSON-LD wins
        matching = [v for v in spd["variants"] if v["variant_name"] == "商品A" and v["price"] == 1000.0]
        assert len(matching) == 1
        assert matching[0]["data_source"] == "json_ld"

    @pytest.mark.asyncio
    async def test_jsonld_wins_over_microdata(self, plugin, ctx):
        """Req 6.4: JSON-LD > Microdata."""
        ctx.html_content = """
        <html>
        <head>
        <script type="application/ld+json">
        {"@type": "Product", "name": "商品B", "offers": {"@type": "Offer", "price": "2000", "priceCurrency": "JPY", "name": "デフォルト"}}
        </script>
        </head>
        <body>
        <div itemscope itemtype="https://schema.org/Product">
            <span itemprop="name">デフォルト</span>
            <div itemscope itemtype="https://schema.org/Offer">
                <meta itemprop="price" content="2000" />
                <meta itemprop="priceCurrency" content="JPY" />
            </div>
        </div>
        </body></html>
        """
        result = await plugin.execute(ctx)
        spd = result.extracted_data["structured_price_data"]
        matching = [v for v in spd["variants"] if v["variant_name"] == "デフォルト" and v["price"] == 2000.0]
        assert len(matching) == 1
        assert matching[0]["data_source"] == "json_ld"

    @pytest.mark.asyncio
    async def test_different_prices_kept_separately(self, plugin, ctx):
        """Different prices from different sources are kept."""
        ctx.html_content = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Product", "name": "商品", "offers": {"@type": "Offer", "price": "1000", "priceCurrency": "JPY", "name": "デフォルト"}}
        </script>
        <meta property="og:title" content="デフォルト" />
        <meta property="product:price:amount" content="1500" />
        <meta property="product:price:currency" content="JPY" />
        </head></html>
        """
        result = await plugin.execute(ctx)
        spd = result.extracted_data["structured_price_data"]
        # Different prices → both kept
        assert len(spd["variants"]) == 2


# ------------------------------------------------------------------
# Empty structured data (Req 6.5)
# ------------------------------------------------------------------


class TestEmptyStructuredData:
    """構造化データが取得できない場合の動作。"""

    @pytest.mark.asyncio
    async def test_sets_metadata_empty_flag(self, plugin, ctx):
        """Req 6.5: structured_data_empty: True when no data found."""
        ctx.html_content = "<html><body><p>No structured data</p></body></html>"
        result = await plugin.execute(ctx)
        assert result.metadata["structureddata_empty"] is True
        assert "structured_price_data" not in result.extracted_data

    @pytest.mark.asyncio
    async def test_empty_html(self, plugin, ctx):
        """Empty HTML sets empty flag."""
        ctx.html_content = ""
        result = await plugin.execute(ctx)
        assert result.metadata["structureddata_empty"] is True


# ------------------------------------------------------------------
# Field preservation
# ------------------------------------------------------------------


class TestFieldPreservation:
    """既存フィールドを破壊しない。"""

    @pytest.mark.asyncio
    async def test_preserves_existing_metadata(self, plugin, ctx):
        ctx.metadata["existing_key"] = "existing_value"
        ctx.html_content = "<html></html>"
        result = await plugin.execute(ctx)
        assert result.metadata["existing_key"] == "existing_value"

    @pytest.mark.asyncio
    async def test_preserves_existing_errors(self, plugin, ctx):
        ctx.errors.append({"plugin": "other", "error": "previous"})
        ctx.html_content = "<html></html>"
        result = await plugin.execute(ctx)
        assert len(result.errors) == 1
        assert result.errors[0]["plugin"] == "other"

    @pytest.mark.asyncio
    async def test_preserves_existing_extracted_data(self, plugin, ctx):
        ctx.extracted_data["other_data"] = {"key": "value"}
        ctx.html_content = "<html></html>"
        result = await plugin.execute(ctx)
        assert result.extracted_data["other_data"] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_returns_same_ctx(self, plugin, ctx):
        ctx.html_content = "<html></html>"
        result = await plugin.execute(ctx)
        assert result is ctx


# ------------------------------------------------------------------
# Plugin name
# ------------------------------------------------------------------


class TestPluginName:
    def test_name(self, plugin):
        assert plugin.name == "StructuredDataPlugin"


# ------------------------------------------------------------------
# Extraction timestamp
# ------------------------------------------------------------------


class TestExtractionTimestamp:
    @pytest.mark.asyncio
    async def test_has_extraction_timestamp(self, plugin, ctx):
        ctx.html_content = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Product", "name": "P", "offers": {"@type": "Offer", "price": "100", "priceCurrency": "JPY"}}
        </script>
        </head></html>
        """
        result = await plugin.execute(ctx)
        spd = result.extracted_data["structured_price_data"]
        assert "extraction_timestamp" in spd
        assert isinstance(spd["extraction_timestamp"], str)
