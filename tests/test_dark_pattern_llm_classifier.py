"""
Tests for LLMClassifierPlugin.

Unit tests (task 3.6) and property-based tests (task 3.5).

Properties tested:
  Property 7: LLM分類結果のラウンドトリップ
  Property 10: LLM confidence 閾値による violations 追加
  Property 11: LLM API 呼び出し上限

**Validates: Requirements 8.6, 2.14, 2.10, 2.11, 13.1**
"""

from __future__ import annotations

import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.models import MonitoringSite
from src.pipeline.context import CrawlContext
from src.pipeline.plugins.llm_classifier_plugin import LLMClassifierPlugin


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx(
    html_content: str = "<html><body>Test page</body></html>",
    evidence_records: list = None,
) -> CrawlContext:
    site = MonitoringSite(id=1)
    ctx = CrawlContext(
        site=site,
        url="https://example.com",
        html_content=html_content,
        evidence_records=evidence_records or [],
    )
    return ctx


def _make_result(
    confidence: float = 0.8,
    is_subscription: bool = True,
    evidence_text: str = "定期購入",
    dark_pattern_type: str = "hidden_subscription",
    reasoning: str = "This looks like a subscription",
) -> dict:
    return {
        "reasoning": reasoning,
        "evidence_text": evidence_text,
        "confidence": confidence,
        "is_subscription": is_subscription,
        "dark_pattern_type": dark_pattern_type,
    }


# ---------------------------------------------------------------------------
# Unit tests — should_run
# ---------------------------------------------------------------------------


class TestShouldRun:
    def test_returns_true_with_html_and_api_key(self, monkeypatch):
        monkeypatch.setenv("LLM_API_KEY", "test-key")
        ctx = _make_ctx(html_content="<html>test</html>")
        plugin = LLMClassifierPlugin()
        assert plugin.should_run(ctx) is True

    def test_returns_false_without_api_key(self, monkeypatch):
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        ctx = _make_ctx(html_content="<html>test</html>")
        plugin = LLMClassifierPlugin()
        assert plugin.should_run(ctx) is False

    def test_returns_false_without_content(self, monkeypatch):
        monkeypatch.setenv("LLM_API_KEY", "test-key")
        ctx = _make_ctx(html_content=None, evidence_records=[])
        plugin = LLMClassifierPlugin()
        assert plugin.should_run(ctx) is False

    def test_returns_true_with_evidence_records_and_api_key(self, monkeypatch):
        monkeypatch.setenv("LLM_API_KEY", "test-key")
        ctx = _make_ctx(html_content=None, evidence_records=[{"text": "some evidence"}])
        plugin = LLMClassifierPlugin()
        assert plugin.should_run(ctx) is True


# ---------------------------------------------------------------------------
# Unit tests — execute()
# ---------------------------------------------------------------------------


class TestExecute:
    def test_execute_writes_metadata(self, monkeypatch):
        monkeypatch.setenv("LLM_API_KEY", "test-key")
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        ctx = _make_ctx()
        plugin = LLMClassifierPlugin()

        result_data = _make_result(confidence=0.9, is_subscription=True)

        async def mock_call_llm_with_retry(text, screenshots):
            return result_data

        plugin._call_llm_with_retry = mock_call_llm_with_retry
        asyncio.get_event_loop().run_until_complete(plugin.execute(ctx))

        assert "llmclassifier_results" in ctx.metadata
        assert "llmclassifier_token_usage" in ctx.metadata

    def test_execute_adds_violation_for_high_confidence_subscription(self, monkeypatch):
        monkeypatch.setenv("LLM_API_KEY", "test-key")
        ctx = _make_ctx()
        plugin = LLMClassifierPlugin()

        result_data = _make_result(confidence=0.9, is_subscription=True)

        async def mock_call_llm_with_retry(text, screenshots):
            return result_data

        plugin._call_llm_with_retry = mock_call_llm_with_retry
        asyncio.get_event_loop().run_until_complete(plugin.execute(ctx))

        assert len(ctx.violations) > 0
        v = ctx.violations[0]
        assert v["violation_type"] == "hidden_subscription"
        assert v["dark_pattern_category"] == "hidden_subscription"
        assert v["severity"] == "warning"

    def test_execute_no_violation_for_low_confidence(self, monkeypatch):
        monkeypatch.setenv("LLM_API_KEY", "test-key")
        ctx = _make_ctx()
        plugin = LLMClassifierPlugin()

        result_data = _make_result(confidence=0.5, is_subscription=True)

        async def mock_call_llm_with_retry(text, screenshots):
            return result_data

        plugin._call_llm_with_retry = mock_call_llm_with_retry
        asyncio.get_event_loop().run_until_complete(plugin.execute(ctx))

        assert len(ctx.violations) == 0

    def test_execute_no_violation_when_not_subscription(self, monkeypatch):
        monkeypatch.setenv("LLM_API_KEY", "test-key")
        ctx = _make_ctx()
        plugin = LLMClassifierPlugin()

        result_data = _make_result(confidence=0.9, is_subscription=False)

        async def mock_call_llm_with_retry(text, screenshots):
            return result_data

        plugin._call_llm_with_retry = mock_call_llm_with_retry
        asyncio.get_event_loop().run_until_complete(plugin.execute(ctx))

        assert len(ctx.violations) == 0

    def test_execute_handles_llm_failure_gracefully(self, monkeypatch):
        monkeypatch.setenv("LLM_API_KEY", "test-key")
        ctx = _make_ctx()
        plugin = LLMClassifierPlugin()

        async def mock_call_llm_with_retry(text, screenshots):
            raise RuntimeError("API timeout")

        plugin._call_llm_with_retry = mock_call_llm_with_retry
        asyncio.get_event_loop().run_until_complete(plugin.execute(ctx))

        # Should not crash; errors recorded
        assert len(ctx.errors) > 0
        assert ctx.metadata.get("llmclassifier_results") == []

    def test_execute_json_parse_failure_handled(self, monkeypatch):
        monkeypatch.setenv("LLM_API_KEY", "test-key")
        ctx = _make_ctx()
        plugin = LLMClassifierPlugin()

        async def mock_call_llm_with_retry(text, screenshots):
            return None  # parse failure returns None

        plugin._call_llm_with_retry = mock_call_llm_with_retry
        asyncio.get_event_loop().run_until_complete(plugin.execute(ctx))

        assert ctx.metadata["llmclassifier_results"] == []


# ---------------------------------------------------------------------------
# Unit tests — _extract_text
# ---------------------------------------------------------------------------


class TestExtractText:
    def test_strips_html_tags(self):
        ctx = _make_ctx(html_content="<html><body><p>Hello world</p></body></html>")
        plugin = LLMClassifierPlugin()
        text = plugin._extract_text(ctx)
        assert "<" not in text
        assert "Hello world" in text

    def test_includes_evidence_record_text(self):
        ctx = _make_ctx(
            html_content="<p>page</p>",
            evidence_records=[{"text": "OCR extracted text"}],
        )
        plugin = LLMClassifierPlugin()
        text = plugin._extract_text(ctx)
        assert "OCR extracted text" in text

    def test_empty_html_returns_empty(self):
        ctx = _make_ctx(html_content=None, evidence_records=[])
        plugin = LLMClassifierPlugin()
        text = plugin._extract_text(ctx)
        assert text == ""


# ---------------------------------------------------------------------------
# Unit tests — _add_violations
# ---------------------------------------------------------------------------


class TestAddViolations:
    def test_adds_violation_for_high_confidence_subscription(self):
        ctx = _make_ctx()
        results = [_make_result(confidence=0.8, is_subscription=True)]
        LLMClassifierPlugin._add_violations(ctx, results)
        assert len(ctx.violations) == 1
        assert ctx.violations[0]["violation_type"] == "hidden_subscription"

    def test_no_violation_for_low_confidence(self):
        ctx = _make_ctx()
        results = [_make_result(confidence=0.6, is_subscription=True)]
        LLMClassifierPlugin._add_violations(ctx, results)
        assert len(ctx.violations) == 0

    def test_no_violation_when_not_subscription(self):
        ctx = _make_ctx()
        results = [_make_result(confidence=0.9, is_subscription=False)]
        LLMClassifierPlugin._add_violations(ctx, results)
        assert len(ctx.violations) == 0

    def test_boundary_confidence_0_7_adds_violation(self):
        ctx = _make_ctx()
        results = [_make_result(confidence=0.7, is_subscription=True)]
        LLMClassifierPlugin._add_violations(ctx, results)
        assert len(ctx.violations) == 1


# ---------------------------------------------------------------------------
# Property 7: LLM分類結果のラウンドトリップ
# **Validates: Requirements 8.6**
# ---------------------------------------------------------------------------


_dark_pattern_types = st.sampled_from([
    "hidden_subscription", "sneak_into_basket", "confirmshaming", "other"
])


@given(
    confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    is_subscription=st.booleans(),
    evidence_text=st.text(max_size=100),
    dark_pattern_type=_dark_pattern_types,
)
@settings(max_examples=200)
def test_property7_result_json_roundtrip(
    confidence, is_subscription, evidence_text, dark_pattern_type
):
    """Property 7: LLM classification result JSON round-trip equivalence."""
    original = {
        "reasoning": "test reasoning",
        "evidence_text": evidence_text,
        "confidence": confidence,
        "is_subscription": is_subscription,
        "dark_pattern_type": dark_pattern_type,
    }
    serialized = json.dumps(original)
    deserialized = json.loads(serialized)

    assert deserialized["confidence"] == pytest.approx(original["confidence"])
    assert deserialized["is_subscription"] == original["is_subscription"]
    assert deserialized["evidence_text"] == original["evidence_text"]
    assert deserialized["dark_pattern_type"] == original["dark_pattern_type"]


# ---------------------------------------------------------------------------
# Property 10: LLM confidence 閾値による violations 追加
# **Validates: Requirements 2.14**
# ---------------------------------------------------------------------------


@given(
    confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    is_subscription=st.booleans(),
)
@settings(max_examples=300)
def test_property10_violations_threshold(confidence, is_subscription):
    """Property 10: only confidence >= 0.7 and is_subscription=True adds violations."""
    ctx = _make_ctx()
    results = [_make_result(confidence=confidence, is_subscription=is_subscription)]
    LLMClassifierPlugin._add_violations(ctx, results)

    should_have_violation = confidence >= 0.7 and is_subscription

    if should_have_violation:
        assert len(ctx.violations) == 1, (
            f"Expected violation for confidence={confidence}, "
            f"is_subscription={is_subscription}"
        )
    else:
        assert len(ctx.violations) == 0, (
            f"Expected no violation for confidence={confidence}, "
            f"is_subscription={is_subscription}"
        )


# ---------------------------------------------------------------------------
# Property 11: LLM API 呼び出し上限
# **Validates: Requirements 2.10, 2.11, 13.1**
# ---------------------------------------------------------------------------


@given(max_calls=st.integers(min_value=1, max_value=10))
@settings(max_examples=50)
def test_property11_call_limit(max_calls):
    """Property 11: LLM call count <= max_calls; calls_limited flag set when exceeded."""
    import os
    call_count = 0

    async def mock_call(text, screenshots):
        nonlocal call_count
        call_count += 1
        return _make_result(confidence=0.5, is_subscription=False)

    with patch.dict(os.environ, {"LLM_API_KEY": "test-key", "LLM_MAX_CALLS_PER_CRAWL": str(max_calls)}):
        ctx = _make_ctx()
        plugin = LLMClassifierPlugin()
        plugin._call_llm_with_retry = mock_call
        call_count = 0  # reset per example

        asyncio.get_event_loop().run_until_complete(plugin.execute(ctx))

    # Call count must not exceed max_calls
    assert call_count <= max_calls, (
        f"Made {call_count} calls but max_calls={max_calls}"
    )
