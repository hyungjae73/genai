"""
Unit tests for OCRPlugin.

Feature: crawl-pipeline-architecture
Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5
"""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.models import MonitoringSite
from src.pipeline.context import CrawlContext, VariantCapture
from src.pipeline.plugins.ocr_plugin import OCRPlugin


def _make_ocr_result(full_text="¥1,980", regions=None, success=True, confidence=0.85):
    """Helper to build a mock OCRResult."""
    result = MagicMock()
    result.full_text = full_text
    result.success = success
    result.average_confidence = confidence
    if regions is None:
        region = MagicMock()
        region.text = full_text
        region.confidence = confidence
        region.bbox = (100, 200, 150, 30)
        regions = [region]
    result.regions = regions
    return result


@pytest.fixture
def ctx():
    site = MonitoringSite(id=1, name="Test Site", url="https://example.com")
    c = CrawlContext(site=site, url="https://example.com")
    c.screenshots = [
        VariantCapture(
            variant_name="デフォルト",
            image_path="/tmp/screenshot_1.png",
            captured_at=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        )
    ]
    return c


@pytest.fixture
def mock_ocr_engine():
    engine = MagicMock()
    engine.extract_text.return_value = _make_ocr_result()
    return engine


@pytest.fixture
def plugin(mock_ocr_engine):
    return OCRPlugin(ocr_engine=mock_ocr_engine)


# ------------------------------------------------------------------
# should_run (Req 9.1)
# ------------------------------------------------------------------


class TestShouldRun:
    """should_run() は screenshots が1件以上の場合に True を返す。"""

    def test_returns_true_when_screenshots_exist(self, plugin, ctx):
        assert plugin.should_run(ctx) is True

    def test_returns_false_when_no_screenshots(self, plugin, ctx):
        ctx.screenshots = []
        assert plugin.should_run(ctx) is False

    def test_returns_true_with_multiple_screenshots(self, plugin, ctx):
        ctx.screenshots.append(
            VariantCapture(
                variant_name="バリアントA",
                image_path="/tmp/screenshot_2.png",
                captured_at=datetime(2024, 1, 15, 10, 1, 0, tzinfo=timezone.utc),
            )
        )
        assert plugin.should_run(ctx) is True


# ------------------------------------------------------------------
# execute — ROI detection and OCR (Req 9.2, 9.3, 9.5)
# ------------------------------------------------------------------


class TestExecuteWithROI:
    """ROI 検出 → 切り出し → OCR 実行 → evidence_records に追加。"""

    @pytest.mark.asyncio
    async def test_detects_price_roi_and_adds_evidence(self, ctx, mock_ocr_engine):
        """Req 9.2, 9.3: ROI 検出 → OCR → evidence_records。"""
        # First call: detect ROIs (returns regions with price text)
        # Second call: OCR on cropped ROI
        mock_ocr_engine.extract_text.return_value = _make_ocr_result(full_text="¥1,980")

        # Use image_processor mock to avoid PIL dependency
        mock_crop = MagicMock(return_value=Path("/tmp/screenshot_1_roi_100_200.png"))
        plugin = OCRPlugin(ocr_engine=mock_ocr_engine, image_processor=mock_crop)

        result = await plugin.execute(ctx)

        assert len(result.evidence_records) >= 1
        evidence = result.evidence_records[0]
        assert evidence["variant_name"] == "デフォルト"
        assert evidence["screenshot_path"] == "/tmp/screenshot_1.png"
        assert evidence["evidence_type"] == "price_display"
        assert "ocr_text" in evidence
        assert "ocr_confidence" in evidence
        assert "created_at" in evidence

    @pytest.mark.asyncio
    async def test_roi_image_path_set_when_cropped(self, ctx, mock_ocr_engine):
        """Req 9.3: ROI 切り出し画像パスが設定される。"""
        mock_ocr_engine.extract_text.return_value = _make_ocr_result(full_text="¥1,980")
        roi_path = Path("/tmp/screenshot_1_roi_100_200.png")
        mock_crop = MagicMock(return_value=roi_path)
        plugin = OCRPlugin(ocr_engine=mock_ocr_engine, image_processor=mock_crop)

        result = await plugin.execute(ctx)

        assert len(result.evidence_records) >= 1
        assert result.evidence_records[0]["roi_image_path"] == str(roi_path)

    @pytest.mark.asyncio
    async def test_price_pattern_matching(self, ctx, mock_ocr_engine):
        """Req 9.5: 通貨記号 + 数値のパターンマッチング。"""
        region = MagicMock()
        region.text = "$29.99"
        region.confidence = 0.9
        region.bbox = (50, 100, 80, 20)
        mock_ocr_engine.extract_text.return_value = _make_ocr_result(
            full_text="$29.99", regions=[region]
        )
        mock_crop = MagicMock(return_value=Path("/tmp/roi.png"))
        plugin = OCRPlugin(ocr_engine=mock_ocr_engine, image_processor=mock_crop)

        result = await plugin.execute(ctx)

        assert len(result.evidence_records) >= 1
        assert result.evidence_records[0]["evidence_type"] == "price_display"


# ------------------------------------------------------------------
# execute — no ROI detected, full screenshot OCR (Req 9.4)
# ------------------------------------------------------------------


class TestExecuteFullScreenshot:
    """ROI 未検出時はスクリーンショット全体に OCR を実行する。"""

    @pytest.mark.asyncio
    async def test_full_screenshot_ocr_when_no_roi(self, ctx, mock_ocr_engine):
        """Req 9.4: ROI 未検出時はフルスクリーンショット OCR。"""
        # Return regions with no price/terms patterns
        region = MagicMock()
        region.text = "Hello World"
        region.confidence = 0.9
        region.bbox = (10, 10, 100, 20)
        mock_ocr_engine.extract_text.return_value = _make_ocr_result(
            full_text="Hello World", regions=[region]
        )
        plugin = OCRPlugin(ocr_engine=mock_ocr_engine)

        result = await plugin.execute(ctx)

        assert len(result.evidence_records) == 1
        evidence = result.evidence_records[0]
        assert evidence["roi_image_path"] is None
        assert evidence["evidence_type"] == "general"
        assert evidence["ocr_text"] == "Hello World"

    @pytest.mark.asyncio
    async def test_full_screenshot_ocr_when_no_regions(self, ctx, mock_ocr_engine):
        """No regions at all → full screenshot OCR."""
        mock_ocr_engine.extract_text.return_value = _make_ocr_result(
            full_text="Some text", regions=[]
        )
        plugin = OCRPlugin(ocr_engine=mock_ocr_engine)

        result = await plugin.execute(ctx)

        assert len(result.evidence_records) == 1
        assert result.evidence_records[0]["roi_image_path"] is None


# ------------------------------------------------------------------
# execute — multiple screenshots
# ------------------------------------------------------------------


class TestMultipleScreenshots:
    """複数スクリーンショットの処理。"""

    @pytest.mark.asyncio
    async def test_processes_all_screenshots(self, ctx, mock_ocr_engine):
        ctx.screenshots.append(
            VariantCapture(
                variant_name="バリアントA",
                image_path="/tmp/screenshot_2.png",
                captured_at=datetime(2024, 1, 15, 10, 1, 0, tzinfo=timezone.utc),
            )
        )
        # No price regions → full screenshot OCR for each
        region = MagicMock()
        region.text = "text"
        region.confidence = 0.8
        region.bbox = (10, 10, 50, 20)
        mock_ocr_engine.extract_text.return_value = _make_ocr_result(
            full_text="text", regions=[region]
        )
        plugin = OCRPlugin(ocr_engine=mock_ocr_engine)

        result = await plugin.execute(ctx)

        assert result.metadata["ocr_screenshot_count"] == 2
        assert result.metadata["ocr_processed_count"] >= 2


# ------------------------------------------------------------------
# execute — error handling
# ------------------------------------------------------------------


class TestExecuteErrors:
    """エラー処理。"""

    @pytest.mark.asyncio
    async def test_handles_ocr_engine_not_available(self, ctx):
        plugin = OCRPlugin(ocr_engine=None)
        # Override lazy loader to return None
        plugin._get_ocr_engine = MagicMock(return_value=None)

        result = await plugin.execute(ctx)

        assert len(result.errors) == 1
        assert "OCR engine not available" in result.errors[0]["error"]

    @pytest.mark.asyncio
    async def test_handles_ocr_failure_for_screenshot(self, ctx, mock_ocr_engine):
        mock_ocr_engine.extract_text.side_effect = Exception("OCR crash")
        plugin = OCRPlugin(ocr_engine=mock_ocr_engine)

        result = await plugin.execute(ctx)

        assert len(result.errors) == 1
        assert result.errors[0]["plugin"] == "OCRPlugin"
        assert result.errors[0]["screenshot"] == "/tmp/screenshot_1.png"

    @pytest.mark.asyncio
    async def test_continues_after_single_screenshot_error(self, ctx, mock_ocr_engine):
        """1つのスクリーンショットでエラーが発生しても残りは処理する。"""
        ctx.screenshots.append(
            VariantCapture(
                variant_name="バリアントA",
                image_path="/tmp/screenshot_2.png",
                captured_at=datetime(2024, 1, 15, 10, 1, 0, tzinfo=timezone.utc),
            )
        )
        # extract_text is called in _detect_rois and potentially _process_full_screenshot
        # For screenshot 1: _detect_rois fails, _process_full_screenshot also fails → error recorded
        # For screenshot 2: _detect_rois succeeds (no price ROIs), _process_full_screenshot succeeds
        region = MagicMock()
        region.text = "text"
        region.confidence = 0.8
        region.bbox = (10, 10, 50, 20)
        success_result = _make_ocr_result(full_text="text", regions=[region])
        mock_ocr_engine.extract_text.side_effect = [
            Exception("File not found"),   # screenshot 1: _detect_rois
            Exception("File not found"),   # screenshot 1: _process_full_screenshot
            success_result,                # screenshot 2: _detect_rois
            success_result,                # screenshot 2: _process_full_screenshot
        ]
        plugin = OCRPlugin(ocr_engine=mock_ocr_engine)

        result = await plugin.execute(ctx)

        assert len(result.errors) >= 1
        assert result.metadata["ocr_processed_count"] >= 1


# ------------------------------------------------------------------
# ROI classification
# ------------------------------------------------------------------


class TestROIClassification:
    """テキスト内容に基づく ROI タイプ分類。"""

    def test_classifies_yen_price(self, plugin):
        assert plugin._classify_region("¥1,980") == "price_display"

    def test_classifies_dollar_price(self, plugin):
        assert plugin._classify_region("$29.99") == "price_display"

    def test_classifies_euro_price(self, plugin):
        assert plugin._classify_region("€19.99") == "price_display"

    def test_classifies_yen_suffix(self, plugin):
        assert plugin._classify_region("1,980円") == "price_display"

    def test_classifies_terms_notice(self, plugin):
        assert plugin._classify_region("利用規約と条件") == "terms_notice"

    def test_classifies_subscription(self, plugin):
        assert plugin._classify_region("月額サブスクリプション") == "subscription_condition"

    def test_returns_none_for_generic_text(self, plugin):
        assert plugin._classify_region("Hello World") is None

    def test_returns_none_for_empty_text(self, plugin):
        assert plugin._classify_region("") is None


# ------------------------------------------------------------------
# Field preservation
# ------------------------------------------------------------------


class TestFieldPreservation:
    """既存フィールドを破壊しない。"""

    @pytest.mark.asyncio
    async def test_preserves_existing_metadata(self, plugin, ctx):
        ctx.metadata["existing_key"] = "existing_value"
        result = await plugin.execute(ctx)
        assert result.metadata["existing_key"] == "existing_value"

    @pytest.mark.asyncio
    async def test_preserves_existing_errors(self, plugin, ctx):
        ctx.errors.append({"plugin": "other", "error": "previous"})
        result = await plugin.execute(ctx)
        assert result.errors[0]["plugin"] == "other"

    @pytest.mark.asyncio
    async def test_preserves_existing_evidence_records(self, plugin, ctx):
        ctx.evidence_records.append({"existing": True})
        result = await plugin.execute(ctx)
        assert result.evidence_records[0] == {"existing": True}

    @pytest.mark.asyncio
    async def test_returns_same_ctx(self, plugin, ctx):
        result = await plugin.execute(ctx)
        assert result is ctx


# ------------------------------------------------------------------
# Plugin name
# ------------------------------------------------------------------


class TestPluginName:
    def test_name(self, plugin):
        assert plugin.name == "OCRPlugin"
