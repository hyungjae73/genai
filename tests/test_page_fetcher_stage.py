"""
Unit tests for PageFetcherStage.

Feature: crawl-pipeline-architecture
Validates: Requirements 23.1, 23.2, 23.3, 18.2, 18.3, 18.4, 18.5

Tests use mock Playwright objects since Playwright may not be installed.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from src.models import MonitoringSite
from src.pipeline.context import CrawlContext, VariantCapture
from src.pipeline.page_fetcher import (
    PageFetcherStage,
    _build_conditional_headers,
)


# --- Mock helpers ---


def _make_site(**kwargs) -> MonitoringSite:
    """Create a MonitoringSite with defaults."""
    defaults = {
        "id": 1,
        "name": "Test Site",
        "url": "https://example.com",
        "etag": None,
        "last_modified_header": None,
        "pre_capture_script": None,
    }
    defaults.update(kwargs)
    return MonitoringSite(**defaults)


def _make_ctx(site=None, **kwargs) -> CrawlContext:
    """Create a CrawlContext with defaults."""
    if site is None:
        site = _make_site()
    defaults = {"site": site, "url": site.url}
    defaults.update(kwargs)
    return CrawlContext(**defaults)


def _make_mock_response(status=200, headers=None):
    """Create a mock Playwright Response."""
    if headers is None:
        headers = {}
    response = MagicMock()
    response.status = status
    response.headers = headers
    return response


def _make_mock_page(response=None, content="<html><body>Test</body></html>"):
    """Create a mock Playwright Page with common methods."""
    page = AsyncMock()
    page.context = AsyncMock()
    page.context.set_extra_http_headers = AsyncMock()

    if response is None:
        response = _make_mock_response()
    page.goto = AsyncMock(return_value=response)
    page.content = AsyncMock(return_value=content)
    page.screenshot = AsyncMock(return_value=b"fake_screenshot_bytes")
    page.wait_for_timeout = AsyncMock()
    page.set_extra_http_headers = AsyncMock()
    page.keyboard = AsyncMock()
    page.keyboard.press = AsyncMock()
    page.query_selector_all = AsyncMock(return_value=[])
    page.is_closed = MagicMock(return_value=False)
    page.close = AsyncMock()
    return page


def _make_mock_browser_pool(page=None, response=None):
    """Create a mock BrowserPool."""
    if page is None:
        page = _make_mock_page(response=response)
    browser = MagicMock()
    browser.is_connected = MagicMock(return_value=True)

    pool = AsyncMock()
    pool.acquire = AsyncMock(return_value=(browser, page))
    pool.release = AsyncMock()
    return pool, browser, page


# --- Tests for _build_conditional_headers ---


class TestBuildConditionalHeaders:
    """Validates: Requirements 18.2, 18.5"""

    def test_no_headers_when_no_etag_or_last_modified(self):
        """Req 18.5: 未設定時は条件付きヘッダーを付与しない。"""
        site = _make_site(etag=None, last_modified_header=None)
        headers = _build_conditional_headers(site)
        assert headers == {}

    def test_if_none_match_when_etag_set(self):
        """Req 18.2: etag 設定時に If-None-Match ヘッダーを付与する。"""
        site = _make_site(etag='"abc123"')
        headers = _build_conditional_headers(site)
        assert headers == {"If-None-Match": '"abc123"'}

    def test_if_modified_since_when_last_modified_set(self):
        """Req 18.2: last_modified_header 設定時に If-Modified-Since ヘッダーを付与する。"""
        site = _make_site(last_modified_header="Wed, 15 Jan 2024 10:30:00 GMT")
        headers = _build_conditional_headers(site)
        assert headers == {"If-Modified-Since": "Wed, 15 Jan 2024 10:30:00 GMT"}

    def test_both_headers_when_both_set(self):
        """Req 18.2: 両方設定時に両方のヘッダーを付与する。"""
        site = _make_site(
            etag='"abc123"',
            last_modified_header="Wed, 15 Jan 2024 10:30:00 GMT",
        )
        headers = _build_conditional_headers(site)
        assert headers == {
            "If-None-Match": '"abc123"',
            "If-Modified-Since": "Wed, 15 Jan 2024 10:30:00 GMT",
        }

    def test_empty_string_etag_treated_as_no_etag(self):
        """空文字列の etag はヘッダーを付与しない。"""
        site = _make_site(etag="")
        headers = _build_conditional_headers(site)
        assert headers == {}

    def test_empty_string_last_modified_treated_as_no_header(self):
        """空文字列の last_modified_header はヘッダーを付与しない。"""
        site = _make_site(last_modified_header="")
        headers = _build_conditional_headers(site)
        assert headers == {}


# --- Tests for PageFetcherStage execution order ---


class TestPageFetcherStageExecutionOrder:
    """Validates: Requirements 23.1, 23.2, 23.3"""

    @pytest.mark.asyncio
    async def test_full_execution_order(self):
        """Req 23.1: 固定順序で実行される。"""
        execution_log = []

        pool, browser, page = _make_mock_browser_pool()

        # Track execution order via side effects
        original_goto = page.goto

        async def tracked_goto(*args, **kwargs):
            execution_log.append("page_fetch")
            return _make_mock_response()

        page.goto = AsyncMock(side_effect=tracked_goto)

        async def tracked_screenshot(*args, **kwargs):
            execution_log.append("screenshot")
            return b"fake_bytes"

        page.screenshot = AsyncMock(side_effect=tracked_screenshot)

        stage = PageFetcherStage(browser_pool=pool)

        # Patch plugins to track execution
        async def locale_execute(ctx):
            execution_log.append("locale")
            ctx.metadata["locale_config"] = {"locale": "ja-JP"}
            return ctx

        async def pre_capture_execute(ctx):
            execution_log.append("pre_capture")
            return ctx

        async def modal_dismiss_execute(ctx):
            execution_log.append("modal_dismiss")
            return ctx

        stage._locale_plugin.execute = locale_execute
        stage._pre_capture_plugin.execute = pre_capture_execute
        stage._pre_capture_plugin.should_run = lambda ctx: True
        stage._modal_dismiss_plugin.execute = modal_dismiss_execute

        site = _make_site(pre_capture_script=[{"action": "click", "selector": ".btn"}])
        ctx = _make_ctx(site=site)
        await stage.execute(ctx)

        assert execution_log == [
            "locale",
            "page_fetch",
            "pre_capture",
            "modal_dismiss",
            "screenshot",
        ]

    @pytest.mark.asyncio
    async def test_pre_capture_skipped_when_should_run_false(self):
        """Req 23.2: PreCaptureScriptPlugin の should_run が False の場合スキップ。"""
        execution_log = []

        pool, browser, page = _make_mock_browser_pool()

        async def tracked_goto(*args, **kwargs):
            execution_log.append("page_fetch")
            return _make_mock_response()

        page.goto = AsyncMock(side_effect=tracked_goto)

        async def tracked_screenshot(*args, **kwargs):
            execution_log.append("screenshot")
            return b"fake_bytes"

        page.screenshot = AsyncMock(side_effect=tracked_screenshot)

        stage = PageFetcherStage(browser_pool=pool)

        async def locale_execute(ctx):
            execution_log.append("locale")
            ctx.metadata["locale_config"] = {}
            return ctx

        async def modal_dismiss_execute(ctx):
            execution_log.append("modal_dismiss")
            return ctx

        stage._locale_plugin.execute = locale_execute
        stage._modal_dismiss_plugin.execute = modal_dismiss_execute

        # No pre_capture_script → should_run returns False
        ctx = _make_ctx()
        await stage.execute(ctx)

        assert "pre_capture" not in execution_log
        assert execution_log == [
            "locale",
            "page_fetch",
            "modal_dismiss",
            "screenshot",
        ]

    @pytest.mark.asyncio
    async def test_html_content_set_from_page(self):
        """Req 23.3: HTML コンテンツを ctx.html_content に格納する。"""
        pool, browser, page = _make_mock_browser_pool()
        page.content = AsyncMock(return_value="<html><body>Hello</body></html>")

        stage = PageFetcherStage(browser_pool=pool)
        ctx = _make_ctx()
        result = await stage.execute(ctx)

        assert result.html_content == "<html><body>Hello</body></html>"

    @pytest.mark.asyncio
    async def test_screenshot_added_to_ctx(self):
        """Req 23.3: スクリーンショットを ctx.screenshots に格納する。"""
        pool, browser, page = _make_mock_browser_pool()

        stage = PageFetcherStage(browser_pool=pool)
        ctx = _make_ctx()
        result = await stage.execute(ctx)

        assert len(result.screenshots) == 1
        assert result.screenshots[0].variant_name == "default"
        assert "pagefetcher_source" in result.screenshots[0].metadata


# --- Tests for delta crawl ---


class TestPageFetcherStageDeltaCrawl:
    """Validates: Requirements 18.2, 18.3, 18.4, 18.5"""

    @pytest.mark.asyncio
    async def test_304_sets_not_modified_flag(self):
        """Req 18.3: 304 レスポンスで pagefetcher_not_modified フラグを設定。"""
        response = _make_mock_response(status=304)
        pool, browser, page = _make_mock_browser_pool(response=response)
        page.goto = AsyncMock(return_value=response)

        stage = PageFetcherStage(browser_pool=pool)
        ctx = _make_ctx()
        result = await stage.execute(ctx)

        assert result.metadata.get("pagefetcher_not_modified") is True

    @pytest.mark.asyncio
    async def test_304_skips_remaining_steps(self):
        """Req 18.3: 304 レスポンスでフルクロールをスキップ。"""
        response = _make_mock_response(status=304)
        pool, browser, page = _make_mock_browser_pool(response=response)
        page.goto = AsyncMock(return_value=response)

        stage = PageFetcherStage(browser_pool=pool)

        modal_called = False

        async def modal_execute(ctx):
            nonlocal modal_called
            modal_called = True
            return ctx

        stage._modal_dismiss_plugin.execute = modal_execute

        ctx = _make_ctx()
        result = await stage.execute(ctx)

        # Modal dismiss and screenshot should NOT have been called
        assert modal_called is False
        assert len(result.screenshots) == 0
        assert result.html_content is None

    @pytest.mark.asyncio
    async def test_200_saves_etag_to_metadata(self):
        """Req 18.4: 200 レスポンスで新しい ETag を metadata に記録。"""
        response = _make_mock_response(
            status=200, headers={"etag": '"new-etag-value"'}
        )
        pool, browser, page = _make_mock_browser_pool(response=response)
        page.goto = AsyncMock(return_value=response)

        stage = PageFetcherStage(browser_pool=pool)
        ctx = _make_ctx()
        result = await stage.execute(ctx)

        assert result.metadata.get("pagefetcher_etag") == '"new-etag-value"'

    @pytest.mark.asyncio
    async def test_200_saves_last_modified_to_metadata(self):
        """Req 18.4: 200 レスポンスで新しい Last-Modified を metadata に記録。"""
        response = _make_mock_response(
            status=200,
            headers={"last-modified": "Thu, 16 Jan 2024 12:00:00 GMT"},
        )
        pool, browser, page = _make_mock_browser_pool(response=response)
        page.goto = AsyncMock(return_value=response)

        stage = PageFetcherStage(browser_pool=pool)
        ctx = _make_ctx()
        result = await stage.execute(ctx)

        assert (
            result.metadata.get("pagefetcher_last_modified")
            == "Thu, 16 Jan 2024 12:00:00 GMT"
        )

    @pytest.mark.asyncio
    async def test_conditional_headers_sent_when_etag_set(self):
        """Req 18.2: etag 設定時に If-None-Match ヘッダーを送信。"""
        pool, browser, page = _make_mock_browser_pool()

        stage = PageFetcherStage(browser_pool=pool)
        site = _make_site(etag='"existing-etag"')
        ctx = _make_ctx(site=site)
        await stage.execute(ctx)

        # Verify set_extra_http_headers was called with conditional headers
        page.set_extra_http_headers.assert_called()
        call_args = page.set_extra_http_headers.call_args[0][0]
        assert call_args.get("If-None-Match") == '"existing-etag"'

    @pytest.mark.asyncio
    async def test_conditional_headers_sent_when_last_modified_set(self):
        """Req 18.2: last_modified_header 設定時に If-Modified-Since ヘッダーを送信。"""
        pool, browser, page = _make_mock_browser_pool()

        stage = PageFetcherStage(browser_pool=pool)
        site = _make_site(last_modified_header="Wed, 15 Jan 2024 10:30:00 GMT")
        ctx = _make_ctx(site=site)
        await stage.execute(ctx)

        page.set_extra_http_headers.assert_called()
        call_args = page.set_extra_http_headers.call_args[0][0]
        assert call_args.get("If-Modified-Since") == "Wed, 15 Jan 2024 10:30:00 GMT"

    @pytest.mark.asyncio
    async def test_no_conditional_headers_when_neither_set(self):
        """Req 18.5: 未設定時は条件付きヘッダーを付与しない。"""
        pool, browser, page = _make_mock_browser_pool()

        stage = PageFetcherStage(browser_pool=pool)
        ctx = _make_ctx()
        await stage.execute(ctx)

        # set_extra_http_headers should not be called for conditional headers
        # (it may be called for locale headers via context)
        # Check that page.set_extra_http_headers was NOT called
        # (conditional headers are set on page, not context)
        if page.set_extra_http_headers.called:
            # If called, it should not contain conditional headers
            call_args = page.set_extra_http_headers.call_args[0][0]
            assert "If-None-Match" not in call_args
            assert "If-Modified-Since" not in call_args


# --- Tests for browser pool lifecycle ---


class TestPageFetcherStageBrowserLifecycle:
    """Test browser acquire/release lifecycle."""

    @pytest.mark.asyncio
    async def test_browser_released_after_success(self):
        """ブラウザが正常完了後にプールに返却される。"""
        pool, browser, page = _make_mock_browser_pool()

        stage = PageFetcherStage(browser_pool=pool)
        ctx = _make_ctx()
        await stage.execute(ctx)

        pool.acquire.assert_called_once()
        pool.release.assert_called_once_with(browser, page)

    @pytest.mark.asyncio
    async def test_browser_released_after_error(self):
        """エラー発生後もブラウザがプールに返却される。"""
        pool, browser, page = _make_mock_browser_pool()
        page.goto = AsyncMock(side_effect=Exception("Navigation failed"))

        stage = PageFetcherStage(browser_pool=pool)
        ctx = _make_ctx()
        await stage.execute(ctx)

        pool.release.assert_called_once_with(browser, page)

    @pytest.mark.asyncio
    async def test_page_reference_cleaned_from_metadata(self):
        """page 参照が metadata からクリーンアップされる。"""
        pool, browser, page = _make_mock_browser_pool()

        stage = PageFetcherStage(browser_pool=pool)
        ctx = _make_ctx()
        result = await stage.execute(ctx)

        assert "page" not in result.metadata

    @pytest.mark.asyncio
    async def test_no_browser_pool_skips_browser_operations(self):
        """BrowserPool が None の場合、ブラウザ操作をスキップ。"""
        stage = PageFetcherStage(browser_pool=None)
        ctx = _make_ctx()
        result = await stage.execute(ctx)

        # Should still run LocalePlugin
        assert "locale_config" in result.metadata
        # But no screenshots or html_content
        assert len(result.screenshots) == 0
        assert result.html_content is None


# --- Tests for error handling ---


class TestPageFetcherStageErrorHandling:
    """Test error handling in PageFetcherStage."""

    @pytest.mark.asyncio
    async def test_navigation_error_recorded(self):
        """ナビゲーションエラーが ctx.errors に記録される。"""
        pool, browser, page = _make_mock_browser_pool()
        page.goto = AsyncMock(side_effect=Exception("Timeout"))

        stage = PageFetcherStage(browser_pool=pool)
        ctx = _make_ctx()
        result = await stage.execute(ctx)

        nav_errors = [e for e in result.errors if e.get("type") == "navigation_error"]
        assert len(nav_errors) == 1
        assert "Timeout" in nav_errors[0]["error"]

    @pytest.mark.asyncio
    async def test_screenshot_error_recorded(self):
        """スクリーンショットエラーが ctx.errors に記録される。"""
        pool, browser, page = _make_mock_browser_pool()
        page.screenshot = AsyncMock(side_effect=Exception("Screenshot failed"))

        stage = PageFetcherStage(browser_pool=pool)
        ctx = _make_ctx()
        result = await stage.execute(ctx)

        screenshot_errors = [
            e for e in result.errors if e.get("type") == "screenshot_error"
        ]
        assert len(screenshot_errors) == 1

    @pytest.mark.asyncio
    async def test_goto_returns_none_records_error(self):
        """page.goto が None を返した場合にエラーが記録される。"""
        pool, browser, page = _make_mock_browser_pool()
        page.goto = AsyncMock(return_value=None)

        stage = PageFetcherStage(browser_pool=pool)
        ctx = _make_ctx()
        result = await stage.execute(ctx)

        nav_errors = [e for e in result.errors if e.get("type") == "navigation_error"]
        assert len(nav_errors) == 1
        assert "None response" in nav_errors[0]["error"]

    @pytest.mark.asyncio
    async def test_plugin_error_does_not_stop_stage(self):
        """プラグインエラーがステージ全体を停止しない。"""
        pool, browser, page = _make_mock_browser_pool()

        stage = PageFetcherStage(browser_pool=pool)

        async def failing_locale(ctx):
            raise RuntimeError("Locale plugin failed")

        stage._locale_plugin.execute = failing_locale

        ctx = _make_ctx()
        result = await stage.execute(ctx)

        # Should still have attempted to continue
        # Error should be recorded
        locale_errors = [
            e for e in result.errors if "LocalePlugin" in e.get("plugin", "")
        ]
        assert len(locale_errors) == 1
