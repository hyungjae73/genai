"""
Unit tests for AlertPlugin.

Feature: crawl-pipeline-architecture
Validates: Requirements 14.1, 14.2, 14.3
"""

from unittest.mock import MagicMock

import pytest

from src.models import MonitoringSite
from src.pipeline.context import CrawlContext
from src.pipeline.plugins.alert_plugin import AlertPlugin


def _make_ctx(violations=None):
    """Helper to build a CrawlContext with violations."""
    site = MonitoringSite(id=1, name="Test Site", url="https://example.com")
    ctx = CrawlContext(site=site, url="https://example.com")
    if violations:
        ctx.violations = violations
    return ctx


# ------------------------------------------------------------------
# should_run (Req 14.1)
# ------------------------------------------------------------------


class TestShouldRun:
    def test_returns_true_when_violations_exist(self):
        ctx = _make_ctx(violations=[{"violation_type": "price_mismatch"}])
        plugin = AlertPlugin()
        assert plugin.should_run(ctx) is True

    def test_returns_false_when_no_violations(self):
        ctx = _make_ctx()
        plugin = AlertPlugin()
        assert plugin.should_run(ctx) is False

    def test_returns_false_when_empty_violations(self):
        ctx = _make_ctx(violations=[])
        plugin = AlertPlugin()
        assert plugin.should_run(ctx) is False


# ------------------------------------------------------------------
# execute — alert generation (Req 14.2)
# ------------------------------------------------------------------


class TestAlertGeneration:
    @pytest.mark.asyncio
    async def test_generates_one_alert_per_violation(self):
        """Req 14.2: 各違反に対して1つの Alert レコードを生成。"""
        violations = [
            {"violation_type": "price_mismatch", "variant_name": "A", "contract_price": 1000, "actual_price": 1500, "data_source": "json_ld"},
            {"violation_type": "price_mismatch", "variant_name": "B", "contract_price": 2000, "actual_price": 2500, "data_source": "shopify_api"},
        ]
        ctx = _make_ctx(violations=violations)
        plugin = AlertPlugin()
        result = await plugin.execute(ctx)

        alerts = result.metadata["alertplugin_alerts"]
        assert len(alerts) == 2
        assert result.metadata["alertplugin_alerts_generated"] == 2

    @pytest.mark.asyncio
    async def test_alert_contains_site_id(self):
        ctx = _make_ctx(violations=[{"violation_type": "price_mismatch"}])
        plugin = AlertPlugin()
        result = await plugin.execute(ctx)

        alert = result.metadata["alertplugin_alerts"][0]
        assert alert["site_id"] == 1

    @pytest.mark.asyncio
    async def test_alert_contains_violation_data(self):
        violation = {"violation_type": "price_mismatch", "variant_name": "A", "actual_price": 1500}
        ctx = _make_ctx(violations=[violation])
        plugin = AlertPlugin()
        result = await plugin.execute(ctx)

        alert = result.metadata["alertplugin_alerts"][0]
        assert alert["violation_data"] == violation


# ------------------------------------------------------------------
# execute — severity (Req 14.3)
# ------------------------------------------------------------------


class TestSeverity:
    @pytest.mark.asyncio
    async def test_price_mismatch_severity_is_warning(self):
        """Req 14.3: 価格不一致 → warning。"""
        ctx = _make_ctx(violations=[{"violation_type": "price_mismatch"}])
        plugin = AlertPlugin()
        result = await plugin.execute(ctx)

        alert = result.metadata["alertplugin_alerts"][0]
        assert alert["severity"] == "warning"

    @pytest.mark.asyncio
    async def test_structured_data_failure_severity_is_info(self):
        """Req 14.3: 構造化データ取得失敗 → info。"""
        ctx = _make_ctx(violations=[{"violation_type": "structured_data_failure"}])
        plugin = AlertPlugin()
        result = await plugin.execute(ctx)

        alert = result.metadata["alertplugin_alerts"][0]
        assert alert["severity"] == "info"

    @pytest.mark.asyncio
    async def test_unknown_type_defaults_to_warning(self):
        ctx = _make_ctx(violations=[{"violation_type": "unknown_type"}])
        plugin = AlertPlugin()
        result = await plugin.execute(ctx)

        alert = result.metadata["alertplugin_alerts"][0]
        assert alert["severity"] == "warning"

    @pytest.mark.asyncio
    async def test_mixed_severities(self):
        violations = [
            {"violation_type": "price_mismatch"},
            {"violation_type": "structured_data_failure"},
        ]
        ctx = _make_ctx(violations=violations)
        plugin = AlertPlugin()
        result = await plugin.execute(ctx)

        alerts = result.metadata["alertplugin_alerts"]
        assert alerts[0]["severity"] == "warning"
        assert alerts[1]["severity"] == "info"


# ------------------------------------------------------------------
# execute — DB save
# ------------------------------------------------------------------


class TestDBSave:
    @pytest.mark.asyncio
    async def test_saves_alerts_to_db(self):
        session = MagicMock()
        ctx = _make_ctx(violations=[{"violation_type": "price_mismatch"}])
        plugin = AlertPlugin(session_factory=lambda: session)
        await plugin.execute(ctx)

        assert session.add.call_count == 1
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_db_error(self):
        session = MagicMock()
        session.add.side_effect = Exception("DB error")
        ctx = _make_ctx(violations=[{"violation_type": "price_mismatch"}])
        plugin = AlertPlugin(session_factory=lambda: session)
        result = await plugin.execute(ctx)

        assert len(result.errors) >= 1
        assert "DB save failed" in result.errors[0]["error"]


# ------------------------------------------------------------------
# Alert message
# ------------------------------------------------------------------


class TestAlertMessage:
    @pytest.mark.asyncio
    async def test_price_mismatch_message(self):
        violation = {
            "violation_type": "price_mismatch",
            "variant_name": "Large",
            "contract_price": 1000,
            "actual_price": 1500,
            "data_source": "json_ld",
        }
        ctx = _make_ctx(violations=[violation])
        plugin = AlertPlugin()
        result = await plugin.execute(ctx)

        alert = result.metadata["alertplugin_alerts"][0]
        assert "Large" in alert["message"]
        assert "1000" in alert["message"]
        assert "1500" in alert["message"]


# ------------------------------------------------------------------
# Field preservation
# ------------------------------------------------------------------


class TestFieldPreservation:
    @pytest.mark.asyncio
    async def test_preserves_existing_metadata(self):
        ctx = _make_ctx(violations=[{"violation_type": "price_mismatch"}])
        ctx.metadata["existing_key"] = "value"
        plugin = AlertPlugin()
        result = await plugin.execute(ctx)

        assert result.metadata["existing_key"] == "value"

    @pytest.mark.asyncio
    async def test_preserves_existing_errors(self):
        ctx = _make_ctx(violations=[{"violation_type": "price_mismatch"}])
        ctx.errors.append({"plugin": "other", "error": "previous"})
        plugin = AlertPlugin()
        result = await plugin.execute(ctx)

        assert result.errors[0]["plugin"] == "other"


# ------------------------------------------------------------------
# Plugin name
# ------------------------------------------------------------------


class TestPluginName:
    def test_name(self):
        plugin = AlertPlugin()
        assert plugin.name == "AlertPlugin"
