"""
Dark Pattern Detection Utilities.

Pure functions shared across CSSVisualPlugin, LLMClassifierPlugin,
JourneyPlugin, UITrapPlugin, and DarkPatternScore post-process.

All functions are side-effect-free and testable without Playwright.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Task 1.1 — WCAG Contrast Ratio
# ---------------------------------------------------------------------------


def parse_rgba(color_str: str) -> tuple[int, int, int, float]:
    """Parse a CSS color string into (r, g, b, alpha).

    Supports:
      - "rgb(r, g, b)"
      - "rgba(r, g, b, a)"

    Returns:
        Tuple of (r, g, b, alpha) where r/g/b are 0-255 ints and alpha is
        a 0.0-1.0 float (defaults to 1.0 for rgb()).

    Raises:
        ValueError: if the string cannot be parsed.
    """
    color_str = color_str.strip()
    rgba_match = re.match(
        r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*([\d.]+))?\s*\)",
        color_str,
        re.IGNORECASE,
    )
    if not rgba_match:
        raise ValueError(f"Cannot parse color string: {color_str!r}")

    r = int(rgba_match.group(1))
    g = int(rgba_match.group(2))
    b = int(rgba_match.group(3))
    alpha = float(rgba_match.group(4)) if rgba_match.group(4) is not None else 1.0

    # Clamp to valid ranges
    r = max(0, min(255, r))
    g = max(0, min(255, g))
    b = max(0, min(255, b))
    alpha = max(0.0, min(1.0, alpha))

    return r, g, b, alpha


def relative_luminance(r: int, g: int, b: int) -> float:
    """Compute WCAG 2.0 relative luminance for an sRGB colour.

    Applies sRGB gamma correction (linearisation) per WCAG 2.0 spec:
      if c/255 <= 0.03928: c_lin = c/255 / 12.92
      else:                c_lin = ((c/255 + 0.055) / 1.055) ** 2.4

    Returns:
        Relative luminance in [0.0, 1.0].
    """

    def _linearise(c: int) -> float:
        v = c / 255.0
        if v <= 0.03928:
            return v / 12.92
        return ((v + 0.055) / 1.055) ** 2.4

    r_lin = _linearise(r)
    g_lin = _linearise(g)
    b_lin = _linearise(b)
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def contrast_ratio(fg: tuple, bg: tuple) -> float:
    """Compute WCAG 2.0 contrast ratio between two colours.

    Args:
        fg: Foreground colour as (r, g, b) or (r, g, b, a) tuple.
        bg: Background colour as (r, g, b) or (r, g, b, a) tuple.

    Returns:
        Contrast ratio in [1.0, 21.0].
    """
    l_fg = relative_luminance(fg[0], fg[1], fg[2])
    l_bg = relative_luminance(bg[0], bg[1], bg[2])
    l1 = max(l_fg, l_bg)
    l2 = min(l_fg, l_bg)
    return (l1 + 0.05) / (l2 + 0.05)


# ---------------------------------------------------------------------------
# Task 1.3 — Middle-Out Truncation and HTML tag stripping
# ---------------------------------------------------------------------------

# Tags whose entire content (including children) should be removed
_REMOVE_CONTENT_TAGS = re.compile(
    r"<(script|style|noscript)(\s[^>]*)?>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)
# All remaining HTML tags
_HTML_TAG = re.compile(r"<[^>]+>", re.DOTALL)
# Collapse whitespace
_WHITESPACE = re.compile(r"\s+")


def strip_html_tags(html: str) -> str:
    """Remove HTML tags and return plain text.

    Steps:
      1. Remove <script>, <style>, <noscript> blocks (including content).
      2. Remove all remaining HTML tags.
      3. Normalise whitespace.

    Args:
        html: Raw HTML string.

    Returns:
        Plain text with no HTML markup.
    """
    text = _REMOVE_CONTENT_TAGS.sub(" ", html)
    text = _HTML_TAG.sub(" ", text)
    text = _WHITESPACE.sub(" ", text)
    return text.strip()


def middle_out_truncate(text: str, max_chars: int) -> str:
    """Truncate *text* to *max_chars* using Middle-Out strategy.

    Preserves:
      - Top 20 % of characters (header / price display area)
      - Bottom 30 % of characters (footer / cancellation terms)

    Inserts "[...中略...]" between the two preserved sections.

    If ``len(text) <= max_chars`` the original text is returned unchanged.

    🚨 CTO Override: simple head-truncation is forbidden.

    Args:
        text:      Input text string.
        max_chars: Maximum character budget.

    Returns:
        Truncated string (or original if short enough).
    """
    if len(text) <= max_chars:
        return text

    top_len = int(max_chars * 0.20)
    bottom_len = int(max_chars * 0.30)

    top_part = text[:top_len]
    bottom_part = text[-bottom_len:] if bottom_len > 0 else ""

    return top_part + "\n[...中略...]\n" + bottom_part


# ---------------------------------------------------------------------------
# Task 1.5 — LLM response parsing utilities
# ---------------------------------------------------------------------------

_JSON_BLOCK = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


def extract_json_block(text: str) -> Optional[dict]:
    """Extract a JSON object from *text*.

    Tries in order:
      1. Fenced markdown code block: ```json ... ```
      2. Raw JSON object anywhere in the string.

    Args:
        text: LLM response text.

    Returns:
        Parsed dict, or None if no valid JSON found.
    """
    # 1. Fenced block
    block_match = _JSON_BLOCK.search(text)
    if block_match:
        try:
            return json.loads(block_match.group(1))
        except json.JSONDecodeError:
            pass

    # 2. Raw JSON object
    obj_match = _JSON_OBJECT.search(text)
    if obj_match:
        try:
            return json.loads(obj_match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def clamp_confidence(value: float) -> float:
    """Clamp *value* to the range [0.0, 1.0].

    Args:
        value: Raw confidence float from LLM response.

    Returns:
        Value clamped to [0.0, 1.0].
    """
    return max(0.0, min(1.0, value))


# ---------------------------------------------------------------------------
# Task 1.7 — JourneyScript parsing and serialisation
# ---------------------------------------------------------------------------

VALID_STEP_TYPES = frozenset(
    {"add_to_cart", "goto_checkout", "click", "wait", "screenshot"}
)
VALID_ASSERTION_KEYS = frozenset(
    {"no_new_fees", "no_upsell_modal", "no_preselected_subscription"}
)


def parse_journey_script(raw: Any) -> list[dict]:
    """Parse and validate a JourneyScript definition.

    *raw* may be:
      - A JSON string (will be decoded first).
      - A list of step dicts.

    Each step must have a ``"step"`` key with a value in
    ``VALID_STEP_TYPES``.  Optional ``"assert"`` dict keys must be in
    ``VALID_ASSERTION_KEYS``.

    Args:
        raw: Raw JourneyScript (JSON string or list).

    Returns:
        Validated list of step dicts.

    Raises:
        ValueError: if the input is not a valid JourneyScript.
    """
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"JourneyScript JSON decode error: {exc}") from exc

    if not isinstance(raw, list):
        raise ValueError(
            f"JourneyScript must be a list of steps, got {type(raw).__name__}"
        )

    validated: list[dict] = []
    for i, step in enumerate(raw):
        if not isinstance(step, dict):
            raise ValueError(f"Step {i} must be a dict, got {type(step).__name__}")

        step_type = step.get("step")
        if step_type not in VALID_STEP_TYPES:
            raise ValueError(
                f"Step {i} has invalid type {step_type!r}. "
                f"Valid types: {sorted(VALID_STEP_TYPES)}"
            )

        # Validate assertion keys if present
        assertions = step.get("assert", {})
        if assertions:
            if not isinstance(assertions, dict):
                raise ValueError(f"Step {i} 'assert' must be a dict")
            invalid_keys = set(assertions.keys()) - VALID_ASSERTION_KEYS
            if invalid_keys:
                raise ValueError(
                    f"Step {i} has invalid assertion keys: {invalid_keys}. "
                    f"Valid keys: {sorted(VALID_ASSERTION_KEYS)}"
                )

        validated.append(step)

    return validated


def serialize_journey_script(steps: list[dict]) -> str:
    """Serialise a validated step list back to a JSON string.

    Args:
        steps: List of step dicts (as returned by ``parse_journey_script``).

    Returns:
        JSON string representation.
    """
    return json.dumps(steps, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Task 1.9 — Confirmshaming pattern detection
# ---------------------------------------------------------------------------

CONFIRMSHAMING_PATTERNS_JA: list[re.Pattern] = [
    # "いいえ" + negative self-reference (plain and polite forms)
    re.compile(r"いいえ.*(?:したくない|したくありません|不要|必要ない|いりません|けっこうです)", re.IGNORECASE),
    # Benefit-forfeiture expressions
    re.compile(r"(?:不要です|必要ありません|いりません)", re.IGNORECASE),
    # Emotional manipulation
    re.compile(r"(?:チャンスを逃す|後悔|損する|損をする)", re.IGNORECASE),
]

CONFIRMSHAMING_PATTERNS_EN: list[re.Pattern] = [
    # "No" + negative self-reference
    re.compile(r"\bno\b.*(?:don'?t want|not interested|don'?t need)", re.IGNORECASE),
    # Emotional manipulation
    re.compile(r"\b(?:miss out|regret|lose out)\b", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Task 1.9b — Important keyword detection for misleading_font_size
# Requirement 17
# ---------------------------------------------------------------------------

# Japanese keywords indicating important purchase terms
IMPORTANT_KEYWORDS_JA: list[str] = [
    "定期", "自動更新", "自動継続", "解約", "キャンセル", "返金", "返品",
    "手数料", "縛り", "最低利用期間", "違約金", "特定商取引", "重要事項",
    "注意事項", "同意", "承諾",
]

# English keywords indicating important purchase terms
IMPORTANT_KEYWORDS_EN: list[str] = [
    "subscription", "auto-renew", "auto renewal", "cancel", "cancellation",
    "refund", "fee", "charge", "terms", "important", "notice", "agree",
    "consent", "binding",
]

# Pre-compiled patterns for performance
_IMPORTANT_PATTERN_JA = re.compile(
    "|".join(re.escape(k) for k in IMPORTANT_KEYWORDS_JA),
    re.IGNORECASE,
)
_IMPORTANT_PATTERN_EN = re.compile(
    r"\b(?:" + "|".join(re.escape(k) for k in IMPORTANT_KEYWORDS_EN) + r")\b",
    re.IGNORECASE,
)


def contains_important_keyword(text: str) -> bool:
    """Return True if *text* contains any important purchase-related keyword.

    Checks both Japanese and English keyword lists.

    Args:
        text: Element text to check.

    Returns:
        True if any important keyword is found.
    """
    return bool(_IMPORTANT_PATTERN_JA.search(text) or _IMPORTANT_PATTERN_EN.search(text))


def detect_misleading_font_size(
    elem: dict,
    median_font_size: float,
    ratio_threshold: float = 0.75,
) -> bool:
    """Return True if *elem* has a misleadingly small font for important text.

    Conditions (both must be true):
      1. Element text contains an important purchase keyword.
      2. Element font size < median_font_size * ratio_threshold.

    Args:
        elem:             Element dict from BATCH_STYLE_JS.
        median_font_size: Median font size across all page elements (px).
        ratio_threshold:  Font size ratio below which text is flagged
                          (default 0.75, configurable via
                          MISLEADING_FONT_SIZE_RATIO env var).

    Returns:
        True if the element should be flagged as misleading_font_size.
    """
    if median_font_size <= 0:
        return False

    font_size = elem.get("fontSize", 0)
    if not isinstance(font_size, (int, float)) or font_size <= 0:
        return False

    if (font_size / median_font_size) >= ratio_threshold:
        return False

    text = elem.get("text", "")
    return contains_important_keyword(text)


def compute_median_font_size(elements: list[dict]) -> float:
    """Compute the median font size across all page elements.

    Args:
        elements: List of element dicts from BATCH_STYLE_JS.

    Returns:
        Median font size in px, or 0.0 if no valid sizes found.
    """
    sizes = [
        e["fontSize"]
        for e in elements
        if isinstance(e.get("fontSize"), (int, float)) and e["fontSize"] > 0
    ]
    if not sizes:
        return 0.0
    sizes.sort()
    mid = len(sizes) // 2
    if len(sizes) % 2 == 0:
        return (sizes[mid - 1] + sizes[mid]) / 2.0
    return float(sizes[mid])


def detect_confirmshaming(text: str) -> Optional[str]:
    """Detect confirmshaming patterns in *text*.

    Checks Japanese patterns first, then English patterns.
    Matching is case-insensitive.

    Args:
        text: Button or link text to analyse.

    Returns:
        A string describing the matched pattern type, or None if no match.
    """
    for pattern in CONFIRMSHAMING_PATTERNS_JA:
        if pattern.search(text):
            return "confirmshaming_ja"

    for pattern in CONFIRMSHAMING_PATTERNS_EN:
        if pattern.search(text):
            return "confirmshaming_en"

    return None


# ---------------------------------------------------------------------------
# Task 1.11 — DarkPatternScore computation
# ---------------------------------------------------------------------------

# Metadata keys written by each plugin
_PLUGIN_META_KEYS: dict[str, str] = {
    "css_visual": "cssvisual_deception_score",
    "llm_classifier": "llmclassifier_results",
    "journey": "journey_steps",
    "ui_trap": "uitrap_detections",
}


def _extract_subscore(plugin_key: str, metadata: dict) -> float:
    """Extract a normalised subscore from *metadata* for *plugin_key*."""
    if plugin_key == "css_visual":
        return float(metadata.get("cssvisual_deception_score", 0.0))

    if plugin_key == "llm_classifier":
        results = metadata.get("llmclassifier_results", [])
        if not results:
            return 0.0
        confidences = [
            r.get("confidence", 0.0)
            for r in results
            if isinstance(r, dict)
        ]
        return max(confidences) if confidences else 0.0

    if plugin_key == "journey":
        steps = metadata.get("journey_steps", [])
        if not steps:
            return 0.0
        violated = sum(
            1 for s in steps if isinstance(s, dict) and s.get("assertion_failed")
        )
        return min(1.0, violated / len(steps))

    if plugin_key == "ui_trap":
        detections = metadata.get("uitrap_detections", [])
        if not detections:
            return 0.0
        # Each detection contributes 0.25, capped at 1.0
        return min(1.0, len(detections) * 0.25)

    return 0.0


def _plugin_was_executed(plugin_key: str, executed_plugins: set) -> bool:
    """Return True if *plugin_key* appears in *executed_plugins*."""
    # Accept both short key and full class name variants
    aliases = {
        "css_visual": {"CSSVisualPlugin", "css_visual"},
        "llm_classifier": {"LLMClassifierPlugin", "llm_classifier"},
        "journey": {"JourneyPlugin", "journey"},
        "ui_trap": {"UITrapPlugin", "ui_trap"},
    }
    return bool(aliases.get(plugin_key, set()) & executed_plugins)


def compute_dark_pattern_score(ctx: "CrawlContext") -> "CrawlContext":  # type: ignore[name-defined]
    """Compute the integrated DarkPatternScore and write it to *ctx*.

    Algorithm (🚨 CTO Override — weighted average is forbidden):
      1. For each of the 4 plugins, determine whether it was executed.
      2. Executed plugins contribute their actual subscore.
      3. Unexecuted plugins contribute the penalty baseline
         (env ``DARK_PATTERN_PENALTY_BASELINE``, default 0.15).
      4. Final score = max(all subscores), clamped to [0.0, 1.0].
      5. If score >= threshold (env ``DARK_PATTERN_SCORE_THRESHOLD``,
         default 0.6), append a ``high_dark_pattern_risk`` violation.

    Writes to ``ctx.metadata``:
      - ``darkpattern_score``   (float)
      - ``darkpattern_subscores`` (dict)

    Args:
        ctx: Current CrawlContext.

    Returns:
        Updated CrawlContext.
    """
    penalty = float(os.environ.get("DARK_PATTERN_PENALTY_BASELINE", "0.15"))
    threshold = float(os.environ.get("DARK_PATTERN_SCORE_THRESHOLD", "0.6"))

    # Collect executed plugin names from pipeline_stages metadata
    executed_plugins: set = set()
    for stage_info in ctx.metadata.get("pipeline_stages", {}).values():
        if isinstance(stage_info, dict):
            executed_plugins.update(stage_info.get("executed_plugins", []))

    subscores: dict[str, float] = {}
    for key in _PLUGIN_META_KEYS:
        if _plugin_was_executed(key, executed_plugins):
            subscores[key] = _extract_subscore(key, ctx.metadata)
        else:
            subscores[key] = penalty

    score = max(subscores.values()) if subscores else 0.0
    score = max(0.0, min(1.0, score))

    ctx.metadata["darkpattern_score"] = score
    ctx.metadata["darkpattern_subscores"] = subscores

    if score >= threshold:
        ctx.violations.append(
            {
                "violation_type": "high_dark_pattern_risk",
                "severity": "critical",
                "dark_pattern_category": "high_dark_pattern_risk",
                "score": score,
                "subscores": subscores,
            }
        )

    return ctx
