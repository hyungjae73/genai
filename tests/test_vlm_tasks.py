"""
Tests for VLM classification Celery task.

Validates: Requirements 16.1, 16.2, 16.3, 16.4, 16.5, 16.6
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.pipeline.vlm_tasks import (
    DEFAULT_VLM_RATE_LIMIT_PER_SITE_HOUR,
    FALLBACK_LABEL,
    VALID_VLM_LABELS,
    VLM_CACHE_KEY_PREFIX,
    VLM_CACHE_TTL,
    VLM_RATE_KEY_PREFIX,
    _cache_normal_result,
    _check_rate_limit,
    _parse_vlm_response,
    classify_page_vlm,
)


# ---------------------------------------------------------------------------
# _parse_vlm_response
# ---------------------------------------------------------------------------


class TestParseVLMResponse:
    def test_valid_labels_map_correctly(self):
        for label in VALID_VLM_LABELS:
            assert _parse_vlm_response(label) == label

    def test_strips_whitespace(self):
        assert _parse_vlm_response("  NORMAL  ") == "NORMAL"
        assert _parse_vlm_response("\nCAPTCHA_CHALLENGE\n") == "CAPTCHA_CHALLENGE"

    def test_case_insensitive(self):
        assert _parse_vlm_response("normal") == "NORMAL"
        assert _parse_vlm_response("access_denied") == "ACCESS_DENIED"

    def test_unknown_response_falls_back(self):
        assert _parse_vlm_response("something_else") == FALLBACK_LABEL
        assert _parse_vlm_response("") == FALLBACK_LABEL
        assert _parse_vlm_response("maybe a captcha?") == FALLBACK_LABEL

    def test_all_four_labels_recognized(self):
        assert _parse_vlm_response("CAPTCHA_CHALLENGE") == "CAPTCHA_CHALLENGE"
        assert _parse_vlm_response("ACCESS_DENIED") == "ACCESS_DENIED"
        assert _parse_vlm_response("CONTENT_CHANGED") == "CONTENT_CHANGED"
        assert _parse_vlm_response("NORMAL") == "NORMAL"


# ---------------------------------------------------------------------------
# _check_rate_limit
# ---------------------------------------------------------------------------


class TestCheckRateLimit:
    def test_allows_calls_under_limit(self):
        r = MagicMock()
        r.incr.return_value = 1
        assert _check_rate_limit(r, site_id=1, rate_limit=5) is True
        r.expire.assert_called_once()

    def test_allows_calls_at_limit(self):
        r = MagicMock()
        r.incr.return_value = 5
        assert _check_rate_limit(r, site_id=1, rate_limit=5) is True

    def test_blocks_calls_over_limit(self):
        r = MagicMock()
        r.incr.return_value = 6
        assert _check_rate_limit(r, site_id=1, rate_limit=5) is False

    def test_sets_expire_on_first_call(self):
        r = MagicMock()
        r.incr.return_value = 1
        _check_rate_limit(r, site_id=42, rate_limit=5)
        r.expire.assert_called_once_with(f"{VLM_RATE_KEY_PREFIX}42", 3600)

    def test_does_not_set_expire_on_subsequent_calls(self):
        r = MagicMock()
        r.incr.return_value = 3
        _check_rate_limit(r, site_id=42, rate_limit=5)
        r.expire.assert_not_called()

    def test_uses_correct_key_format(self):
        r = MagicMock()
        r.incr.return_value = 1
        _check_rate_limit(r, site_id=99, rate_limit=5)
        r.incr.assert_called_once_with(f"{VLM_RATE_KEY_PREFIX}99")


# ---------------------------------------------------------------------------
# _cache_normal_result
# ---------------------------------------------------------------------------


class TestCacheNormalResult:
    def test_caches_with_correct_key_and_ttl(self):
        r = MagicMock()
        _cache_normal_result(r, "abc123def456")
        r.setex.assert_called_once_with(
            f"{VLM_CACHE_KEY_PREFIX}abc123def456",
            VLM_CACHE_TTL,
            "NORMAL",
        )


# ---------------------------------------------------------------------------
# classify_page_vlm (Celery task)
# ---------------------------------------------------------------------------


class TestClassifyPageVLM:
    @patch("src.pipeline.vlm_tasks._get_redis_client")
    @patch("src.pipeline.vlm_tasks._call_vlm_api")
    def test_successful_classification(self, mock_vlm_api, mock_redis):
        """VLM returns a valid label → result contains that label."""
        mock_vlm_api.return_value = "CAPTCHA_CHALLENGE"
        r = MagicMock()
        r.incr.return_value = 1
        mock_redis.return_value = r

        result = classify_page_vlm(
            site_id=1,
            screenshot_path="/tmp/shot.png",
            dom_hash="abcd1234",
            vlm_provider="gemini",
            vlm_api_key="test-key",
        )

        assert result["label"] == "CAPTCHA_CHALLENGE"
        assert result["site_id"] == 1
        assert result["dom_hash"] == "abcd1234"
        assert result["rate_limited"] is False

    @patch("src.pipeline.vlm_tasks._get_redis_client")
    @patch("src.pipeline.vlm_tasks._call_vlm_api")
    def test_normal_result_is_cached(self, mock_vlm_api, mock_redis):
        """NORMAL classification → cached in Redis."""
        mock_vlm_api.return_value = "NORMAL"
        r = MagicMock()
        r.incr.return_value = 1
        mock_redis.return_value = r

        result = classify_page_vlm(
            site_id=1,
            screenshot_path="/tmp/shot.png",
            dom_hash="hash123",
            vlm_provider="gemini",
            vlm_api_key="test-key",
        )

        assert result["label"] == "NORMAL"
        assert result["cached"] is True
        r.setex.assert_called_once_with(
            f"{VLM_CACHE_KEY_PREFIX}hash123",
            VLM_CACHE_TTL,
            "NORMAL",
        )

    @patch("src.pipeline.vlm_tasks._get_redis_client")
    @patch("src.pipeline.vlm_tasks._call_vlm_api")
    def test_non_normal_result_not_cached(self, mock_vlm_api, mock_redis):
        """Non-NORMAL classification → NOT cached."""
        mock_vlm_api.return_value = "ACCESS_DENIED"
        r = MagicMock()
        r.incr.return_value = 1
        mock_redis.return_value = r

        result = classify_page_vlm(
            site_id=1,
            screenshot_path="/tmp/shot.png",
            dom_hash="hash123",
            vlm_provider="gemini",
            vlm_api_key="test-key",
        )

        assert result["label"] == "ACCESS_DENIED"
        assert result["cached"] is False
        r.setex.assert_not_called()

    @patch("src.pipeline.vlm_tasks._get_redis_client")
    def test_rate_limited_returns_unknown_block(self, mock_redis):
        """Rate limit exceeded → UNKNOWN_BLOCK, no VLM call."""
        r = MagicMock()
        r.incr.return_value = 6  # Over default limit of 5
        mock_redis.return_value = r

        result = classify_page_vlm(
            site_id=1,
            screenshot_path="/tmp/shot.png",
            dom_hash="hash123",
            vlm_rate_limit=5,
        )

        assert result["label"] == FALLBACK_LABEL
        assert result["rate_limited"] is True

    @patch("src.pipeline.vlm_tasks._get_redis_client")
    @patch("src.pipeline.vlm_tasks._call_vlm_api")
    def test_vlm_api_error_falls_back(self, mock_vlm_api, mock_redis):
        """VLM API raises exception → UNKNOWN_BLOCK fallback (Req 16.5)."""
        mock_vlm_api.side_effect = RuntimeError("API timeout")
        r = MagicMock()
        r.incr.return_value = 1
        mock_redis.return_value = r

        result = classify_page_vlm(
            site_id=1,
            screenshot_path="/tmp/shot.png",
            dom_hash="hash123",
            vlm_provider="gemini",
            vlm_api_key="test-key",
        )

        assert result["label"] == FALLBACK_LABEL
        assert result["rate_limited"] is False

    @patch("src.pipeline.vlm_tasks._get_redis_client")
    @patch("src.pipeline.vlm_tasks._call_vlm_api")
    def test_unrecognized_vlm_response_falls_back(self, mock_vlm_api, mock_redis):
        """VLM returns garbage → UNKNOWN_BLOCK."""
        mock_vlm_api.return_value = "I think this is a captcha page"
        r = MagicMock()
        r.incr.return_value = 1
        mock_redis.return_value = r

        result = classify_page_vlm(
            site_id=1,
            screenshot_path="/tmp/shot.png",
            dom_hash="hash123",
            vlm_provider="gemini",
            vlm_api_key="test-key",
        )

        assert result["label"] == FALLBACK_LABEL

    @patch("src.pipeline.vlm_tasks._get_redis_client")
    @patch("src.pipeline.vlm_tasks._call_vlm_api")
    def test_all_valid_labels_accepted(self, mock_vlm_api, mock_redis):
        """All 4 valid VLM labels are accepted and returned as-is."""
        r = MagicMock()
        r.incr.return_value = 1
        mock_redis.return_value = r

        for label in ["CAPTCHA_CHALLENGE", "ACCESS_DENIED", "CONTENT_CHANGED", "NORMAL"]:
            r.reset_mock()
            r.incr.return_value = 1
            mock_vlm_api.return_value = label

            result = classify_page_vlm(
                site_id=1,
                screenshot_path="/tmp/shot.png",
                dom_hash="hash123",
                vlm_provider="gemini",
                vlm_api_key="test-key",
            )

            assert result["label"] == label


# ---------------------------------------------------------------------------
# Celery task routing
# ---------------------------------------------------------------------------


class TestCeleryTaskRouting:
    def test_task_is_registered(self):
        """classify_page_vlm should be a registered Celery task."""
        from src.celery_app import celery_app

        assert "src.pipeline.vlm_tasks.classify_page_vlm" in celery_app.tasks

    def test_task_routed_to_extract_queue(self):
        """Task should be routed to the 'extract' queue."""
        from src.celery_app import celery_app

        routes = celery_app.conf.task_routes
        assert routes["src.pipeline.vlm_tasks.classify_page_vlm"] == {"queue": "extract"}
