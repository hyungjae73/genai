"""
Unit tests for HTMLParserPlugin.

Feature: crawl-pipeline-architecture
Validates: Requirements 8.1, 8.2, 8.3
"""

from unittest.mock import MagicMock

import pytest

from src.models import MonitoringSite
from src.pipeline.context import CrawlContext
from src.pipeline.plugins.html_parser_plugin import HTMLParserPlugin


def _make_extraction_result(prices=None, product_name=None, source="semantic_html"):
    """Helper to build a PaymentInfoExtractor result."""
    if prices is None:
        prices = [{"amount": 1980, "currency": "JPY", "price_type": "base_price", "source": source}]
    return {
        "product_info": {"name": product_name, "description": None, "sku": None},
        "price_info": prices,
        "payment_methods": [],
        "fees": [],
        "metadata": {},
        "confidence_scores": {},
        "overall_confidence": 0.7,
        "language": "ja",
        "extraction_source": source,
    }


@pytest.fixture
def ctx():
    site = MonitoringSite(id=1, name="Test Site", url="https://example.com")
    c = CrawlContext(site=site, url="https://example.com")
    c.html_content = "<html><body><p>Price: ¥1,980</p></body></html>"
    c.metadata["structureddata_empty"] = True
    return c


@pytest.fixture
def mock_extractor():
    extractor = MagicMock()
    extractor.extract_payment_info.return_value = _make_extraction_result(product_name="テスト商品")
    return extractor


@pytest.fixture
def plugin(mock_extractor):
    return HTMLParserPlugin(extractor=mock_extractor)


# ------------------------------------------------------------------
# should_run (Req 8.1)
# ------------------------------------------------------------------


class TestShouldRun:
    """should_run() は metadata に structureddata_empty: True がある場合に True を返す。"""

    def test_returns_true_when_structured_data_empty(self, plugin, ctx):
        assert plugin.should_run(ctx) is True

    def test_returns_false_when_flag_not_set(self, plugin, ctx):
        ctx.metadata.pop("structureddata_empty", None)
        assert plugin.should_run(ctx) is False

    def test_returns_false_when_flag_is_false(self, plugin, ctx):
        ctx.metadata["structureddata_empty"] = False
        assert plugin.should_run(ctx) is False

    def test_returns_false_when_metadata_empty(self, plugin, ctx):
        ctx.metadata = {}
        assert plugin.should_run(ctx) is False


# ------------------------------------------------------------------
# execute — successful extraction (Req 8.2, 8.3)
# ------------------------------------------------------------------


class TestExecuteSuccess:
    """PaymentInfoExtractor を呼び出してフォールバック抽出を行う。"""

    @pytest.mark.asyncio
    async def test_calls_payment_info_extractor(self, plugin, ctx, mock_extractor):
        """Req 8.2: PaymentInfoExtractor を呼び出す。"""
        await plugin.execute(ctx)
        mock_extractor.extract_payment_info.assert_called_once_with(ctx.html_content, ctx.url)

    @pytest.mark.asyncio
    async def test_sets_data_source_html_fallback(self, plugin, ctx):
        """Req 8.3: data_source を html_fallback として格納。"""
        result = await plugin.execute(ctx)
        spd = result.extracted_data["structured_price_data"]
        for v in spd["variants"]:
            assert v["data_source"] == "html_fallback"

    @pytest.mark.asyncio
    async def test_extracts_price_info(self, plugin, ctx):
        result = await plugin.execute(ctx)
        spd = result.extracted_data["structured_price_data"]
        assert len(spd["variants"]) == 1
        assert spd["variants"][0]["price"] == 1980.0

    @pytest.mark.asyncio
    async def test_sets_product_name(self, plugin, ctx):
        result = await plugin.execute(ctx)
        spd = result.extracted_data["structured_price_data"]
        assert spd["product_name"] == "テスト商品"

    @pytest.mark.asyncio
    async def test_sets_data_sources_used(self, plugin, ctx):
        result = await plugin.execute(ctx)
        spd = result.extracted_data["structured_price_data"]
        assert "html_fallback" in spd["data_sources_used"]

    @pytest.mark.asyncio
    async def test_records_metadata(self, plugin, ctx):
        result = await plugin.execute(ctx)
        assert result.metadata["htmlparser_extraction_source"] == "semantic_html"
        assert result.metadata["htmlparser_price_count"] == 1

    @pytest.mark.asyncio
    async def test_multiple_prices(self, ctx):
        """複数価格の抽出。"""
        prices = [
            {"amount": 1980, "currency": "JPY", "price_type": "base_price", "source": "semantic_html"},
            {"amount": 2480, "currency": "JPY", "price_type": "base_price", "source": "regex"},
        ]
        extractor = MagicMock()
        extractor.extract_payment_info.return_value = _make_extraction_result(prices=prices)
        plugin = HTMLParserPlugin(extractor=extractor)

        result = await plugin.execute(ctx)
        spd = result.extracted_data["structured_price_data"]
        assert len(spd["variants"]) == 2


# ------------------------------------------------------------------
# execute — edge cases
# ------------------------------------------------------------------


class TestExecuteEdgeCases:
    """エッジケースの処理。"""

    @pytest.mark.asyncio
    async def test_empty_html_content(self, plugin, ctx):
        ctx.html_content = ""
        result = await plugin.execute(ctx)
        assert result.metadata.get("htmlparser_skipped") is True

    @pytest.mark.asyncio
    async def test_none_html_content(self, plugin, ctx):
        ctx.html_content = None
        result = await plugin.execute(ctx)
        assert result.metadata.get("htmlparser_skipped") is True

    @pytest.mark.asyncio
    async def test_extractor_returns_no_prices(self, ctx):
        extractor = MagicMock()
        extractor.extract_payment_info.return_value = _make_extraction_result(prices=[])
        plugin = HTMLParserPlugin(extractor=extractor)

        result = await plugin.execute(ctx)
        assert "structured_price_data" not in result.extracted_data or \
               len(result.extracted_data.get("structured_price_data", {}).get("variants", [])) == 0

    @pytest.mark.asyncio
    async def test_extractor_raises_exception(self, ctx):
        extractor = MagicMock()
        extractor.extract_payment_info.side_effect = Exception("Parse error")
        plugin = HTMLParserPlugin(extractor=extractor)

        result = await plugin.execute(ctx)
        assert len(result.errors) == 1
        assert "Parse error" in result.errors[0]["error"]
        assert result.errors[0]["plugin"] == "HTMLParserPlugin"


# ------------------------------------------------------------------
# Field preservation
# ------------------------------------------------------------------


class TestFieldPreservation:
    """既存フィールドを破壊しない。"""

    @pytest.mark.asyncio
    async def test_preserves_existing_metadata(self, plugin, ctx):
        ctx.metadata["existing_key"] = "existing_value"
        result = await plugin.execute(ctx)
        assert result.metadata["existing_key"] == "existing_value"

    @pytest.mark.asyncio
    async def test_preserves_existing_errors(self, plugin, ctx):
        ctx.errors.append({"plugin": "other", "error": "previous"})
        result = await plugin.execute(ctx)
        assert result.errors[0]["plugin"] == "other"

    @pytest.mark.asyncio
    async def test_merges_with_existing_extracted_data(self, plugin, ctx):
        ctx.extracted_data["structured_price_data"] = {
            "product_name": "Existing",
            "variants": [{"variant_name": "Existing", "price": 100, "data_source": "json_ld"}],
            "data_sources_used": ["json_ld"],
        }
        result = await plugin.execute(ctx)
        spd = result.extracted_data["structured_price_data"]
        assert len(spd["variants"]) == 2
        assert "json_ld" in spd["data_sources_used"]
        assert "html_fallback" in spd["data_sources_used"]

    @pytest.mark.asyncio
    async def test_returns_same_ctx(self, plugin, ctx):
        result = await plugin.execute(ctx)
        assert result is ctx


# ------------------------------------------------------------------
# Plugin name
# ------------------------------------------------------------------


class TestPluginName:
    def test_name(self, plugin):
        assert plugin.name == "HTMLParserPlugin"
