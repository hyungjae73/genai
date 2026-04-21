"""
Tests for CSSVisualPlugin.

Unit tests (tasks 3.3) and property-based tests (tasks 3.2).

Properties tested:
  Property 3: フォントサイズ異常検出の正確性
  Property 4: CSS隠蔽検出の網羅性
  Property 5: visual_deception_score の範囲不変条件

**Validates: Requirements 1.4, 1.5, 1.6, 1.7, 1.8**
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.models import MonitoringSite
from src.pipeline.context import CrawlContext
from src.pipeline.plugins.css_visual_plugin import CSSVisualPlugin


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx(with_page: bool = True) -> CrawlContext:
    site = MonitoringSite(id=1)
    ctx = CrawlContext(site=site, url="https://example.com")
    if with_page:
        ctx.metadata["pagefetcher_page"] = MagicMock()
    return ctx


def _make_elem(
    color="rgb(200, 200, 200)",
    bg="rgb(210, 210, 210)",
    font_size=12.0,
    display="block",
    visibility="visible",
    opacity=1.0,
    left=0.0,
    text="some text",
    selector="span",
) -> dict:
    return {
        "selector": selector,
        "text": text,
        "color": color,
        "backgroundColor": bg,
        "fontSize": font_size,
        "display": display,
        "visibility": visibility,
        "opacity": opacity,
        "overflow": "visible",
        "position": "static",
        "left": left,
        "top": 0.0,
    }


# ---------------------------------------------------------------------------
# Unit tests — should_run
# ---------------------------------------------------------------------------


class TestShouldRun:
    def test_returns_true_when_page_present(self):
        ctx = _make_ctx(with_page=True)
        plugin = CSSVisualPlugin()
        assert plugin.should_run(ctx) is True

    def test_returns_false_when_page_absent(self):
        ctx = _make_ctx(with_page=False)
        plugin = CSSVisualPlugin()
        assert plugin.should_run(ctx) is False

    def test_returns_false_when_page_is_none(self):
        ctx = _make_ctx(with_page=False)
        ctx.metadata["pagefetcher_page"] = None
        plugin = CSSVisualPlugin()
        assert plugin.should_run(ctx) is False


# ---------------------------------------------------------------------------
# Unit tests — execute()
# ---------------------------------------------------------------------------


class TestExecute:
    def test_execute_writes_metadata(self):
        ctx = _make_ctx()
        mock_page = AsyncMock()
        mock_page.evaluate = AsyncMock(return_value=[])
        ctx.metadata["pagefetcher_page"] = mock_page

        plugin = CSSVisualPlugin()
        asyncio.get_event_loop().run_until_complete(plugin.execute(ctx))

        assert "cssvisual_deception_score" in ctx.metadata
        assert "cssvisual_techniques" in ctx.metadata
        assert ctx.metadata["cssvisual_deception_score"] == 0.0
        assert ctx.metadata["cssvisual_techniques"] == []

    def test_execute_detects_low_contrast(self):
        ctx = _make_ctx()
        mock_page = AsyncMock()
        # Very similar colors → low contrast
        elem = _make_elem(color="rgb(200,200,200)", bg="rgb(210,210,210)")
        mock_page.evaluate = AsyncMock(return_value=[elem])
        ctx.metadata["pagefetcher_page"] = mock_page

        plugin = CSSVisualPlugin()
        asyncio.get_event_loop().run_until_complete(plugin.execute(ctx))

        techniques = ctx.metadata["cssvisual_techniques"]
        assert any(t["type"] == "low_contrast" for t in techniques)

    def test_execute_detects_css_hidden_display_none(self):
        ctx = _make_ctx()
        mock_page = AsyncMock()
        elem = _make_elem(display="none")
        mock_page.evaluate = AsyncMock(return_value=[elem])
        ctx.metadata["pagefetcher_page"] = mock_page

        plugin = CSSVisualPlugin()
        asyncio.get_event_loop().run_until_complete(plugin.execute(ctx))

        techniques = ctx.metadata["cssvisual_techniques"]
        assert any(t["type"] == "css_hidden" for t in techniques)

    def test_execute_adds_violations(self):
        ctx = _make_ctx()
        mock_page = AsyncMock()
        elem = _make_elem(display="none")
        mock_page.evaluate = AsyncMock(return_value=[elem])
        ctx.metadata["pagefetcher_page"] = mock_page

        plugin = CSSVisualPlugin()
        asyncio.get_event_loop().run_until_complete(plugin.execute(ctx))

        assert len(ctx.violations) > 0
        for v in ctx.violations:
            assert v["dark_pattern_category"] == "visual_deception"
            assert v["severity"] == "warning"

    def test_execute_page_evaluate_failure_records_error(self):
        ctx = _make_ctx()
        mock_page = AsyncMock()
        mock_page.evaluate = AsyncMock(side_effect=RuntimeError("page crashed"))
        ctx.metadata["pagefetcher_page"] = mock_page

        plugin = CSSVisualPlugin()
        asyncio.get_event_loop().run_until_complete(plugin.execute(ctx))

        assert ctx.metadata["cssvisual_deception_score"] == 0.0
        assert len(ctx.errors) > 0
        assert any("page.evaluate" in e["error"] for e in ctx.errors)

    def test_execute_unparseable_css_skips_element(self):
        ctx = _make_ctx()
        mock_page = AsyncMock()
        # Invalid color string — should be skipped, not crash
        elem = _make_elem(color="not-a-color", bg="also-not-a-color")
        mock_page.evaluate = AsyncMock(return_value=[elem])
        ctx.metadata["pagefetcher_page"] = mock_page

        plugin = CSSVisualPlugin()
        asyncio.get_event_loop().run_until_complete(plugin.execute(ctx))

        # Should not crash; score should be 0 or based on other detections
        assert "cssvisual_deception_score" in ctx.metadata


# ---------------------------------------------------------------------------
# Unit tests — _is_low_contrast
# ---------------------------------------------------------------------------


class TestIsLowContrast:
    def test_similar_colors_are_low_contrast(self):
        plugin = CSSVisualPlugin()
        elem = _make_elem(color="rgb(200,200,200)", bg="rgb(210,210,210)")
        assert plugin._is_low_contrast(elem) is True

    def test_black_on_white_is_not_low_contrast(self):
        plugin = CSSVisualPlugin()
        elem = _make_elem(color="rgb(0,0,0)", bg="rgb(255,255,255)")
        assert plugin._is_low_contrast(elem) is False

    def test_invalid_color_returns_false(self):
        plugin = CSSVisualPlugin()
        elem = _make_elem(color="invalid", bg="also-invalid")
        assert plugin._is_low_contrast(elem) is False


# ---------------------------------------------------------------------------
# Unit tests — _is_css_hidden
# ---------------------------------------------------------------------------


class TestIsCssHidden:
    def test_display_none_is_hidden(self):
        plugin = CSSVisualPlugin()
        assert plugin._is_css_hidden(_make_elem(display="none")) is True

    def test_visibility_hidden_is_hidden(self):
        plugin = CSSVisualPlugin()
        assert plugin._is_css_hidden(_make_elem(visibility="hidden")) is True

    def test_opacity_zero_is_hidden(self):
        plugin = CSSVisualPlugin()
        assert plugin._is_css_hidden(_make_elem(opacity=0)) is True

    def test_offscreen_left_is_hidden(self):
        plugin = CSSVisualPlugin()
        assert plugin._is_css_hidden(_make_elem(left=-10000)) is True

    def test_zero_font_size_is_hidden(self):
        plugin = CSSVisualPlugin()
        assert plugin._is_css_hidden(_make_elem(font_size=0)) is True

    def test_normal_element_is_not_hidden(self):
        plugin = CSSVisualPlugin()
        assert plugin._is_css_hidden(_make_elem()) is False


# ---------------------------------------------------------------------------
# Unit tests — _calculate_deception_score
# ---------------------------------------------------------------------------


class TestCalculateDeceptionScore:
    def test_empty_techniques_returns_zero(self):
        assert CSSVisualPlugin._calculate_deception_score([]) == 0.0

    def test_five_techniques_returns_one(self):
        techniques = [{"type": "low_contrast"}] * 5
        assert CSSVisualPlugin._calculate_deception_score(techniques) == 1.0

    def test_ten_techniques_capped_at_one(self):
        techniques = [{"type": "css_hidden"}] * 10
        assert CSSVisualPlugin._calculate_deception_score(techniques) == 1.0

    def test_one_technique_returns_point_two(self):
        techniques = [{"type": "low_contrast"}]
        assert CSSVisualPlugin._calculate_deception_score(techniques) == pytest.approx(0.2)


# ---------------------------------------------------------------------------
# Property 3: フォントサイズ異常検出の正確性
# **Validates: Requirements 1.5**
# ---------------------------------------------------------------------------


@given(
    cond_size=st.floats(min_value=0.1, max_value=100.0, allow_nan=False),
    price_size=st.floats(min_value=1.0, max_value=100.0, allow_nan=False),
)
@settings(max_examples=200)
def test_property3_tiny_font_detection(cond_size, price_size):
    """Property 3: cond_size / price_size < 0.25 ↔ tiny font detected."""
    plugin = CSSVisualPlugin()

    # Build a price element and a condition element
    price_elem = _make_elem(
        font_size=price_size,
        text="¥1,000",
        color="rgb(0,0,0)",
        bg="rgb(255,255,255)",
    )
    cond_elem = _make_elem(
        font_size=cond_size,
        text="条件テキスト",
        color="rgb(0,0,0)",
        bg="rgb(255,255,255)",
    )
    elements = [price_elem, cond_elem]

    is_tiny = plugin._is_tiny_font(cond_elem, elements)
    ratio = cond_size / price_size

    if ratio < 0.25:
        assert is_tiny, (
            f"Expected tiny font for cond={cond_size}, price={price_size} "
            f"(ratio={ratio:.3f} < 0.25)"
        )
    else:
        assert not is_tiny, (
            f"Expected NOT tiny font for cond={cond_size}, price={price_size} "
            f"(ratio={ratio:.3f} >= 0.25)"
        )


# ---------------------------------------------------------------------------
# Property 4: CSS隠蔽検出の網羅性
# **Validates: Requirements 1.6, 1.7**
# ---------------------------------------------------------------------------


@given(
    left=st.floats(min_value=-20000, max_value=0, allow_nan=False),
    opacity=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    font_size=st.floats(min_value=0.0, max_value=50.0, allow_nan=False),
    display=st.sampled_from(["none", "block", "inline", "flex"]),
    visibility=st.sampled_from(["hidden", "visible", "collapse"]),
)
@settings(max_examples=300)
def test_property4_css_hidden_detection(left, opacity, font_size, display, visibility):
    """Property 4: CSS hidden detection covers all hiding techniques."""
    plugin = CSSVisualPlugin()
    elem = _make_elem(
        left=left,
        opacity=opacity,
        font_size=font_size,
        display=display,
        visibility=visibility,
    )

    is_hidden = plugin._is_css_hidden(elem)

    # Determine expected result
    expected_hidden = (
        left < -9000
        or opacity == 0
        or font_size == 0
        or display.lower() == "none"
        or visibility.lower() == "hidden"
    )

    assert is_hidden == expected_hidden, (
        f"Expected is_hidden={expected_hidden} for "
        f"left={left}, opacity={opacity}, font_size={font_size}, "
        f"display={display!r}, visibility={visibility!r}"
    )


# ---------------------------------------------------------------------------
# Property 5: visual_deception_score の範囲不変条件
# **Validates: Requirements 1.8**
# ---------------------------------------------------------------------------


@given(n_techniques=st.integers(min_value=0, max_value=100))
@settings(max_examples=200)
def test_property5_score_in_range(n_techniques):
    """Property 5: _calculate_deception_score always returns [0.0, 1.0]."""
    techniques = [{"type": "low_contrast"}] * n_techniques
    score = CSSVisualPlugin._calculate_deception_score(techniques)
    assert 0.0 <= score <= 1.0, f"Score {score} out of [0, 1] for {n_techniques} techniques"


# ---------------------------------------------------------------------------
# Tests for misleading_font_size detection (Requirement 17)
# ---------------------------------------------------------------------------

from src.pipeline.plugins.dark_pattern_utils import (
    contains_important_keyword,
    compute_median_font_size,
    detect_misleading_font_size,
)


class TestContainsImportantKeyword:
    """Unit tests for contains_important_keyword (Req 17.3, 17.4)."""

    def test_japanese_keyword_detected(self):
        assert contains_important_keyword("定期購入の条件") is True

    def test_japanese_cancellation_detected(self):
        assert contains_important_keyword("解約方法はこちら") is True

    def test_english_subscription_detected(self):
        assert contains_important_keyword("auto-renew applies") is True

    def test_english_cancellation_detected(self):
        assert contains_important_keyword("cancellation policy") is True

    def test_normal_text_not_detected(self):
        assert contains_important_keyword("商品の説明文です") is False

    def test_empty_text(self):
        assert contains_important_keyword("") is False

    def test_case_insensitive_english(self):
        assert contains_important_keyword("SUBSCRIPTION plan") is True


class TestComputeMedianFontSize:
    """Unit tests for compute_median_font_size (Req 17.1)."""

    def test_odd_count(self):
        elements = [{"fontSize": 10}, {"fontSize": 14}, {"fontSize": 20}]
        assert compute_median_font_size(elements) == 14.0

    def test_even_count(self):
        elements = [{"fontSize": 10}, {"fontSize": 20}]
        assert compute_median_font_size(elements) == 15.0

    def test_empty_list(self):
        assert compute_median_font_size([]) == 0.0

    def test_ignores_zero_and_invalid(self):
        elements = [{"fontSize": 0}, {"fontSize": "bad"}, {"fontSize": 16}]
        assert compute_median_font_size(elements) == 16.0


class TestDetectMisleadingFontSize:
    """Unit tests for detect_misleading_font_size (Req 17.2, 17.5)."""

    def test_detects_small_important_text(self):
        elem = {"fontSize": 8, "text": "定期購入の条件が適用されます"}
        assert detect_misleading_font_size(elem, median_font_size=16.0) is True

    def test_normal_size_not_flagged(self):
        elem = {"fontSize": 14, "text": "定期購入の条件が適用されます"}
        assert detect_misleading_font_size(elem, median_font_size=16.0) is False

    def test_small_but_no_keyword(self):
        elem = {"fontSize": 8, "text": "商品の説明文です"}
        assert detect_misleading_font_size(elem, median_font_size=16.0) is False

    def test_zero_median_returns_false(self):
        elem = {"fontSize": 8, "text": "解約条件"}
        assert detect_misleading_font_size(elem, median_font_size=0.0) is False

    def test_custom_ratio_threshold(self):
        # 10/16 = 0.625 < 0.7 → flagged
        elem = {"fontSize": 10, "text": "手数料について"}
        assert detect_misleading_font_size(elem, median_font_size=16.0, ratio_threshold=0.7) is True
        # 10/16 = 0.625 > 0.6 → not flagged
        assert detect_misleading_font_size(elem, median_font_size=16.0, ratio_threshold=0.6) is False


# ---------------------------------------------------------------------------
# Property test: misleading_font_size detection invariant (Req 17.2)
# ---------------------------------------------------------------------------

@given(
    font_size=st.floats(min_value=1.0, max_value=100.0, allow_nan=False),
    median=st.floats(min_value=1.0, max_value=100.0, allow_nan=False),
    ratio=st.floats(min_value=0.1, max_value=0.99, allow_nan=False),
)
@settings(max_examples=200)
def test_property_misleading_font_size_threshold(font_size, median, ratio):
    """Property: detect_misleading_font_size flags iff font_size/median < ratio AND keyword present."""
    elem = {"fontSize": font_size, "text": "定期購入の条件"}
    result = detect_misleading_font_size(elem, median_font_size=median, ratio_threshold=ratio)
    expected = (font_size / median) < ratio
    assert result == expected, (
        f"font_size={font_size}, median={median}, ratio={ratio}: "
        f"expected {expected}, got {result}"
    )


@pytest.mark.asyncio
async def test_css_visual_plugin_misleading_font_size_violation():
    """Integration: CSSVisualPlugin adds misleading_font_size violation."""
    plugin = CSSVisualPlugin()
    site = MagicMock(spec=MonitoringSite)
    site.id = 1
    ctx = CrawlContext(site=site, url="https://example.com")

    # Elements: median=16px, one important text at 8px (ratio 0.5 < 0.75)
    mock_elements = [
        {"selector": "p.body", "text": "商品説明", "color": "rgb(0,0,0)",
         "backgroundColor": "rgb(255,255,255)", "fontSize": 16,
         "display": "block", "visibility": "visible", "opacity": 1.0,
         "overflow": "visible", "position": "static", "left": 0, "top": 0},
        {"selector": "small.terms", "text": "定期購入の条件が適用されます", "color": "rgb(0,0,0)",
         "backgroundColor": "rgb(255,255,255)", "fontSize": 8,
         "display": "block", "visibility": "visible", "opacity": 1.0,
         "overflow": "visible", "position": "static", "left": 0, "top": 0},
    ]

    mock_page = AsyncMock()
    mock_page.evaluate = AsyncMock(return_value=mock_elements)
    ctx.metadata["pagefetcher_page"] = mock_page

    result = await plugin.execute(ctx)

    misleading = [v for v in result.violations if v.get("dark_pattern_category") == "misleading_font_size"]
    assert len(misleading) >= 1, "Expected at least one misleading_font_size violation"
    assert misleading[0]["violation_type"] == "misleading_font_size"
    assert misleading[0]["severity"] == "warning"
