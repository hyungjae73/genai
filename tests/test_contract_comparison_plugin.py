"""
Unit tests for ContractComparisonPlugin.

Feature: crawl-pipeline-architecture
Validates: Requirements 10.1, 10.2, 10.3, 10.4
"""

import pytest

from src.models import MonitoringSite
from src.pipeline.context import CrawlContext
from src.pipeline.plugins.contract_comparison_plugin import ContractComparisonPlugin


def _make_ctx(variants=None, contract_prices=None):
    """Helper to build a CrawlContext with extracted price data and a contract provider."""
    site = MonitoringSite(id=1, name="Test Site", url="https://example.com")
    ctx = CrawlContext(site=site, url="https://example.com")

    if variants is not None:
        ctx.extracted_data["structured_price_data"] = {
            "product_name": "Test Product",
            "variants": variants,
            "data_sources_used": ["json_ld"],
        }

    provider = None
    if contract_prices is not None:
        provider = lambda site_id: {"prices": contract_prices}

    return ctx, provider


# ------------------------------------------------------------------
# should_run (Req 10.1)
# ------------------------------------------------------------------


class TestShouldRun:
    def test_returns_true_when_price_data_exists(self):
        ctx, _ = _make_ctx(variants=[{"variant_name": "A", "price": 1000, "data_source": "json_ld"}])
        plugin = ContractComparisonPlugin()
        assert plugin.should_run(ctx) is True

    def test_returns_false_when_no_extracted_data(self):
        ctx, _ = _make_ctx()
        plugin = ContractComparisonPlugin()
        assert plugin.should_run(ctx) is False

    def test_returns_false_when_variants_empty(self):
        ctx, _ = _make_ctx(variants=[])
        plugin = ContractComparisonPlugin()
        assert plugin.should_run(ctx) is False

    def test_returns_false_when_no_structured_price_data(self):
        site = MonitoringSite(id=1, name="Test", url="https://example.com")
        ctx = CrawlContext(site=site, url="https://example.com")
        ctx.extracted_data["other_key"] = "value"
        plugin = ContractComparisonPlugin()
        assert plugin.should_run(ctx) is False


# ------------------------------------------------------------------
# execute — price match (Req 10.4)
# ------------------------------------------------------------------


class TestExecuteMatch:
    @pytest.mark.asyncio
    async def test_all_match_sets_metadata(self):
        """Req 10.4: 全一致時は metadata に match インジケータを記録。"""
        variants = [
            {"variant_name": "Default", "price": 1980.0, "data_source": "json_ld"},
        ]
        ctx, provider = _make_ctx(
            variants=variants,
            contract_prices={"Default": 1980.0},
        )
        plugin = ContractComparisonPlugin(contract_provider=provider)
        result = await plugin.execute(ctx)

        assert result.metadata["contractcomparison_match"] is True
        assert len(result.violations) == 0

    @pytest.mark.asyncio
    async def test_multiple_variants_all_match(self):
        variants = [
            {"variant_name": "Small", "price": 1000.0, "data_source": "json_ld"},
            {"variant_name": "Large", "price": 2000.0, "data_source": "json_ld"},
        ]
        ctx, provider = _make_ctx(
            variants=variants,
            contract_prices={"Small": 1000.0, "Large": 2000.0},
        )
        plugin = ContractComparisonPlugin(contract_provider=provider)
        result = await plugin.execute(ctx)

        assert result.metadata["contractcomparison_match"] is True
        assert len(result.violations) == 0


# ------------------------------------------------------------------
# execute — price mismatch (Req 10.2, 10.3)
# ------------------------------------------------------------------


class TestExecuteMismatch:
    @pytest.mark.asyncio
    async def test_mismatch_adds_violation(self):
        """Req 10.3: 不一致時は variant_name, contract_price, actual_price, data_source を含む。"""
        variants = [
            {"variant_name": "Default", "price": 2500.0, "data_source": "json_ld"},
        ]
        ctx, provider = _make_ctx(
            variants=variants,
            contract_prices={"Default": 1980.0},
        )
        plugin = ContractComparisonPlugin(contract_provider=provider)
        result = await plugin.execute(ctx)

        assert len(result.violations) == 1
        v = result.violations[0]
        assert v["variant_name"] == "Default"
        assert v["contract_price"] == 1980.0
        assert v["actual_price"] == 2500.0
        assert v["data_source"] == "json_ld"
        assert v["violation_type"] == "price_mismatch"
        assert result.metadata["contractcomparison_match"] is False

    @pytest.mark.asyncio
    async def test_partial_mismatch(self):
        """Req 10.2: 各バリアント価格を個別に比較。"""
        variants = [
            {"variant_name": "Small", "price": 1000.0, "data_source": "json_ld"},
            {"variant_name": "Large", "price": 3000.0, "data_source": "shopify_api"},
        ]
        ctx, provider = _make_ctx(
            variants=variants,
            contract_prices={"Small": 1000.0, "Large": 2000.0},
        )
        plugin = ContractComparisonPlugin(contract_provider=provider)
        result = await plugin.execute(ctx)

        assert len(result.violations) == 1
        assert result.violations[0]["variant_name"] == "Large"
        assert result.violations[0]["data_source"] == "shopify_api"
        assert result.metadata["contractcomparison_match"] is False


# ------------------------------------------------------------------
# execute — contract lookup via base_price
# ------------------------------------------------------------------


class TestContractLookup:
    @pytest.mark.asyncio
    async def test_base_price_fallback(self):
        """base_price がフォールバックとして使用される。"""
        variants = [
            {"variant_name": "Unknown", "price": 1500.0, "data_source": "json_ld"},
        ]
        ctx, provider = _make_ctx(
            variants=variants,
            contract_prices={"base_price": 1980.0},
        )
        plugin = ContractComparisonPlugin(contract_provider=provider)
        result = await plugin.execute(ctx)

        assert len(result.violations) == 1
        assert result.violations[0]["contract_price"] == 1980.0

    @pytest.mark.asyncio
    async def test_variants_list_format(self):
        """Contract prices in variants list format."""
        variants = [
            {"variant_name": "A", "price": 500.0, "data_source": "microdata"},
        ]
        ctx, provider = _make_ctx(
            variants=variants,
            contract_prices={"variants": [{"name": "A", "price": 1000.0}]},
        )
        plugin = ContractComparisonPlugin(contract_provider=provider)
        result = await plugin.execute(ctx)

        assert len(result.violations) == 1
        assert result.violations[0]["contract_price"] == 1000.0


# ------------------------------------------------------------------
# execute — no contract (error handling)
# ------------------------------------------------------------------


class TestNoContract:
    @pytest.mark.asyncio
    async def test_no_contract_records_error(self):
        variants = [
            {"variant_name": "Default", "price": 1000.0, "data_source": "json_ld"},
        ]
        ctx, _ = _make_ctx(variants=variants)
        plugin = ContractComparisonPlugin(contract_provider=lambda sid: None)
        result = await plugin.execute(ctx)

        assert len(result.errors) == 1
        assert "No contract condition" in result.errors[0]["error"]


# ------------------------------------------------------------------
# Field preservation
# ------------------------------------------------------------------


class TestFieldPreservation:
    @pytest.mark.asyncio
    async def test_preserves_existing_violations(self):
        variants = [
            {"variant_name": "Default", "price": 1980.0, "data_source": "json_ld"},
        ]
        ctx, provider = _make_ctx(
            variants=variants,
            contract_prices={"Default": 1980.0},
        )
        ctx.violations.append({"existing": "violation"})
        plugin = ContractComparisonPlugin(contract_provider=provider)
        result = await plugin.execute(ctx)

        assert {"existing": "violation"} in result.violations

    @pytest.mark.asyncio
    async def test_preserves_existing_metadata(self):
        variants = [
            {"variant_name": "Default", "price": 1980.0, "data_source": "json_ld"},
        ]
        ctx, provider = _make_ctx(
            variants=variants,
            contract_prices={"Default": 1980.0},
        )
        ctx.metadata["existing_key"] = "value"
        plugin = ContractComparisonPlugin(contract_provider=provider)
        result = await plugin.execute(ctx)

        assert result.metadata["existing_key"] == "value"


# ------------------------------------------------------------------
# Plugin name
# ------------------------------------------------------------------


class TestPluginName:
    def test_name(self):
        plugin = ContractComparisonPlugin()
        assert plugin.name == "ContractComparisonPlugin"
