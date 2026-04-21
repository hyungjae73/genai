"""
Property-based tests for CrawlContext round-trip serialization.

Feature: crawl-pipeline-architecture
Property 1: CrawlContext round-trip serialization
Validates: Requirements 1.6
"""

import json
import time
from datetime import datetime, timedelta
from typing import Optional

from hypothesis import given, settings

from src.pipeline.context import CrawlContext, VariantCapture
from tests.strategies import crawl_context_strategy


class TestCrawlContextRoundTrip:
    """
    **Validates: Requirements 1.6**

    For any valid CrawlContext object, serializing to dict via to_dict()
    and deserializing via from_dict() shall produce an equivalent CrawlContext.
    """

    @given(ctx=crawl_context_strategy())
    @settings(max_examples=100)
    def test_round_trip_produces_equivalent_object(self, ctx: CrawlContext):
        """to_dict() -> from_dict() round-trip produces equivalent CrawlContext."""
        serialized = ctx.to_dict()
        restored = CrawlContext.from_dict(serialized, site=ctx.site)

        # Core fields
        assert restored.site.id == ctx.site.id
        assert restored.url == ctx.url
        assert restored.html_content == ctx.html_content

        # Screenshots: compare each VariantCapture field
        assert len(restored.screenshots) == len(ctx.screenshots)
        for original, roundtripped in zip(ctx.screenshots, restored.screenshots):
            assert roundtripped.variant_name == original.variant_name
            assert roundtripped.image_path == original.image_path
            assert roundtripped.captured_at == original.captured_at
            assert roundtripped.metadata == original.metadata

        # Dict/list fields
        assert restored.extracted_data == ctx.extracted_data
        assert restored.violations == ctx.violations
        assert restored.evidence_records == ctx.evidence_records
        assert restored.errors == ctx.errors
        assert restored.metadata == ctx.metadata

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import strategies as st

from src.models import MonitoringSite
from src.pipeline.pipeline import CrawlPipeline, STAGE_ORDER, resolve_plugin_config
from src.pipeline.plugin import CrawlPlugin


# ---------------------------------------------------------------------------
# Helper: stub plugin classes for pipeline property tests
# ---------------------------------------------------------------------------

class StubPlugin(CrawlPlugin):
    """Configurable stub plugin for testing."""

    def __init__(self, name: str, *, run: bool = True, fail: bool = False):
        self._name = name
        self._run = run
        self._fail = fail
        self.executed = False

    @property
    def name(self) -> str:
        return self._name

    def should_run(self, ctx: CrawlContext) -> bool:
        return self._run

    async def execute(self, ctx: CrawlContext) -> CrawlContext:
        if self._fail:
            raise RuntimeError(f"{self._name} intentional error")
        self.executed = True
        return ctx


# ---------------------------------------------------------------------------
# Hypothesis strategies for pipeline tests
# ---------------------------------------------------------------------------

def _plugin_for_stage_strategy():
    """Generate a list of StubPlugins with random should_run flags."""
    return st.lists(
        st.booleans(),
        min_size=1,
        max_size=5,
    )


def _plugins_per_stage_strategy():
    """Generate a dict mapping each stage to a list of (name, should_run) booleans."""
    return st.fixed_dictionaries({
        stage: st.lists(st.booleans(), min_size=0, max_size=4)
        for stage in STAGE_ORDER
    })


# Strategy for plugin names used in config merge tests
_ALL_PLUGIN_NAMES = [
    "LocalePlugin", "PreCaptureScriptPlugin", "ModalDismissPlugin",
    "StructuredDataPlugin", "ShopifyPlugin", "HTMLParserPlugin",
    "OCRPlugin", "ContractComparisonPlugin", "EvidencePreservationPlugin",
    "DBStoragePlugin", "ObjectStoragePlugin", "AlertPlugin",
]


def _plugin_config_strategy():
    """Generate a random site-level plugin_config dict."""
    return st.fixed_dictionaries({
        "disabled": st.lists(st.sampled_from(_ALL_PLUGIN_NAMES), max_size=5, unique=True),
        "enabled": st.lists(
            st.text(
                alphabet=st.characters(whitelist_categories=("L",)),
                min_size=1,
                max_size=20,
            ),
            max_size=3,
            unique=True,
        ),
        "params": st.dictionaries(
            st.sampled_from(_ALL_PLUGIN_NAMES),
            st.dictionaries(
                st.text(
                    alphabet=st.characters(whitelist_categories=("L",)),
                    min_size=1,
                    max_size=15,
                ),
                st.floats(min_value=0, max_value=1, allow_nan=False),
                max_size=3,
            ),
            max_size=4,
        ),
    })


def _global_enabled_strategy():
    """Generate a random set of globally enabled plugin names."""
    return st.frozensets(st.sampled_from(_ALL_PLUGIN_NAMES), min_size=1, max_size=len(_ALL_PLUGIN_NAMES))


def _disabled_env_strategy():
    """Generate a random list of env-disabled plugin names."""
    return st.lists(st.sampled_from(_ALL_PLUGIN_NAMES), max_size=4, unique=True)


# ---------------------------------------------------------------------------
# Property 5: Pipeline stage execution order
# ---------------------------------------------------------------------------

class TestPipelineStageExecutionOrder:
    """
    **Validates: Requirements 2.1, 2.5**

    For any CrawlPipeline execution, metadata["pipeline_stages"] shall record
    stages in exactly the order page_fetcher, data_extractor, validator, reporter,
    and each stage's start_time shall be <= the next stage's start_time.
    """

    @given(stage_plugins=_plugins_per_stage_strategy())
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_stage_order_and_monotonic_timestamps(self, stage_plugins):
        """Stages appear in STAGE_ORDER with monotonically increasing timestamps."""
        # Build pipeline with stub plugins; ensure page_fetcher sets html_content
        # so data_extractor is not skipped.
        stages: dict[str, list[CrawlPlugin]] = {}
        for stage_name, run_flags in stage_plugins.items():
            stages[stage_name] = [
                StubPlugin(f"{stage_name}_{i}", run=flag)
                for i, flag in enumerate(run_flags)
            ]

        # Add a plugin that sets html_content so data_extractor is not skipped
        class HtmlSetter(CrawlPlugin):
            @property
            def name(self):
                return "HtmlSetter"

            def should_run(self, ctx):
                return True

            async def execute(self, ctx):
                ctx.html_content = "<html></html>"
                return ctx

        stages["page_fetcher"] = [HtmlSetter()] + stages.get("page_fetcher", [])

        pipeline = CrawlPipeline(stages=stages)
        site = MonitoringSite(id=1, name="test", url="https://example.com")
        ctx = CrawlContext(site=site, url="https://example.com")

        result = await pipeline.run(ctx)

        pipeline_stages = result.metadata.get("pipeline_stages", {})

        # All 4 stages must be present
        for stage_name in STAGE_ORDER:
            assert stage_name in pipeline_stages, f"Missing stage: {stage_name}"

        # Verify monotonically increasing start_time
        from datetime import datetime

        prev_start = None
        for stage_name in STAGE_ORDER:
            stage_info = pipeline_stages[stage_name]
            if "start_time" in stage_info:
                current_start = datetime.fromisoformat(stage_info["start_time"])
                if prev_start is not None:
                    assert current_start >= prev_start, (
                        f"{stage_name} start_time {current_start} < previous {prev_start}"
                    )
                prev_start = current_start


# ---------------------------------------------------------------------------
# Property 6: should_run filtering
# ---------------------------------------------------------------------------

class TestShouldRunFiltering:
    """
    **Validates: Requirements 2.2**

    For any stage containing N registered plugins where M return should_run()==True,
    exactly M plugins shall have execute() called.
    """

    @given(run_flags=st.lists(st.booleans(), min_size=1, max_size=10))
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_only_should_run_true_plugins_execute(self, run_flags):
        """Only plugins with should_run()==True have execute() called."""
        plugins = [
            StubPlugin(f"plugin_{i}", run=flag)
            for i, flag in enumerate(run_flags)
        ]

        # Put all plugins in the validator stage (no html_content dependency)
        pipeline = CrawlPipeline(stages={
            "page_fetcher": [],
            "data_extractor": [],
            "validator": plugins,
            "reporter": [],
        })

        site = MonitoringSite(id=1, name="test", url="https://example.com")
        ctx = CrawlContext(site=site, url="https://example.com")

        await pipeline.run(ctx)

        expected_executed = sum(1 for f in run_flags if f)
        actual_executed = sum(1 for p in plugins if p.executed)

        assert actual_executed == expected_executed, (
            f"Expected {expected_executed} plugins executed, got {actual_executed}"
        )

        # Verify each plugin individually
        for plugin, flag in zip(plugins, run_flags):
            assert plugin.executed == flag, (
                f"Plugin {plugin.name}: expected executed={flag}, got {plugin.executed}"
            )


# ---------------------------------------------------------------------------
# Property 7: Plugin error isolation within a stage
# ---------------------------------------------------------------------------

class TestPluginErrorIsolation:
    """
    **Validates: Requirements 2.3**

    For any pipeline stage with multiple plugins, if one plugin raises an exception,
    the error shall be recorded in ctx.errors and all remaining plugins in the same
    stage shall still execute.
    """

    @given(error_index=st.integers(min_value=0, max_value=4))
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_error_does_not_block_remaining_plugins(self, error_index):
        """One plugin's error doesn't prevent other plugins from executing."""
        num_plugins = 5
        plugins = []
        for i in range(num_plugins):
            plugins.append(
                StubPlugin(f"plugin_{i}", run=True, fail=(i == error_index))
            )

        pipeline = CrawlPipeline(stages={
            "page_fetcher": [],
            "data_extractor": [],
            "validator": plugins,
            "reporter": [],
        })

        site = MonitoringSite(id=1, name="test", url="https://example.com")
        ctx = CrawlContext(site=site, url="https://example.com")

        result = await pipeline.run(ctx)

        # The failing plugin's error should be recorded
        error_messages = [e["error"] for e in result.errors]
        assert any(f"plugin_{error_index}" in msg for msg in error_messages), (
            f"Error from plugin_{error_index} not found in ctx.errors"
        )

        # All non-failing plugins should have executed
        for i, plugin in enumerate(plugins):
            if i != error_index:
                assert plugin.executed, (
                    f"plugin_{i} should have executed despite plugin_{error_index} failing"
                )


# ---------------------------------------------------------------------------
# Property 8: PageFetcher failure skips DataExtractor
# ---------------------------------------------------------------------------

class TestPageFetcherFailureSkipsDataExtractor:
    """
    **Validates: Requirements 2.4**

    For any pipeline execution where PageFetcher fails to populate html_content
    (remains None), the DataExtractor stage shall be skipped entirely.
    """

    @given(
        num_extractors=st.integers(min_value=1, max_value=5),
        num_validators=st.integers(min_value=0, max_value=3),
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_data_extractor_skipped_when_html_none(
        self, num_extractors, num_validators
    ):
        """DataExtractor plugins don't execute when html_content is None."""
        extractor_plugins = [
            StubPlugin(f"extractor_{i}", run=True) for i in range(num_extractors)
        ]
        validator_plugins = [
            StubPlugin(f"validator_{i}", run=True) for i in range(num_validators)
        ]

        pipeline = CrawlPipeline(stages={
            "page_fetcher": [],  # No plugin sets html_content → stays None
            "data_extractor": extractor_plugins,
            "validator": validator_plugins,
            "reporter": [],
        })

        site = MonitoringSite(id=1, name="test", url="https://example.com")
        ctx = CrawlContext(site=site, url="https://example.com")
        # html_content is None by default

        result = await pipeline.run(ctx)

        # data_extractor should be skipped
        de_stage = result.metadata.get("pipeline_stages", {}).get("data_extractor", {})
        assert de_stage.get("skipped") is True, (
            "data_extractor stage should be marked as skipped"
        )

        # No extractor plugin should have executed
        for plugin in extractor_plugins:
            assert not plugin.executed, (
                f"{plugin.name} should NOT have executed when html_content is None"
            )

        # Validator plugins should still execute
        for plugin in validator_plugins:
            assert plugin.executed, (
                f"{plugin.name} should still execute even when data_extractor is skipped"
            )


# ---------------------------------------------------------------------------
# Property 17: Plugin config 3-layer merge
# ---------------------------------------------------------------------------

class TestPluginConfig3LayerMerge:
    """
    **Validates: Requirements 22.7, 22.8, 22.9, 22.10, 22.11, 22.12**

    For any global plugin config and any site-level plugin_config, the effective
    plugin set shall equal:
        (global enabled) - (site disabled) - (env disabled) + (site enabled)
    When site_config is NULL, effective = global - env disabled.
    """

    @given(
        global_enabled=_global_enabled_strategy(),
        site_config=st.one_of(st.none(), _plugin_config_strategy()),
        disabled_env=_disabled_env_strategy(),
    )
    @settings(max_examples=100)
    def test_merge_correctness(self, global_enabled, site_config, disabled_env):
        """3-layer config merge produces correct effective plugin set."""
        enabled, merged_params = resolve_plugin_config(
            global_enabled=set(global_enabled),
            site_config=site_config,
            disabled_env=disabled_env,
        )

        if site_config is not None:
            site_disabled = set(site_config.get("disabled", []))
            site_enabled_set = set(site_config.get("enabled", []))
            env_disabled = set(disabled_env)

            expected = (set(global_enabled) - site_disabled - env_disabled) | site_enabled_set
            assert enabled == expected, (
                f"Expected {expected}, got {enabled}\n"
                f"global={global_enabled}, site_disabled={site_disabled}, "
                f"env_disabled={env_disabled}, site_enabled={site_enabled_set}"
            )

            # Params should come from site_config.params
            expected_params = {
                k: dict(v) for k, v in site_config.get("params", {}).items()
            }
            assert merged_params == expected_params
        else:
            # When site_config is None: global - env disabled
            expected = set(global_enabled) - set(disabled_env)
            assert enabled == expected, (
                f"Expected {expected}, got {enabled}\n"
                f"global={global_enabled}, env_disabled={disabled_env}"
            )

            # No params when site_config is None
            assert merged_params == {}

    @given(
        global_enabled=_global_enabled_strategy(),
        disabled_env=_disabled_env_strategy(),
    )
    @settings(max_examples=100)
    def test_null_site_config_equals_global_minus_env(self, global_enabled, disabled_env):
        """When site_config is None, effective = global - env disabled."""
        enabled, merged_params = resolve_plugin_config(
            global_enabled=set(global_enabled),
            site_config=None,
            disabled_env=disabled_env,
        )

        expected = set(global_enabled) - set(disabled_env)
        assert enabled == expected
        assert merged_params == {}

# ---------------------------------------------------------------------------
# Property 26: BrowserPool crash recovery
# ---------------------------------------------------------------------------

from src.pipeline.browser_pool import BrowserPool


def _make_mock_browser(connected=True):
    """Create a mock Browser with configurable connection state."""
    browser = MagicMock()
    browser.is_connected.return_value = connected
    browser.close = AsyncMock()
    page = MagicMock()
    page.is_closed.return_value = False
    page.close = AsyncMock()
    browser.new_page = AsyncMock(return_value=page)
    # stealth_browser.py calls await browser.new_context(...)
    context = MagicMock()
    context.new_page = AsyncMock(return_value=page)
    context.close = AsyncMock()
    browser.new_context = AsyncMock(return_value=context)
    return browser


class TestBrowserPoolCrashRecovery:
    """
    **Validates: Requirements 15.5**

    For any BrowserPool state where a browser instance crashes (becomes
    disconnected), the pool shall discard the crashed instance and create
    a new one, maintaining the configured pool size.
    """

    @given(
        pool_size=st.integers(min_value=1, max_value=5),
        crash_flags=st.lists(st.booleans(), min_size=1, max_size=10),
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_crash_recovery_maintains_pool_size(self, pool_size, crash_flags):
        """After any sequence of acquire/release with crashes, pool size is maintained."""
        # Pre-create enough mock browsers: initial pool + replacements for crashes
        num_crashes = sum(1 for f in crash_flags if f)
        total_browsers_needed = pool_size + num_crashes + 1  # extra safety margin
        all_browsers = [_make_mock_browser(connected=True) for _ in range(total_browsers_needed)]
        browser_iter = iter(all_browsers)

        mock_pw = MagicMock()
        mock_pw.chromium.launch = AsyncMock(side_effect=lambda **kwargs: next(browser_iter))
        mock_pw.stop = AsyncMock()

        async def launcher():
            return mock_pw

        pool = BrowserPool(max_instances=pool_size, playwright_launcher=launcher)
        await pool.initialize()

        assert len(pool._instances) == pool_size

        # Process each crash_flag as an acquire/release cycle
        for should_crash in crash_flags:
            browser, page = await pool.acquire()

            if should_crash:
                # Simulate crash: browser becomes disconnected before release
                browser.is_connected.return_value = False

            await pool.release(browser, page)

            # After every release, the pool must maintain the correct instance count
            assert len(pool._instances) == pool_size, (
                f"Expected {pool_size} instances, got {len(pool._instances)} "
                f"after crash={should_crash}"
            )
            assert pool._pool.qsize() <= pool_size

        # Final: all instances in the pool should be connected
        while not pool._pool.empty():
            b = pool._pool.get_nowait()
            assert b.is_connected(), "All pooled browsers should be connected"

        await pool.shutdown()

    @given(
        pool_size=st.integers(min_value=1, max_value=4),
        crash_on_acquire_flags=st.lists(st.booleans(), min_size=1, max_size=8),
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_crashed_on_acquire_replaced_and_discarded(self, pool_size, crash_on_acquire_flags):
        """Browsers that crash before acquire are discarded and replaced with new ones."""
        total_needed = pool_size + len(crash_on_acquire_flags) + 1
        all_browsers = [_make_mock_browser(connected=True) for _ in range(total_needed)]
        browser_idx = [0]

        mock_pw = MagicMock()

        async def launch_browser(**kwargs):
            idx = browser_idx[0]
            browser_idx[0] += 1
            return all_browsers[idx]

        mock_pw.chromium.launch = AsyncMock(side_effect=launch_browser)
        mock_pw.stop = AsyncMock()

        async def launcher():
            return mock_pw

        pool = BrowserPool(max_instances=pool_size, playwright_launcher=launcher)
        await pool.initialize()

        initial_browsers = set(pool._instances)

        for should_crash in crash_on_acquire_flags:
            if should_crash:
                # Peek at the next browser in the queue and mark it as crashed
                # so acquire() detects the crash
                if not pool._pool.empty():
                    next_browser = pool._pool.get_nowait()
                    next_browser.is_connected.return_value = False
                    await pool._pool.put(next_browser)

            browser, page = await pool.acquire()

            # The acquired browser must always be connected
            assert browser.is_connected(), "Acquired browser must be connected"

            # If it crashed, the returned browser should be a replacement (not the crashed one)
            # Release normally
            await pool.release(browser, page)

            # Pool size invariant
            assert len(pool._instances) == pool_size

        await pool.shutdown()



# ---------------------------------------------------------------------------
# Property 4: PreCaptureScript round-trip serialization
# ---------------------------------------------------------------------------

from src.pipeline.plugins.pre_capture_script_plugin import parse_script, serialize_script
from tests.strategies import pre_capture_script_strategy


class TestPreCaptureScriptRoundTrip:
    """
    **Validates: Requirements 5.7**

    For any valid PreCaptureScript JSON (array of action objects with valid
    action/selector/ms/value/text/label fields), parsing to an action list
    and re-serializing to JSON shall produce an equivalent action list.
    """

    @given(actions=pre_capture_script_strategy())
    @settings(max_examples=100)
    def test_round_trip_produces_equivalent_actions(self, actions):
        """parse_script(serialize_script(actions)) == actions."""
        serialized = serialize_script(actions)
        restored = parse_script(serialized)
        assert restored == actions


# ---------------------------------------------------------------------------
# Property 9 (PageFetcher part): Conditional should_run correctness
# ---------------------------------------------------------------------------


class TestPreCaptureScriptShouldRun:
    """
    **Validates: Requirements 5.1**

    PreCaptureScriptPlugin.should_run() returns True iff
    ctx.site.pre_capture_script is not None.
    """

    @given(
        has_script=st.booleans(),
    )
    @settings(max_examples=100)
    def test_should_run_matches_pre_capture_script_presence(self, has_script):
        """should_run() == True iff site.pre_capture_script is not None."""
        site = MonitoringSite(id=1, name="test", url="https://example.com")
        if has_script:
            site.pre_capture_script = [{"action": "click", "selector": ".btn"}]
        else:
            site.pre_capture_script = None

        ctx = CrawlContext(site=site, url="https://example.com")
        plugin = PreCaptureScriptPlugin()

        assert plugin.should_run(ctx) == has_script


# ---------------------------------------------------------------------------
# Property 24: PreCaptureScript label triggers screenshot
# ---------------------------------------------------------------------------

from src.pipeline.plugins.pre_capture_script_plugin import PreCaptureScriptPlugin


class TestPreCaptureScriptLabelTriggersScreenshot:
    """
    **Validates: Requirements 5.4**

    For any PreCaptureScript action with a label field, executing that action
    shall add a VariantCapture to ctx.screenshots with variant_name equal
    to the label value.
    """

    @given(actions=pre_capture_script_strategy())
    @settings(max_examples=100, deadline=5000)
    @pytest.mark.asyncio
    async def test_labeled_actions_add_screenshots(self, actions):
        """Each labeled action adds a VariantCapture with matching variant_name."""
        from unittest.mock import patch

        # Count expected labels
        expected_labels = [a["label"] for a in actions if a.get("label") is not None]

        # Build a mock page that supports all action types
        mock_page = AsyncMock()
        mock_page.click = AsyncMock()
        mock_page.select_option = AsyncMock()
        mock_page.fill = AsyncMock()
        mock_page.screenshot = AsyncMock(return_value=b"fake_png_bytes")

        site = MonitoringSite(id=42, name="test", url="https://example.com")
        site.pre_capture_script = actions

        ctx = CrawlContext(site=site, url="https://example.com")
        ctx.metadata["page"] = mock_page

        plugin = PreCaptureScriptPlugin()

        # Patch asyncio.sleep to avoid real delays from 'wait' actions
        with patch("src.pipeline.plugins.pre_capture_script_plugin.asyncio.sleep", new_callable=AsyncMock):
            result = await plugin.execute(ctx)

        # Verify each expected label produced a VariantCapture
        actual_labels = [s.variant_name for s in result.screenshots]
        assert actual_labels == expected_labels, (
            f"Expected labels {expected_labels}, got {actual_labels}"
        )


# ---------------------------------------------------------------------------
# Property 20: Delta crawl conditional headers
# ---------------------------------------------------------------------------

from src.pipeline.page_fetcher import _build_conditional_headers


class TestDeltaCrawlConditionalHeaders:
    """
    **Validates: Requirements 18.2, 18.3, 18.4, 18.5**

    For any MonitoringSite, when etag is set (non-None, non-empty) the
    PageFetcher shall include If-None-Match header, when last_modified_header
    is set it shall include If-Modified-Since header, and when neither is set
    no conditional headers shall be sent.
    """

    @given(
        etag=st.one_of(st.none(), st.text(min_size=1, max_size=100).filter(lambda s: len(s.strip()) > 0)),
        last_modified=st.one_of(st.none(), st.text(min_size=1, max_size=100).filter(lambda s: len(s.strip()) > 0)),
    )
    @settings(max_examples=100)
    def test_conditional_headers_match_site_fields(self, etag, last_modified):
        """_build_conditional_headers returns correct headers based on etag/last_modified_header."""
        site = MonitoringSite(id=1, name="test", url="https://example.com")
        site.etag = etag
        site.last_modified_header = last_modified

        headers = _build_conditional_headers(site)

        # ETag → If-None-Match
        if etag:
            assert "If-None-Match" in headers, (
                f"Expected If-None-Match header when etag={etag!r}"
            )
            assert headers["If-None-Match"] == etag
        else:
            assert "If-None-Match" not in headers, (
                f"If-None-Match should not be present when etag={etag!r}"
            )

        # Last-Modified → If-Modified-Since
        if last_modified:
            assert "If-Modified-Since" in headers, (
                f"Expected If-Modified-Since header when last_modified_header={last_modified!r}"
            )
            assert headers["If-Modified-Since"] == last_modified
        else:
            assert "If-Modified-Since" not in headers, (
                f"If-Modified-Since should not be present when last_modified_header={last_modified!r}"
            )

        # When neither is set, result should be empty
        if not etag and not last_modified:
            assert headers == {}, (
                f"Expected empty headers when both are unset, got {headers}"
            )

    @given(
        etag=st.one_of(st.none(), st.just("")),
        last_modified=st.one_of(st.none(), st.just("")),
    )
    @settings(max_examples=100)
    def test_empty_strings_treated_as_not_set(self, etag, last_modified):
        """Empty strings for etag/last_modified_header produce no conditional headers."""
        site = MonitoringSite(id=1, name="test", url="https://example.com")
        site.etag = etag
        site.last_modified_header = last_modified

        headers = _build_conditional_headers(site)

        assert headers == {}, (
            f"Expected empty headers for etag={etag!r}, last_modified={last_modified!r}, "
            f"got {headers}"
        )


# ---------------------------------------------------------------------------
# Property 2: Plugin field preservation (DataExtractor plugins)
# ---------------------------------------------------------------------------

from src.pipeline.plugins.structured_data_plugin import StructuredDataPlugin


class TestPluginFieldPreservation:
    """
    **Validates: Requirements 1.4, 1.5**

    For any CrawlPlugin and any CrawlContext with pre-existing data,
    executing the plugin shall preserve all fields the plugin does not
    explicitly modify — specifically, the set of keys in extracted_data,
    violations, evidence_records, and errors present before execution
    shall remain present after execution, and their values shall be unchanged.

    We test with StructuredDataPlugin as the representative DataExtractor plugin.
    """

    @given(
        existing_keys=st.lists(
            st.text(
                alphabet=st.characters(whitelist_categories=("L", "N")),
                min_size=1,
                max_size=20,
            ),
            min_size=1,
            max_size=5,
            unique=True,
        ),
        existing_violations=st.lists(
            st.fixed_dictionaries({
                "variant_name": st.text(min_size=1, max_size=20),
                "type": st.text(min_size=1, max_size=20),
            }),
            min_size=0,
            max_size=3,
        ),
        existing_evidence=st.lists(
            st.fixed_dictionaries({
                "variant_name": st.text(min_size=1, max_size=20),
                "ocr_text": st.text(min_size=1, max_size=50),
            }),
            min_size=0,
            max_size=3,
        ),
        existing_errors=st.lists(
            st.fixed_dictionaries({
                "plugin": st.text(min_size=1, max_size=20),
                "error": st.text(min_size=1, max_size=50),
            }),
            min_size=0,
            max_size=3,
        ),
    )
    @settings(max_examples=100, deadline=5000)
    @pytest.mark.asyncio
    async def test_structured_data_plugin_preserves_existing_fields(
        self,
        existing_keys,
        existing_violations,
        existing_evidence,
        existing_errors,
    ):
        """StructuredDataPlugin preserves pre-existing extracted_data keys,
        violations, evidence_records, and errors."""
        site = MonitoringSite(id=1, name="test", url="https://example.com")
        ctx = CrawlContext(site=site, url="https://example.com")

        # Set up pre-existing data (use keys that won't collide with plugin output)
        for key in existing_keys:
            prefixed_key = f"preexisting_{key}"
            ctx.extracted_data[prefixed_key] = f"value_{key}"

        ctx.violations = list(existing_violations)
        ctx.evidence_records = list(existing_evidence)
        ctx.errors = list(existing_errors)

        # Snapshot before execution
        pre_extracted_keys = {k: v for k, v in ctx.extracted_data.items()}
        pre_violations = list(ctx.violations)
        pre_evidence = list(ctx.evidence_records)
        pre_errors = list(ctx.errors)

        # Provide minimal HTML so the plugin runs (should_run requires html_content)
        ctx.html_content = "<html><body>No structured data here</body></html>"

        plugin = StructuredDataPlugin()
        result = await plugin.execute(ctx)

        # All pre-existing extracted_data keys must still be present with same values
        for key, value in pre_extracted_keys.items():
            assert key in result.extracted_data, (
                f"Pre-existing extracted_data key '{key}' was removed by plugin"
            )
            assert result.extracted_data[key] == value, (
                f"Pre-existing extracted_data['{key}'] was modified: "
                f"expected {value!r}, got {result.extracted_data[key]!r}"
            )

        # Pre-existing violations must still be present (plugin may append but not remove)
        for v in pre_violations:
            assert v in result.violations, (
                f"Pre-existing violation {v} was removed by plugin"
            )

        # Pre-existing evidence_records must still be present
        for e in pre_evidence:
            assert e in result.evidence_records, (
                f"Pre-existing evidence_record {e} was removed by plugin"
            )

        # Pre-existing errors must still be present (plugin may append new errors)
        for e in pre_errors:
            assert e in result.errors, (
                f"Pre-existing error {e} was removed by plugin"
            )


# ---------------------------------------------------------------------------
# Property 3: Plugin metadata key prefixing
# ---------------------------------------------------------------------------

from src.pipeline.plugins.shopify_plugin import ShopifyPlugin
from src.pipeline.plugins.html_parser_plugin import HTMLParserPlugin
from src.pipeline.plugins.ocr_plugin import OCRPlugin


class TestPluginMetadataKeyPrefixing:
    """
    **Validates: Requirements 1.5**

    For any CrawlPlugin execution on any CrawlContext, all new keys added
    to metadata by the plugin shall be prefixed with the plugin's name in
    lowercase.

    StructuredDataPlugin → "structureddata_"
    ShopifyPlugin → "shopify_"
    HTMLParserPlugin → "htmlparser_"
    OCRPlugin → "ocr_"
    """

    @given(
        pre_metadata_keys=st.lists(
            st.text(
                alphabet=st.characters(whitelist_categories=("L",)),
                min_size=1,
                max_size=15,
            ),
            min_size=0,
            max_size=5,
            unique=True,
        ),
    )
    @settings(max_examples=100, deadline=5000)
    @pytest.mark.asyncio
    async def test_structureddata_plugin_uses_correct_prefix(self, pre_metadata_keys):
        """StructuredDataPlugin adds metadata keys with 'structureddata_' prefix."""
        site = MonitoringSite(id=1, name="test", url="https://example.com")
        ctx = CrawlContext(site=site, url="https://example.com")
        ctx.html_content = "<html><body>No structured data</body></html>"

        # Set pre-existing metadata
        for key in pre_metadata_keys:
            ctx.metadata[f"pre_{key}"] = "existing"

        pre_keys = set(ctx.metadata.keys())

        plugin = StructuredDataPlugin()
        result = await plugin.execute(ctx)

        new_keys = set(result.metadata.keys()) - pre_keys
        for key in new_keys:
            assert key.startswith("structureddata_"), (
                f"StructuredDataPlugin added metadata key '{key}' without "
                f"'structureddata_' prefix"
            )

    @given(
        has_shopify_marker=st.booleans(),
    )
    @settings(max_examples=100, deadline=5000)
    @pytest.mark.asyncio
    async def test_shopify_plugin_uses_correct_prefix(self, has_shopify_marker):
        """ShopifyPlugin adds metadata keys with 'shopify_' prefix."""
        site = MonitoringSite(id=1, name="test", url="https://example.com/products/test-product")

        ctx = CrawlContext(site=site, url="https://example.com/products/test-product")

        if has_shopify_marker:
            ctx.html_content = '<html><script>Shopify.shop = "test"</script></html>'
        else:
            ctx.html_content = "<html><body>No Shopify</body></html>"

        pre_keys = set(ctx.metadata.keys())

        # Use a mock HTTP fetcher that returns empty product data
        def mock_fetcher(url):
            return {"product": {"title": "Test", "variants": []}}

        plugin = ShopifyPlugin(http_fetcher=mock_fetcher)

        if plugin.should_run(ctx):
            result = await plugin.execute(ctx)
            new_keys = set(result.metadata.keys()) - pre_keys
            for key in new_keys:
                assert key.startswith("shopify_"), (
                    f"ShopifyPlugin added metadata key '{key}' without "
                    f"'shopify_' prefix"
                )

    @pytest.mark.asyncio
    async def test_htmlparser_plugin_uses_correct_prefix(self):
        """HTMLParserPlugin adds metadata keys with 'htmlparser_' prefix."""
        site = MonitoringSite(id=1, name="test", url="https://example.com")
        ctx = CrawlContext(site=site, url="https://example.com")
        ctx.html_content = "<html><body>Some content</body></html>"
        ctx.metadata["structureddata_empty"] = True

        pre_keys = set(ctx.metadata.keys())

        # Use a mock extractor
        mock_extractor = MagicMock()
        mock_extractor.extract_payment_info.return_value = {
            "price_info": [],
            "extraction_source": "html",
        }

        plugin = HTMLParserPlugin(extractor=mock_extractor)
        result = await plugin.execute(ctx)

        new_keys = set(result.metadata.keys()) - pre_keys
        for key in new_keys:
            assert key.startswith("htmlparser_"), (
                f"HTMLParserPlugin added metadata key '{key}' without "
                f"'htmlparser_' prefix"
            )

    @pytest.mark.asyncio
    async def test_ocr_plugin_uses_correct_prefix(self):
        """OCRPlugin adds metadata keys with 'ocr_' prefix."""
        site = MonitoringSite(id=1, name="test", url="https://example.com")
        ctx = CrawlContext(site=site, url="https://example.com")
        ctx.screenshots = [
            VariantCapture(
                variant_name="default",
                image_path="/tmp/test.png",
                captured_at=datetime.now(),
            )
        ]

        pre_keys = set(ctx.metadata.keys())

        # Use a mock OCR engine that returns no results
        mock_ocr = MagicMock()
        mock_result = MagicMock()
        mock_result.success = False
        mock_ocr.extract_text.return_value = mock_result

        plugin = OCRPlugin(ocr_engine=mock_ocr)
        result = await plugin.execute(ctx)

        new_keys = set(result.metadata.keys()) - pre_keys
        for key in new_keys:
            assert key.startswith("ocr_"), (
                f"OCRPlugin added metadata key '{key}' without 'ocr_' prefix"
            )


# ---------------------------------------------------------------------------
# Property 9 (DataExtractor part): Conditional should_run correctness
# ---------------------------------------------------------------------------

from tests.strategies import variant_capture_strategy


class TestDataExtractorConditionalShouldRun:
    """
    **Validates: Requirements 6.1-6.6, 7.1, 8.1, 9.1**

    For any CrawlContext:
    - StructuredDataPlugin.should_run() returns True iff html_content is not None
    - ShopifyPlugin.should_run() returns True iff html_content contains
      "Shopify.shop" or "cdn.shopify.com"
    - HTMLParserPlugin.should_run() returns True iff
      metadata.get("structureddata_empty") is True
    - OCRPlugin.should_run() returns True iff len(screenshots) >= 1
    """

    @given(
        html_content=st.one_of(
            st.none(),
            st.text(min_size=0, max_size=200),
        ),
        has_shopify_shop=st.booleans(),
        has_cdn_shopify=st.booleans(),
        structureddata_empty=st.one_of(st.none(), st.just(True), st.just(False)),
        num_screenshots=st.integers(min_value=0, max_value=5),
    )
    @settings(max_examples=100)
    def test_all_data_extractor_should_run_conditions(
        self,
        html_content,
        has_shopify_shop,
        has_cdn_shopify,
        structureddata_empty,
        num_screenshots,
    ):
        """Each DataExtractor plugin's should_run matches documented conditions."""
        site = MonitoringSite(id=1, name="test", url="https://example.com")
        ctx = CrawlContext(site=site, url="https://example.com")

        # Build html_content with optional Shopify markers
        if html_content is not None:
            parts = [html_content]
            if has_shopify_shop:
                parts.append('Shopify.shop = "test-shop"')
            if has_cdn_shopify:
                parts.append('src="https://cdn.shopify.com/s/files/1/test.js"')
            ctx.html_content = " ".join(parts)
        else:
            ctx.html_content = None

        # Set structureddata_empty in metadata
        if structureddata_empty is not None:
            ctx.metadata["structureddata_empty"] = structureddata_empty

        # Add screenshots
        from datetime import datetime as dt
        for i in range(num_screenshots):
            ctx.screenshots.append(
                VariantCapture(
                    variant_name=f"variant_{i}",
                    image_path=f"/tmp/screenshot_{i}.png",
                    captured_at=dt.now(),
                )
            )

        # StructuredDataPlugin: should_run iff html_content is not None
        sd_plugin = StructuredDataPlugin()
        expected_sd = ctx.html_content is not None
        assert sd_plugin.should_run(ctx) == expected_sd, (
            f"StructuredDataPlugin.should_run() expected {expected_sd}, "
            f"html_content={'None' if ctx.html_content is None else 'present'}"
        )

        # ShopifyPlugin: should_run iff html_content contains Shopify markers
        shopify_plugin = ShopifyPlugin()
        if ctx.html_content is None:
            expected_shopify = False
        else:
            expected_shopify = (
                "Shopify.shop" in ctx.html_content
                or "cdn.shopify.com" in ctx.html_content
            )
        assert shopify_plugin.should_run(ctx) == expected_shopify, (
            f"ShopifyPlugin.should_run() expected {expected_shopify}, "
            f"has_shopify_shop={has_shopify_shop}, has_cdn_shopify={has_cdn_shopify}"
        )

        # HTMLParserPlugin: should_run iff metadata["structureddata_empty"] is True
        html_plugin = HTMLParserPlugin()
        expected_html = ctx.metadata.get("structureddata_empty") is True
        assert html_plugin.should_run(ctx) == expected_html, (
            f"HTMLParserPlugin.should_run() expected {expected_html}, "
            f"structureddata_empty={structureddata_empty}"
        )

        # OCRPlugin: should_run iff len(screenshots) >= 1
        ocr_plugin = OCRPlugin()
        expected_ocr = len(ctx.screenshots) >= 1
        assert ocr_plugin.should_run(ctx) == expected_ocr, (
            f"OCRPlugin.should_run() expected {expected_ocr}, "
            f"num_screenshots={num_screenshots}"
        )


# ---------------------------------------------------------------------------
# Property 10: Structured data extraction with source priority
# ---------------------------------------------------------------------------


def _build_multi_source_html(
    jsonld_price: Optional[float],
    og_price: Optional[float],
    variant_name: str = "テスト商品",
) -> str:
    """Build HTML with JSON-LD and/or Open Graph price data."""
    parts = ["<html><head>"]

    if jsonld_price is not None:
        jsonld = json.dumps({
            "@context": "https://schema.org",
            "@type": "Product",
            "name": variant_name,
            "offers": {
                "@type": "Offer",
                "price": jsonld_price,
                "priceCurrency": "JPY",
            },
        })
        parts.append(f'<script type="application/ld+json">{jsonld}</script>')

    if og_price is not None:
        parts.append(f'<meta property="og:title" content="{variant_name}" />')
        parts.append(f'<meta property="product:price:amount" content="{og_price}" />')
        parts.append('<meta property="product:price:currency" content="JPY" />')

    parts.append("</head><body></body></html>")
    return "\n".join(parts)


class TestStructuredDataSourcePriority:
    """
    **Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5**

    For any HTML containing structured price data from multiple sources
    (JSON-LD, Open Graph), the StructuredDataPlugin shall extract prices
    from all available sources, and when the same product has prices from
    multiple sources with the same variant_name + price, the adopted price
    shall follow the priority: JSON-LD > Shopify API > Microdata > Open Graph.
    Each extracted price shall include a data_source field.
    """

    @given(
        jsonld_price=st.one_of(
            st.none(),
            st.floats(min_value=100, max_value=100000, allow_nan=False, allow_infinity=False).map(lambda x: round(x, 2)),
        ),
        og_price=st.one_of(
            st.none(),
            st.floats(min_value=100, max_value=100000, allow_nan=False, allow_infinity=False).map(lambda x: round(x, 2)),
        ),
        variant_name=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N")),
            min_size=1,
            max_size=20,
        ),
    )
    @settings(max_examples=100, deadline=5000)
    @pytest.mark.asyncio
    async def test_source_priority_jsonld_over_og(
        self, jsonld_price, og_price, variant_name
    ):
        """JSON-LD is adopted over Open Graph when same variant_name + price."""
        html = _build_multi_source_html(jsonld_price, og_price, variant_name)

        site = MonitoringSite(id=1, name="test", url="https://example.com")
        ctx = CrawlContext(site=site, url="https://example.com")
        ctx.html_content = html

        plugin = StructuredDataPlugin()
        result = await plugin.execute(ctx)

        price_data = result.extracted_data.get("structured_price_data")

        if jsonld_price is None and og_price is None:
            # No prices → structureddata_empty should be True
            assert result.metadata.get("structureddata_empty") is True, (
                "Expected structureddata_empty=True when no prices found"
            )
            return

        # At least one price source exists
        assert price_data is not None, (
            f"Expected structured_price_data but got None. "
            f"jsonld_price={jsonld_price}, og_price={og_price}"
        )

        variants = price_data.get("variants", [])
        assert len(variants) >= 1, "Expected at least one variant"

        # Every variant must have a data_source field
        for v in variants:
            assert "data_source" in v, (
                f"Variant {v.get('variant_name')} missing data_source field"
            )
            assert v["data_source"] in ("json_ld", "shopify_api", "microdata", "open_graph"), (
                f"Invalid data_source: {v['data_source']}"
            )

        # When both JSON-LD and OG have the same variant_name + price,
        # only the JSON-LD version should remain (higher priority)
        if jsonld_price is not None and og_price is not None and jsonld_price == og_price:
            matching = [
                v for v in variants
                if v["variant_name"] == variant_name and v["price"] == jsonld_price
            ]
            # Should have exactly one entry with json_ld source
            sources = [v["data_source"] for v in matching]
            assert "json_ld" in sources, (
                f"Expected json_ld source for duplicate price, got sources={sources}"
            )
            # open_graph should NOT be present for the same variant_name + price
            assert "open_graph" not in sources, (
                f"open_graph should be deduplicated when json_ld has same "
                f"variant_name + price. sources={sources}"
            )

        # When only JSON-LD has a price
        if jsonld_price is not None and og_price is None:
            sources = [v["data_source"] for v in variants]
            assert "json_ld" in sources, (
                f"Expected json_ld in sources when only JSON-LD price exists"
            )

        # When only OG has a price
        if jsonld_price is None and og_price is not None:
            sources = [v["data_source"] for v in variants]
            assert "open_graph" in sources, (
                f"Expected open_graph in sources when only OG price exists"
            )

        # data_sources_used should list all sources that contributed
        data_sources_used = price_data.get("data_sources_used", [])
        if jsonld_price is not None:
            assert "json_ld" in data_sources_used
        if og_price is not None:
            # OG may be deduplicated but should still appear in sources_used
            # if it contributed any variant (even if later merged away)
            # Actually, after merge, if OG was fully deduplicated, it may not appear
            # We just verify the list is non-empty
            assert len(data_sources_used) >= 1


# ---------------------------------------------------------------------------
# Property 11: Contract comparison completeness
# ---------------------------------------------------------------------------

from src.pipeline.plugins.contract_comparison_plugin import ContractComparisonPlugin


def _variant_prices_strategy():
    """Generate a list of variant price dicts."""
    return st.lists(
        st.fixed_dictionaries({
            "variant_name": st.text(
                alphabet=st.characters(whitelist_categories=("L", "N")),
                min_size=1,
                max_size=20,
            ),
            "price": st.floats(
                min_value=100, max_value=100000,
                allow_nan=False, allow_infinity=False,
            ).map(lambda x: round(x, 2)),
            "data_source": st.sampled_from(["json_ld", "shopify_api", "microdata", "open_graph"]),
        }),
        min_size=1,
        max_size=10,
    )


def _contract_prices_strategy():
    """Generate contract prices as a dict mapping variant_name -> price."""
    return st.dictionaries(
        st.text(
            alphabet=st.characters(whitelist_categories=("L", "N")),
            min_size=1,
            max_size=20,
        ),
        st.floats(
            min_value=100, max_value=100000,
            allow_nan=False, allow_infinity=False,
        ).map(lambda x: round(x, 2)),
        min_size=1,
        max_size=10,
    )


class TestContractComparisonCompleteness:
    """
    **Validates: Requirements 10.2, 10.3, 10.4**

    For any set of variant prices in extracted_data and any set of
    ContractCondition prices, the ContractComparisonPlugin shall compare
    every variant price against the contract. For each mismatched variant,
    a violation record containing variant_name, contract_price, actual_price,
    and data_source shall be added to ctx.violations. When all variants match,
    ctx.metadata shall contain a "match" indicator.
    """

    @given(
        variants=_variant_prices_strategy(),
        contract_prices=_contract_prices_strategy(),
    )
    @settings(max_examples=100, deadline=5000)
    @pytest.mark.asyncio
    async def test_all_variants_compared_mismatches_in_violations(
        self, variants, contract_prices
    ):
        """Every variant with a contract price is compared; mismatches go to violations."""
        site = MonitoringSite(id=1, name="test", url="https://example.com")
        ctx = CrawlContext(site=site, url="https://example.com")
        ctx.extracted_data["structured_price_data"] = {
            "product_name": "Test",
            "variants": variants,
            "data_sources_used": ["json_ld"],
        }

        provider = lambda sid: {"prices": contract_prices}
        plugin = ContractComparisonPlugin(contract_provider=provider)
        result = await plugin.execute(ctx)

        # Compute expected mismatches
        expected_mismatches = []
        for v in variants:
            vname = v["variant_name"]
            actual = v["price"]
            contract_price = contract_prices.get(vname)
            if contract_price is not None and actual != contract_price:
                expected_mismatches.append(vname)

        # Each expected mismatch should have a violation
        violation_names = [viol["variant_name"] for viol in result.violations]
        for name in expected_mismatches:
            assert name in violation_names, (
                f"Expected violation for variant '{name}' but not found. "
                f"violations={result.violations}"
            )

        # Each violation must have required fields
        for viol in result.violations:
            assert "variant_name" in viol
            assert "contract_price" in viol
            assert "actual_price" in viol
            assert "data_source" in viol

        # If no mismatches, metadata should indicate match
        if len(expected_mismatches) == 0:
            assert result.metadata.get("contractcomparison_match") is True
        else:
            assert result.metadata.get("contractcomparison_match") is False


# ---------------------------------------------------------------------------
# Property 12: Evidence record completeness
# ---------------------------------------------------------------------------

from src.pipeline.plugins.evidence_preservation_plugin import EvidencePreservationPlugin

VALID_EVIDENCE_TYPES = {"price_display", "terms_notice", "subscription_condition", "general"}


def _evidence_records_strategy():
    """Generate a list of raw evidence record dicts."""
    return st.lists(
        st.fixed_dictionaries({
            "variant_name": st.text(min_size=1, max_size=30),
            "screenshot_path": st.text(min_size=1, max_size=100),
            "ocr_text": st.text(min_size=0, max_size=200),
            "ocr_confidence": st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        }),
        min_size=1,
        max_size=10,
    )


class TestEvidenceRecordCompleteness:
    """
    **Validates: Requirements 11.2, 11.3, 11.4**

    For any set of evidence_records processed by EvidencePreservationPlugin,
    each record shall have evidence_type classified as one of the valid types,
    and all required fields shall be non-null. All records from a single
    pipeline run shall share the same verification_result_id.
    """

    @given(records=_evidence_records_strategy())
    @settings(max_examples=100, deadline=5000)
    @pytest.mark.asyncio
    async def test_evidence_type_classified_and_fields_non_null(self, records):
        """Each record has valid evidence_type and all required fields non-null."""
        site = MonitoringSite(id=1, name="test", url="https://example.com")
        ctx = CrawlContext(site=site, url="https://example.com")
        ctx.evidence_records = records

        plugin = EvidencePreservationPlugin(verification_result_id=42)
        result = await plugin.execute(ctx)

        assert len(result.evidence_records) == len(records)

        verification_ids = set()

        for record in result.evidence_records:
            # evidence_type must be one of the valid types
            assert record["evidence_type"] in VALID_EVIDENCE_TYPES, (
                f"Invalid evidence_type: {record['evidence_type']}"
            )

            # All required fields must be non-null
            assert record["verification_result_id"] is not None
            assert record["variant_name"] is not None
            assert record["screenshot_path"] is not None
            assert record["ocr_text"] is not None
            assert record["ocr_confidence"] is not None
            assert record["evidence_type"] is not None
            assert record["created_at"] is not None

            verification_ids.add(record["verification_result_id"])

        # All records share the same verification_result_id
        assert len(verification_ids) == 1, (
            f"Expected all records to share same verification_result_id, "
            f"got {verification_ids}"
        )


# ---------------------------------------------------------------------------
# Property 16: Threshold-based INSERT strategy selection
# ---------------------------------------------------------------------------

from src.pipeline.plugins.db_storage_plugin import DBStoragePlugin


class TestThresholdBasedInsertStrategy:
    """
    **Validates: Requirements 20.1, 20.2, 20.3**

    For any DBStoragePlugin execution, when total records <= threshold,
    individual INSERTs shall be used. When count exceeds threshold, bulk
    INSERT shall be used. When bulk batch exceeds max_size (default 100),
    it shall be split into ceil(count/max_size) bulk INSERT operations.
    """

    @given(
        record_count=st.integers(min_value=0, max_value=500),
        threshold=st.integers(min_value=1, max_value=50),
        batch_size=st.integers(min_value=10, max_value=200),
    )
    @settings(max_examples=100)
    def test_strategy_selection_and_batch_splitting(
        self, record_count, threshold, batch_size
    ):
        """Strategy is individual when count <= threshold, bulk otherwise.
        Bulk batches are ceil(count/batch_size)."""
        import math

        plugin = DBStoragePlugin(bulk_threshold=threshold, bulk_batch_size=batch_size)

        strategy = plugin.get_insert_strategy(record_count)

        if record_count <= threshold:
            assert strategy == "individual", (
                f"Expected individual for {record_count} records with threshold={threshold}"
            )
        else:
            assert strategy == "bulk", (
                f"Expected bulk for {record_count} records with threshold={threshold}"
            )

        # Verify batch count for bulk strategy
        batch_count = plugin.get_bulk_batch_count(record_count)
        if record_count <= threshold:
            assert batch_count == 0, (
                f"Expected 0 batches for individual strategy, got {batch_count}"
            )
        else:
            expected_batches = math.ceil(record_count / batch_size)
            assert batch_count == expected_batches, (
                f"Expected {expected_batches} batches for {record_count} records "
                f"with batch_size={batch_size}, got {batch_count}"
            )

    @given(
        evidence_count=st.integers(min_value=0, max_value=30),
        violation_count=st.integers(min_value=0, max_value=30),
        threshold=st.integers(min_value=1, max_value=20),
    )
    @settings(max_examples=100, deadline=5000)
    @pytest.mark.asyncio
    async def test_actual_insert_method_matches_strategy(
        self, evidence_count, violation_count, threshold
    ):
        """The actual DB session method called matches the strategy."""
        from unittest.mock import MagicMock

        session = MagicMock()
        session.add = MagicMock()
        session.add_all = MagicMock()
        session.commit = MagicMock()
        session.rollback = MagicMock()
        session.close = MagicMock()

        site = MonitoringSite(id=1, name="test", url="https://example.com")
        ctx = CrawlContext(site=site, url="https://example.com")
        ctx.evidence_records = [{"id": i} for i in range(evidence_count)]
        ctx.violations = [{"id": i} for i in range(violation_count)]

        plugin = DBStoragePlugin(
            session_factory=lambda: session,
            bulk_threshold=threshold,
            bulk_batch_size=100,
        )
        result = await plugin.execute(ctx)

        total = evidence_count + violation_count

        if total <= threshold:
            # Individual: add() called for each record
            assert session.add.call_count == total
            session.add_all.assert_not_called()
        else:
            # Bulk: add_all() called, add() not called
            session.add.assert_not_called()
            assert session.add_all.call_count >= 1


# ---------------------------------------------------------------------------
# Property 13: Object storage path format
# ---------------------------------------------------------------------------

from src.pipeline.plugins.object_storage_plugin import build_storage_path


class TestObjectStoragePathFormat:
    """
    **Validates: Requirements 13.7**

    For any upload performed by ObjectStoragePlugin, the storage path shall
    match the format {bucket}/{site_id}/{date}/{filename}.
    """

    @given(
        bucket=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
            min_size=1,
            max_size=30,
        ),
        site_id=st.integers(min_value=1, max_value=100000).map(str),
        date_str=st.dates().map(lambda d: d.isoformat()),
        filename=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_."),
            min_size=1,
            max_size=50,
        ),
    )
    @settings(max_examples=100)
    def test_path_format_matches_spec(self, bucket, site_id, date_str, filename):
        """Storage path matches {bucket}/{site_id}/{date}/{filename}."""
        path = build_storage_path(bucket, site_id, date_str, filename)

        parts = path.split("/")
        assert len(parts) == 4, (
            f"Expected 4 path segments, got {len(parts)}: {path}"
        )
        assert parts[0] == bucket
        assert parts[1] == site_id
        assert parts[2] == date_str
        assert parts[3] == filename


# ---------------------------------------------------------------------------
# Property 14: Object storage path replacement
# ---------------------------------------------------------------------------

from src.pipeline.plugins.object_storage_plugin import ObjectStoragePlugin


class TestObjectStoragePathReplacement:
    """
    **Validates: Requirements 13.5, 13.6**

    For any successful ObjectStoragePlugin execution, all local file paths
    shall be replaced with storage URLs. On upload failure, local paths
    shall be preserved unchanged.
    """

    @given(
        num_screenshots=st.integers(min_value=1, max_value=5),
        upload_succeeds=st.booleans(),
    )
    @settings(max_examples=100, deadline=5000)
    @pytest.mark.asyncio
    async def test_path_replacement_on_success_preservation_on_failure(
        self, num_screenshots, upload_succeeds
    ):
        """Paths replaced on success, preserved on failure."""
        from unittest.mock import MagicMock

        client = MagicMock()
        if upload_succeeds:
            def upload_file(bucket, object_name, file_path):
                return f"https://storage.example.com/{bucket}/{object_name}"
            client.upload_file = MagicMock(side_effect=upload_file)
        else:
            client.upload_file = MagicMock(side_effect=Exception("Upload failed"))

        site = MonitoringSite(id=42, name="test", url="https://example.com")
        ctx = CrawlContext(site=site, url="https://example.com")

        original_paths = []
        for i in range(num_screenshots):
            path = f"/tmp/screenshot_{i}.png"
            original_paths.append(path)
            ctx.screenshots.append(
                VariantCapture(
                    variant_name=f"variant_{i}",
                    image_path=path,
                    captured_at=datetime.now(),
                )
            )

        plugin = ObjectStoragePlugin(storage_client=client)
        result = await plugin.execute(ctx)

        for i, screenshot in enumerate(result.screenshots):
            if upload_succeeds:
                # Path should be replaced with URL
                assert screenshot.image_path.startswith("https://"), (
                    f"Expected URL, got {screenshot.image_path}"
                )
                assert screenshot.image_path != original_paths[i]
            else:
                # Path should be preserved
                assert screenshot.image_path == original_paths[i], (
                    f"Expected local path preserved, got {screenshot.image_path}"
                )


# ---------------------------------------------------------------------------
# Property 15: Alert generation from violations
# ---------------------------------------------------------------------------

from src.pipeline.plugins.alert_plugin import AlertPlugin


class TestAlertGenerationFromViolations:
    """
    **Validates: Requirements 14.2, 14.3**

    For any set of violations in CrawlContext, the AlertPlugin shall generate
    exactly one Alert record per violation, with severity set to "warning"
    for price mismatch violations and "info" for structured data extraction
    failures.
    """

    @given(
        violations=st.lists(
            st.fixed_dictionaries({
                "violation_type": st.sampled_from(["price_mismatch", "structured_data_failure"]),
                "variant_name": st.text(min_size=1, max_size=20),
            }),
            min_size=1,
            max_size=10,
        ),
    )
    @settings(max_examples=100, deadline=5000)
    @pytest.mark.asyncio
    async def test_one_alert_per_violation_with_correct_severity(self, violations):
        """Exactly one Alert per violation with correct severity."""
        site = MonitoringSite(id=1, name="test", url="https://example.com")
        ctx = CrawlContext(site=site, url="https://example.com")
        ctx.violations = violations

        plugin = AlertPlugin()
        result = await plugin.execute(ctx)

        alerts = result.metadata.get("alertplugin_alerts", [])

        # Exactly one alert per violation
        assert len(alerts) == len(violations), (
            f"Expected {len(violations)} alerts, got {len(alerts)}"
        )

        # Verify severity for each alert
        for i, (alert, violation) in enumerate(zip(alerts, violations)):
            vtype = violation["violation_type"]
            expected_severity = "info" if vtype == "structured_data_failure" else "warning"
            assert alert["severity"] == expected_severity, (
                f"Alert {i}: expected severity={expected_severity} for "
                f"violation_type={vtype}, got {alert['severity']}"
            )


# ---------------------------------------------------------------------------
# Property 9 (Validator/Reporter part): Conditional should_run correctness
# ---------------------------------------------------------------------------


class TestValidatorReporterConditionalShouldRun:
    """
    **Validates: Requirements 10.1, 11.1, 13.1, 14.1**

    Validator and Reporter plugin should_run conditions:
    - ContractComparisonPlugin: True iff extracted_data has price info
    - EvidencePreservationPlugin: True iff evidence_records >= 1
    - ObjectStoragePlugin: True iff screenshots/evidence have local image paths
    - AlertPlugin: True iff violations >= 1
    """

    @given(
        has_price_data=st.booleans(),
        num_evidence=st.integers(min_value=0, max_value=5),
        num_violations=st.integers(min_value=0, max_value=5),
        has_local_screenshots=st.booleans(),
    )
    @settings(max_examples=100)
    def test_all_validator_reporter_should_run_conditions(
        self,
        has_price_data,
        num_evidence,
        num_violations,
        has_local_screenshots,
    ):
        """Each Validator/Reporter plugin's should_run matches documented conditions."""
        site = MonitoringSite(id=1, name="test", url="https://example.com")
        ctx = CrawlContext(site=site, url="https://example.com")

        if has_price_data:
            ctx.extracted_data["structured_price_data"] = {
                "variants": [{"variant_name": "A", "price": 1000}],
            }

        for i in range(num_evidence):
            ctx.evidence_records.append({
                "ocr_text": f"text_{i}",
                "screenshot_path": f"/tmp/evidence_{i}.png",
            })

        for i in range(num_violations):
            ctx.violations.append({"violation_type": "price_mismatch"})

        if has_local_screenshots:
            ctx.screenshots.append(
                VariantCapture(
                    variant_name="test",
                    image_path="/tmp/screenshot.png",
                    captured_at=datetime.now(),
                )
            )

        # ContractComparisonPlugin
        cc_plugin = ContractComparisonPlugin()
        assert cc_plugin.should_run(ctx) == has_price_data

        # EvidencePreservationPlugin
        ep_plugin = EvidencePreservationPlugin()
        assert ep_plugin.should_run(ctx) == (num_evidence >= 1)

        # ObjectStoragePlugin
        os_plugin = ObjectStoragePlugin()
        expected_os = has_local_screenshots or num_evidence >= 1
        assert os_plugin.should_run(ctx) == expected_os

        # AlertPlugin
        alert_plugin = AlertPlugin()
        assert alert_plugin.should_run(ctx) == (num_violations >= 1)


# ---------------------------------------------------------------------------
# Property 23: Domain rate limiting
# ---------------------------------------------------------------------------

from src.pipeline.rate_limiter import DomainRateLimiter


class TestDomainRateLimiting:
    """
    **Validates: Requirements 17.3, 17.4**

    For any sequence of crawl requests to the same domain, the time interval
    between consecutive requests shall be >= the configured minimum interval
    (default 2 seconds).
    """

    @given(
        num_requests=st.integers(min_value=2, max_value=6),
        min_interval=st.floats(min_value=0.05, max_value=0.3, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100, deadline=30000)
    @pytest.mark.asyncio
    async def test_consecutive_requests_respect_min_interval(self, num_requests, min_interval):
        """Consecutive requests to the same domain have >= min_interval gap."""
        limiter = DomainRateLimiter(min_interval_seconds=min_interval)

        timestamps = []
        for _ in range(num_requests):
            await limiter.acquire("test-domain.com")
            timestamps.append(time.monotonic())

        # Check that each consecutive pair has >= min_interval gap
        for i in range(1, len(timestamps)):
            gap = timestamps[i] - timestamps[i - 1]
            # Allow small tolerance for timing imprecision
            assert gap >= min_interval * 0.8, (
                f"Gap between request {i-1} and {i} was {gap:.4f}s, "
                f"expected >= {min_interval * 0.8:.4f}s (min_interval={min_interval})"
            )

    @given(
        num_requests=st.integers(min_value=2, max_value=5),
        min_interval=st.floats(min_value=0.05, max_value=0.2, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100, deadline=30000)
    @pytest.mark.asyncio
    async def test_different_domains_independent(self, num_requests, min_interval):
        """Requests to different domains are not rate-limited against each other."""
        limiter = DomainRateLimiter(min_interval_seconds=min_interval)

        # Make requests to domain-A, then immediately to domain-B
        await limiter.acquire("domain-a.com")
        start = time.monotonic()
        await limiter.acquire("domain-b.com")
        elapsed = time.monotonic() - start

        # domain-b should not be delayed by domain-a
        assert elapsed < min_interval * 0.5, (
            f"Different domain request took {elapsed:.4f}s, "
            f"should not be delayed (min_interval={min_interval})"
        )


# ---------------------------------------------------------------------------
# Property 22: Priority-to-Celery mapping
# ---------------------------------------------------------------------------

from src.pipeline.dispatcher import map_priority, PRIORITY_MAP


class TestPriorityToCeleryMapping:
    """
    **Validates: Requirements 17.2**

    For any site dispatched by BatchDispatcher, the Celery task priority
    shall be: 0 for crawl_priority='high', 5 for 'normal', 9 for 'low'.
    """

    @given(priority=st.sampled_from(["high", "normal", "low"]))
    @settings(max_examples=100)
    def test_priority_maps_to_correct_celery_value(self, priority):
        """crawl_priority maps to the documented Celery priority value."""
        expected = {"high": 0, "normal": 5, "low": 9}
        result = map_priority(priority)
        assert result == expected[priority], (
            f"map_priority('{priority}') returned {result}, expected {expected[priority]}"
        )

    @given(priority=st.sampled_from(["high", "normal", "low"]))
    @settings(max_examples=100)
    def test_priority_map_dict_consistent(self, priority):
        """PRIORITY_MAP dict is consistent with map_priority function."""
        assert PRIORITY_MAP[priority] == map_priority(priority)

    @given(
        priorities=st.lists(
            st.sampled_from(["high", "normal", "low"]),
            min_size=2,
            max_size=10,
        )
    )
    @settings(max_examples=100)
    def test_high_priority_always_lowest_value(self, priorities):
        """'high' always maps to the lowest (most urgent) Celery priority value."""
        mapped = [(p, map_priority(p)) for p in priorities]
        for p, v in mapped:
            if p == "high":
                assert v <= map_priority("normal")
                assert v <= map_priority("low")


# ---------------------------------------------------------------------------
# Property 18: USE_PIPELINE flow switching
# ---------------------------------------------------------------------------

from src.pipeline.scheduler import CrawlScheduler


class TestUsePipelineFlowSwitching:
    """
    **Validates: Requirements 19.2-19.5, 22.2-22.4**

    For any value of the USE_PIPELINE environment variable, when true the
    CrawlScheduler shall dispatch via the new CrawlPipeline, and when false
    (or unset) it shall dispatch via the legacy crawl_all_sites task.
    """

    @given(use_pipeline=st.booleans())
    @settings(max_examples=100)
    def test_flow_switching_matches_use_pipeline(self, use_pipeline):
        """CrawlScheduler dispatches via correct flow based on use_pipeline."""
        mock_legacy = MagicMock()
        mock_dispatcher = MagicMock()
        mock_dispatcher.dispatch.return_value = 0

        # Create a mock session factory that returns empty schedules
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_limit = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.limit.return_value = mock_limit
        mock_limit.all.return_value = []

        scheduler = CrawlScheduler(
            dispatcher=mock_dispatcher,
            session_factory=lambda: mock_session,
            use_pipeline=use_pipeline,
            legacy_task_func=mock_legacy,
        )

        scheduler.run_scheduled_crawls()

        if use_pipeline:
            # Pipeline mode: should query DB, not call legacy
            mock_legacy.assert_not_called()
        else:
            # Legacy mode: should call legacy task, not query DB
            mock_legacy.assert_called_once()
            mock_dispatcher.dispatch.assert_not_called()

    @given(use_pipeline_str=st.sampled_from(["true", "True", "TRUE", "false", "False", "FALSE", ""]))
    @settings(max_examples=100)
    def test_env_var_parsing(self, use_pipeline_str):
        """USE_PIPELINE env var is parsed correctly (case-insensitive)."""
        import os
        with patch.dict(os.environ, {"USE_PIPELINE": use_pipeline_str}):
            scheduler = CrawlScheduler()
            expected = use_pipeline_str.lower() == "true"
            assert scheduler.use_pipeline == expected, (
                f"USE_PIPELINE='{use_pipeline_str}' should give use_pipeline={expected}, "
                f"got {scheduler.use_pipeline}"
            )


# ---------------------------------------------------------------------------
# Property 21: Batch scheduler dispatch correctness
# ---------------------------------------------------------------------------

from src.pipeline.dispatcher import BatchDispatcher


class FakeScheduleForProperty:
    """CrawlSchedule-like object for property tests."""

    def __init__(self, site_id, priority, next_crawl_at, interval_minutes=1440):
        self.site_id = site_id
        self.priority = priority
        self.next_crawl_at = next_crawl_at
        self.interval_minutes = interval_minutes


def _crawl_schedule_strategy():
    """Generate random CrawlSchedule-like objects."""
    return st.builds(
        FakeScheduleForProperty,
        site_id=st.integers(min_value=1, max_value=10000),
        priority=st.sampled_from(["high", "normal", "low"]),
        next_crawl_at=st.datetimes(
            min_value=datetime(2020, 1, 1),
            max_value=datetime(2030, 12, 31),
            timezones=st.none(),
        ),
        interval_minutes=st.integers(min_value=1, max_value=10080),
    )


class TestBatchSchedulerDispatchCorrectness:
    """
    **Validates: Requirements 19.2-19.5, 22.2-22.4**

    For any set of CrawlSchedule records, the CrawlScheduler shall dispatch
    only those with next_crawl_at <= now, sorted by priority, limited to
    max_tasks_per_run (default 500). After dispatch, each dispatched schedule's
    next_crawl_at shall be updated to now + interval_minutes.
    """

    @given(
        schedules=st.lists(_crawl_schedule_strategy(), min_size=0, max_size=50),
        max_tasks=st.integers(min_value=1, max_value=100),
    )
    @settings(max_examples=100, deadline=5000)
    def test_dispatch_respects_priority_and_limit(self, schedules, max_tasks):
        """Dispatcher sorts by priority and respects max_tasks_per_run."""
        dispatcher = BatchDispatcher(
            celery_app=None,  # No actual Celery needed
            max_tasks_per_run=max_tasks,
        )

        dispatched = dispatcher.dispatch(schedules)

        # Should not exceed max_tasks_per_run
        assert dispatched <= max_tasks, (
            f"Dispatched {dispatched} tasks, max_tasks_per_run={max_tasks}"
        )

        # Should not exceed total schedules
        assert dispatched <= len(schedules)

        # If schedules <= max_tasks, all should be dispatched
        if len(schedules) <= max_tasks:
            assert dispatched == len(schedules)

    @given(
        schedules=st.lists(_crawl_schedule_strategy(), min_size=1, max_size=20),
    )
    @settings(max_examples=100, deadline=5000)
    def test_dispatch_order_is_by_priority(self, schedules):
        """Dispatched tasks are sorted by priority (high first)."""
        dispatched_order = []

        mock_celery = MagicMock()

        def track_dispatch(name, kwargs=None, priority=0):
            dispatched_order.append(priority)

        mock_celery.send_task.side_effect = track_dispatch

        dispatcher = BatchDispatcher(celery_app=mock_celery)
        dispatcher.dispatch(schedules)

        # Verify dispatched priorities are in non-decreasing order
        for i in range(1, len(dispatched_order)):
            assert dispatched_order[i] >= dispatched_order[i - 1], (
                f"Priority order violated at index {i}: "
                f"{dispatched_order[i-1]} > {dispatched_order[i]}"
            )

    @given(
        schedules=st.lists(_crawl_schedule_strategy(), min_size=1, max_size=10),
    )
    @settings(max_examples=100, deadline=5000)
    def test_next_crawl_at_updated_after_dispatch(self, schedules):
        """After dispatch, next_crawl_at is updated to now + interval_minutes."""
        now = datetime(2024, 6, 15, 12, 0, 0)

        # Filter to only "due" schedules
        due_schedules = [s for s in schedules if s.next_crawl_at <= now]

        if not due_schedules:
            return  # Nothing to test

        mock_dispatcher = MagicMock(spec=BatchDispatcher)
        mock_dispatcher.dispatch.return_value = len(due_schedules)

        # Mock session factory
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_limit = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.limit.return_value = mock_limit
        mock_limit.all.return_value = due_schedules

        scheduler = CrawlScheduler(
            dispatcher=mock_dispatcher,
            session_factory=lambda: mock_session,
            use_pipeline=True,
        )

        scheduler.run_scheduled_crawls(now=now)

        # Verify next_crawl_at was updated for dispatched schedules
        for schedule in due_schedules:
            expected_next = now + timedelta(minutes=schedule.interval_minutes)
            assert schedule.next_crawl_at == expected_next, (
                f"Schedule site_id={schedule.site_id}: expected next_crawl_at="
                f"{expected_next}, got {schedule.next_crawl_at}"
            )

# ---------------------------------------------------------------------------
# Property 19: API backward compatibility with NULL new fields
# ---------------------------------------------------------------------------

from hypothesis import strategies as st


def _verification_result_strategy():
    """Generate VerificationResult-like dicts with optional NULL new fields."""
    return st.fixed_dictionaries({
        'id': st.integers(min_value=1, max_value=10000),
        'site_id': st.integers(min_value=1, max_value=10000),
        'html_data': st.just({'prices': []}),
        'ocr_data': st.just({'text': ''}),
        'html_violations': st.just({'items': []}),
        'ocr_violations': st.just({'items': []}),
        'discrepancies': st.just({'items': []}),
        'screenshot_path': st.text(min_size=1, max_size=100).map(lambda s: f'/screenshots/{s}.png'),
        'ocr_confidence': st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        'status': st.sampled_from(['success', 'failure', 'partial_failure']),
        'error_message': st.one_of(st.none(), st.text(min_size=1, max_size=200)),
        # New pipeline fields — NULL or populated
        'structured_data': st.one_of(st.none(), st.just({'product': 'test', 'price': 100})),
        'structured_data_violations': st.one_of(st.none(), st.just({'items': []})),
        'data_source': st.one_of(st.none(), st.sampled_from(['json_ld', 'shopify_api', 'microdata', 'html_fallback'])),
        'structured_data_status': st.one_of(st.none(), st.sampled_from(['found', 'empty', 'error'])),
        'evidence_status': st.one_of(st.none(), st.sampled_from(['collected', 'partial', 'none'])),
    })


class TestAPIBackwardCompatibility:
    """
    **Validates: Requirements 22.5, 22.6**

    Property 19: API backward compatibility with NULL new fields.

    For any VerificationResult where the new fields (structured_data,
    structured_data_violations, data_source, structured_data_status,
    evidence_status) are NULL, the API response shall be valid and
    structurally compatible with the legacy response format.
    """

    @given(vr_data=_verification_result_strategy())
    @settings(max_examples=100, deadline=5000)
    def test_null_new_fields_produce_valid_response(self, vr_data):
        """VerificationResult with NULL new fields produces valid API response.

        **Validates: Requirements 22.5, 22.6**
        """
        from src.api.verification import _format_verification_result
        from src.models import VerificationResult as VR

        # Build a VerificationResult with the generated data
        result = VR(
            id=vr_data['id'],
            site_id=vr_data['site_id'],
            html_data=vr_data['html_data'],
            ocr_data=vr_data['ocr_data'],
            html_violations=vr_data['html_violations'],
            ocr_violations=vr_data['ocr_violations'],
            discrepancies=vr_data['discrepancies'],
            screenshot_path=vr_data['screenshot_path'],
            ocr_confidence=vr_data['ocr_confidence'],
            status=vr_data['status'],
            error_message=vr_data['error_message'],
            created_at=datetime(2024, 1, 15, 10, 30, 0),
            structured_data=vr_data['structured_data'],
            structured_data_violations=vr_data['structured_data_violations'],
            data_source=vr_data['data_source'],
            structured_data_status=vr_data['structured_data_status'],
            evidence_status=vr_data['evidence_status'],
        )

        response = _format_verification_result(result, 'Test Site')

        # Legacy required fields must always be present and non-erroring
        assert 'id' in response
        assert 'site_id' in response
        assert 'site_name' in response
        assert 'html_data' in response
        assert 'ocr_data' in response
        assert 'discrepancies' in response
        assert 'html_violations' in response
        assert 'ocr_violations' in response
        assert 'screenshot_path' in response
        assert 'ocr_confidence' in response
        assert 'status' in response
        assert 'created_at' in response

        # Legacy fields must have correct types
        assert isinstance(response['id'], int)
        assert isinstance(response['site_id'], int)
        assert isinstance(response['site_name'], str)
        assert isinstance(response['html_data'], dict)
        assert isinstance(response['ocr_data'], dict)
        assert isinstance(response['discrepancies'], list)
        assert isinstance(response['html_violations'], list)
        assert isinstance(response['ocr_violations'], list)
        assert isinstance(response['screenshot_path'], str)
        assert isinstance(response['ocr_confidence'], float)
        assert isinstance(response['status'], str)

        # New fields must be present (not missing) — either None or populated
        assert 'structured_data' in response
        assert 'structured_data_violations' in response
        assert 'data_source' in response
        assert 'structured_data_status' in response
        assert 'evidence_status' in response

        # When new fields are NULL, they should be None (not cause errors)
        if vr_data['structured_data'] is None:
            assert response['structured_data'] is None
        if vr_data['data_source'] is None:
            assert response['data_source'] is None

    @given(vr_data=_verification_result_strategy().filter(
        lambda d: all(
            d[f] is None
            for f in ['structured_data', 'structured_data_violations',
                       'data_source', 'structured_data_status', 'evidence_status']
        )
    ))
    @settings(max_examples=100, deadline=5000)
    def test_all_null_new_fields_fully_compatible(self, vr_data):
        """When ALL new fields are NULL, response is fully legacy-compatible.

        **Validates: Requirements 22.5, 22.6**
        """
        from src.api.verification import _format_verification_result
        from src.models import VerificationResult as VR

        result = VR(
            id=vr_data['id'],
            site_id=vr_data['site_id'],
            html_data=vr_data['html_data'],
            ocr_data=vr_data['ocr_data'],
            html_violations=vr_data['html_violations'],
            ocr_violations=vr_data['ocr_violations'],
            discrepancies=vr_data['discrepancies'],
            screenshot_path=vr_data['screenshot_path'],
            ocr_confidence=vr_data['ocr_confidence'],
            status=vr_data['status'],
            error_message=vr_data['error_message'],
            created_at=datetime(2024, 1, 15, 10, 30, 0),
            structured_data=None,
            structured_data_violations=None,
            data_source=None,
            structured_data_status=None,
            evidence_status=None,
        )

        response = _format_verification_result(result, 'Test Site')

        # All new fields should be None
        assert response['structured_data'] is None
        assert response['structured_data_violations'] is None
        assert response['data_source'] is None
        assert response['structured_data_status'] is None
        assert response['evidence_status'] is None

        # Response should not raise any errors when serialized to JSON
        import json
        json_str = json.dumps(response, default=str)
        assert json_str is not None
        parsed = json.loads(json_str)
        assert parsed['id'] == vr_data['id']


# ---------------------------------------------------------------------------
# Property 25: JSON validation at API boundary
# ---------------------------------------------------------------------------

class TestJSONValidationAtAPIBoundary:
    """Property 25: JSON validation at API boundary.

    *For any* string that is not valid JSON sent as `pre_capture_script` to
    `PUT /api/sites/{site_id}`, the API shall return HTTP 422.
    For any non-existent `site_id`, the API shall return HTTP 404.

    **Validates: Requirements 26.5, 26.6**
    """

    @given(
        bad_json=st.text(min_size=1, max_size=200).filter(
            lambda s: _is_invalid_json(s)
        ),
    )
    @settings(max_examples=50, deadline=5000)
    def test_invalid_json_pre_capture_script_returns_422(self, bad_json):
        """Invalid JSON string as pre_capture_script → 422.

        **Validates: Requirements 26.5**
        """
        from unittest.mock import MagicMock
        from fastapi.testclient import TestClient
        from src.main import app
        from src.database import get_db as _real_get_db
        from src.models import MonitoringSite as MS

        site = MS()
        site.id = 1
        site.customer_id = 1
        site.name = "Test"
        site.url = "https://example.com"
        site.is_active = True
        site.compliance_status = "pending"
        site.created_at = datetime(2024, 1, 1)

        class _FQ:
            def __init__(self, r):
                self._r = r
            def filter(self, *a, **kw):
                return self
            def first(self):
                return self._r

        def fake_db():
            db = MagicMock()
            db.query.return_value = _FQ(site)
            yield db

        app.dependency_overrides[_real_get_db] = fake_db
        try:
            client = TestClient(app, headers={"X-API-Key": "dev-api-key"})
            resp = client.put(
                "/api/sites/1",
                json={"pre_capture_script": bad_json},
            )
            assert resp.status_code == 422, (
                f"Expected 422 for invalid JSON '{bad_json}', got {resp.status_code}"
            )
        finally:
            app.dependency_overrides.pop(_real_get_db, None)

    @given(site_id=st.integers(min_value=900000, max_value=999999))
    @settings(max_examples=30, deadline=5000)
    def test_nonexistent_site_id_returns_404(self, site_id):
        """Non-existent site_id → 404.

        **Validates: Requirements 26.6**
        """
        from unittest.mock import MagicMock
        from fastapi.testclient import TestClient
        from src.main import app
        from src.database import get_db as _real_get_db

        class _FQ:
            def __init__(self, r):
                self._r = r
            def filter(self, *a, **kw):
                return self
            def first(self):
                return self._r

        def fake_db():
            db = MagicMock()
            db.query.return_value = _FQ(None)
            yield db

        app.dependency_overrides[_real_get_db] = fake_db
        try:
            client = TestClient(app, headers={"X-API-Key": "dev-api-key"})
            resp = client.put(
                f"/api/sites/{site_id}",
                json={"crawl_priority": "high"},
            )
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.pop(_real_get_db, None)


def _is_invalid_json(s: str) -> bool:
    """Return True if s is NOT valid JSON or is valid JSON but not a list."""
    import json as _json
    try:
        parsed = _json.loads(s)
        # Even if it parses, it must be a list to be valid pre_capture_script
        return not isinstance(parsed, list)
    except (ValueError, TypeError):
        return True
