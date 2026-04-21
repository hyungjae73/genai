"""
CSSVisualPlugin — DataExtractor ステージ プラグイン。

単一 page.evaluate() RPC でブラウザ内の全テキスト要素のCSSプロパティを
一括取得し、視覚的欺瞞パターンを検出する。

🚨 CTO Override: 要素ごとの getComputedStyle ループは厳禁。
単一 page.evaluate() で全テキスト要素のスタイルを一括取得すること。

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.10, 14.4
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from src.pipeline.context import CrawlContext
from src.pipeline.plugin import CrawlPlugin
from src.pipeline.plugins.dark_pattern_utils import (
    contrast_ratio,
    parse_rgba,
    compute_median_font_size,
    detect_misleading_font_size,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# BATCH_STYLE_JS — single RPC to collect all leaf text element styles
# 🚨 CTO Override: no per-element getComputedStyle loops
# ---------------------------------------------------------------------------

BATCH_STYLE_JS = """
() => {
    const results = [];
    const walker = document.createTreeWalker(
        document.body,
        NodeFilter.SHOW_ELEMENT,
        null,
        false
    );
    while (walker.nextNode()) {
        const el = walker.currentNode;
        const text = el.innerText ? el.innerText.trim() : '';
        if (text.length === 0 || el.children.length > 0) {
            continue;
        }
        const style = window.getComputedStyle(el);
        // Build a simple CSS selector path
        let selector = el.tagName.toLowerCase();
        if (el.id) {
            selector = '#' + el.id;
        } else if (el.className && typeof el.className === 'string') {
            const cls = el.className.trim().split(/\\s+/)[0];
            if (cls) selector += '.' + cls;
        }
        results.push({
            selector: selector,
            text: text.substring(0, 200),
            color: style.color,
            backgroundColor: style.backgroundColor,
            fontSize: parseFloat(style.fontSize) || 0,
            display: style.display,
            visibility: style.visibility,
            opacity: parseFloat(style.opacity),
            overflow: style.overflow,
            position: style.position,
            left: parseFloat(style.left) || 0,
            top: parseFloat(style.top) || 0,
        });
    }
    return results;
}
"""


class CSSVisualPlugin(CrawlPlugin):
    """CSS/視覚階層による欺瞞検出プラグイン。

    🚨 CTO Override: 単一 page.evaluate() で全テキスト要素のスタイルを
    一括取得する。要素ごとの getComputedStyle ループは厳禁。

    Requirements: 1.1–1.10, 14.4
    """

    # Contrast ratio threshold below which text is considered low-contrast
    CONTRAST_THRESHOLD = 2.0

    # Font size ratio below which text is considered tiny (vs price elements)
    TINY_FONT_RATIO = 0.25

    # Offscreen left threshold
    OFFSCREEN_LEFT_THRESHOLD = -9000

    def should_run(self, ctx: CrawlContext) -> bool:
        """metadata に pagefetcher_page が存在する場合に True を返す。"""
        return ctx.metadata.get("pagefetcher_page") is not None

    async def execute(self, ctx: CrawlContext) -> CrawlContext:
        """単一 page.evaluate() でスタイル一括取得 → 欺瞞判定。"""
        page = ctx.metadata["pagefetcher_page"]
        try:
            elements: list[dict] = await page.evaluate(BATCH_STYLE_JS)
        except Exception as exc:
            error_msg = f"CSSVisualPlugin: page.evaluate() failed: {exc}"
            logger.error(error_msg)
            ctx.errors.append({
                "plugin": self.name,
                "stage": "data_extractor",
                "error": error_msg,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            ctx.metadata["cssvisual_deception_score"] = 0.0
            ctx.metadata["cssvisual_techniques"] = []
            return ctx

        # Compute page-wide median font size for misleading_font_size detection
        import os
        misleading_ratio = float(os.environ.get("MISLEADING_FONT_SIZE_RATIO", "0.75"))
        median_fs = compute_median_font_size(elements)

        techniques: list[dict] = []
        for elem in elements:
            try:
                if self._is_low_contrast(elem):
                    techniques.append(self._build_technique("low_contrast", elem))
                if self._is_tiny_font(elem, elements):
                    techniques.append(self._build_technique("tiny_font", elem))
                if self._is_css_hidden(elem):
                    techniques.append(self._build_technique("css_hidden", elem))
                if detect_misleading_font_size(elem, median_fs, misleading_ratio):
                    techniques.append(
                        self._build_misleading_font_technique(elem, median_fs)
                    )
            except Exception as exc:
                error_msg = f"CSSVisualPlugin: error processing element {elem.get('selector', '?')}: {exc}"
                logger.warning(error_msg)
                ctx.errors.append({
                    "plugin": self.name,
                    "stage": "data_extractor",
                    "error": error_msg,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

        score = self._calculate_deception_score(techniques)
        ctx.metadata["cssvisual_deception_score"] = score
        ctx.metadata["cssvisual_techniques"] = techniques
        self._add_violations(ctx, techniques)
        return ctx

    def _is_low_contrast(self, elem: dict) -> bool:
        """Return True if the element has low contrast (ratio < 2.0).

        Uses parse_rgba + contrast_ratio from dark_pattern_utils.
        """
        try:
            fg = parse_rgba(elem.get("color", "rgb(0,0,0)"))
            bg = parse_rgba(elem.get("backgroundColor", "rgb(255,255,255)"))
            ratio = contrast_ratio(fg, bg)
            return ratio < self.CONTRAST_THRESHOLD
        except (ValueError, TypeError):
            return False

    def _is_tiny_font(self, elem: dict, elements: list[dict]) -> bool:
        """Return True if font size < 25% of max price font size on page."""
        font_size = elem.get("fontSize", 0)
        if not isinstance(font_size, (int, float)) or font_size <= 0:
            return False

        # Find max font size among elements that look like price elements
        price_sizes = []
        for e in elements:
            text = e.get("text", "")
            # Heuristic: price elements contain currency symbols or digits with ¥/$
            if any(c in text for c in ("¥", "$", "€", "£")) or (
                any(c.isdigit() for c in text) and "円" in text
            ):
                fs = e.get("fontSize", 0)
                if isinstance(fs, (int, float)) and fs > 0:
                    price_sizes.append(fs)

        if not price_sizes:
            return False

        max_price_size = max(price_sizes)
        if max_price_size <= 0:
            return False

        return (font_size / max_price_size) < self.TINY_FONT_RATIO

    def _is_css_hidden(self, elem: dict) -> bool:
        """Return True if the element is hidden via CSS tricks."""
        # Offscreen positioning
        left = elem.get("left", 0)
        if isinstance(left, (int, float)) and left < self.OFFSCREEN_LEFT_THRESHOLD:
            return True

        # Zero opacity
        opacity = elem.get("opacity", 1.0)
        if isinstance(opacity, (int, float)) and opacity == 0:
            return True

        # Zero font size
        font_size = elem.get("fontSize", 1)
        if isinstance(font_size, (int, float)) and font_size == 0:
            return True

        # display: none
        display = elem.get("display", "")
        if isinstance(display, str) and display.lower() == "none":
            return True

        # visibility: hidden
        visibility = elem.get("visibility", "")
        if isinstance(visibility, str) and visibility.lower() == "hidden":
            return True

        return False

    @staticmethod
    def _calculate_deception_score(techniques: list[dict]) -> float:
        """Calculate deception score from detected techniques.

        Score = min(1.0, len(techniques) * 0.2), clamped to [0.0, 1.0].
        """
        return min(1.0, len(techniques) * 0.2)

    @staticmethod
    def _build_technique(technique_type: str, elem: dict) -> dict:
        """Build a technique record from an element."""
        return {
            "type": technique_type,
            "selector": elem.get("selector", ""),
            "text": elem.get("text", "")[:100],
            "evidence": {
                "color": elem.get("color"),
                "backgroundColor": elem.get("backgroundColor"),
                "fontSize": elem.get("fontSize"),
                "display": elem.get("display"),
                "visibility": elem.get("visibility"),
                "opacity": elem.get("opacity"),
                "left": elem.get("left"),
            },
        }

    @staticmethod
    def _build_misleading_font_technique(elem: dict, median_font_size: float) -> dict:
        """Build a misleading_font_size technique record.

        Requirements: 17.5
        """
        font_size = elem.get("fontSize", 0)
        ratio = (font_size / median_font_size) if median_font_size > 0 else 0.0
        return {
            "type": "misleading_font_size",
            "selector": elem.get("selector", ""),
            "text": elem.get("text", "")[:200],
            "evidence": {
                "fontSize": font_size,
                "medianFontSize": median_font_size,
                "ratio": round(ratio, 4),
            },
        }

    @staticmethod
    def _add_violations(ctx: CrawlContext, techniques: list[dict]) -> None:
        """Add violations to ctx for each detected technique.

        misleading_font_size uses its own dark_pattern_category (Req 17.6).
        All other techniques use visual_deception.
        """
        for technique in techniques:
            t_type = technique["type"]
            category = (
                "misleading_font_size"
                if t_type == "misleading_font_size"
                else "visual_deception"
            )
            ctx.violations.append({
                "violation_type": t_type,
                "severity": "warning",
                "dark_pattern_category": category,
                "selector": technique.get("selector", ""),
                "text": technique.get("text", ""),
                "evidence": technique.get("evidence", {}),
            })
