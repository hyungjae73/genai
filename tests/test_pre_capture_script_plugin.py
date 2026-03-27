"""
Unit tests for PreCaptureScriptPlugin.

Feature: crawl-pipeline-architecture
Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6

All Playwright objects are mocked since Playwright may not be installed
in the test environment.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models import MonitoringSite
from src.pipeline.context import CrawlContext
from src.pipeline.plugins.pre_capture_script_plugin import (
    PreCaptureScriptPlugin,
    parse_script,
    serialize_script,
)


@pytest.fixture
def plugin():
    return PreCaptureScriptPlugin()


@pytest.fixture
def mock_page():
    """Create a mock Playwright page."""
    page = MagicMock()
    page.click = AsyncMock()
    page.select_option = AsyncMock()
    page.fill = AsyncMock()
    page.screenshot = AsyncMock(return_value=b"fake_png_bytes")
    return page


def _make_ctx(pre_capture_script=None, page=None):
    """Create a CrawlContext with the given pre_capture_script and page."""
    site = MonitoringSite(
        id=1, name="Test Site", url="https://example.com",
        pre_capture_script=pre_capture_script,
    )
    ctx = CrawlContext(site=site, url="https://example.com")
    if page is not None:
        ctx.metadata["page"] = page
    return ctx


# --- parse_script / serialize_script tests ---


class TestParseScript:
    """parse_script() のテスト。"""

    def test_parses_json_string(self):
        raw = json.dumps([{"action": "click", "selector": ".btn"}])
        actions = parse_script(raw)
        assert len(actions) == 1
        assert actions[0]["action"] == "click"

    def test_parses_list_directly(self):
        raw = [{"action": "wait", "ms": 1000}]
        actions = parse_script(raw)
        assert len(actions) == 1
        assert actions[0]["action"] == "wait"

    def test_all_action_types(self):
        raw = [
            {"action": "click", "selector": ".btn"},
            {"action": "wait", "ms": 500},
            {"action": "select", "selector": "#sel", "value": "opt"},
            {"action": "type", "selector": "#input", "text": "hello"},
        ]
        actions = parse_script(raw)
        assert len(actions) == 4

    def test_raises_on_invalid_json(self):
        with pytest.raises(ValueError, match="Invalid JSON"):
            parse_script("not valid json {{{")

    def test_raises_on_non_array(self):
        with pytest.raises(ValueError, match="must be a JSON array"):
            parse_script({"action": "click"})

    def test_raises_on_non_object_item(self):
        with pytest.raises(ValueError, match="must be an object"):
            parse_script(["not_a_dict"])

    def test_raises_on_unsupported_action(self):
        with pytest.raises(ValueError, match="unsupported action type"):
            parse_script([{"action": "hover", "selector": ".btn"}])

    def test_raises_on_missing_action(self):
        with pytest.raises(ValueError, match="unsupported action type"):
            parse_script([{"selector": ".btn"}])


class TestSerializeScript:
    """serialize_script() のテスト。"""

    def test_round_trip(self):
        """Req 5.7: JSON パース/シリアライズのラウンドトリップ。"""
        original = [
            {"action": "click", "selector": ".lang-ja", "label": "日本語選択"},
            {"action": "wait", "ms": 1000},
        ]
        serialized = serialize_script(original)
        restored = parse_script(serialized)
        assert restored == original


# --- should_run() tests ---


class TestPreCaptureScriptPluginShouldRun:
    """should_run() のテスト。"""

    def test_returns_true_when_script_set(self, plugin):
        """Req 5.1: pre_capture_script が設定されている場合 True。"""
        ctx = _make_ctx(pre_capture_script=[{"action": "click", "selector": ".btn"}])
        assert plugin.should_run(ctx) is True

    def test_returns_false_when_script_none(self, plugin):
        """Req 5.1: pre_capture_script が None の場合 False。"""
        ctx = _make_ctx(pre_capture_script=None)
        assert plugin.should_run(ctx) is False


# --- execute() tests ---


class TestPreCaptureScriptPluginExecuteActions:
    """execute() のアクション実行テスト。"""

    @pytest.mark.asyncio
    async def test_click_action(self, plugin, mock_page):
        """Req 5.3: click アクション。"""
        ctx = _make_ctx(
            pre_capture_script=[{"action": "click", "selector": ".btn"}],
            page=mock_page,
        )
        await plugin.execute(ctx)
        mock_page.click.assert_awaited_once_with(".btn")

    @pytest.mark.asyncio
    async def test_wait_action(self, plugin, mock_page):
        """Req 5.3: wait アクション。"""
        ctx = _make_ctx(
            pre_capture_script=[{"action": "wait", "ms": 500}],
            page=mock_page,
        )
        with patch(
            "src.pipeline.plugins.pre_capture_script_plugin.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep:
            await plugin.execute(ctx)
        mock_sleep.assert_awaited_once_with(0.5)

    @pytest.mark.asyncio
    async def test_select_action(self, plugin, mock_page):
        """Req 5.3: select アクション。"""
        ctx = _make_ctx(
            pre_capture_script=[
                {"action": "select", "selector": "#variant", "value": "opt-a"}
            ],
            page=mock_page,
        )
        await plugin.execute(ctx)
        mock_page.select_option.assert_awaited_once_with("#variant", "opt-a")

    @pytest.mark.asyncio
    async def test_type_action(self, plugin, mock_page):
        """Req 5.3: type アクション。"""
        ctx = _make_ctx(
            pre_capture_script=[
                {"action": "type", "selector": "#search", "text": "hello"}
            ],
            page=mock_page,
        )
        await plugin.execute(ctx)
        mock_page.fill.assert_awaited_once_with("#search", "hello")

    @pytest.mark.asyncio
    async def test_sequential_execution(self, plugin, mock_page):
        """Req 5.2: アクションを定義順に逐次実行する。"""
        call_order = []
        mock_page.click = AsyncMock(side_effect=lambda s: call_order.append(("click", s)))
        mock_page.fill = AsyncMock(side_effect=lambda s, t: call_order.append(("type", s)))

        ctx = _make_ctx(
            pre_capture_script=[
                {"action": "click", "selector": ".first"},
                {"action": "type", "selector": ".second", "text": "text"},
            ],
            page=mock_page,
        )
        await plugin.execute(ctx)
        assert call_order == [("click", ".first"), ("type", ".second")]


class TestPreCaptureScriptPluginLabel:
    """label 付きアクションのスクリーンショット取得テスト。"""

    @pytest.mark.asyncio
    async def test_label_triggers_screenshot(self, plugin, mock_page):
        """Req 5.4: label 付きアクションでスクリーンショットを取得する。"""
        ctx = _make_ctx(
            pre_capture_script=[
                {"action": "click", "selector": ".lang-ja", "label": "日本語選択"}
            ],
            page=mock_page,
        )
        await plugin.execute(ctx)
        assert len(ctx.screenshots) == 1
        assert ctx.screenshots[0].variant_name == "日本語選択"

    @pytest.mark.asyncio
    async def test_no_label_no_screenshot(self, plugin, mock_page):
        """label なしアクションではスクリーンショットを取得しない。"""
        ctx = _make_ctx(
            pre_capture_script=[{"action": "click", "selector": ".btn"}],
            page=mock_page,
        )
        await plugin.execute(ctx)
        assert len(ctx.screenshots) == 0
        mock_page.screenshot.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_screenshot_metadata(self, plugin, mock_page):
        """スクリーンショットのメタデータが正しく設定される。"""
        ctx = _make_ctx(
            pre_capture_script=[
                {"action": "click", "selector": ".btn", "label": "TestLabel"}
            ],
            page=mock_page,
        )
        await plugin.execute(ctx)
        capture = ctx.screenshots[0]
        assert capture.metadata["precapturescript_source"] == "pre_capture_script"
        assert capture.metadata["precapturescript_action"] == "click"
        assert capture.captured_at is not None
        assert str(ctx.site.id) in capture.image_path

    @pytest.mark.asyncio
    async def test_screenshot_bytes_stored_in_metadata(self, plugin, mock_page):
        """スクリーンショットバイトが metadata に格納される。"""
        ctx = _make_ctx(
            pre_capture_script=[
                {"action": "click", "selector": ".btn", "label": "MyLabel"}
            ],
            page=mock_page,
        )
        await plugin.execute(ctx)
        assert ctx.metadata["precapturescript_screenshot_MyLabel"] == b"fake_png_bytes"


class TestPreCaptureScriptPluginErrorHandling:
    """エラーハンドリングテスト。"""

    @pytest.mark.asyncio
    async def test_invalid_json_records_validation_error(self, plugin, mock_page):
        """Req 5.6: JSON 不正時はバリデーションエラーを記録しスキップ。"""
        ctx = _make_ctx(pre_capture_script="not valid json", page=mock_page)
        result = await plugin.execute(ctx)
        assert len(result.errors) == 1
        assert result.errors[0]["type"] == "validation_error"
        assert result.errors[0]["plugin"] == "PreCaptureScriptPlugin"

    @pytest.mark.asyncio
    async def test_action_error_records_and_skips_remaining(self, plugin, mock_page):
        """Req 5.5: アクションエラー時は記録し残りスキップ。"""
        mock_page.click = AsyncMock(side_effect=Exception("Element not found"))

        ctx = _make_ctx(
            pre_capture_script=[
                {"action": "click", "selector": ".missing"},
                {"action": "click", "selector": ".second"},
            ],
            page=mock_page,
        )
        result = await plugin.execute(ctx)
        assert len(result.errors) == 1
        assert result.errors[0]["type"] == "action_error"
        # Second action should not have been attempted
        assert mock_page.click.await_count == 1

    @pytest.mark.asyncio
    async def test_missing_page_records_error(self, plugin):
        """page がない場合はエラーを記録する。"""
        ctx = _make_ctx(
            pre_capture_script=[{"action": "click", "selector": ".btn"}],
            page=None,
        )
        result = await plugin.execute(ctx)
        assert len(result.errors) == 1
        assert result.errors[0]["type"] == "missing_page"

    @pytest.mark.asyncio
    async def test_preserves_existing_errors(self, plugin, mock_page):
        """既存のエラーを破壊しない。"""
        ctx = _make_ctx(
            pre_capture_script=[{"action": "click", "selector": ".btn"}],
            page=mock_page,
        )
        ctx.errors.append({"plugin": "other", "error": "previous"})
        result = await plugin.execute(ctx)
        assert result.errors[0]["plugin"] == "other"

    @pytest.mark.asyncio
    async def test_preserves_existing_screenshots(self, plugin, mock_page):
        """既存のスクリーンショットを破壊しない。"""
        from datetime import datetime, timezone
        from src.pipeline.context import VariantCapture

        ctx = _make_ctx(
            pre_capture_script=[
                {"action": "click", "selector": ".btn", "label": "New"}
            ],
            page=mock_page,
        )
        ctx.screenshots.append(
            VariantCapture(
                variant_name="Existing",
                image_path="/existing.png",
                captured_at=datetime.now(timezone.utc),
            )
        )
        result = await plugin.execute(ctx)
        assert len(result.screenshots) == 2
        assert result.screenshots[0].variant_name == "Existing"
        assert result.screenshots[1].variant_name == "New"


class TestPreCaptureScriptPluginName:
    def test_name(self, plugin):
        assert plugin.name == "PreCaptureScriptPlugin"
