"""
VLM (Vision-Language Model) classification Celery task.

Asynchronously classifies unknown block pages via a VLM API
(Gemini Vision / Claude Vision) with zero-shot prompting.

Rate-limited per site_id to control costs. NORMAL results are
cached in Redis to short-circuit future VLM calls for identical
DOM structures.

Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

import redis

from src.celery_app import celery_app

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Classification labels (Req 16.3)
# ---------------------------------------------------------------------------
VALID_VLM_LABELS = frozenset({
    "CAPTCHA_CHALLENGE",
    "ACCESS_DENIED",
    "CONTENT_CHANGED",
    "NORMAL",
})

FALLBACK_LABEL = "UNKNOWN_BLOCK"

# Redis key patterns
VLM_CACHE_KEY_PREFIX = "vlm_cache:"
VLM_RATE_KEY_PREFIX = "vlm_rate:"

# TTLs
VLM_CACHE_TTL = 86400  # 24 hours
VLM_RATE_WINDOW = 3600  # 1 hour

# Default rate limit (overridden by ScrapingConfig)
DEFAULT_VLM_RATE_LIMIT_PER_SITE_HOUR = 5

# Zero-shot classification prompt (Req 16.2)
VLM_CLASSIFICATION_PROMPT = (
    "この画面は以下のいずれですか？\n"
    "(a) CAPTCHA_CHALLENGE — CAPTCHA チャレンジ\n"
    "(b) ACCESS_DENIED — アクセス拒否\n"
    "(c) CONTENT_CHANGED — コンテンツ変更\n"
    "(d) NORMAL — 正常なページ\n\n"
    "ラベル名のみを回答してください。"
)


def _get_redis_client() -> redis.Redis:
    """Get a synchronous Redis client for use inside Celery tasks."""
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    return redis.Redis.from_url(redis_url, decode_responses=True)


def _check_rate_limit(
    redis_client: redis.Redis,
    site_id: int,
    rate_limit: int = DEFAULT_VLM_RATE_LIMIT_PER_SITE_HOUR,
) -> bool:
    """Check and increment the per-site VLM rate counter.

    Uses Redis INCR + EXPIRE for a sliding window of 1 hour.

    Returns True if the call is allowed, False if rate limit exceeded.
    """
    key = f"{VLM_RATE_KEY_PREFIX}{site_id}"
    current = redis_client.incr(key)
    if current == 1:
        # First call in this window — set TTL
        redis_client.expire(key, VLM_RATE_WINDOW)
    if current > rate_limit:
        return False
    return True


def _call_vlm_api(
    screenshot_path: str,
    provider: str = "gemini",
    api_key: str = "",
) -> str:
    """Call the VLM API with a screenshot for zero-shot classification.

    This is a placeholder that returns the classification label string.
    The actual implementation depends on the VLM provider SDK.

    Args:
        screenshot_path: Path to the screenshot image file.
        provider: VLM provider name ("gemini" or "claude").
        api_key: VLM API key.

    Returns:
        Classification label string from the VLM response.

    Raises:
        Exception: On any VLM API error.
    """
    # Placeholder — real implementation would use provider SDK
    # e.g., google.generativeai for Gemini, anthropic for Claude
    if not api_key:
        raise ValueError("VLM API key is not configured")

    if provider == "gemini":
        return _call_gemini_vision(screenshot_path, api_key)
    elif provider == "claude":
        return _call_claude_vision(screenshot_path, api_key)
    else:
        raise ValueError(f"Unknown VLM provider: {provider}")


def _call_gemini_vision(screenshot_path: str, api_key: str) -> str:
    """Call Gemini Vision API. Placeholder for actual SDK integration."""
    # In production, this would use google.generativeai:
    #   model = genai.GenerativeModel("gemini-pro-vision")
    #   response = model.generate_content([prompt, image])
    #   return response.text.strip()
    raise NotImplementedError("Gemini Vision API integration pending")


def _call_claude_vision(screenshot_path: str, api_key: str) -> str:
    """Call Claude Vision API. Placeholder for actual SDK integration."""
    # In production, this would use anthropic:
    #   client = anthropic.Anthropic(api_key=api_key)
    #   response = client.messages.create(...)
    #   return response.content[0].text.strip()
    raise NotImplementedError("Claude Vision API integration pending")


def _parse_vlm_response(raw_response: str) -> str:
    """Parse VLM API response and map to a valid classification label.

    Strips whitespace and validates against the known label set.
    Falls back to UNKNOWN_BLOCK for unrecognized responses.

    Args:
        raw_response: Raw text response from the VLM API.

    Returns:
        A valid classification label.
    """
    label = raw_response.strip().upper()
    if label in VALID_VLM_LABELS:
        return label
    return FALLBACK_LABEL


def _cache_normal_result(redis_client: redis.Redis, dom_hash: str) -> None:
    """Cache a NORMAL classification result in Redis.

    Key: vlm_cache:{dom_hash} → "NORMAL" with TTL 86400s.
    """
    key = f"{VLM_CACHE_KEY_PREFIX}{dom_hash}"
    redis_client.setex(key, VLM_CACHE_TTL, "NORMAL")


@celery_app.task(
    name="src.pipeline.vlm_tasks.classify_page_vlm",
    bind=True,
    max_retries=0,
    queue="extract",
)
def classify_page_vlm(
    self,
    site_id: int,
    screenshot_path: str,
    dom_hash: str,
    vlm_provider: Optional[str] = None,
    vlm_api_key: Optional[str] = None,
    vlm_rate_limit: Optional[int] = None,
) -> dict[str, Any]:
    """Classify a page screenshot via VLM API.

    This Celery task:
    1. Checks per-site rate limit (Redis INCR on vlm_rate:{site_id})
    2. Calls the VLM API with the screenshot
    3. Maps the response to a classification label
    4. Caches NORMAL results in Redis (vlm_cache:{dom_hash})
    5. Returns the classification result

    Args:
        site_id: The site ID for rate limiting.
        screenshot_path: Path to the screenshot image.
        dom_hash: DOM structure hash for cache key.
        vlm_provider: VLM provider ("gemini" or "claude"). Defaults to config.
        vlm_api_key: VLM API key. Defaults to config.
        vlm_rate_limit: Max VLM calls per site per hour. Defaults to config.

    Returns:
        Dict with classification result:
        - label: Classification label
        - site_id: Site ID
        - dom_hash: DOM hash
        - cached: Whether the result was cached
        - rate_limited: Whether the call was rate-limited
    """
    # Load config defaults
    provider = vlm_provider or os.getenv("VLM_PROVIDER", "gemini")
    api_key = vlm_api_key or os.getenv("VLM_API_KEY", "")
    rate_limit = vlm_rate_limit or int(
        os.getenv("VLM_RATE_LIMIT_PER_SITE_HOUR", str(DEFAULT_VLM_RATE_LIMIT_PER_SITE_HOUR))
    )

    result: dict[str, Any] = {
        "label": FALLBACK_LABEL,
        "site_id": site_id,
        "dom_hash": dom_hash,
        "cached": False,
        "rate_limited": False,
    }

    try:
        r = _get_redis_client()

        # Step 1: Check rate limit (Req 16.6)
        if not _check_rate_limit(r, site_id, rate_limit):
            logger.warning(
                "VLM rate limit exceeded for site %d (%d/hour)",
                site_id,
                rate_limit,
            )
            result["rate_limited"] = True
            return result

        # Step 2: Call VLM API (Req 16.1, 16.2)
        raw_response = _call_vlm_api(screenshot_path, provider, api_key)

        # Step 3: Parse and map response to label (Req 16.3)
        label = _parse_vlm_response(raw_response)
        result["label"] = label

        # Step 4: Cache NORMAL results (Req 16.5 — pHash cache)
        if label == "NORMAL" and dom_hash:
            _cache_normal_result(r, dom_hash)
            result["cached"] = True

        logger.info(
            "VLM classification for site %d: %s (dom_hash=%s)",
            site_id,
            label,
            dom_hash,
        )

    except Exception as exc:
        # Req 16.5: Fallback to UNKNOWN_BLOCK on VLM API error
        logger.error(
            "VLM API error for site %d: %s — falling back to %s",
            site_id,
            exc,
            FALLBACK_LABEL,
        )
        result["label"] = FALLBACK_LABEL

    return result
