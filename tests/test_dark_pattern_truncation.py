"""
Property-based tests for Middle-Out Truncation and HTML tag stripping.

**Validates: Requirements 2.3, 13.5**

Properties tested:
  Property 6: HTMLタグパージの完全性
  Property 12: Middle-Out Truncation の保持特性
"""

import re

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.pipeline.plugins.dark_pattern_utils import middle_out_truncate, strip_html_tags

# ---------------------------------------------------------------------------
# Unit tests — strip_html_tags
# ---------------------------------------------------------------------------


class TestStripHtmlTags:
    def test_removes_script_content(self):
        html = "<p>Hello</p><script>alert('xss')</script><p>World</p>"
        result = strip_html_tags(html)
        assert "alert" not in result
        assert "Hello" in result
        assert "World" in result

    def test_removes_style_content(self):
        html = "<style>body { color: red; }</style><p>Text</p>"
        result = strip_html_tags(html)
        assert "color" not in result
        assert "Text" in result

    def test_removes_noscript_content(self):
        html = "<noscript>Enable JS</noscript><p>Main</p>"
        result = strip_html_tags(html)
        assert "Enable JS" not in result
        assert "Main" in result

    def test_removes_all_tags(self):
        html = "<div><span class='x'>Hello</span></div>"
        result = strip_html_tags(html)
        assert "<" not in result
        assert "Hello" in result

    def test_empty_string(self):
        assert strip_html_tags("") == ""

    def test_plain_text_unchanged(self):
        text = "Hello World"
        assert strip_html_tags(text) == text

    def test_normalises_whitespace(self):
        html = "<p>Hello   \n\t  World</p>"
        result = strip_html_tags(html)
        assert "  " not in result


# ---------------------------------------------------------------------------
# Unit tests — middle_out_truncate
# ---------------------------------------------------------------------------


class TestMiddleOutTruncate:
    def test_short_text_unchanged(self):
        text = "Hello"
        assert middle_out_truncate(text, 100) == text

    def test_exact_length_unchanged(self):
        text = "A" * 100
        assert middle_out_truncate(text, 100) == text

    def test_truncated_contains_marker(self):
        text = "A" * 1000
        result = middle_out_truncate(text, 100)
        assert "[...中略...]" in result

    def test_top_20_percent_preserved(self):
        text = "T" * 200 + "M" * 600 + "B" * 200
        result = middle_out_truncate(text, 100)
        top_len = int(100 * 0.20)
        assert result[:top_len] == text[:top_len]

    def test_bottom_30_percent_preserved(self):
        text = "T" * 200 + "M" * 600 + "B" * 200
        result = middle_out_truncate(text, 100)
        bottom_len = int(100 * 0.30)
        assert result[-bottom_len:] == text[-bottom_len:]

    def test_zero_max_chars(self):
        # Edge case: max_chars=0 → top_len=0, bottom_len=0
        text = "Hello World"
        result = middle_out_truncate(text, 0)
        assert "[...中略...]" in result


# ---------------------------------------------------------------------------
# Property 6: HTMLタグパージの完全性
# **Validates: Requirements 2.3**
# ---------------------------------------------------------------------------

# Strategy: generate HTML-like strings with script/style/noscript blocks
_TAG_NAMES = st.sampled_from(["script", "style", "noscript", "div", "p", "span"])
_INNER_TEXT = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="<>"),
    min_size=0,
    max_size=50,
)


@st.composite
def html_with_forbidden_blocks(draw):
    """Generate HTML strings that may contain script/style/noscript blocks."""
    parts = []
    for _ in range(draw(st.integers(0, 5))):
        tag = draw(_TAG_NAMES)
        inner = draw(_INNER_TEXT)
        parts.append(f"<{tag}>{inner}</{tag}>")
    return "".join(parts)


@given(html=html_with_forbidden_blocks())
@settings(max_examples=200)
def test_property6_no_forbidden_tags_in_output(html):
    """Property 6: output contains no <script>, <style>, <noscript> content."""
    result = strip_html_tags(html)
    # No HTML tags remain
    assert not re.search(r"<[^>]+>", result), (
        f"HTML tag found in output: {result!r}"
    )


@given(html=html_with_forbidden_blocks())
@settings(max_examples=200)
def test_property6_no_script_style_noscript_content(html):
    """Property 6: script/style/noscript blocks are removed (content stripped).

    We verify this by constructing HTML where the forbidden-tag content is
    unique (not present in any other tag), then checking it's absent from
    the output.
    """
    # Build a version where forbidden-tag content is replaced with a unique
    # sentinel that won't appear elsewhere, then check the sentinel is gone.
    sentinel = "FORBIDDEN_SENTINEL_XYZ_12345"
    # Replace content inside forbidden tags with the sentinel
    modified_html = re.sub(
        r"(<(?:script|style|noscript)[^>]*>).*?(</(?:script|style|noscript)>)",
        rf"\g<1>{sentinel}\g<2>",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    # Only run the assertion if the sentinel was actually injected
    if sentinel in modified_html:
        result = strip_html_tags(modified_html)
        assert sentinel not in result, (
            f"Forbidden tag content (sentinel) found in output: {result!r}"
        )


# ---------------------------------------------------------------------------
# Property 12: Middle-Out Truncation の保持特性
# **Validates: Requirements 13.5**
# ---------------------------------------------------------------------------


@given(
    text=st.text(min_size=1, max_size=2000),
    max_chars=st.integers(min_value=1, max_value=500),
)
@settings(max_examples=300)
def test_property12_truncation_preserves_top_and_bottom(text, max_chars):
    """Property 12: top 20% and bottom 30% are preserved when truncated."""
    result = middle_out_truncate(text, max_chars)

    if len(text) <= max_chars:
        # No truncation: original returned unchanged
        assert result == text
    else:
        top_len = int(max_chars * 0.20)
        bottom_len = int(max_chars * 0.30)

        # (a) Top 20% preserved
        if top_len > 0:
            assert result.startswith(text[:top_len]), (
                f"Top {top_len} chars not preserved. "
                f"Expected prefix: {text[:top_len]!r}, got: {result[:top_len]!r}"
            )

        # (b) Bottom 30% preserved
        if bottom_len > 0:
            assert result.endswith(text[-bottom_len:]), (
                f"Bottom {bottom_len} chars not preserved. "
                f"Expected suffix: {text[-bottom_len:]!r}, got: {result[-bottom_len:]!r}"
            )

        # (c) Marker present
        assert "[...中略...]" in result, "Truncation marker missing"


@given(text=st.text(min_size=0, max_size=100))
@settings(max_examples=100)
def test_property12_no_truncation_when_short(text):
    """Property 12: text shorter than max_chars is returned unchanged."""
    max_chars = len(text) + 50
    assert middle_out_truncate(text, max_chars) == text
