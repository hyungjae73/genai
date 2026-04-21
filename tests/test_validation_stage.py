"""
Tests for ValidationStage CrawlPlugin.

Validates: Requirements 15.1, 15.2, 15.3, 15.4, 15.5
"""

from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.pipeline.context import CrawlContext
from src.pipeline.plugins.validation_stage import (
    DEFAULT_SIGNATURES,
    MIN_BODY_SIZE_BYTES,
    MIN_TEXT_TO_TAG_RATIO,
    PHASH_CACHE_KEY_PREFIX,
    PHASH_CACHE_TTL,
    ValidationStage,
)


def _make_ctx(
    html: str = "<html><body>Hello</body></html>",
    headers: dict | None = None,
    cookies: list | None = None,
) -> CrawlContext:
    """Helper to create a CrawlContext with minimal setup."""
    site = MagicMock()
    site.id = 1
    ctx = CrawlContext(site=site, url="https://example.com")
    ctx.html_content = html
    if headers:
        ctx.metadata["response_headers"] = headers
    if cookies:
        ctx.metadata["response_cookies"] = cookies
    return ctx


# --- should_run ---


class TestShouldRun:
    def test_returns_true_when_html_present(self):
        stage = ValidationStage()
        ctx = _make_ctx(html="<html></html>")
        assert stage.should_run(ctx) is True

    def test_returns_false_when_html_none(self):
        stage = ValidationStage()
        ctx = _make_ctx()
        ctx.html_content = None
        assert stage.should_run(ctx) is False


# --- Signature detection ---


class TestSignatureDetection:
    @pytest.mark.asyncio
    async def test_css_selector_cloudflare_challenge(self):
        # Signature check is substring match: "#challenge-running" in html
        html = '<html><body><div>#challenge-running detected</div></body></html>'
        ctx = _make_ctx(html=html)
        stage = ValidationStage()
        result = await stage.execute(ctx)
        assert result.metadata["validation_label"] == "SOFT_BLOCKED"
        assert "cloudflare_challenge" in result.metadata["validation_matched_signatures"]

    @pytest.mark.asyncio
    async def test_css_selector_captcha_generic(self):
        # Signature check is substring match: "[class*='captcha']" in html
        html = "<html><body><div [class*='captcha']>Solve</div></body></html>"
        ctx = _make_ctx(html=html)
        stage = ValidationStage()
        result = await stage.execute(ctx)
        assert result.metadata["validation_label"] == "SOFT_BLOCKED"
        assert "captcha_generic" in result.metadata["validation_matched_signatures"]

    @pytest.mark.asyncio
    async def test_css_selector_akamai(self):
        # Signature check is substring match: "#ak-challenge" in html
        html = '<html><body><div>#ak-challenge page</div></body></html>'
        ctx = _make_ctx(html=html)
        stage = ValidationStage()
        result = await stage.execute(ctx)
        assert result.metadata["validation_label"] == "SOFT_BLOCKED"
        assert "akamai_bot_manager" in result.metadata["validation_matched_signatures"]

    @pytest.mark.asyncio
    async def test_header_cf_ray(self):
        html = "<html><body>Normal page content here with enough text</body></html>"
        ctx = _make_ctx(html=html, headers={"cf-ray": "abc123"})
        stage = ValidationStage()
        result = await stage.execute(ctx)
        assert result.metadata["validation_label"] == "SOFT_BLOCKED"
        assert "cloudflare_ray" in result.metadata["validation_matched_signatures"]

    @pytest.mark.asyncio
    async def test_cookie_perimeterx(self):
        html = "<html><body>Normal page content here with enough text</body></html>"
        cookies = [{"name": "_px3", "value": "abc"}]
        ctx = _make_ctx(html=html, cookies=cookies)
        stage = ValidationStage()
        result = await stage.execute(ctx)
        assert result.metadata["validation_label"] == "SOFT_BLOCKED"
        assert "perimeterx" in result.metadata["validation_matched_signatures"]

    @pytest.mark.asyncio
    async def test_cookie_datadome(self):
        html = "<html><body>Normal page content here with enough text</body></html>"
        cookies = [{"name": "datadome", "value": "xyz"}]
        ctx = _make_ctx(html=html, cookies=cookies)
        stage = ValidationStage()
        result = await stage.execute(ctx)
        assert result.metadata["validation_label"] == "SOFT_BLOCKED"
        assert "datadome" in result.metadata["validation_matched_signatures"]

    @pytest.mark.asyncio
    async def test_multiple_signatures_matched(self):
        html = '<html><body><div>#challenge-running</div><div>[class*=\'captcha\']</div></body></html>'
        ctx = _make_ctx(html=html, headers={"cf-ray": "abc"})
        stage = ValidationStage()
        result = await stage.execute(ctx)
        assert result.metadata["validation_label"] == "SOFT_BLOCKED"
        matched = result.metadata["validation_matched_signatures"]
        assert "cloudflare_challenge" in matched
        assert "cloudflare_ray" in matched


# --- Configurable signatures ---


class TestConfigurableSignatures:
    def test_custom_signatures_via_constructor(self):
        custom = [{"name": "custom_bot", "selector": "#my-bot-check", "type": "css"}]
        stage = ValidationStage(signatures=custom)
        assert stage._signatures == custom

    def test_env_var_overrides_defaults(self, monkeypatch):
        custom = [{"name": "env_sig", "header": "x-bot", "type": "header"}]
        monkeypatch.setenv("ANTIBOT_SIGNATURES_JSON", json.dumps(custom))
        stage = ValidationStage()
        assert stage._signatures == custom

    def test_env_var_overrides_constructor(self, monkeypatch):
        env_sigs = [{"name": "env_sig", "header": "x-bot", "type": "header"}]
        ctor_sigs = [{"name": "ctor_sig", "selector": "#ctor", "type": "css"}]
        monkeypatch.setenv("ANTIBOT_SIGNATURES_JSON", json.dumps(env_sigs))
        stage = ValidationStage(signatures=ctor_sigs)
        assert stage._signatures == env_sigs

    def test_defaults_when_no_env_or_constructor(self, monkeypatch):
        monkeypatch.delenv("ANTIBOT_SIGNATURES_JSON", raising=False)
        stage = ValidationStage()
        assert stage._signatures == DEFAULT_SIGNATURES


# --- DOM anomaly detection (CTO Review Fix: AND logic) ---


class TestDOMAnomalyDetection:
    @pytest.mark.asyncio
    async def test_small_body_and_low_ratio_is_anomaly(self):
        """Body < 1KB AND text-to-tag ratio < 5.0 → SOFT_BLOCKED."""
        # Small HTML with many tags, little text
        html = "<a><b><c><d><e></e></d></c></b></a>"
        assert len(html.encode("utf-8")) < MIN_BODY_SIZE_BYTES
        ctx = _make_ctx(html=html)
        stage = ValidationStage()
        result = await stage.execute(ctx)
        assert result.metadata["validation_label"] == "SOFT_BLOCKED"
        assert "validation_anomaly" in result.metadata

    @pytest.mark.asyncio
    async def test_small_body_but_high_ratio_is_not_anomaly(self):
        """Body < 1KB but text-to-tag ratio >= 5.0 → SUCCESS (not anomaly)."""
        # Small HTML but lots of text relative to tags
        html = "<html><body>" + "A" * 200 + "</body></html>"
        assert len(html.encode("utf-8")) < MIN_BODY_SIZE_BYTES
        ctx = _make_ctx(html=html)
        stage = ValidationStage()
        result = await stage.execute(ctx)
        assert result.metadata["validation_label"] == "SUCCESS"

    @pytest.mark.asyncio
    async def test_large_body_and_low_ratio_is_not_anomaly(self):
        """Body >= 1KB but low ratio → SUCCESS (not anomaly, AND logic)."""
        # Large HTML with many tags
        html = "<div>" * 200 + "</div>" * 200
        assert len(html.encode("utf-8")) >= MIN_BODY_SIZE_BYTES
        ctx = _make_ctx(html=html)
        stage = ValidationStage()
        result = await stage.execute(ctx)
        assert result.metadata["validation_label"] == "SUCCESS"

    @pytest.mark.asyncio
    async def test_large_body_and_high_ratio_is_success(self):
        """Body >= 1KB and high ratio → SUCCESS."""
        html = "<html><body>" + "Normal product page content. " * 100 + "</body></html>"
        assert len(html.encode("utf-8")) >= MIN_BODY_SIZE_BYTES
        ctx = _make_ctx(html=html)
        stage = ValidationStage()
        result = await stage.execute(ctx)
        assert result.metadata["validation_label"] == "SUCCESS"

    @pytest.mark.asyncio
    async def test_anomaly_metadata_includes_metrics(self):
        """Anomaly metadata should include body_bytes, tag_count, text_to_tag_ratio."""
        html = "<a><b><c><d><e></e></d></c></b></a>"
        ctx = _make_ctx(html=html)
        stage = ValidationStage()
        result = await stage.execute(ctx)
        anomaly = result.metadata["validation_anomaly"]
        assert "body_bytes" in anomaly
        assert "tag_count" in anomaly
        assert "text_to_tag_ratio" in anomaly


# --- DOM hash (pHash) ---


class TestDOMHash:
    def test_compute_dom_hash_returns_16_chars(self):
        stage = ValidationStage()
        h = stage._compute_dom_hash("<html><body><div>Hello</div></body></html>")
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)

    def test_same_structure_different_text_same_hash(self):
        """Tag structure only — text content changes should not affect hash."""
        stage = ValidationStage()
        h1 = stage._compute_dom_hash("<html><body><div>Hello</div></body></html>")
        h2 = stage._compute_dom_hash("<html><body><div>World</div></body></html>")
        assert h1 == h2

    def test_different_structure_different_hash(self):
        stage = ValidationStage()
        h1 = stage._compute_dom_hash("<html><body><div></div></body></html>")
        h2 = stage._compute_dom_hash("<html><body><span></span></body></html>")
        assert h1 != h2


# --- Redis pHash cache ---


class TestPHashCache:
    @pytest.mark.asyncio
    async def test_cache_hit_returns_normal(self):
        """When Redis has NORMAL cached for dom_hash, label should be NORMAL."""
        redis_mock = AsyncMock()
        redis_mock.get = AsyncMock(return_value="NORMAL")

        html = "<a><b><c><d><e></e></d></c></b></a>"
        ctx = _make_ctx(html=html)
        stage = ValidationStage(redis_client=redis_mock)
        result = await stage.execute(ctx)
        assert result.metadata["validation_label"] == "NORMAL"
        assert result.metadata.get("validation_vlm_cache_hit") is True

    @pytest.mark.asyncio
    async def test_cache_miss_enqueues_vlm(self):
        """When Redis returns None, VLM should be enqueued."""
        redis_mock = AsyncMock()
        redis_mock.get = AsyncMock(return_value=None)

        html = "<a><b><c><d><e></e></d></c></b></a>"
        ctx = _make_ctx(html=html)
        stage = ValidationStage(redis_client=redis_mock)
        result = await stage.execute(ctx)
        assert result.metadata["validation_label"] == "SOFT_BLOCKED"
        assert result.metadata.get("validation_vlm_requested") is True
        assert "validation_dom_hash" in result.metadata

    @pytest.mark.asyncio
    async def test_no_redis_client_enqueues_vlm(self):
        """When no Redis client is injected, VLM should be enqueued."""
        html = "<a><b><c><d><e></e></d></c></b></a>"
        ctx = _make_ctx(html=html)
        stage = ValidationStage(redis_client=None)
        result = await stage.execute(ctx)
        assert result.metadata["validation_label"] == "SOFT_BLOCKED"
        assert result.metadata.get("validation_vlm_requested") is True

    @pytest.mark.asyncio
    async def test_redis_error_falls_back_to_vlm(self):
        """When Redis raises an exception, should fall back to VLM enqueue."""
        redis_mock = AsyncMock()
        redis_mock.get = AsyncMock(side_effect=ConnectionError("Redis down"))

        html = "<a><b><c><d><e></e></d></c></b></a>"
        ctx = _make_ctx(html=html)
        stage = ValidationStage(redis_client=redis_mock)
        result = await stage.execute(ctx)
        assert result.metadata["validation_label"] == "SOFT_BLOCKED"
        assert result.metadata.get("validation_vlm_requested") is True

    @pytest.mark.asyncio
    async def test_cache_hit_with_bytes_value(self):
        """Redis may return bytes b'NORMAL' instead of str."""
        redis_mock = AsyncMock()
        redis_mock.get = AsyncMock(return_value=b"NORMAL")

        html = "<a><b><c><d><e></e></d></c></b></a>"
        ctx = _make_ctx(html=html)
        stage = ValidationStage(redis_client=redis_mock)
        result = await stage.execute(ctx)
        assert result.metadata["validation_label"] == "NORMAL"


# --- VLM enqueue ---


class TestVLMEnqueue:
    @pytest.mark.asyncio
    async def test_enqueue_sets_metadata_flags(self):
        html = "<a><b><c><d><e></e></d></c></b></a>"
        ctx = _make_ctx(html=html)
        stage = ValidationStage()
        result = await stage.execute(ctx)
        assert result.metadata.get("validation_vlm_requested") is True
        assert isinstance(result.metadata.get("validation_dom_hash"), str)
        assert len(result.metadata["validation_dom_hash"]) == 16


# --- Telemetry ---


class TestTelemetry:
    @pytest.mark.asyncio
    async def test_telemetry_on_success(self):
        html = "<html><body>" + "Normal content. " * 100 + "</body></html>"
        ctx = _make_ctx(html=html)
        stage = ValidationStage()
        result = await stage.execute(ctx)
        telemetry = result.metadata["validation_telemetry"]
        assert telemetry["label"] == "SUCCESS"
        assert telemetry["site_id"] == 1
        assert telemetry["url"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_telemetry_on_soft_blocked(self):
        html = '<html><body><div>#challenge-running</div></body></html>'
        ctx = _make_ctx(html=html)
        stage = ValidationStage()
        result = await stage.execute(ctx)
        assert result.metadata["validation_telemetry"]["label"] == "SOFT_BLOCKED"

    @pytest.mark.asyncio
    async def test_telemetry_on_normal_cache_hit(self):
        redis_mock = AsyncMock()
        redis_mock.get = AsyncMock(return_value="NORMAL")

        html = "<a><b><c><d><e></e></d></c></b></a>"
        ctx = _make_ctx(html=html)
        stage = ValidationStage(redis_client=redis_mock)
        result = await stage.execute(ctx)
        assert result.metadata["validation_telemetry"]["label"] == "NORMAL"


# --- Name property ---


class TestNameProperty:
    def test_name_returns_class_name(self):
        stage = ValidationStage()
        assert stage.name == "ValidationStage"


# --- Empty HTML ---


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_html_content(self):
        """Empty string html_content should trigger DOM anomaly (0 bytes, 0 tags)."""
        ctx = _make_ctx(html="")
        stage = ValidationStage()
        result = await stage.execute(ctx)
        # body_bytes=0 < 1024 AND text_to_tag_ratio=0/1=0 < 5.0 → anomaly
        assert result.metadata["validation_label"] == "SOFT_BLOCKED"

    @pytest.mark.asyncio
    async def test_none_html_treated_as_empty(self):
        """When html_content is None but should_run passed, treat as empty."""
        ctx = _make_ctx(html="")
        ctx.html_content = None
        # should_run would be False, but if execute is called directly:
        stage = ValidationStage()
        # html defaults to "" inside execute
        result = await stage.execute(ctx)
        assert result.metadata["validation_label"] == "SOFT_BLOCKED"
