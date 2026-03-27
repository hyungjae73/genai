"""
Unit tests for CrawlPipeline orchestrator.

Feature: crawl-pipeline-architecture
Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6
"""

import pytest
from datetime import datetime, timezone

from src.models import MonitoringSite
from src.pipeline.context import CrawlContext
from src.pipeline.pipeline import CrawlPipeline, STAGE_ORDER, resolve_plugin_config
from src.pipeline.plugin import CrawlPlugin


# --- Test helpers ---


class PassthroughPlugin(CrawlPlugin):
    """A plugin that always runs and does nothing."""

    def __init__(self, name_override: str = "PassthroughPlugin"):
        self._name = name_override

    async def execute(self, ctx: CrawlContext) -> CrawlContext:
        return ctx

    def should_run(self, ctx: CrawlContext) -> bool:
        return True

    @property
    def name(self) -> str:
        return self._name


class SkippedPlugin(CrawlPlugin):
    """A plugin that never runs."""

    def __init__(self, name_override: str = "SkippedPlugin"):
        self._name = name_override

    async def execute(self, ctx: CrawlContext) -> CrawlContext:
        raise AssertionError("Should not be called")

    def should_run(self, ctx: CrawlContext) -> bool:
        return False

    @property
    def name(self) -> str:
        return self._name


class ErrorPlugin(CrawlPlugin):
    """A plugin that always raises an error."""

    def __init__(self, name_override: str = "ErrorPlugin"):
        self._name = name_override

    async def execute(self, ctx: CrawlContext) -> CrawlContext:
        raise RuntimeError("Test error from plugin")

    def should_run(self, ctx: CrawlContext) -> bool:
        return True

    @property
    def name(self) -> str:
        return self._name


class TrackingPlugin(CrawlPlugin):
    """A plugin that records its execution order."""

    call_log: list[str] = []

    def __init__(self, name_override: str = "TrackingPlugin"):
        self._name = name_override

    async def execute(self, ctx: CrawlContext) -> CrawlContext:
        TrackingPlugin.call_log.append(self._name)
        return ctx

    def should_run(self, ctx: CrawlContext) -> bool:
        return True

    @property
    def name(self) -> str:
        return self._name


class HtmlSetterPlugin(CrawlPlugin):
    """A plugin that sets html_content on the context."""

    async def execute(self, ctx: CrawlContext) -> CrawlContext:
        ctx.html_content = "<html>test</html>"
        return ctx

    def should_run(self, ctx: CrawlContext) -> bool:
        return True


def _make_ctx(**kwargs) -> CrawlContext:
    site = MonitoringSite(id=1, url="https://example.com")
    defaults = {"site": site, "url": "https://example.com"}
    defaults.update(kwargs)
    return CrawlContext(**defaults)


# --- Tests ---


class TestCrawlPipelineStageOrder:
    """Validates: Requirements 2.1 — 4 stages executed in order."""

    @pytest.mark.asyncio
    async def test_stages_execute_in_order(self):
        TrackingPlugin.call_log = []
        stages = {
            "page_fetcher": [TrackingPlugin("pf")],
            "data_extractor": [TrackingPlugin("de")],
            "validator": [TrackingPlugin("val")],
            "reporter": [TrackingPlugin("rep")],
        }
        pipeline = CrawlPipeline(stages=stages)
        ctx = _make_ctx(html_content="<html></html>")
        result = await pipeline.run(ctx)

        assert TrackingPlugin.call_log == ["pf", "de", "val", "rep"]

        # Verify metadata records all 4 stages
        ps = result.metadata["pipeline_stages"]
        assert list(ps.keys()) == STAGE_ORDER

    @pytest.mark.asyncio
    async def test_stage_metadata_has_start_end_times(self):
        stages = {
            "page_fetcher": [PassthroughPlugin()],
            "data_extractor": [PassthroughPlugin()],
            "validator": [PassthroughPlugin()],
            "reporter": [PassthroughPlugin()],
        }
        pipeline = CrawlPipeline(stages=stages)
        ctx = _make_ctx(html_content="<html></html>")
        result = await pipeline.run(ctx)

        for stage_name in STAGE_ORDER:
            stage_meta = result.metadata["pipeline_stages"][stage_name]
            assert "start_time" in stage_meta
            assert "end_time" in stage_meta
            assert "executed_plugins" in stage_meta
            # Verify times are valid ISO format
            datetime.fromisoformat(stage_meta["start_time"])
            datetime.fromisoformat(stage_meta["end_time"])


class TestCrawlPipelineShouldRunFiltering:
    """Validates: Requirements 2.2 — should_run filtering."""

    @pytest.mark.asyncio
    async def test_only_should_run_true_plugins_execute(self):
        TrackingPlugin.call_log = []
        stages = {
            "page_fetcher": [
                TrackingPlugin("active"),
                SkippedPlugin("skipped"),
                TrackingPlugin("active2"),
            ],
        }
        pipeline = CrawlPipeline(stages=stages)
        ctx = _make_ctx(html_content="<html></html>")
        result = await pipeline.run(ctx)

        assert TrackingPlugin.call_log == ["active", "active2"]
        executed = result.metadata["pipeline_stages"]["page_fetcher"][
            "executed_plugins"
        ]
        assert executed == ["active", "active2"]


class TestCrawlPipelineErrorHandling:
    """Validates: Requirements 2.3 — error isolation within a stage."""

    @pytest.mark.asyncio
    async def test_plugin_error_recorded_and_stage_continues(self):
        TrackingPlugin.call_log = []
        stages = {
            "page_fetcher": [
                TrackingPlugin("before"),
                ErrorPlugin("failing"),
                TrackingPlugin("after"),
            ],
        }
        pipeline = CrawlPipeline(stages=stages)
        ctx = _make_ctx(html_content="<html></html>")
        result = await pipeline.run(ctx)

        # Both tracking plugins and the error plugin should have been attempted
        assert TrackingPlugin.call_log == ["before", "after"]

        # Error should be recorded
        assert len(result.errors) == 1
        err = result.errors[0]
        assert err["plugin"] == "failing"
        assert err["stage"] == "page_fetcher"
        assert "Test error from plugin" in err["error"]
        assert "timestamp" in err

    @pytest.mark.asyncio
    async def test_multiple_errors_in_same_stage(self):
        stages = {
            "page_fetcher": [
                ErrorPlugin("err1"),
                ErrorPlugin("err2"),
            ],
        }
        pipeline = CrawlPipeline(stages=stages)
        ctx = _make_ctx(html_content="<html></html>")
        result = await pipeline.run(ctx)

        assert len(result.errors) == 2
        assert result.errors[0]["plugin"] == "err1"
        assert result.errors[1]["plugin"] == "err2"


class TestCrawlPipelineDataExtractorSkip:
    """Validates: Requirements 2.4 — skip DataExtractor when html_content is None."""

    @pytest.mark.asyncio
    async def test_data_extractor_skipped_when_html_none(self):
        TrackingPlugin.call_log = []
        stages = {
            "page_fetcher": [PassthroughPlugin("pf")],
            "data_extractor": [TrackingPlugin("de")],
            "validator": [TrackingPlugin("val")],
            "reporter": [TrackingPlugin("rep")],
        }
        pipeline = CrawlPipeline(stages=stages)
        ctx = _make_ctx()  # html_content defaults to None
        result = await pipeline.run(ctx)

        # data_extractor should be skipped
        assert TrackingPlugin.call_log == ["val", "rep"]

        # Metadata should indicate skip
        de_meta = result.metadata["pipeline_stages"]["data_extractor"]
        assert de_meta["skipped"] is True
        assert de_meta["reason"] == "html_content is None"

    @pytest.mark.asyncio
    async def test_data_extractor_runs_when_html_present(self):
        TrackingPlugin.call_log = []
        stages = {
            "page_fetcher": [HtmlSetterPlugin()],
            "data_extractor": [TrackingPlugin("de")],
            "validator": [TrackingPlugin("val")],
            "reporter": [TrackingPlugin("rep")],
        }
        pipeline = CrawlPipeline(stages=stages)
        ctx = _make_ctx()
        result = await pipeline.run(ctx)

        assert "de" in TrackingPlugin.call_log
        de_meta = result.metadata["pipeline_stages"]["data_extractor"]
        assert "skipped" not in de_meta


class TestCrawlPipelineReturnContext:
    """Validates: Requirements 2.6 — returns final CrawlContext."""

    @pytest.mark.asyncio
    async def test_returns_crawl_context(self):
        pipeline = CrawlPipeline(stages={})
        ctx = _make_ctx(html_content="<html></html>")
        result = await pipeline.run(ctx)

        assert isinstance(result, CrawlContext)
        assert result.url == "https://example.com"

    @pytest.mark.asyncio
    async def test_empty_stages_still_records_metadata(self):
        pipeline = CrawlPipeline(stages={})
        ctx = _make_ctx(html_content="<html></html>")
        result = await pipeline.run(ctx)

        ps = result.metadata["pipeline_stages"]
        for stage_name in STAGE_ORDER:
            if stage_name == "data_extractor" and result.html_content is not None:
                assert "start_time" in ps[stage_name]
            elif stage_name == "data_extractor":
                assert ps[stage_name].get("skipped") is True


class TestCrawlPipelineInit:
    """Test pipeline initialization."""

    def test_default_init_creates_empty_stages(self):
        pipeline = CrawlPipeline()
        for name in STAGE_ORDER:
            assert name in pipeline._stages
            assert pipeline._stages[name] == []

    def test_partial_stages_fills_missing(self):
        pipeline = CrawlPipeline(stages={"page_fetcher": [PassthroughPlugin()]})
        assert len(pipeline._stages["page_fetcher"]) == 1
        assert pipeline._stages["data_extractor"] == []
        assert pipeline._stages["validator"] == []
        assert pipeline._stages["reporter"] == []

class TestResolvePluginConfig:
    """Validates: Requirements 22.7, 22.8, 22.9, 22.10, 22.11, 22.12"""

    def test_global_only_returns_all_global_plugins(self):
        """site_config=None, disabled_env=None → グローバル設定そのまま"""
        global_enabled = {"PluginA", "PluginB", "PluginC"}
        enabled, params = resolve_plugin_config(global_enabled)
        assert enabled == {"PluginA", "PluginB", "PluginC"}
        assert params == {}

    def test_site_disabled_removes_plugins(self):
        """site_config.disabled でプラグイン無効化"""
        global_enabled = {"PluginA", "PluginB", "PluginC"}
        site_config = {"disabled": ["PluginB"], "enabled": [], "params": {}}
        enabled, params = resolve_plugin_config(global_enabled, site_config)
        assert enabled == {"PluginA", "PluginC"}

    def test_env_disabled_removes_plugins(self):
        """PIPELINE_DISABLED_PLUGINS 環境変数でプラグイン無効化"""
        global_enabled = {"PluginA", "PluginB", "PluginC"}
        enabled, params = resolve_plugin_config(
            global_enabled, disabled_env=["PluginA"]
        )
        assert enabled == {"PluginB", "PluginC"}

    def test_site_enabled_adds_plugins(self):
        """site_config.enabled で追加有効化"""
        global_enabled = {"PluginA"}
        site_config = {"disabled": [], "enabled": ["CustomPlugin"], "params": {}}
        enabled, params = resolve_plugin_config(global_enabled, site_config)
        assert enabled == {"PluginA", "CustomPlugin"}

    def test_full_3_layer_merge(self):
        """グローバル → サイト disabled → env disabled → サイト enabled の順でマージ"""
        global_enabled = {"PluginA", "PluginB", "PluginC", "PluginD"}
        site_config = {
            "disabled": ["PluginB"],
            "enabled": ["CustomPlugin"],
            "params": {"PluginA": {"threshold": 0.8}},
        }
        disabled_env = ["PluginC"]
        enabled, params = resolve_plugin_config(
            global_enabled, site_config, disabled_env
        )
        assert enabled == {"PluginA", "PluginD", "CustomPlugin"}
        assert params == {"PluginA": {"threshold": 0.8}}

    def test_site_config_none_uses_global_minus_env(self):
        """site_config=None の場合、グローバル設定 - env disabled"""
        global_enabled = {"PluginA", "PluginB", "PluginC"}
        enabled, params = resolve_plugin_config(
            global_enabled, site_config=None, disabled_env=["PluginB"]
        )
        assert enabled == {"PluginA", "PluginC"}
        assert params == {}

    def test_site_enabled_overrides_env_disabled(self):
        """site_config.enabled は env disabled より後に適用される"""
        global_enabled = {"PluginA", "PluginB"}
        site_config = {
            "disabled": [],
            "enabled": ["PluginB"],
            "params": {},
        }
        disabled_env = ["PluginB"]
        enabled, params = resolve_plugin_config(
            global_enabled, site_config, disabled_env
        )
        # PluginB is removed by env, then re-added by site enabled
        assert "PluginB" in enabled

    def test_params_merged_from_site_config(self):
        """site_config.params がマージされる"""
        global_enabled = {"PluginA"}
        site_config = {
            "disabled": [],
            "enabled": [],
            "params": {
                "PluginA": {"confidence_threshold": 0.8},
                "PluginB": {"mode": "fast"},
            },
        }
        enabled, params = resolve_plugin_config(global_enabled, site_config)
        assert params == {
            "PluginA": {"confidence_threshold": 0.8},
            "PluginB": {"mode": "fast"},
        }

    def test_empty_site_config_no_changes(self):
        """空の site_config はグローバル設定を変更しない"""
        global_enabled = {"PluginA", "PluginB"}
        site_config = {"disabled": [], "enabled": [], "params": {}}
        enabled, params = resolve_plugin_config(global_enabled, site_config)
        assert enabled == {"PluginA", "PluginB"}
        assert params == {}

    def test_disable_nonexistent_plugin_is_noop(self):
        """存在しないプラグインの無効化は無視される"""
        global_enabled = {"PluginA"}
        site_config = {"disabled": ["NonExistent"], "enabled": [], "params": {}}
        enabled, params = resolve_plugin_config(global_enabled, site_config)
        assert enabled == {"PluginA"}

    def test_empty_global_with_site_enabled(self):
        """グローバルが空でも site_config.enabled で追加可能"""
        global_enabled: set[str] = set()
        site_config = {"disabled": [], "enabled": ["CustomPlugin"], "params": {}}
        enabled, params = resolve_plugin_config(global_enabled, site_config)
        assert enabled == {"CustomPlugin"}

    def test_does_not_mutate_input(self):
        """入力の global_enabled セットを変更しない"""
        global_enabled = {"PluginA", "PluginB"}
        original = set(global_enabled)
        site_config = {"disabled": ["PluginA"], "enabled": [], "params": {}}
        resolve_plugin_config(global_enabled, site_config, ["PluginB"])
        assert global_enabled == original

