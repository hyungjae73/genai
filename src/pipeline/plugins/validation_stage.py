"""
ValidationStage — Soft Block 検知 CrawlPlugin。

HTTP 200 の裏に隠れた CAPTCHA/アクセス拒否を DOM 分析で検知する。
未知のブロックは VLM 分類タスクをエンキューする（非同期 Celery タスク）。

🚨 CTO Review Fix: VLM 呼び出し前に pHash キャッシュをチェックし、
過去24h以内に NORMAL と判定された類似画面はショートサーキットする。

Requirements: 15.1, 15.2, 15.3, 15.4, 15.5
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from typing import Any, Optional

from src.pipeline.context import CrawlContext
from src.pipeline.plugin import CrawlPlugin

logger = logging.getLogger(__name__)

# Default anti-bot signature patterns
DEFAULT_SIGNATURES: list[dict[str, str]] = [
    {"name": "cloudflare_challenge", "selector": "#challenge-running", "type": "css"},
    {"name": "cloudflare_ray", "header": "cf-ray", "type": "header"},
    {"name": "perimeterx", "cookie_prefix": "_px", "type": "cookie"},
    {"name": "datadome", "cookie_prefix": "datadome", "type": "cookie"},
    {"name": "akamai_bot_manager", "selector": "#ak-challenge", "type": "css"},
    {"name": "captcha_generic", "selector": "[class*='captcha']", "type": "css"},
]

MIN_BODY_SIZE_BYTES = 1024  # 1KB threshold for DOM anomaly
MIN_TEXT_TO_TAG_RATIO = 5.0  # Text-to-Tag ratio threshold
PHASH_CACHE_TTL = 86400  # 24 hours
PHASH_CACHE_KEY_PREFIX = "vlm_cache:"


class ValidationStage(CrawlPlugin):
    """Soft Block 検知プラグイン。

    HTTP 200 の裏に隠れた CAPTCHA/アクセス拒否を DOM 分析で検知する。
    未知のブロックは VLM 分類タスクをエンキューする。

    🚨 CTO Review Fix: VLM 呼び出し前に pHash キャッシュをチェックし、
    過去24h以内に NORMAL と判定された類似画面はショートサーキットする。

    🚨 CTO Review Fix: DOM anomaly detection uses AND logic
    (body < 1KB AND text-to-tag ratio < 5.0) to avoid false positives on SPAs.
    """

    def __init__(
        self,
        signatures: Optional[list[dict[str, Any]]] = None,
        redis_client: Optional[Any] = None,
    ) -> None:
        """Initialize ValidationStage.

        Args:
            signatures: Custom anti-bot signature patterns. Falls back to
                        ANTIBOT_SIGNATURES_JSON env var, then DEFAULT_SIGNATURES.
            redis_client: Optional async Redis client for pHash cache (DI).
        """
        env_sigs = os.getenv("ANTIBOT_SIGNATURES_JSON")
        if env_sigs:
            self._signatures: list[dict[str, Any]] = json.loads(env_sigs)
        elif signatures:
            self._signatures = signatures
        else:
            self._signatures = list(DEFAULT_SIGNATURES)

        self._redis = redis_client

    def should_run(self, ctx: CrawlContext) -> bool:
        """HTML コンテンツが存在する場合に実行する。"""
        return ctx.html_content is not None

    async def execute(self, ctx: CrawlContext) -> CrawlContext:
        """DOM 分析で Soft Block を検知し、ラベルを付与する。

        Flow:
        1. Check known anti-bot signatures → SOFT_BLOCKED
        2. Check DOM anomaly (body < 1KB AND text-to-tag ratio < 5.0) →
           pHash cache check → NORMAL (cache hit) or enqueue VLM → SOFT_BLOCKED
        3. No anomaly → SUCCESS

        Args:
            ctx: パイプライン共有コンテキスト

        Returns:
            validation_label を metadata に追記した CrawlContext
        """
        html = ctx.html_content or ""
        headers = ctx.metadata.get("response_headers", {})

        # Step 1: Check known anti-bot signatures
        matched = self._check_signatures(html, headers, ctx)
        if matched:
            ctx.metadata["validation_label"] = "SOFT_BLOCKED"
            ctx.metadata["validation_matched_signatures"] = matched
            self._log_telemetry(ctx, "SOFT_BLOCKED")
            return ctx

        # Step 2: Check DOM anomaly
        # 🚨 CTO Review Fix: BOTH conditions must be true (AND logic)
        body_bytes = len(html.encode("utf-8"))
        tag_count = html.count("<")
        text_length = len(html.replace("<", "").replace(">", "").strip())
        text_to_tag_ratio = text_length / max(tag_count, 1)

        is_dom_anomaly = (
            body_bytes < MIN_BODY_SIZE_BYTES
            and text_to_tag_ratio < MIN_TEXT_TO_TAG_RATIO
        )

        if is_dom_anomaly:
            ctx.metadata["validation_label"] = "SOFT_BLOCKED"
            ctx.metadata["validation_anomaly"] = {
                "body_bytes": body_bytes,
                "tag_count": tag_count,
                "text_to_tag_ratio": round(text_to_tag_ratio, 2),
            }

            # pHash cache check before VLM call
            dom_hash = self._compute_dom_hash(html)
            if await self._is_cached_normal(dom_hash):
                ctx.metadata["validation_label"] = "NORMAL"
                ctx.metadata["validation_vlm_cache_hit"] = True
            else:
                self._enqueue_vlm_classification(ctx, dom_hash)

            self._log_telemetry(ctx, ctx.metadata["validation_label"])
            return ctx

        # Step 3: No anomaly detected
        ctx.metadata["validation_label"] = "SUCCESS"
        self._log_telemetry(ctx, "SUCCESS")
        return ctx

    def _check_signatures(
        self, html: str, headers: dict[str, Any], ctx: CrawlContext
    ) -> list[str]:
        """既知の anti-bot シグネチャをチェックする。

        Args:
            html: ページの HTML コンテンツ
            headers: レスポンスヘッダー
            ctx: CrawlContext (cookie チェック用)

        Returns:
            マッチしたシグネチャ名のリスト
        """
        matched: list[str] = []
        for sig in self._signatures:
            sig_type = sig.get("type", "")
            if sig_type == "css" and sig.get("selector", "") in html:
                matched.append(sig["name"])
            elif sig_type == "header" and sig.get("header", "") in headers:
                matched.append(sig["name"])
            elif sig_type == "cookie":
                cookies = ctx.metadata.get("response_cookies", [])
                prefix = sig.get("cookie_prefix", "")
                if any(
                    c.get("name", "").startswith(prefix) for c in cookies
                ):
                    matched.append(sig["name"])
        return matched

    def _compute_dom_hash(self, html: str) -> str:
        """DOM 構造のハッシュを計算する（pHash の簡易版）。

        タグ構造のみをハッシュ化し、テキスト内容の変化（A/Bテスト等）を無視する。
        SHA-256 を 16 文字に切り詰める。

        Args:
            html: ページの HTML コンテンツ

        Returns:
            16 文字の hex ハッシュ文字列
        """
        # Extract tag structure only (strip text content between tags)
        tags_only = re.sub(r">[^<]+<", "><", html)
        tags_only = re.sub(r"\s+", " ", tags_only).strip()
        return hashlib.sha256(tags_only.encode("utf-8")).hexdigest()[:16]

    async def _is_cached_normal(self, dom_hash: str) -> bool:
        """Redis キャッシュで過去24h以内に NORMAL と判定された類似画面かチェック。

        Redis key: vlm_cache:{dom_hash} → "NORMAL" (TTL: 86400s)

        Args:
            dom_hash: _compute_dom_hash で計算した DOM ハッシュ

        Returns:
            True if cached as NORMAL, False otherwise (cache miss or no Redis)
        """
        if self._redis is None:
            return False

        try:
            key = f"{PHASH_CACHE_KEY_PREFIX}{dom_hash}"
            cached = await self._redis.get(key)
            return cached == "NORMAL" or cached == b"NORMAL"
        except Exception as e:
            logger.warning("Redis pHash cache check failed: %s", e)
            return False

    def _enqueue_vlm_classification(
        self, ctx: CrawlContext, dom_hash: str = ""
    ) -> None:
        """VLM 分類タスクをエンキューする（非同期 Celery タスク）。

        Sets metadata flags so a downstream Celery task can pick up the
        classification request asynchronously.

        Args:
            ctx: CrawlContext to annotate with VLM request flags
            dom_hash: DOM structure hash for cache key
        """
        ctx.metadata["validation_vlm_requested"] = True
        ctx.metadata["validation_dom_hash"] = dom_hash

    def _log_telemetry(self, ctx: CrawlContext, label: str) -> None:
        """テレメトリデータを ctx.metadata に記録する。

        Args:
            ctx: CrawlContext to annotate with telemetry
            label: Validation label (SOFT_BLOCKED, SUCCESS, NORMAL)
        """
        ctx.metadata["validation_telemetry"] = {
            "label": label,
            "site_id": ctx.site.id,
            "url": ctx.url,
        }
