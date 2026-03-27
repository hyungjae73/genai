"""
Unit tests for ModalDismissPlugin.

Feature: crawl-pipeline-architecture
Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7

All Playwright objects are mocked since Playwright may not be installed
in the test environment.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models import MonitoringSite
from src.pipeline.context import CrawlContext
from src.pipeline.plugins.modal_dismiss_plugin import (
    CLOSE_BUTTON_SELECTORS,
    MODAL_SELECTORS,
    ModalDismissPlugin,
)


@pytest.fixture
def plugin():
    return ModalDismissPlugin()


@pytest.fixture
def site():
    return MonitoringSite(id=1, name="Test Site", url="https://example.com")


@pytest.fixture
def mock_page():
    """Create a mock Playwright page with no modals by default."""
    page = MagicMock()
    page.query_selector_all = AsyncMock(return_value=[])
    page.keyboard = MagicMock()
    page.keyboard.press = AsyncMock()
    return page


@pytest.fixture
def ctx(site, mock_page):
    c = CrawlContext(site=site, url="https://example.com")
    c.metadata["page"] = mock_page
    return c


def _make_modal_element(visible=True, close_button=None):
    """Create a mock modal element."""
    element = MagicMock()
    element.is_visible = AsyncMock(return_value=visible)
    if close_button:
        element.query_selector = AsyncMock(return_value=close_button)
    else:
        element.query_selector = AsyncMock(return_value=None)
    return element


def _make_close_button():
    """Create a mock close button."""
    btn = MagicMock()
    btn.click = AsyncMock()
    return btn


class TestModalDismissPluginShouldRun:
    """should_run() は常に True を返す。"""

    def test_always_returns_true(self, plugin, ctx):
        assert plugin.should_run(ctx) is True

    def test_returns_true_without_page(self, plugin, site):
        ctx = CrawlContext(site=site, url="https://example.com")
        assert plugin.should_run(ctx) is True


class TestModalDismissPluginExecuteNoModals:
    """モーダルが検出されない場合。"""

    @pytest.mark.asyncio
    async def test_no_modals_no_errors(self, plugin, ctx, mock_page):
        result = await plugin.execute(ctx)
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_queries_all_modal_selectors(self, plugin, ctx, mock_page):
        await plugin.execute(ctx)
        assert mock_page.query_selector_all.call_count == len(MODAL_SELECTORS)


class TestModalDismissPluginExecuteWithCloseButton:
    """閉じるボタンが見つかる場合。"""

    @pytest.mark.asyncio
    async def test_clicks_close_button(self, plugin, ctx, mock_page):
        """Req 4.3: 閉じるボタンをクリックして閉じる。"""
        close_btn = _make_close_button()
        modal = _make_modal_element(visible=True, close_button=close_btn)
        mock_page.query_selector_all = AsyncMock(
            side_effect=lambda sel: [modal] if sel == '[role="dialog"]' else []
        )

        with patch("src.pipeline.plugins.modal_dismiss_plugin.asyncio.sleep", new_callable=AsyncMock):
            await plugin.execute(ctx)

        close_btn.click.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_does_not_press_escape_when_button_found(self, plugin, ctx, mock_page):
        close_btn = _make_close_button()
        modal = _make_modal_element(visible=True, close_button=close_btn)
        mock_page.query_selector_all = AsyncMock(
            side_effect=lambda sel: [modal] if sel == '[role="dialog"]' else []
        )

        with patch("src.pipeline.plugins.modal_dismiss_plugin.asyncio.sleep", new_callable=AsyncMock):
            await plugin.execute(ctx)

        mock_page.keyboard.press.assert_not_awaited()


class TestModalDismissPluginExecuteEscapeFallback:
    """閉じるボタンが見つからない場合の Escape キーフォールバック。"""

    @pytest.mark.asyncio
    async def test_presses_escape_when_no_close_button(self, plugin, ctx, mock_page):
        """Req 4.4: 閉じるボタンが見つからない場合は Escape キーを送信する。"""
        modal = _make_modal_element(visible=True, close_button=None)
        mock_page.query_selector_all = AsyncMock(
            side_effect=lambda sel: [modal] if sel == '[role="dialog"]' else []
        )

        with patch("src.pipeline.plugins.modal_dismiss_plugin.asyncio.sleep", new_callable=AsyncMock):
            await plugin.execute(ctx)

        mock_page.keyboard.press.assert_awaited_once_with("Escape")


class TestModalDismissPluginWait:
    """モーダル閉じ後の待機。"""

    @pytest.mark.asyncio
    async def test_waits_500ms_after_dismiss(self, plugin, ctx, mock_page):
        """Req 4.5: 500ms 待機する。"""
        modal = _make_modal_element(visible=True, close_button=None)
        mock_page.query_selector_all = AsyncMock(
            side_effect=lambda sel: [modal] if sel == '[role="dialog"]' else []
        )

        with patch("src.pipeline.plugins.modal_dismiss_plugin.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await plugin.execute(ctx)

        mock_sleep.assert_awaited_once_with(0.5)


class TestModalDismissPluginInvisibleModals:
    """非表示モーダルはスキップされる。"""

    @pytest.mark.asyncio
    async def test_skips_invisible_modals(self, plugin, ctx, mock_page):
        modal = _make_modal_element(visible=False)
        mock_page.query_selector_all = AsyncMock(
            side_effect=lambda sel: [modal] if sel == '[role="dialog"]' else []
        )

        with patch("src.pipeline.plugins.modal_dismiss_plugin.asyncio.sleep", new_callable=AsyncMock):
            result = await plugin.execute(ctx)

        # No escape pressed, no close button clicked
        mock_page.keyboard.press.assert_not_awaited()
        assert len(result.errors) == 0


class TestModalDismissPluginErrorHandling:
    """エラーハンドリング。"""

    @pytest.mark.asyncio
    async def test_records_error_on_missing_page(self, plugin, site):
        """Req 4.6: page がない場合はエラーを記録する。"""
        ctx = CrawlContext(site=site, url="https://example.com")
        result = await plugin.execute(ctx)
        assert len(result.errors) == 1
        assert result.errors[0]["plugin"] == "ModalDismissPlugin"
        assert result.errors[0]["type"] == "missing_page"

    @pytest.mark.asyncio
    async def test_records_error_on_query_failure(self, plugin, ctx, mock_page):
        """Req 4.6: セレクタクエリ失敗時はエラーを記録しパイプライン継続。"""
        mock_page.query_selector_all = AsyncMock(side_effect=Exception("Query failed"))
        result = await plugin.execute(ctx)
        assert len(result.errors) > 0
        assert any(e["type"] == "modal_query_error" for e in result.errors)

    @pytest.mark.asyncio
    async def test_records_error_on_close_failure(self, plugin, ctx, mock_page):
        """Req 4.6: モーダル閉じ失敗時はエラーを記録しパイプライン継続。"""
        modal = MagicMock()
        modal.is_visible = AsyncMock(side_effect=Exception("Visibility check failed"))
        mock_page.query_selector_all = AsyncMock(
            side_effect=lambda sel: [modal] if sel == '[role="dialog"]' else []
        )

        result = await plugin.execute(ctx)
        assert any(e["type"] == "modal_close_error" for e in result.errors)

    @pytest.mark.asyncio
    async def test_preserves_existing_errors(self, plugin, ctx, mock_page):
        """既存のエラーを破壊しない。"""
        ctx.errors.append({"plugin": "other", "error": "previous"})
        result = await plugin.execute(ctx)
        assert result.errors[0]["plugin"] == "other"


class TestModalDismissPluginName:
    def test_name(self, plugin):
        assert plugin.name == "ModalDismissPlugin"
