"""
Unit tests for ShopifyPlugin.

Feature: crawl-pipeline-architecture
Validates: Requirements 7.1, 7.2, 7.3, 7.4
"""

import json
from unittest.mock import MagicMock
from urllib.error import HTTPError

import pytest

from src.models import MonitoringSite
from src.pipeline.context import CrawlContext
from src.pipeline.plugins.shopify_plugin import ShopifyPlugin


def _make_product_json(variants=None, title="Test Product"):
    """Helper to build a Shopify product.json response."""
    if variants is None:
        variants = [
            {
                "title": "Default",
                "price": "1980.00",
                "compare_at_price": "2980.00",
                "sku": "SKU-001",
                "option1": "S",
                "option2": "Red",
                "option3": None,
            }
        ]
    return {"product": {"title": title, "variants": variants}}


@pytest.fixture
def ctx():
    site = MonitoringSite(id=1, name="Shopify Store", url="https://shop.example.com/products/test-product")
    return CrawlContext(site=site, url="https://shop.example.com/products/test-product")


@pytest.fixture
def mock_fetcher():
    return MagicMock(return_value=_make_product_json())


@pytest.fixture
def plugin(mock_fetcher):
    return ShopifyPlugin(http_fetcher=mock_fetcher)


# ------------------------------------------------------------------
# should_run (Req 7.1)
# ------------------------------------------------------------------


class TestShouldRun:
    """should_run() は html_content に Shopify 検出パターンがある場合に True を返す。"""

    def test_returns_true_when_shopify_shop_present(self, plugin, ctx):
        ctx.html_content = '<script>var Shopify = Shopify || {}; Shopify.shop = "test.myshopify.com";</script>'
        assert plugin.should_run(ctx) is True

    def test_returns_true_when_cdn_shopify_present(self, plugin, ctx):
        ctx.html_content = '<link rel="stylesheet" href="https://cdn.shopify.com/s/files/1/theme.css">'
        assert plugin.should_run(ctx) is True

    def test_returns_false_when_no_shopify_markers(self, plugin, ctx):
        ctx.html_content = "<html><body>Regular site</body></html>"
        assert plugin.should_run(ctx) is False

    def test_returns_false_when_html_is_none(self, plugin, ctx):
        ctx.html_content = None
        assert plugin.should_run(ctx) is False

    def test_returns_false_for_empty_html(self, plugin, ctx):
        ctx.html_content = ""
        assert plugin.should_run(ctx) is False


# ------------------------------------------------------------------
# execute — successful extraction (Req 7.2, 7.3)
# ------------------------------------------------------------------


class TestExecuteSuccess:
    """正常な Shopify API レスポンスからバリアント価格を抽出する。"""

    @pytest.mark.asyncio
    async def test_extracts_single_variant(self, plugin, ctx, mock_fetcher):
        """Req 7.3: title, price, compare_at_price, sku, option1-3 を抽出。"""
        ctx.html_content = '<script>Shopify.shop = "test";</script>'
        result = await plugin.execute(ctx)

        spd = result.extracted_data["structured_price_data"]
        assert len(spd["variants"]) == 1

        v = spd["variants"][0]
        assert v["variant_name"] == "Default"
        assert v["price"] == 1980.0
        assert v["compare_at_price"] == 2980.0
        assert v["sku"] == "SKU-001"
        assert v["data_source"] == "shopify_api"
        assert v["options"]["option1"] == "S"
        assert v["options"]["option2"] == "Red"

    @pytest.mark.asyncio
    async def test_extracts_multiple_variants(self, ctx):
        """Req 7.3: 複数バリアントの抽出。"""
        variants = [
            {"title": "Small", "price": "1980", "compare_at_price": None, "sku": "S-001", "option1": "S"},
            {"title": "Large", "price": "2480", "compare_at_price": "3000", "sku": "L-001", "option1": "L"},
        ]
        fetcher = MagicMock(return_value=_make_product_json(variants))
        plugin = ShopifyPlugin(http_fetcher=fetcher)

        ctx.html_content = '<script>Shopify.shop = "test";</script>'
        result = await plugin.execute(ctx)

        spd = result.extracted_data["structured_price_data"]
        assert len(spd["variants"]) == 2
        prices = {v["variant_name"]: v["price"] for v in spd["variants"]}
        assert prices["Small"] == 1980.0
        assert prices["Large"] == 2480.0

    @pytest.mark.asyncio
    async def test_sets_product_name(self, plugin, ctx, mock_fetcher):
        ctx.html_content = '<script>Shopify.shop = "test";</script>'
        result = await plugin.execute(ctx)
        spd = result.extracted_data["structured_price_data"]
        assert spd["product_name"] == "Test Product"

    @pytest.mark.asyncio
    async def test_sets_data_sources_used(self, plugin, ctx, mock_fetcher):
        ctx.html_content = '<script>Shopify.shop = "test";</script>'
        result = await plugin.execute(ctx)
        spd = result.extracted_data["structured_price_data"]
        assert "shopify_api" in spd["data_sources_used"]

    @pytest.mark.asyncio
    async def test_calls_correct_api_url(self, plugin, ctx, mock_fetcher):
        """Req 7.2: /products/{handle}.json にリクエストを送信。"""
        ctx.html_content = '<script>Shopify.shop = "test";</script>'
        await plugin.execute(ctx)
        mock_fetcher.assert_called_once_with("https://shop.example.com/products/test-product.json")

    @pytest.mark.asyncio
    async def test_records_metadata(self, plugin, ctx, mock_fetcher):
        ctx.html_content = '<script>Shopify.shop = "test";</script>'
        result = await plugin.execute(ctx)
        assert result.metadata["shopify_variants_count"] == 1
        assert "shopify_api_url" in result.metadata


# ------------------------------------------------------------------
# execute — error handling (Req 7.4)
# ------------------------------------------------------------------


class TestExecuteErrors:
    """404/アクセス拒否時は ctx.errors に記録しパイプライン継続。"""

    @pytest.mark.asyncio
    async def test_handles_404_error(self, ctx):
        """Req 7.4: 404 エラー時は errors に記録。"""
        fetcher = MagicMock(side_effect=HTTPError(
            url="https://shop.example.com/products/test-product.json",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=None,
        ))
        plugin = ShopifyPlugin(http_fetcher=fetcher)
        ctx.html_content = '<script>Shopify.shop = "test";</script>'

        result = await plugin.execute(ctx)

        assert len(result.errors) == 1
        assert "404" in result.errors[0]["error"]
        assert result.errors[0]["plugin"] == "ShopifyPlugin"
        assert result.errors[0]["http_code"] == 404

    @pytest.mark.asyncio
    async def test_handles_403_error(self, ctx):
        """Req 7.4: アクセス拒否時は errors に記録。"""
        fetcher = MagicMock(side_effect=HTTPError(
            url="https://shop.example.com/products/test-product.json",
            code=403,
            msg="Forbidden",
            hdrs=None,
            fp=None,
        ))
        plugin = ShopifyPlugin(http_fetcher=fetcher)
        ctx.html_content = '<script>Shopify.shop = "test";</script>'

        result = await plugin.execute(ctx)

        assert len(result.errors) == 1
        assert "403" in result.errors[0]["error"]

    @pytest.mark.asyncio
    async def test_handles_generic_exception(self, ctx):
        fetcher = MagicMock(side_effect=Exception("Connection timeout"))
        plugin = ShopifyPlugin(http_fetcher=fetcher)
        ctx.html_content = '<script>Shopify.shop = "test";</script>'

        result = await plugin.execute(ctx)

        assert len(result.errors) == 1
        assert "Connection timeout" in result.errors[0]["error"]

    @pytest.mark.asyncio
    async def test_no_handle_in_url(self, ctx):
        """URL にプロダクトハンドルがない場合。"""
        fetcher = MagicMock()
        plugin = ShopifyPlugin(http_fetcher=fetcher)
        ctx.url = "https://shop.example.com/"
        ctx.html_content = '<script>Shopify.shop = "test";</script>'

        result = await plugin.execute(ctx)

        fetcher.assert_not_called()
        assert result.metadata.get("shopify_no_handle") is True


# ------------------------------------------------------------------
# Product handle extraction
# ------------------------------------------------------------------


class TestProductHandleExtraction:
    """URL からプロダクトハンドルを正しく抽出する。"""

    def test_standard_product_url(self, plugin):
        assert plugin._extract_product_handle("https://shop.com/products/my-product") == "my-product"

    def test_product_url_with_query(self, plugin):
        assert plugin._extract_product_handle("https://shop.com/products/my-product?variant=123") == "my-product"

    def test_collection_product_url(self, plugin):
        assert plugin._extract_product_handle("https://shop.com/collections/all/products/my-product") == "my-product"

    def test_no_product_path(self, plugin):
        assert plugin._extract_product_handle("https://shop.com/about") is None

    def test_trailing_slash(self, plugin):
        assert plugin._extract_product_handle("https://shop.com/products/my-product/") == "my-product"


# ------------------------------------------------------------------
# Field preservation
# ------------------------------------------------------------------


class TestFieldPreservation:
    """既存フィールドを破壊しない。"""

    @pytest.mark.asyncio
    async def test_preserves_existing_metadata(self, plugin, ctx, mock_fetcher):
        ctx.metadata["existing_key"] = "existing_value"
        ctx.html_content = '<script>Shopify.shop = "test";</script>'
        result = await plugin.execute(ctx)
        assert result.metadata["existing_key"] == "existing_value"

    @pytest.mark.asyncio
    async def test_preserves_existing_errors(self, plugin, ctx, mock_fetcher):
        ctx.errors.append({"plugin": "other", "error": "previous"})
        ctx.html_content = '<script>Shopify.shop = "test";</script>'
        result = await plugin.execute(ctx)
        assert result.errors[0]["plugin"] == "other"

    @pytest.mark.asyncio
    async def test_merges_with_existing_extracted_data(self, plugin, ctx, mock_fetcher):
        """既存の structured_price_data にマージする。"""
        ctx.extracted_data["structured_price_data"] = {
            "product_name": "Existing",
            "variants": [{"variant_name": "Existing", "price": 100, "data_source": "json_ld"}],
            "data_sources_used": ["json_ld"],
        }
        ctx.html_content = '<script>Shopify.shop = "test";</script>'
        result = await plugin.execute(ctx)

        spd = result.extracted_data["structured_price_data"]
        assert len(spd["variants"]) == 2  # existing + shopify
        assert "json_ld" in spd["data_sources_used"]
        assert "shopify_api" in spd["data_sources_used"]

    @pytest.mark.asyncio
    async def test_returns_same_ctx(self, plugin, ctx, mock_fetcher):
        ctx.html_content = '<script>Shopify.shop = "test";</script>'
        result = await plugin.execute(ctx)
        assert result is ctx


# ------------------------------------------------------------------
# Plugin name
# ------------------------------------------------------------------


class TestPluginName:
    def test_name(self, plugin):
        assert plugin.name == "ShopifyPlugin"
