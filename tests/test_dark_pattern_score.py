"""
Property-based tests for DarkPatternScore computation.

**Validates: Requirements 5.2, 5.3, 5.4, 5.7**

Properties tested:
  Property 17: DarkPatternScore の Max Pooling + ペナルティ正確性
  Property 18: DarkPatternScore の範囲不変条件
  Property 19: DarkPatternScore の閾値判定
"""

import os
from unittest.mock import patch

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from src.models import MonitoringSite
from src.pipeline.context import CrawlContext
from src.pipeline.plugins.dark_pattern_utils import compute_dark_pattern_score

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PLUGIN_KEYS = ["css_visual", "llm_classifier", "journey", "ui_trap"]
_PLUGIN_CLASS_NAMES = {
    "css_visual": "CSSVisualPlugin",
    "llm_classifier": "LLMClassifierPlugin",
    "journey": "JourneyPlugin",
    "ui_trap": "UITrapPlugin",
}


def _make_ctx(
    executed: dict[str, bool],
    subscores: dict[str, float],
    penalty: float = 0.15,
) -> CrawlContext:
    """Build a minimal CrawlContext for score testing.

    Args:
        executed:  {plugin_key: True/False} — whether each plugin ran.
        subscores: {plugin_key: float} — actual scores for executed plugins.
        penalty:   Penalty baseline for unexecuted plugins.
    """
    site = MonitoringSite(id=1)
    ctx = CrawlContext(site=site, url="https://example.com")

    # Build pipeline_stages metadata
    executed_plugin_names = [
        _PLUGIN_CLASS_NAMES[k] for k, ran in executed.items() if ran
    ]
    ctx.metadata["pipeline_stages"] = {
        "data_extractor": {"executed_plugins": executed_plugin_names}
    }

    # Write actual subscores into metadata for executed plugins
    for key, ran in executed.items():
        if ran:
            score = subscores.get(key, 0.0)
            if key == "css_visual":
                ctx.metadata["cssvisual_deception_score"] = score
            elif key == "llm_classifier":
                ctx.metadata["llmclassifier_results"] = [
                    {"confidence": score, "is_subscription": True}
                ] if score > 0 else []
            elif key == "journey":
                if score > 0:
                    # Use a multi-step list where only some are violated
                    # to approximate the score
                    total_steps = 10
                    violated_steps = max(0, min(total_steps, round(score * total_steps)))
                    steps = [{"assertion_failed": True}] * violated_steps
                    steps += [{"assertion_failed": False}] * (total_steps - violated_steps)
                    ctx.metadata["journey_steps"] = steps
                else:
                    ctx.metadata["journey_steps"] = [{"assertion_failed": False}]
            elif key == "ui_trap":
                n = round(score / 0.25)
                ctx.metadata["uitrap_detections"] = [{}] * n

    return ctx


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestComputeDarkPatternScore:
    def test_all_executed_max_pooling(self, monkeypatch):
        monkeypatch.setenv("DARK_PATTERN_PENALTY_BASELINE", "0.15")
        monkeypatch.setenv("DARK_PATTERN_SCORE_THRESHOLD", "0.6")

        executed = {k: True for k in _PLUGIN_KEYS}
        subscores = {
            "css_visual": 0.3,
            "llm_classifier": 0.8,
            "journey": 0.0,
            "ui_trap": 0.25,
        }
        ctx = _make_ctx(executed, subscores)
        result = compute_dark_pattern_score(ctx)

        assert result.metadata["darkpattern_score"] == pytest.approx(0.8, abs=1e-6)

    def test_unexecuted_gets_penalty(self, monkeypatch):
        monkeypatch.setenv("DARK_PATTERN_PENALTY_BASELINE", "0.15")
        monkeypatch.setenv("DARK_PATTERN_SCORE_THRESHOLD", "0.6")

        executed = {k: False for k in _PLUGIN_KEYS}
        ctx = _make_ctx(executed, {})
        result = compute_dark_pattern_score(ctx)

        subscores = result.metadata["darkpattern_subscores"]
        for key in _PLUGIN_KEYS:
            assert subscores[key] == pytest.approx(0.15, abs=1e-9)

    def test_threshold_violation_added(self, monkeypatch):
        monkeypatch.setenv("DARK_PATTERN_PENALTY_BASELINE", "0.15")
        monkeypatch.setenv("DARK_PATTERN_SCORE_THRESHOLD", "0.6")

        executed = {"css_visual": True, "llm_classifier": False, "journey": False, "ui_trap": False}
        subscores = {"css_visual": 0.9}
        ctx = _make_ctx(executed, subscores)
        result = compute_dark_pattern_score(ctx)

        assert result.metadata["darkpattern_score"] >= 0.6
        violation_types = [v["violation_type"] for v in result.violations]
        assert "high_dark_pattern_risk" in violation_types

    def test_below_threshold_no_violation(self, monkeypatch):
        monkeypatch.setenv("DARK_PATTERN_PENALTY_BASELINE", "0.05")
        monkeypatch.setenv("DARK_PATTERN_SCORE_THRESHOLD", "0.6")

        executed = {k: True for k in _PLUGIN_KEYS}
        subscores = {k: 0.1 for k in _PLUGIN_KEYS}
        ctx = _make_ctx(executed, subscores)
        result = compute_dark_pattern_score(ctx)

        assert result.metadata["darkpattern_score"] < 0.6
        violation_types = [v["violation_type"] for v in result.violations]
        assert "high_dark_pattern_risk" not in violation_types

    def test_score_written_to_metadata(self, monkeypatch):
        monkeypatch.setenv("DARK_PATTERN_PENALTY_BASELINE", "0.15")
        monkeypatch.setenv("DARK_PATTERN_SCORE_THRESHOLD", "0.6")

        ctx = _make_ctx({k: False for k in _PLUGIN_KEYS}, {})
        result = compute_dark_pattern_score(ctx)

        assert "darkpattern_score" in result.metadata
        assert "darkpattern_subscores" in result.metadata


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_subscore_st = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)
_executed_st = st.booleans()
_penalty_st = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)
_threshold_st = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)


@st.composite
def score_scenario(draw):
    """Generate a complete scoring scenario."""
    executed = {k: draw(_executed_st) for k in _PLUGIN_KEYS}
    subscores = {k: draw(_subscore_st) for k in _PLUGIN_KEYS}
    penalty = draw(_penalty_st)
    threshold = draw(_threshold_st)
    return executed, subscores, penalty, threshold


# ---------------------------------------------------------------------------
# Property 17: DarkPatternScore の Max Pooling + ペナルティ正確性
# **Validates: Requirements 5.2, 5.3**
# ---------------------------------------------------------------------------


@given(scenario=score_scenario())
@settings(max_examples=300)
def test_property17_max_pooling_with_penalty(scenario):
    """Property 17: executed plugins use actual score; unexecuted use penalty."""
    executed, subscores, penalty, threshold = scenario
    env_overrides = {
        "DARK_PATTERN_PENALTY_BASELINE": str(penalty),
        "DARK_PATTERN_SCORE_THRESHOLD": str(threshold),
    }
    with patch.dict(os.environ, env_overrides):
        ctx = _make_ctx(executed, subscores, penalty)
        result = compute_dark_pattern_score(ctx)
    result_subscores = result.metadata["darkpattern_subscores"]

    for key in _PLUGIN_KEYS:
        if not executed[key]:
            # Unexecuted → penalty
            assert result_subscores[key] == pytest.approx(penalty, abs=1e-9), (
                f"Unexecuted plugin {key} should have penalty {penalty}, "
                f"got {result_subscores[key]}"
            )

    # Final score must be the max of all subscores
    expected_max = max(result_subscores.values())
    assert result.metadata["darkpattern_score"] == pytest.approx(
        max(0.0, min(1.0, expected_max)), abs=1e-9
    )


# ---------------------------------------------------------------------------
# Property 18: DarkPatternScore の範囲不変条件
# **Validates: Requirements 5.4**
# ---------------------------------------------------------------------------


@given(scenario=score_scenario())
@settings(max_examples=300)
def test_property18_score_in_range(scenario):
    """Property 18: final score always in [0.0, 1.0]."""
    executed, subscores, penalty, threshold = scenario
    env_overrides = {
        "DARK_PATTERN_PENALTY_BASELINE": str(penalty),
        "DARK_PATTERN_SCORE_THRESHOLD": str(threshold),
    }
    with patch.dict(os.environ, env_overrides):
        ctx = _make_ctx(executed, subscores, penalty)
        result = compute_dark_pattern_score(ctx)

    score = result.metadata["darkpattern_score"]
    assert 0.0 <= score <= 1.0, f"Score {score} out of [0, 1]"


# ---------------------------------------------------------------------------
# Property 19: DarkPatternScore の閾値判定
# **Validates: Requirements 5.7**
# ---------------------------------------------------------------------------


@given(scenario=score_scenario())
@settings(max_examples=300)
def test_property19_threshold_violation(scenario):
    """Property 19: score >= threshold ↔ high_dark_pattern_risk violation added."""
    executed, subscores, penalty, threshold = scenario
    env_overrides = {
        "DARK_PATTERN_PENALTY_BASELINE": str(penalty),
        "DARK_PATTERN_SCORE_THRESHOLD": str(threshold),
    }
    with patch.dict(os.environ, env_overrides):
        ctx = _make_ctx(executed, subscores, penalty)
        result = compute_dark_pattern_score(ctx)

    score = result.metadata["darkpattern_score"]
    has_violation = any(
        v.get("violation_type") == "high_dark_pattern_risk"
        for v in result.violations
    )

    if score >= threshold:
        assert has_violation, (
            f"score={score} >= threshold={threshold} but no high_dark_pattern_risk violation"
        )
    else:
        assert not has_violation, (
            f"score={score} < threshold={threshold} but high_dark_pattern_risk violation added"
        )
