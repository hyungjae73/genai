"""
Property-based tests for LLM response parsing utilities.

**Validates: Requirements 8.3, 8.5**

Properties tested:
  Property 8: LLM confidence クランプ
  Property 9: LLM JSONブロック抽出
"""

import json

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.pipeline.plugins.dark_pattern_utils import clamp_confidence, extract_json_block

# ---------------------------------------------------------------------------
# Unit tests — clamp_confidence
# ---------------------------------------------------------------------------


class TestClampConfidence:
    def test_value_in_range_unchanged(self):
        assert clamp_confidence(0.5) == pytest.approx(0.5)

    def test_zero_unchanged(self):
        assert clamp_confidence(0.0) == pytest.approx(0.0)

    def test_one_unchanged(self):
        assert clamp_confidence(1.0) == pytest.approx(1.0)

    def test_negative_clamped_to_zero(self):
        assert clamp_confidence(-0.5) == pytest.approx(0.0)

    def test_above_one_clamped(self):
        assert clamp_confidence(1.5) == pytest.approx(1.0)

    def test_large_negative(self):
        assert clamp_confidence(-999.0) == pytest.approx(0.0)

    def test_large_positive(self):
        assert clamp_confidence(999.0) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Unit tests — extract_json_block
# ---------------------------------------------------------------------------


class TestExtractJsonBlock:
    def test_fenced_json_block(self):
        text = '```json\n{"key": "value"}\n```'
        result = extract_json_block(text)
        assert result == {"key": "value"}

    def test_raw_json_object(self):
        text = 'Some text {"is_subscription": true, "confidence": 0.9} more text'
        result = extract_json_block(text)
        assert result is not None
        assert result["is_subscription"] is True

    def test_no_json_returns_none(self):
        assert extract_json_block("No JSON here at all") is None

    def test_invalid_json_in_block_falls_back(self):
        # Invalid JSON in fenced block only — should return None
        text = "```json\n{invalid}\n```\nno raw json here"
        result = extract_json_block(text)
        assert result is None

    def test_empty_string_returns_none(self):
        assert extract_json_block("") is None

    def test_nested_json(self):
        obj = {"a": {"b": [1, 2, 3]}, "c": True}
        text = f"```json\n{json.dumps(obj)}\n```"
        assert extract_json_block(text) == obj

    def test_fenced_block_case_insensitive(self):
        text = '```JSON\n{"x": 1}\n```'
        result = extract_json_block(text)
        assert result == {"x": 1}


# ---------------------------------------------------------------------------
# Property 8: LLM confidence クランプ
# **Validates: Requirements 8.5**
# ---------------------------------------------------------------------------


@given(v=st.floats(allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6))
@settings(max_examples=500)
def test_property8_clamped_value_in_range(v):
    """Property 8: clamped value always in [0.0, 1.0]."""
    result = clamp_confidence(v)
    assert 0.0 <= result <= 1.0, f"clamp_confidence({v}) = {result} out of range"


@given(v=st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
@settings(max_examples=300)
def test_property8_in_range_values_unchanged(v):
    """Property 8: values already in [0.0, 1.0] are not changed."""
    result = clamp_confidence(v)
    assert result == pytest.approx(v, abs=1e-12), (
        f"clamp_confidence({v}) = {result} changed an in-range value"
    )


# ---------------------------------------------------------------------------
# Property 9: LLM JSONブロック抽出
# **Validates: Requirements 8.3**
# ---------------------------------------------------------------------------

# Strategy: generate valid JSON-serialisable dicts
_json_leaf = st.one_of(
    st.text(min_size=0, max_size=30),
    st.integers(min_value=-1000, max_value=1000),
    st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
    st.booleans(),
    st.none(),
)

_json_dict = st.dictionaries(
    st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_")),
    _json_leaf,
    min_size=1,
    max_size=5,
)


@given(obj=_json_dict)
@settings(max_examples=300)
def test_property9_fenced_block_round_trip(obj):
    """Property 9: JSON wrapped in ```json...``` is correctly extracted."""
    json_str = json.dumps(obj)
    wrapped = f"```json\n{json_str}\n```"
    result = extract_json_block(wrapped)
    assert result is not None, f"extract_json_block returned None for: {wrapped!r}"
    assert result == obj, f"Round-trip mismatch: {result!r} != {obj!r}"


@given(obj=_json_dict)
@settings(max_examples=200)
def test_property9_raw_json_round_trip(obj):
    """Property 9: raw JSON object in text is correctly extracted."""
    json_str = json.dumps(obj)
    text = f"Some prefix text. {json_str} Some suffix text."
    result = extract_json_block(text)
    assert result is not None
    assert result == obj
