"""
Unit tests for JourneyPlugin (task 3.8).

Tests:
  - should_run() True/False based on plugin_config
  - Step execution with mocked Playwright page
  - Heuristic fallback when selector not found
  - Assertion types (no_new_fees, no_upsell_modal, no_preselected_subscription)
  - Invalid JourneyScript JSON error handling
  - Step execution error handling

**Validates: Requirements 3.1, 3.2, 3.9, 3.10, 3.11**
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models import MonitoringSite
from src.pipeline.context import CrawlContext
from src.pipeline.plugins.journey_plugin import JourneyPlugin


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_site(journey_script=None) -> MonitoringSite:
    site = MonitoringSite(id=1)
    if journey_script is not None:
        site.plugin_config = {
            "JourneyPlugin": {"journey_script": journey_script}
        }
    else:
        site.plugin_config = {}
    return site


def _make_ctx(journey_script=None, with_page: bool = True) -> CrawlContext:
    site = _make_site(journey_script)
    ctx = CrawlContext(site=site, url="https://example.com")
    if with_page:
        ctx.metadata["pagefetcher_page"] = _make_mock_page()
    return ctx


def _make_mock_page() -> AsyncMock:
    page = AsyncMock()
    page.click = AsyncMock()
    page.goto = AsyncMock()
    page.screenshot = AsyncMock(return_value=b"fake-png-data")

    # Mock locator
    mock_locator = AsyncMock()
    mock_locator.count = AsyncMock(return_value=0)
    mock_locator.nth = MagicMock(return_value=AsyncMock())
    page.locator = MagicMock(return_value=mock_locator)

    # Mock get_by_role
    mock_role_locator = AsyncMock()
    mock_role_locator.click = AsyncMock()
    page.get_by_role = MagicMock(return_value=mock_role_locator)

    return page


_SIMPLE_SCRIPT = json.dumps([
    {"step": "add_to_cart", "selector": "#add-to-cart"}
])

_SCRIPT_WITH_ASSERTIONS = json.dumps([
    {
        "step": "add_to_cart",
        "selector": "#add-to-cart",
        "assert": {"no_new_fees": True},
    }
])

_MULTI_STEP_SCRIPT = json.dumps([
    {"step": "add_to_cart", "selector": "#add-to-cart"},
    {"step": "goto_checkout", "url": "https://example.com/checkout"},
])


# ---------------------------------------------------------------------------
# Tests — should_run
# ---------------------------------------------------------------------------


class TestShouldRun:
    def test_returns_true_when_journey_script_configured(self):
        ctx = _make_ctx(journey_script=_SIMPLE_SCRIPT)
        plugin = JourneyPlugin()
        assert plugin.should_run(ctx) is True

    def test_returns_false_when_no_plugin_config(self):
        ctx = _make_ctx(journey_script=None)
        plugin = JourneyPlugin()
        assert plugin.should_run(ctx) is False

    def test_returns_false_when_journey_script_empty(self):
        site = MonitoringSite(id=1)
        site.plugin_config = {"JourneyPlugin": {"journey_script": ""}}
        ctx = CrawlContext(site=site, url="https://example.com")
        plugin = JourneyPlugin()
        assert plugin.should_run(ctx) is False

    def test_returns_false_when_plugin_config_none(self):
        site = MonitoringSite(id=1)
        site.plugin_config = None
        ctx = CrawlContext(site=site, url="https://example.com")
        plugin = JourneyPlugin()
        assert plugin.should_run(ctx) is False


# ---------------------------------------------------------------------------
# Tests — execute() basic flow
# ---------------------------------------------------------------------------


class TestExecute:
    def test_execute_writes_journey_steps_metadata(self):
        ctx = _make_ctx(journey_script=_SIMPLE_SCRIPT)
        plugin = JourneyPlugin()
        asyncio.get_event_loop().run_until_complete(plugin.execute(ctx))

        assert "journey_steps" in ctx.metadata
        assert "journey_dom_diffs" in ctx.metadata

    def test_execute_records_step_result(self):
        ctx = _make_ctx(journey_script=_SIMPLE_SCRIPT)
        plugin = JourneyPlugin()
        asyncio.get_event_loop().run_until_complete(plugin.execute(ctx))

        steps = ctx.metadata["journey_steps"]
        assert len(steps) == 1
        assert steps[0]["step"] == "add_to_cart"

    def test_execute_multi_step_records_all_steps(self):
        ctx = _make_ctx(journey_script=_MULTI_STEP_SCRIPT)
        plugin = JourneyPlugin()
        asyncio.get_event_loop().run_until_complete(plugin.execute(ctx))

        steps = ctx.metadata["journey_steps"]
        assert len(steps) == 2

    def test_execute_no_page_records_error(self):
        ctx = _make_ctx(journey_script=_SIMPLE_SCRIPT, with_page=False)
        plugin = JourneyPlugin()
        asyncio.get_event_loop().run_until_complete(plugin.execute(ctx))

        assert len(ctx.errors) > 0
        assert ctx.metadata["journey_steps"] == []

    def test_execute_invalid_json_records_error(self):
        ctx = _make_ctx(journey_script="not valid json {{{")
        plugin = JourneyPlugin()
        asyncio.get_event_loop().run_until_complete(plugin.execute(ctx))

        assert len(ctx.errors) > 0
        assert ctx.metadata["journey_steps"] == []

    def test_execute_captures_screenshots(self):
        ctx = _make_ctx(journey_script=_SIMPLE_SCRIPT)
        plugin = JourneyPlugin()
        asyncio.get_event_loop().run_until_complete(plugin.execute(ctx))

        # Should have before + after screenshots
        assert len(ctx.screenshots) >= 1


# ---------------------------------------------------------------------------
# Tests — step execution and fallback
# ---------------------------------------------------------------------------


class TestExecuteStep:
    def test_click_with_selector_succeeds(self):
        ctx = _make_ctx(journey_script=_SIMPLE_SCRIPT)
        page = ctx.metadata["pagefetcher_page"]
        page.click = AsyncMock()

        plugin = JourneyPlugin()
        step = {"step": "add_to_cart", "selector": "#add-to-cart"}
        asyncio.get_event_loop().run_until_complete(plugin._execute_step(page, step))

        page.click.assert_called_once_with("#add-to-cart", timeout=5000)

    def test_fallback_to_get_by_role_when_selector_fails(self):
        ctx = _make_ctx(journey_script=_SIMPLE_SCRIPT)
        page = ctx.metadata["pagefetcher_page"]
        page.click = AsyncMock(side_effect=Exception("selector not found"))

        mock_role_locator = AsyncMock()
        mock_role_locator.click = AsyncMock()
        page.get_by_role = MagicMock(return_value=mock_role_locator)

        plugin = JourneyPlugin()
        step = {"step": "add_to_cart", "selector": "#missing"}
        asyncio.get_event_loop().run_until_complete(plugin._execute_step(page, step))

        page.get_by_role.assert_called_once()
        mock_role_locator.click.assert_called_once()

    def test_wait_step_does_not_click(self):
        page = _make_mock_page()
        plugin = JourneyPlugin()
        step = {"step": "wait", "wait_ms": 100}
        asyncio.get_event_loop().run_until_complete(plugin._execute_step(page, step))
        page.click.assert_not_called()

    def test_goto_checkout_navigates(self):
        page = _make_mock_page()
        plugin = JourneyPlugin()
        step = {"step": "goto_checkout", "url": "https://example.com/checkout"}
        asyncio.get_event_loop().run_until_complete(plugin._execute_step(page, step))
        page.goto.assert_called_once_with("https://example.com/checkout")


# ---------------------------------------------------------------------------
# Tests — get_by_role fallback
# ---------------------------------------------------------------------------


class TestGetRoleFallback:
    def test_add_to_cart_returns_button_locator(self):
        page = _make_mock_page()
        plugin = JourneyPlugin()
        step = {"step": "add_to_cart"}
        result = plugin._get_role_fallback(page, step)
        assert result is not None
        page.get_by_role.assert_called_once()
        call_args = page.get_by_role.call_args
        assert call_args[0][0] == "button"

    def test_unknown_step_returns_none(self):
        page = _make_mock_page()
        plugin = JourneyPlugin()
        step = {"step": "unknown_step"}
        result = plugin._get_role_fallback(page, step)
        assert result is None


# ---------------------------------------------------------------------------
# Tests — assertion evaluators
# ---------------------------------------------------------------------------


class TestAssertionEvaluators:
    def test_no_new_fees_passes_when_no_currency_added(self):
        page = _make_mock_page()
        plugin = JourneyPlugin()
        before = {"visible_texts": ["商品名", "数量: 1"]}
        after = {"visible_texts": ["商品名", "数量: 1"]}
        passed, evidence = asyncio.get_event_loop().run_until_complete(
            plugin._eval_no_new_fees(page, before, after)
        )
        assert passed is True

    def test_no_new_fees_fails_when_currency_added(self):
        page = _make_mock_page()
        plugin = JourneyPlugin()
        before = {"visible_texts": ["商品名"]}
        after = {"visible_texts": ["商品名", "追加料金: ¥500"]}
        passed, evidence = asyncio.get_event_loop().run_until_complete(
            plugin._eval_no_new_fees(page, before, after)
        )
        assert passed is False
        assert len(evidence["new_fee_texts"]) > 0

    def test_no_upsell_modal_passes_when_no_modal(self):
        page = _make_mock_page()
        # locator returns count=0 for all modal selectors
        mock_locator = AsyncMock()
        mock_locator.count = AsyncMock(return_value=0)
        page.locator = MagicMock(return_value=mock_locator)

        plugin = JourneyPlugin()
        passed, evidence = asyncio.get_event_loop().run_until_complete(
            plugin._eval_no_upsell_modal(page)
        )
        assert passed is True

    def test_no_preselected_subscription_passes_when_none(self):
        page = _make_mock_page()
        mock_locator = AsyncMock()
        mock_locator.count = AsyncMock(return_value=0)
        page.locator = MagicMock(return_value=mock_locator)

        plugin = JourneyPlugin()
        passed, evidence = asyncio.get_event_loop().run_until_complete(
            plugin._eval_no_preselected_subscription(page)
        )
        assert passed is True


# ---------------------------------------------------------------------------
# Tests — error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_step_error_records_error_and_stops(self):
        ctx = _make_ctx(journey_script=_MULTI_STEP_SCRIPT)
        page = ctx.metadata["pagefetcher_page"]
        # First click fails, no role fallback
        page.click = AsyncMock(side_effect=Exception("click failed"))
        page.get_by_role = MagicMock(return_value=AsyncMock(
            click=AsyncMock(side_effect=Exception("role fallback also failed"))
        ))

        plugin = JourneyPlugin()
        asyncio.get_event_loop().run_until_complete(plugin.execute(ctx))

        # Should have recorded an error
        assert len(ctx.errors) > 0
        # Should have stopped after first failing step
        steps = ctx.metadata["journey_steps"]
        assert len(steps) == 1  # only first step recorded before stopping

    def test_invalid_script_records_error_and_returns_empty(self):
        ctx = _make_ctx(journey_script='[{"step": "invalid_type"}]')
        plugin = JourneyPlugin()
        asyncio.get_event_loop().run_until_complete(plugin.execute(ctx))

        assert len(ctx.errors) > 0
        assert ctx.metadata["journey_steps"] == []
