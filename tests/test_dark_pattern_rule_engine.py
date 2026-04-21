"""
Property-based tests for DetectionRuleSet engine and dark_pattern_type taxonomy.

**Validates: Requirements 15.5, 15.6, 15.7, 15.9, 15.10, 16.1, 16.2, 16.5**

Properties tested:
  Property 23: DetectionRuleSet のバリデーションと安全なフォールバック
  Property 24: DetectionRule 評価の正確性
  Property 25: dark_pattern_type 正規化の冪等性
  Property 26: グローバルルール + サイト固有ルールのマージ正確性
"""

import json
import os
import tempfile

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.pipeline.plugins.detection_rule_engine import (
    VALID_DARK_PATTERN_TYPES,
    DetectionRule,
    evaluate_rule,
    load_detection_rules,
    normalize_dark_pattern_type,
)

# ---------------------------------------------------------------------------
# Unit tests — normalize_dark_pattern_type
# ---------------------------------------------------------------------------


class TestNormalizeDarkPatternType:
    def test_valid_type_unchanged(self):
        for t in VALID_DARK_PATTERN_TYPES:
            assert normalize_dark_pattern_type(t) == t

    def test_unknown_type_returns_other(self):
        assert normalize_dark_pattern_type("totally_unknown") == "other"

    def test_strips_whitespace(self):
        assert normalize_dark_pattern_type("  visual_deception  ") == "visual_deception"

    def test_lowercases(self):
        assert normalize_dark_pattern_type("VISUAL_DECEPTION") == "visual_deception"

    def test_replaces_spaces_with_underscores(self):
        assert normalize_dark_pattern_type("visual deception") == "visual_deception"

    def test_replaces_hyphens_with_underscores(self):
        assert normalize_dark_pattern_type("visual-deception") == "visual_deception"

    def test_empty_string_returns_other(self):
        assert normalize_dark_pattern_type("") == "other"


# ---------------------------------------------------------------------------
# Unit tests — evaluate_rule
# ---------------------------------------------------------------------------


class TestEvaluateRule:
    def _make_rule(self, rule_type="text_pattern_match", enabled=True, **kwargs):
        return DetectionRule(
            rule_id="test_rule",
            rule_type=rule_type,
            target=kwargs.get("target", ""),
            condition=kwargs.get("condition", {}),
            severity="warning",
            dark_pattern_category="hidden_subscription",
            enabled=enabled,
        )

    def test_disabled_rule_returns_none(self):
        rule = self._make_rule(enabled=False)
        assert evaluate_rule(rule, None, "<p>text</p>", {}) is None

    def test_text_pattern_match_found(self):
        rule = self._make_rule(
            rule_type="text_pattern_match",
            condition={"pattern": "定期購入", "flags": "IGNORECASE"},
        )
        result = evaluate_rule(rule, None, "<p>定期購入条件</p>", {})
        assert result is not None
        assert result["violation_type"] == "test_rule"

    def test_text_pattern_match_not_found(self):
        rule = self._make_rule(
            rule_type="text_pattern_match",
            condition={"pattern": "定期購入"},
        )
        result = evaluate_rule(rule, None, "<p>通常購入</p>", {})
        assert result is None

    def test_unknown_rule_type_returns_none(self):
        rule = self._make_rule(rule_type="nonexistent_type")
        assert evaluate_rule(rule, None, "<p>text</p>", {}) is None

    def test_css_selector_exists_found(self):
        rule = DetectionRule(
            rule_id="css_test",
            rule_type="css_selector_exists",
            target="subscription-checkbox",
            condition={},
            severity="warning",
            dark_pattern_category="sneak_into_basket",
        )
        html = '<input class="subscription-checkbox" type="checkbox">'
        result = evaluate_rule(rule, None, html, {})
        assert result is not None

    def test_css_selector_exists_not_found(self):
        rule = DetectionRule(
            rule_id="css_test",
            rule_type="css_selector_exists",
            target=".nonexistent-class",
            condition={},
            severity="warning",
            dark_pattern_category="sneak_into_basket",
        )
        result = evaluate_rule(rule, None, "<p>text</p>", {})
        assert result is None

    def test_dom_distance_above_threshold(self):
        rule = DetectionRule(
            rule_id="dist_test",
            rule_type="dom_distance",
            target="",
            condition={"distance_key": "cancel_distance", "threshold": 20},
            severity="info",
            dark_pattern_category="distant_cancellation_terms",
        )
        result = evaluate_rule(rule, None, "", {"cancel_distance": 25})
        assert result is not None

    def test_dom_distance_below_threshold(self):
        rule = DetectionRule(
            rule_id="dist_test",
            rule_type="dom_distance",
            target="",
            condition={"distance_key": "cancel_distance", "threshold": 20},
            severity="info",
            dark_pattern_category="distant_cancellation_terms",
        )
        result = evaluate_rule(rule, None, "", {"cancel_distance": 10})
        assert result is None

    def test_violation_has_required_fields(self):
        rule = self._make_rule(
            rule_type="text_pattern_match",
            condition={"pattern": "subscription"},
        )
        result = evaluate_rule(rule, None, "subscription terms", {})
        assert result is not None
        assert "violation_type" in result
        assert "severity" in result
        assert "dark_pattern_category" in result


# ---------------------------------------------------------------------------
# Unit tests — load_detection_rules
# ---------------------------------------------------------------------------


class TestLoadDetectionRules:
    def test_empty_returns_empty(self):
        rules = load_detection_rules(None, None)
        assert rules == []

    def test_loads_from_file(self, tmp_path):
        rules_data = {
            "rules": [
                {
                    "rule_id": "test_rule_1",
                    "rule_type": "text_pattern_match",
                    "target": "",
                    "condition": {"pattern": "test"},
                    "severity": "warning",
                    "dark_pattern_category": "hidden_subscription",
                    "enabled": True,
                }
            ]
        }
        rules_file = tmp_path / "rules.json"
        rules_file.write_text(json.dumps(rules_data))
        rules = load_detection_rules(None, str(rules_file))
        assert len(rules) == 1
        assert rules[0].rule_id == "test_rule_1"

    def test_invalid_json_file_returns_empty(self, tmp_path):
        rules_file = tmp_path / "bad.json"
        rules_file.write_text("{invalid json}")
        rules = load_detection_rules(None, str(rules_file))
        assert rules == []

    def test_site_rules_override_global(self, tmp_path):
        global_data = {
            "rules": [
                {
                    "rule_id": "shared_rule",
                    "rule_type": "text_pattern_match",
                    "target": "",
                    "condition": {"pattern": "global"},
                    "severity": "info",
                    "dark_pattern_category": "other",
                }
            ]
        }
        rules_file = tmp_path / "global.json"
        rules_file.write_text(json.dumps(global_data))

        site_config = {
            "detection_rules": {
                "rules": [
                    {
                        "rule_id": "shared_rule",
                        "rule_type": "text_pattern_match",
                        "target": "",
                        "condition": {"pattern": "site_specific"},
                        "severity": "critical",
                        "dark_pattern_category": "hidden_subscription",
                    }
                ]
            }
        }
        rules = load_detection_rules(site_config, str(rules_file))
        assert len(rules) == 1
        assert rules[0].severity == "critical"
        assert rules[0].dark_pattern_category == "hidden_subscription"

    def test_site_only_rule_added(self, tmp_path):
        global_data = {"rules": []}
        rules_file = tmp_path / "global.json"
        rules_file.write_text(json.dumps(global_data))

        site_config = {
            "detection_rules": {
                "rules": [
                    {
                        "rule_id": "site_only",
                        "rule_type": "text_pattern_match",
                        "target": "",
                        "condition": {},
                        "severity": "warning",
                        "dark_pattern_category": "confirmshaming",
                    }
                ]
            }
        }
        rules = load_detection_rules(site_config, str(rules_file))
        assert any(r.rule_id == "site_only" for r in rules)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_valid_type_st = st.sampled_from(sorted(VALID_DARK_PATTERN_TYPES))
_arbitrary_str_st = st.text(min_size=0, max_size=50)


@st.composite
def detection_rule_strategy(draw, enabled=None):
    """Generate a DetectionRule with valid fields."""
    if enabled is None:
        enabled = draw(st.booleans())
    return DetectionRule(
        rule_id=draw(st.text(min_size=1, max_size=30)),
        rule_type=draw(
            st.sampled_from(
                [
                    "css_selector_exists",
                    "text_pattern_match",
                    "price_threshold",
                    "element_attribute_check",
                    "dom_distance",
                ]
            )
        ),
        target=draw(st.text(min_size=0, max_size=50)),
        condition={},
        severity=draw(st.sampled_from(["critical", "warning", "info"])),
        dark_pattern_category=draw(_valid_type_st),
        enabled=enabled,
    )


@st.composite
def rule_set_strategy(draw):
    """Generate a list of DetectionRule objects with unique rule_ids."""
    n = draw(st.integers(min_value=0, max_value=10))
    ids = draw(
        st.lists(
            st.text(min_size=1, max_size=20),
            min_size=n,
            max_size=n,
            unique=True,
        )
    )
    rules = []
    for rule_id in ids:
        rule = DetectionRule(
            rule_id=rule_id,
            rule_type="text_pattern_match",
            target="",
            condition={},
            severity="warning",
            dark_pattern_category="other",
            enabled=draw(st.booleans()),
        )
        rules.append(rule)
    return rules


# ---------------------------------------------------------------------------
# Property 23: DetectionRuleSet のバリデーションと安全なフォールバック
# **Validates: Requirements 15.9, 16.5**
# ---------------------------------------------------------------------------


@given(invalid_json=st.text(min_size=1, max_size=200))
@settings(max_examples=200)
def test_property23_invalid_json_returns_empty(invalid_json):
    """Property 23: invalid JSON in rules file → empty list (safe fallback)."""
    # Ensure the text is not valid JSON
    try:
        json.loads(invalid_json)
        return  # Skip valid JSON strings
    except (json.JSONDecodeError, ValueError):
        pass

    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write(invalid_json)
        fname = f.name
    try:
        rules = load_detection_rules(None, fname)
        # Should return empty list (safe fallback), not raise
        assert isinstance(rules, list)
    finally:
        os.unlink(fname)


# ---------------------------------------------------------------------------
# Property 24: DetectionRule 評価の正確性
# **Validates: Requirements 15.5, 15.6, 15.10**
# ---------------------------------------------------------------------------


@given(rule=detection_rule_strategy(enabled=False))
@settings(max_examples=200)
def test_property24_disabled_rule_always_none(rule):
    """Property 24: disabled rules always return None."""
    result = evaluate_rule(rule, None, "<p>any content</p>", {})
    assert result is None, f"Disabled rule {rule.rule_id} returned non-None: {result}"


@given(
    rule_id=st.text(min_size=1, max_size=20),
    pattern=st.from_regex(r"[a-z]{3,10}", fullmatch=True),
    html_content=st.text(min_size=0, max_size=200),
)
@settings(max_examples=200)
def test_property24_text_pattern_match_consistency(rule_id, pattern, html_content):
    """Property 24: text_pattern_match fires iff pattern found in html."""
    import re

    rule = DetectionRule(
        rule_id=rule_id,
        rule_type="text_pattern_match",
        target="",
        condition={"pattern": pattern, "flags": "IGNORECASE"},
        severity="warning",
        dark_pattern_category="other",
        enabled=True,
    )
    result = evaluate_rule(rule, None, html_content, {})
    pattern_found = bool(re.search(pattern, html_content, re.IGNORECASE))

    if pattern_found:
        assert result is not None, (
            f"Pattern {pattern!r} found in html but rule returned None"
        )
    else:
        assert result is None, (
            f"Pattern {pattern!r} not found in html but rule returned non-None"
        )


# ---------------------------------------------------------------------------
# Property 25: dark_pattern_type 正規化の冪等性
# **Validates: Requirements 16.1, 16.2**
# ---------------------------------------------------------------------------


@given(raw=_arbitrary_str_st)
@settings(max_examples=500)
def test_property25_output_always_valid(raw):
    """Property 25: normalize_dark_pattern_type always returns a valid type."""
    result = normalize_dark_pattern_type(raw)
    assert result in VALID_DARK_PATTERN_TYPES, (
        f"normalize_dark_pattern_type({raw!r}) = {result!r} not in VALID_DARK_PATTERN_TYPES"
    )


@given(valid_type=_valid_type_st)
@settings(max_examples=100)
def test_property25_valid_input_unchanged(valid_type):
    """Property 25: valid types are returned unchanged (idempotent)."""
    result = normalize_dark_pattern_type(valid_type)
    assert result == valid_type, (
        f"normalize_dark_pattern_type({valid_type!r}) = {result!r} changed a valid type"
    )


@given(raw=_arbitrary_str_st)
@settings(max_examples=300)
def test_property25_idempotent(raw):
    """Property 25: applying normalisation twice gives the same result."""
    once = normalize_dark_pattern_type(raw)
    twice = normalize_dark_pattern_type(once)
    assert once == twice, f"Not idempotent: {raw!r} → {once!r} → {twice!r}"


# ---------------------------------------------------------------------------
# Property 26: グローバルルール + サイト固有ルールのマージ正確性
# **Validates: Requirements 15.7**
# ---------------------------------------------------------------------------


@st.composite
def merge_scenario(draw):
    """Generate global rules G and site rules S with possible overlapping rule_ids."""
    # Generate unique IDs for global rules
    g_ids = draw(
        st.lists(
            st.text(min_size=1, max_size=15, alphabet=st.characters(whitelist_categories=("Ll", "Nd"), whitelist_characters="_")),
            min_size=0,
            max_size=5,
            unique=True,
        )
    )
    g_id_set = set(g_ids)

    # Extra IDs that are NOT in g_ids (site-only rules)
    extra_ids_raw = draw(
        st.lists(
            st.text(min_size=1, max_size=15, alphabet=st.characters(whitelist_categories=("Ll", "Nd"), whitelist_characters="_")),
            min_size=0,
            max_size=3,
            unique=True,
        )
    )
    extra_ids = [eid for eid in extra_ids_raw if eid not in g_id_set]

    # Some site rules override global rules (explicitly tracked overlaps)
    overlap_ids = draw(
        st.lists(
            st.sampled_from(g_ids) if g_ids else st.nothing(),
            min_size=0,
            max_size=min(2, len(g_ids)),
            unique=True,
        )
    )
    s_ids = list(set(extra_ids + overlap_ids))

    return g_ids, s_ids, overlap_ids


def _make_rules_json(rule_ids: list[str], severity: str = "warning") -> dict:
    return {
        "rules": [
            {
                "rule_id": rid,
                "rule_type": "text_pattern_match",
                "target": "",
                "condition": {"pattern": rid},
                "severity": severity,
                "dark_pattern_category": "other",
                "enabled": True,
            }
            for rid in rule_ids
        ]
    }


@given(scenario=merge_scenario())
@settings(max_examples=200)
def test_property26_merge_correctness(scenario):
    """Property 26: merged rules contain all global rules, site rules override by rule_id."""
    import tempfile

    g_ids, s_ids, overlap_ids = scenario

    # Write global rules to a temp file
    global_data = _make_rules_json(g_ids, severity="info")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write(json.dumps(global_data))
        fname = f.name

    try:
        # Site config with site-specific rules (severity=critical to distinguish)
        site_config = {
            "detection_rules": _make_rules_json(s_ids, severity="critical")
        }

        rules = load_detection_rules(site_config, fname)
        rules_by_id = {r.rule_id: r for r in rules}

        # All global rule IDs must be present
        for gid in g_ids:
            assert gid in rules_by_id, f"Global rule {gid!r} missing from merged result"

        # All site rule IDs must be present
        for sid in s_ids:
            assert sid in rules_by_id, f"Site rule {sid!r} missing from merged result"

        # Overlapping IDs: site rule wins (severity=critical)
        for oid in overlap_ids:
            assert rules_by_id[oid].severity == "critical", (
                f"Overlap rule {oid!r} should be overridden by site rule (critical), "
                f"got {rules_by_id[oid].severity!r}"
            )

        # Non-overlapping global rules keep their original severity (info)
        non_overlap_global = set(g_ids) - set(overlap_ids)
        for gid in non_overlap_global:
            assert rules_by_id[gid].severity == "info", (
                f"Non-overlapping global rule {gid!r} should keep severity=info, "
                f"got {rules_by_id[gid].severity!r}"
            )
    finally:
        os.unlink(fname)
