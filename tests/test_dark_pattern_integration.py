"""
Integration tests for pipeline stage ordering and end-to-end dark pattern flow.

**Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7**

Tests:
  - Plugin execution order across all 4 stages matches design
  - DarkPatternScore post-process runs after all plugins and before reporter
  - Full pipeline with mocked plugins produces correct darkpattern_score and violations
  - plugin_config site-level disable/enable for each new plugin
  - PIPELINE_DISABLED_PLUGINS env var disables plugins globally
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models import MonitoringSite
from src.pipeline.context import CrawlContext
from src.pipeline.pipeline import CrawlPipeline, resolve_plugin_config
from src.pipeline.plugin import CrawlPlugin
from src.pipeline.plugins.css_visual_plugin import CSSVisualPlugin
from src.pipeline.plugins.journey_plugin import JourneyPlugin
from src.pipeline.plugins.llm_classifier_plugin import LLMClassifierPlugin
from src.pipeline.plugins.ui_trap_plugin import UITrapPlugin
from src.pipeline.plugins.dark_pattern_utils import compute_dark_pattern_score


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class OrderTrackingPlugin(CrawlPlugin):
    """Plugin that records execution order."""

    execution_log: list[str] = []

    def __init__(self, name_override: str):
        self._name = name_override

    async def execute(self, ctx: CrawlContext) -> CrawlContext:
        OrderTrackingPlugin.execution_log.append(self._name)
        return ctx

    def should_run(self, ctx: CrawlContext) -> bool:
        return True

    @property
    def name(self) -> str:
        return self._name


class ConditionalPlugin(CrawlPlugin):
    """Plugin that runs only when should_run returns True."""

    def __init__(self, name_override: str, should_run_val: bool = True):
        self._name = name_override
        self._should_run = should_run_val
        self.executed = False

    async def execute(self, ctx: CrawlContext) -> CrawlContext:
        self.executed = True
        return ctx

    def should_run(self, ctx: CrawlContext) -> bool:
        return self._should_run

    @property
    def name(self) -> str:
        return self._name


def _make_ctx(**kwargs) -> CrawlContext:
    site = MonitoringSite(id=1, url="https://example.com")
    defaults = {
        "site": site,
        "url": "https://example.com",
        "html_content": "<html><body>test</body></html>",
    }
    defaults.update(kwargs)
    return CrawlContext(**defaults)


def _make_site_with_config(plugin_config=None) -> MonitoringSite:
    site = MonitoringSite(id=1, url="https://example.com")
    site.plugin_config = plugin_config
    return site


# ---------------------------------------------------------------------------
# Test: Plugin execution order across all 4 stages (Req 6.1–6.4)
# ---------------------------------------------------------------------------


class TestPluginExecutionOrder:
    """Test that plugins execute in the correct order per design."""

    @pytest.mark.asyncio
    async def test_page_fetcher_stage_order(self):
        """Req 6.1: JourneyPlugin after PreCaptureScriptPlugin, before ModalDismissPlugin."""
        OrderTrackingPlugin.execution_log = []
        stages = {
            "page_fetcher": [
                OrderTrackingPlugin("LocalePlugin"),
                OrderTrackingPlugin("PreCaptureScriptPlugin"),
                OrderTrackingPlugin("JourneyPlugin"),
                OrderTrackingPlugin("ModalDismissPlugin"),
            ],
            "data_extractor": [],
            "validator": [],
            "reporter": [],
        }
        pipeline = CrawlPipeline(stages=stages)
        ctx = _make_ctx()
        await pipeline.run(ctx)

        pf_log = OrderTrackingPlugin.execution_log
        assert pf_log.index("PreCaptureScriptPlugin") < pf_log.index("JourneyPlugin")
        assert pf_log.index("JourneyPlugin") < pf_log.index("ModalDismissPlugin")

    @pytest.mark.asyncio
    async def test_data_extractor_stage_order(self):
        """Req 6.2, 6.3: CSSVisualPlugin after OCRPlugin, LLMClassifierPlugin after CSSVisualPlugin."""
        OrderTrackingPlugin.execution_log = []
        stages = {
            "page_fetcher": [],
            "data_extractor": [
                OrderTrackingPlugin("StructuredDataPlugin"),
                OrderTrackingPlugin("ShopifyPlugin"),
                OrderTrackingPlugin("HTMLParserPlugin"),
                OrderTrackingPlugin("OCRPlugin"),
                OrderTrackingPlugin("CSSVisualPlugin"),
                OrderTrackingPlugin("LLMClassifierPlugin"),
            ],
            "validator": [],
            "reporter": [],
        }
        pipeline = CrawlPipeline(stages=stages)
        ctx = _make_ctx()
        await pipeline.run(ctx)

        de_log = OrderTrackingPlugin.execution_log
        assert de_log.index("OCRPlugin") < de_log.index("CSSVisualPlugin")
        assert de_log.index("CSSVisualPlugin") < de_log.index("LLMClassifierPlugin")

    @pytest.mark.asyncio
    async def test_validator_stage_order(self):
        """Req 6.4: UITrapPlugin after ContractComparisonPlugin."""
        OrderTrackingPlugin.execution_log = []
        stages = {
            "page_fetcher": [],
            "data_extractor": [],
            "validator": [
                OrderTrackingPlugin("ContractComparisonPlugin"),
                OrderTrackingPlugin("UITrapPlugin"),
            ],
            "reporter": [],
        }
        pipeline = CrawlPipeline(stages=stages)
        ctx = _make_ctx()
        await pipeline.run(ctx)

        val_log = OrderTrackingPlugin.execution_log
        assert val_log.index("ContractComparisonPlugin") < val_log.index("UITrapPlugin")

    @pytest.mark.asyncio
    async def test_full_pipeline_stage_order(self):
        """All 4 stages execute in order: page_fetcher → data_extractor → validator → reporter."""
        OrderTrackingPlugin.execution_log = []
        stages = {
            "page_fetcher": [OrderTrackingPlugin("PF")],
            "data_extractor": [OrderTrackingPlugin("DE")],
            "validator": [OrderTrackingPlugin("VAL")],
            "reporter": [OrderTrackingPlugin("REP")],
        }
        pipeline = CrawlPipeline(stages=stages)
        ctx = _make_ctx()
        await pipeline.run(ctx)

        assert OrderTrackingPlugin.execution_log == ["PF", "DE", "VAL", "REP"]


# ---------------------------------------------------------------------------
# Test: DarkPatternScore post-process timing
# ---------------------------------------------------------------------------


class TestDarkPatternScorePostProcess:
    """Test that DarkPatternScore runs after all plugins and before reporter."""

    @pytest.mark.asyncio
    async def test_score_computed_before_reporter(self):
        """DarkPatternScore post-process runs between validator and reporter stages."""
        score_was_set_before_reporter = []

        class ReporterCheckPlugin(CrawlPlugin):
            async def execute(self, ctx: CrawlContext) -> CrawlContext:
                score_was_set_before_reporter.append(
                    "darkpattern_score" in ctx.metadata
                )
                return ctx

            def should_run(self, ctx: CrawlContext) -> bool:
                return True

        stages = {
            "page_fetcher": [],
            "data_extractor": [],
            "validator": [],
            "reporter": [ReporterCheckPlugin()],
        }
        pipeline = CrawlPipeline(stages=stages)
        ctx = _make_ctx()
        await pipeline.run(ctx)

        assert score_was_set_before_reporter == [True], \
            "darkpattern_score should be set before reporter stage executes"

    @pytest.mark.asyncio
    async def test_score_not_set_before_validator(self):
        """DarkPatternScore should NOT be set during validator stage."""
        score_during_validator = []

        class ValidatorCheckPlugin(CrawlPlugin):
            async def execute(self, ctx: CrawlContext) -> CrawlContext:
                score_during_validator.append(
                    "darkpattern_score" in ctx.metadata
                )
                return ctx

            def should_run(self, ctx: CrawlContext) -> bool:
                return True

        stages = {
            "page_fetcher": [],
            "data_extractor": [],
            "validator": [ValidatorCheckPlugin()],
            "reporter": [],
        }
        pipeline = CrawlPipeline(stages=stages)
        ctx = _make_ctx()
        await pipeline.run(ctx)

        assert score_during_validator == [False], \
            "darkpattern_score should NOT be set during validator stage"


# ---------------------------------------------------------------------------
# Test: Full pipeline with mocked plugins
# ---------------------------------------------------------------------------


class TestFullPipelineWithMockedPlugins:
    """Test full pipeline produces correct darkpattern_score and violations."""

    @pytest.mark.asyncio
    async def test_mocked_plugins_produce_score_and_violations(self):
        """Pipeline with plugins writing metadata produces correct final score."""

        class CSSVisualPlugin(CrawlPlugin):
            """Mock that uses the real plugin name so compute_dark_pattern_score recognises it."""

            async def execute(self, ctx: CrawlContext) -> CrawlContext:
                ctx.metadata["cssvisual_deception_score"] = 0.4
                ctx.metadata["cssvisual_techniques"] = [{"type": "low_contrast"}]
                ctx.violations.append({
                    "violation_type": "low_contrast",
                    "severity": "warning",
                    "dark_pattern_category": "visual_deception",
                })
                return ctx

            def should_run(self, ctx: CrawlContext) -> bool:
                return True

        class UITrapPlugin(CrawlPlugin):
            """Mock that uses the real plugin name so compute_dark_pattern_score recognises it."""

            async def execute(self, ctx: CrawlContext) -> CrawlContext:
                ctx.metadata["uitrap_detections"] = [
                    {"type": "preselected_checkbox"},
                    {"type": "confirmshaming"},
                    {"type": "confirmshaming"},
                ]
                ctx.violations.append({
                    "violation_type": "sneak_into_basket",
                    "severity": "warning",
                    "dark_pattern_category": "sneak_into_basket",
                })
                return ctx

            def should_run(self, ctx: CrawlContext) -> bool:
                return True

        stages = {
            "page_fetcher": [],
            "data_extractor": [CSSVisualPlugin()],
            "validator": [UITrapPlugin()],
            "reporter": [],
        }
        pipeline = CrawlPipeline(stages=stages)
        ctx = _make_ctx()

        result = await pipeline.run(ctx)

        # DarkPatternScore should have been computed
        assert "darkpattern_score" in result.metadata
        assert "darkpattern_subscores" in result.metadata

        score = result.metadata["darkpattern_score"]
        assert 0.0 <= score <= 1.0

        subscores = result.metadata["darkpattern_subscores"]
        assert "css_visual" in subscores
        assert "ui_trap" in subscores

        # css_visual was executed with score 0.4
        assert subscores["css_visual"] == pytest.approx(0.4, abs=0.01)

        # ui_trap had 3 detections → min(1.0, 3 * 0.25) = 0.75
        assert subscores["ui_trap"] == pytest.approx(0.75, abs=0.01)

        # Max pooling: max(0.4, 0.75, penalty, penalty) = 0.75
        assert score == pytest.approx(0.75, abs=0.01)

        # Violations should include plugin violations + high_dark_pattern_risk
        violation_types = [v["violation_type"] for v in result.violations]
        assert "low_contrast" in violation_types
        assert "sneak_into_basket" in violation_types
        assert "high_dark_pattern_risk" in violation_types  # score 0.75 >= 0.6

    @pytest.mark.asyncio
    async def test_all_plugins_unexecuted_penalty_baseline(self):
        """When no plugins execute, all subscores get penalty baseline."""
        stages = {
            "page_fetcher": [],
            "data_extractor": [],
            "validator": [],
            "reporter": [],
        }
        pipeline = CrawlPipeline(stages=stages)
        ctx = _make_ctx()
        result = await pipeline.run(ctx)

        score = result.metadata["darkpattern_score"]
        subscores = result.metadata["darkpattern_subscores"]

        # All plugins unexecuted → penalty 0.15 each
        for key in ("css_visual", "llm_classifier", "journey", "ui_trap"):
            assert subscores[key] == pytest.approx(0.15, abs=0.01)

        # Max of all penalties = 0.15
        assert score == pytest.approx(0.15, abs=0.01)

        # 0.15 < 0.6 threshold → no high_dark_pattern_risk violation
        violation_types = [v["violation_type"] for v in result.violations]
        assert "high_dark_pattern_risk" not in violation_types


# ---------------------------------------------------------------------------
# Test: plugin_config site-level disable/enable (Req 6.6)
# ---------------------------------------------------------------------------


class TestPluginConfigSiteLevelOverride:
    """Test plugin_config site-level disable/enable for each new plugin."""

    def test_disable_journey_plugin_via_site_config(self):
        """JourneyPlugin can be disabled via site plugin_config."""
        global_enabled = {"JourneyPlugin", "CSSVisualPlugin", "LLMClassifierPlugin", "UITrapPlugin"}
        site_config = {"disabled": ["JourneyPlugin"], "enabled": [], "params": {}}
        enabled, _ = resolve_plugin_config(global_enabled, site_config)
        assert "JourneyPlugin" not in enabled

    def test_disable_css_visual_plugin_via_site_config(self):
        """CSSVisualPlugin can be disabled via site plugin_config."""
        global_enabled = {"JourneyPlugin", "CSSVisualPlugin", "LLMClassifierPlugin", "UITrapPlugin"}
        site_config = {"disabled": ["CSSVisualPlugin"], "enabled": [], "params": {}}
        enabled, _ = resolve_plugin_config(global_enabled, site_config)
        assert "CSSVisualPlugin" not in enabled

    def test_disable_llm_classifier_plugin_via_site_config(self):
        """LLMClassifierPlugin can be disabled via site plugin_config."""
        global_enabled = {"JourneyPlugin", "CSSVisualPlugin", "LLMClassifierPlugin", "UITrapPlugin"}
        site_config = {"disabled": ["LLMClassifierPlugin"], "enabled": [], "params": {}}
        enabled, _ = resolve_plugin_config(global_enabled, site_config)
        assert "LLMClassifierPlugin" not in enabled

    def test_disable_ui_trap_plugin_via_site_config(self):
        """UITrapPlugin can be disabled via site plugin_config."""
        global_enabled = {"JourneyPlugin", "CSSVisualPlugin", "LLMClassifierPlugin", "UITrapPlugin"}
        site_config = {"disabled": ["UITrapPlugin"], "enabled": [], "params": {}}
        enabled, _ = resolve_plugin_config(global_enabled, site_config)
        assert "UITrapPlugin" not in enabled

    def test_enable_plugin_via_site_config(self):
        """A disabled plugin can be re-enabled via site plugin_config."""
        global_enabled = {"CSSVisualPlugin"}
        site_config = {"disabled": [], "enabled": ["JourneyPlugin"], "params": {}}
        enabled, _ = resolve_plugin_config(global_enabled, site_config)
        assert "JourneyPlugin" in enabled

    def test_site_config_params_passed(self):
        """Plugin params from site_config are available."""
        global_enabled = {"UITrapPlugin"}
        site_config = {
            "disabled": [],
            "enabled": [],
            "params": {"UITrapPlugin": {"dom_distance_threshold": 30}},
        }
        enabled, params = resolve_plugin_config(global_enabled, site_config)
        assert "UITrapPlugin" in enabled
        assert params["UITrapPlugin"]["dom_distance_threshold"] == 30


# ---------------------------------------------------------------------------
# Test: PIPELINE_DISABLED_PLUGINS env var (Req 6.7)
# ---------------------------------------------------------------------------


class TestPipelineDisabledPluginsEnvVar:
    """Test PIPELINE_DISABLED_PLUGINS env var disables plugins globally."""

    def test_env_disables_single_plugin(self):
        """Single plugin disabled via env var."""
        global_enabled = {"JourneyPlugin", "CSSVisualPlugin", "LLMClassifierPlugin", "UITrapPlugin"}
        disabled_env = ["JourneyPlugin"]
        enabled, _ = resolve_plugin_config(global_enabled, disabled_env=disabled_env)
        assert "JourneyPlugin" not in enabled
        assert "CSSVisualPlugin" in enabled

    def test_env_disables_multiple_plugins(self):
        """Multiple plugins disabled via env var."""
        global_enabled = {"JourneyPlugin", "CSSVisualPlugin", "LLMClassifierPlugin", "UITrapPlugin"}
        disabled_env = ["JourneyPlugin", "CSSVisualPlugin", "UITrapPlugin"]
        enabled, _ = resolve_plugin_config(global_enabled, disabled_env=disabled_env)
        assert enabled == {"LLMClassifierPlugin"}

    def test_env_disables_all_new_plugins(self):
        """All 4 new plugins can be disabled via env var."""
        global_enabled = {"JourneyPlugin", "CSSVisualPlugin", "LLMClassifierPlugin", "UITrapPlugin"}
        disabled_env = ["JourneyPlugin", "CSSVisualPlugin", "LLMClassifierPlugin", "UITrapPlugin"]
        enabled, _ = resolve_plugin_config(global_enabled, disabled_env=disabled_env)
        assert len(enabled) == 0

    def test_site_enabled_overrides_env_disabled(self):
        """site_config.enabled can re-enable a plugin disabled by env var."""
        global_enabled = {"JourneyPlugin", "CSSVisualPlugin"}
        site_config = {"disabled": [], "enabled": ["JourneyPlugin"], "params": {}}
        disabled_env = ["JourneyPlugin"]
        enabled, _ = resolve_plugin_config(global_enabled, site_config, disabled_env)
        assert "JourneyPlugin" in enabled

    @pytest.mark.asyncio
    async def test_pipeline_respects_should_run_for_disabled_plugins(self):
        """Plugins with should_run=False are not executed in the pipeline."""
        disabled_plugin = ConditionalPlugin("DisabledPlugin", should_run_val=False)
        enabled_plugin = ConditionalPlugin("EnabledPlugin", should_run_val=True)

        stages = {
            "page_fetcher": [],
            "data_extractor": [disabled_plugin, enabled_plugin],
            "validator": [],
            "reporter": [],
        }
        pipeline = CrawlPipeline(stages=stages)
        ctx = _make_ctx()
        result = await pipeline.run(ctx)

        assert not disabled_plugin.executed
        assert enabled_plugin.executed

        executed_names = result.metadata["pipeline_stages"]["data_extractor"]["executed_plugins"]
        assert "DisabledPlugin" not in executed_names
        assert "EnabledPlugin" in executed_names
