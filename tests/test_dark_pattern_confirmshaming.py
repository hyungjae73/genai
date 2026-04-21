"""
Property-based tests for Confirmshaming pattern detection.

**Validates: Requirements 4.8, 4.9, 10.2, 10.3, 10.5**

Properties tested:
  Property 15: コンファームシェイミングパターンマッチの一貫性
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.pipeline.plugins.dark_pattern_utils import (
    CONFIRMSHAMING_PATTERNS_EN,
    CONFIRMSHAMING_PATTERNS_JA,
    detect_confirmshaming,
)

# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestDetectConfirmshaming:
    # Japanese patterns
    def test_ja_no_want(self):
        assert detect_confirmshaming("いいえ、節約したくありません") is not None

    def test_ja_no_need(self):
        assert detect_confirmshaming("いいえ、不要です") is not None

    def test_ja_miss_out(self):
        assert detect_confirmshaming("チャンスを逃すのは嫌です") is not None

    def test_ja_regret(self):
        assert detect_confirmshaming("後悔したくない") is not None

    def test_ja_lose(self):
        assert detect_confirmshaming("損するのは嫌だ") is not None

    # English patterns
    def test_en_no_dont_want(self):
        assert detect_confirmshaming("No thanks, I don't want to save money") is not None

    def test_en_miss_out(self):
        assert detect_confirmshaming("I don't want to miss out") is not None

    def test_en_regret(self):
        assert detect_confirmshaming("I will regret this") is not None

    # Negative cases
    def test_neutral_text_none(self):
        assert detect_confirmshaming("Yes, add to cart") is None

    def test_empty_string_none(self):
        assert detect_confirmshaming("") is None

    def test_unrelated_text_none(self):
        assert detect_confirmshaming("Continue shopping") is None

    # Case insensitivity
    def test_en_uppercase(self):
        assert detect_confirmshaming("NO THANKS, I DON'T WANT TO SAVE MONEY") is not None

    def test_en_mixed_case(self):
        assert detect_confirmshaming("No Thanks, I Don't Want To Save Money") is not None


# ---------------------------------------------------------------------------
# Property 15: コンファームシェイミングパターンマッチの一貫性
# **Validates: Requirements 4.8, 4.9, 10.2, 10.3, 10.5**
# ---------------------------------------------------------------------------

# Known confirmshaming texts for case-insensitivity testing
_KNOWN_CONFIRMSHAMING_TEXTS = [
    "No thanks, I don't want to save money",
    "No, I don't need this",
    "I don't want to miss out",
    "I will regret this",
    "I don't want to lose out",
    "いいえ、節約したくありません",
    "いいえ、不要です",
    "チャンスを逃すのは嫌です",
    "後悔したくない",
    "損するのは嫌だ",
]


@given(text=st.sampled_from(_KNOWN_CONFIRMSHAMING_TEXTS))
@settings(max_examples=100)
def test_property15_case_insensitive_upper(text):
    """Property 15: if text matches, text.upper() also matches."""
    original_result = detect_confirmshaming(text)
    if original_result is not None:
        upper_result = detect_confirmshaming(text.upper())
        assert upper_result is not None, (
            f"text.upper() did not match when original did: {text.upper()!r}"
        )


@given(text=st.sampled_from(_KNOWN_CONFIRMSHAMING_TEXTS))
@settings(max_examples=100)
def test_property15_case_insensitive_lower(text):
    """Property 15: if text matches, text.lower() also matches."""
    original_result = detect_confirmshaming(text)
    if original_result is not None:
        lower_result = detect_confirmshaming(text.lower())
        assert lower_result is not None, (
            f"text.lower() did not match when original did: {text.lower()!r}"
        )


@given(
    text=st.text(
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd", "Zs"),
            whitelist_characters="、。！？ '\"",
        ),
        min_size=0,
        max_size=100,
    )
)
@settings(max_examples=300)
def test_property15_arbitrary_text_case_consistency(text):
    """Property 15: for any text, upper/lower case gives consistent results."""
    result = detect_confirmshaming(text)
    upper_result = detect_confirmshaming(text.upper())
    lower_result = detect_confirmshaming(text.lower())

    # If original matches, upper and lower must also match (or vice versa)
    # The key property: case should not affect whether a match is found
    # (both None or both non-None for upper/lower)
    if result is not None:
        # upper and lower should also match (patterns are IGNORECASE)
        assert upper_result is not None, (
            f"upper() lost match for {text!r}"
        )
        assert lower_result is not None, (
            f"lower() lost match for {text!r}"
        )
