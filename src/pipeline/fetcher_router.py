"""
FetcherRouter — target difficulty-based fetcher routing.

Routes requests to StealthPlaywrightFetcher or SaaSFetcher based on
MonitoringSite.is_hard_target flag. Implements exponential backoff with
jitter for SaaS retry, and raises SaaSBlockedError on exhaustion.

Phase 4: Integrates AdaptiveEvasionEngine for exploration mode.
When exploring, delegates arm selection to the bandit engine, records
outcomes via TelemetryCollector + AdaptiveEvasionEngine, and exits
exploration on convergence (updating MonitoringSite accordingly).

Requirements: 11.1, 11.2, 11.3, 13.1, 13.2, 13.3, 13.4, 14.1, 14.2,
              18.1, 18.5, 18.6, 18.7
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, Optional

from src.models import MonitoringSite
from src.pipeline.fetcher_protocol import FetchResult, PageFetcher

logger = logging.getLogger(__name__)

# Retry configuration for SaaS failures
# 🚨 CTO Review Fix: base_delay=30 caused 930s total wait (Worker Exhaustion).
# New: base_delay=5 + jitter → max total wait ≈ 5+10+20+40+80 = 155s + jitter.
# Celery soft_time_limit=180s ensures the task is killed before exhaustion.
SAAS_BASE_DELAY = 5  # seconds (was 30 — reduced to prevent worker exhaustion)
SAAS_MAX_RETRIES = 5
SAAS_JITTER_MAX = 3.0  # random jitter added to each delay to decorrelate retries
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
# Mathematical constraint: sum(base * 2^n for n in 0..4) + 5*jitter_max < soft_time_limit
# 155 + 15 = 170 < 180 ✓

# Crawl status constant for SaaS blocked
SAAS_BLOCKED = "SAAS_BLOCKED"

# Import types for type hints only
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.pipeline.adaptive_evasion import AdaptiveEvasionEngine
    from src.pipeline.telemetry_collector import TelemetryCollector


class SaaSBlockedError(Exception):
    """SaaS API が全リトライ失敗した場合のエラー。Playwright フォールバック禁止。"""

    def __init__(
        self, site_id: int, status_code: int, cause: Optional[Exception] = None
    ) -> None:
        self.site_id = site_id
        self.status_code = status_code
        self.cause = cause
        super().__init__(
            f"SAAS_BLOCKED: site_id={site_id}, status={status_code}, cause={cause}"
        )


class FetcherRouter:
    """ターゲット難易度ベースのフェッチャールーター。

    - is_hard_target=False → StealthPlaywrightFetcher
    - is_hard_target=True → SaaSFetcher (with retry + failsafe)
    - Exploration Mode → Epsilon-Greedy Bandit (Phase 4)
    """

    def __init__(
        self,
        playwright_fetcher: PageFetcher,
        saas_fetcher: Optional[PageFetcher] = None,
        bandit_engine: Optional[AdaptiveEvasionEngine] = None,
        telemetry_collector: Optional[TelemetryCollector] = None,
    ) -> None:
        self._playwright = playwright_fetcher
        self._saas = saas_fetcher
        self._bandit = bandit_engine
        self._telemetry = telemetry_collector

    async def fetch(self, url: str, site: MonitoringSite) -> FetchResult:
        """サイトの難易度に基づきフェッチャーを選択して実行する。

        Phase 4: Exploration Mode では bandit arm selection を使用。
        フェッチ後にテレメトリを記録し、収束時に MonitoringSite を更新する。
        """
        is_hard = getattr(site, "is_hard_target", False)

        # Phase 4: Exploration Mode — delegate to bandit arm selection
        if self._bandit and await self._bandit.is_exploring(site.id):
            return await self._fetch_with_exploration(url, site, is_hard)

        # Normal routing
        if is_hard and self._saas:
            result = await self._fetch_with_saas_retry(url, site)
        else:
            result = await self._playwright.fetch(url, site)

        # Record telemetry for non-exploration fetches
        await self._record_telemetry(site.id, result)

        return result

    async def _fetch_with_exploration(
        self, url: str, site: MonitoringSite, is_hard: bool
    ) -> FetchResult:
        """Exploration Mode: bandit arm selection → fetch → record → check convergence."""
        arm_id = await self._bandit.select_arm(site.id, is_hard)

        # Get the fetcher for the selected arm
        fetcher = self._bandit._fetchers.get(arm_id)
        if fetcher is None:
            logger.error(
                "No fetcher registered for arm %s (site %d), falling back to playwright",
                arm_id,
                site.id,
            )
            fetcher = self._playwright

        # Execute fetch with the selected arm's fetcher
        try:
            result = await fetcher.fetch(url, site)
            success = result.status_code == 200
        except Exception as e:
            logger.warning(
                "Exploration fetch failed for arm %s (site %d): %s",
                arm_id,
                site.id,
                e,
            )
            # Record failure outcome
            await self._bandit.record_outcome(site.id, arm_id, success=False)
            await self._record_telemetry(
                site.id,
                FetchResult(html="", status_code=0, headers={}),
                arm_id=arm_id,
            )
            raise

        # Record outcome in bandit engine
        await self._bandit.record_outcome(site.id, arm_id, success=success)

        # Record telemetry
        await self._record_telemetry(site.id, result, arm_id=arm_id)

        # Check convergence
        winning_arm = await self._bandit.check_convergence(site.id, is_hard)
        if winning_arm is not None:
            logger.info(
                "Bandit converged for site %d: winning arm=%s",
                site.id,
                winning_arm,
            )
            await self._bandit.exit_exploration(site.id)
            # Update MonitoringSite based on winning strategy
            await self._apply_winning_strategy(site, winning_arm)

        return result

    async def _apply_winning_strategy(
        self, site: MonitoringSite, winning_arm: str
    ) -> None:
        """Update MonitoringSite.is_hard_target and plugin_config based on winning arm.

        Req 18.5: set is_hard_target=True if winning strategy is a SaaS Arm.
        """
        from src.pipeline.adaptive_evasion import SAAS_ARMS

        is_saas_winner = winning_arm in SAAS_ARMS
        site.is_hard_target = is_saas_winner
        site.plugin_config = site.plugin_config or {}
        site.plugin_config = {
            **site.plugin_config,
            "winning_arm": winning_arm,
        }
        logger.info(
            "Updated site %d: is_hard_target=%s, winning_arm=%s",
            site.id,
            is_saas_winner,
            winning_arm,
        )

    async def _record_telemetry(
        self,
        site_id: int,
        result: FetchResult,
        arm_id: Optional[str] = None,
    ) -> None:
        """Record fetch outcome via TelemetryCollector (if provided)."""
        if self._telemetry is None:
            return
        entry: dict[str, Any] = {
            "status_code": result.status_code,
            "label": "SUCCESS" if result.status_code == 200 else str(result.status_code),
        }
        if arm_id:
            entry["arm_id"] = arm_id
        try:
            await self._telemetry.record(site_id, entry)
        except Exception as e:
            logger.warning("Failed to record telemetry for site %d: %s", site_id, e)

    async def _fetch_with_saas_retry(
        self, url: str, site: MonitoringSite
    ) -> FetchResult:
        """SaaS フェッチャーで指数バックオフ + Jitter リトライ。全滅時は SAAS_BLOCKED。

        🚨 CTO Review Fix: Jitter 付きバックオフで Worker Exhaustion を防止。
        最大待機時間: sum(5*2^n for n=0..4) + 5*3.0 = 155+15 = 170s < soft_time_limit(180s)
        """
        last_error: Optional[Exception] = None

        for attempt in range(SAAS_MAX_RETRIES):
            try:
                result = await self._saas.fetch(url, site)

                # Non-retryable client error (4xx except 429)
                if 400 <= result.status_code < 500 and result.status_code != 429:
                    logger.error(
                        "SaaS non-retryable error %d for site %d",
                        result.status_code,
                        site.id,
                    )
                    raise SaaSBlockedError(site.id, result.status_code)

                # Retryable error
                if result.status_code in RETRYABLE_STATUS_CODES:
                    delay = SAAS_BASE_DELAY * (2**attempt) + random.uniform(
                        0, SAAS_JITTER_MAX
                    )
                    logger.warning(
                        "SaaS retry %d/%d for site %d (status=%d, delay=%.1fs)",
                        attempt + 1,
                        SAAS_MAX_RETRIES,
                        site.id,
                        result.status_code,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue

                return result

            except SaaSBlockedError:
                raise
            except Exception as e:
                last_error = e
                delay = SAAS_BASE_DELAY * (2**attempt) + random.uniform(
                    0, SAAS_JITTER_MAX
                )
                logger.warning(
                    "SaaS error retry %d/%d for site %d: %s (delay=%.1fs)",
                    attempt + 1,
                    SAAS_MAX_RETRIES,
                    site.id,
                    e,
                    delay,
                )
                await asyncio.sleep(delay)

        # All retries exhausted — SAAS_BLOCKED (NO Playwright fallback)
        raise SaaSBlockedError(site.id, 0, last_error)
