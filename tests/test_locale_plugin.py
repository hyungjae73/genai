"""
Unit tests for LocalePlugin.

Feature: crawl-pipeline-architecture
Validates: Requirements 3.1, 3.2, 3.3, 3.4
"""

import pytest

from src.models import MonitoringSite
from src.pipeline.context import CrawlContext
from src.pipeline.plugins.locale_plugin import LocalePlugin


@pytest.fixture
def plugin():
    return LocalePlugin()


@pytest.fixture
def ctx():
    site = MonitoringSite(id=1, name="Test Site", url="https://example.com")
    return CrawlContext(site=site, url="https://example.com")


class TestLocalePluginShouldRun:
    """should_run() は常に True を返す。"""

    def test_always_returns_true(self, plugin, ctx):
        assert plugin.should_run(ctx) is True

    def test_returns_true_with_empty_metadata(self, plugin, ctx):
        ctx.metadata = {}
        assert plugin.should_run(ctx) is True

    def test_returns_true_with_existing_metadata(self, plugin, ctx):
        ctx.metadata = {"some_key": "some_value"}
        assert plugin.should_run(ctx) is True


class TestLocalePluginExecute:
    """execute() がロケール設定を ctx.metadata に格納する。"""

    @pytest.mark.asyncio
    async def test_sets_locale_config_in_metadata(self, plugin, ctx):
        result = await plugin.execute(ctx)
        assert "locale_config" in result.metadata

    @pytest.mark.asyncio
    async def test_locale_is_ja_jp(self, plugin, ctx):
        """Req 3.1: locale を ja-JP に設定する。"""
        result = await plugin.execute(ctx)
        assert result.metadata["locale_config"]["locale"] == "ja-JP"

    @pytest.mark.asyncio
    async def test_accept_language_header(self, plugin, ctx):
        """Req 3.2: Accept-Language ヘッダーを設定する。"""
        result = await plugin.execute(ctx)
        headers = result.metadata["locale_config"]["extra_http_headers"]
        assert headers == {"Accept-Language": "ja-JP,ja;q=0.9"}

    @pytest.mark.asyncio
    async def test_viewport_size(self, plugin, ctx):
        """Req 3.3: ビューポートサイズ 1920x1080 を維持する。"""
        result = await plugin.execute(ctx)
        viewport = result.metadata["locale_config"]["viewport"]
        assert viewport["width"] == 1920
        assert viewport["height"] == 1080

    @pytest.mark.asyncio
    async def test_device_scale_factor(self, plugin, ctx):
        """Req 3.3: デバイススケールファクター 2 を維持する。"""
        result = await plugin.execute(ctx)
        assert result.metadata["locale_config"]["device_scale_factor"] == 2

    @pytest.mark.asyncio
    async def test_preserves_existing_metadata(self, plugin, ctx):
        """既存の metadata を破壊しない。"""
        ctx.metadata["existing_key"] = "existing_value"
        result = await plugin.execute(ctx)
        assert result.metadata["existing_key"] == "existing_value"
        assert "locale_config" in result.metadata

    @pytest.mark.asyncio
    async def test_preserves_existing_errors(self, plugin, ctx):
        """既存の errors を破壊しない。"""
        ctx.errors.append({"plugin": "other", "error": "previous error"})
        result = await plugin.execute(ctx)
        assert len(result.errors) == 1
        assert result.errors[0]["plugin"] == "other"

    @pytest.mark.asyncio
    async def test_returns_same_ctx(self, plugin, ctx):
        """同じ CrawlContext オブジェクトを返す。"""
        result = await plugin.execute(ctx)
        assert result is ctx


class TestLocalePluginName:
    """name プロパティがクラス名を返す。"""

    def test_name(self, plugin):
        assert plugin.name == "LocalePlugin"
