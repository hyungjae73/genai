"""
Property-based tests for JourneyScript parsing and serialisation.

**Validates: Requirements 3.12**

Properties tested:
  Property 13: JourneyScript のラウンドトリップ
"""

import json

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.pipeline.plugins.dark_pattern_utils import (
    VALID_ASSERTION_KEYS,
    VALID_STEP_TYPES,
    parse_journey_script,
    serialize_journey_script,
)

# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestParseJourneyScript:
    def test_valid_add_to_cart(self):
        raw = [{"step": "add_to_cart", "selector": ".btn"}]
        result = parse_journey_script(raw)
        assert len(result) == 1
        assert result[0]["step"] == "add_to_cart"

    def test_valid_json_string(self):
        raw = json.dumps([{"step": "click", "selector": "#x"}])
        result = parse_journey_script(raw)
        assert result[0]["step"] == "click"

    def test_all_step_types(self):
        steps = [{"step": t} for t in VALID_STEP_TYPES]
        result = parse_journey_script(steps)
        assert len(result) == len(VALID_STEP_TYPES)

    def test_with_assertions(self):
        raw = [
            {
                "step": "goto_checkout",
                "assert": {"no_new_fees": True, "no_upsell_modal": True},
            }
        ]
        result = parse_journey_script(raw)
        assert result[0]["assert"]["no_new_fees"] is True

    def test_invalid_step_type_raises(self):
        with pytest.raises(ValueError, match="invalid type"):
            parse_journey_script([{"step": "fly_to_moon"}])

    def test_invalid_assertion_key_raises(self):
        with pytest.raises(ValueError, match="invalid assertion keys"):
            parse_journey_script([{"step": "click", "assert": {"bad_key": True}}])

    def test_not_a_list_raises(self):
        with pytest.raises(ValueError):
            parse_journey_script({"step": "click"})

    def test_invalid_json_string_raises(self):
        with pytest.raises(ValueError, match="JSON decode error"):
            parse_journey_script("{not valid json}")

    def test_empty_list(self):
        assert parse_journey_script([]) == []


class TestSerializeJourneyScript:
    def test_round_trip(self):
        steps = [{"step": "add_to_cart", "selector": ".btn"}]
        serialised = serialize_journey_script(steps)
        parsed = json.loads(serialised)
        assert parsed == steps

    def test_unicode_preserved(self):
        steps = [{"step": "click", "label": "カートに追加"}]
        serialised = serialize_journey_script(steps)
        assert "カートに追加" in serialised


# ---------------------------------------------------------------------------
# Hypothesis strategies for valid JourneyScript steps
# ---------------------------------------------------------------------------

_step_type_st = st.sampled_from(sorted(VALID_STEP_TYPES))
_assertion_key_st = st.sampled_from(sorted(VALID_ASSERTION_KEYS))


@st.composite
def valid_step_strategy(draw):
    """Generate a single valid JourneyScript step dict."""
    step_type = draw(_step_type_st)
    step: dict = {"step": step_type}

    # Optional selector for action steps
    if step_type in ("add_to_cart", "goto_checkout", "click"):
        if draw(st.booleans()):
            step["selector"] = draw(st.text(min_size=1, max_size=50))

    # Optional wait duration
    if step_type == "wait":
        step["ms"] = draw(st.integers(min_value=0, max_value=5000))

    # Optional assertions
    if draw(st.booleans()):
        num_assertions = draw(st.integers(min_value=1, max_value=len(VALID_ASSERTION_KEYS)))
        keys = draw(
            st.lists(
                _assertion_key_st,
                min_size=num_assertions,
                max_size=num_assertions,
                unique=True,
            )
        )
        step["assert"] = {k: draw(st.booleans()) for k in keys}

    return step


@st.composite
def valid_journey_script_strategy(draw):
    """Generate a valid list of JourneyScript steps."""
    return draw(st.lists(valid_step_strategy(), min_size=0, max_size=10))


# ---------------------------------------------------------------------------
# Property 13: JourneyScript のラウンドトリップ
# **Validates: Requirements 3.12**
# ---------------------------------------------------------------------------


@given(steps=valid_journey_script_strategy())
@settings(max_examples=300)
def test_property13_journey_script_round_trip(steps):
    """Property 13: parse(serialize(parse(raw))) == parse(raw)."""
    # First parse
    first_parse = parse_journey_script(steps)

    # Serialize
    serialised = serialize_journey_script(first_parse)

    # Second parse from serialised string
    second_parse = parse_journey_script(serialised)

    assert first_parse == second_parse, (
        f"Round-trip mismatch:\n  first:  {first_parse}\n  second: {second_parse}"
    )


@given(steps=valid_journey_script_strategy())
@settings(max_examples=200)
def test_property13_serialise_is_valid_json(steps):
    """Property 13 (auxiliary): serialize_journey_script always produces valid JSON."""
    parsed = parse_journey_script(steps)
    serialised = serialize_journey_script(parsed)
    # Must be parseable
    decoded = json.loads(serialised)
    assert isinstance(decoded, list)
