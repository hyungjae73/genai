"""
AdaptiveEvasionEngine — Epsilon-Greedy Multi-Armed Bandit for dynamic routing.

Selects the optimal fetch strategy per site by balancing exploration
(trying different arms) and exploitation (using the best-known arm).

Requirements: 18.1, 18.2, 18.3, 18.4, 18.5, 18.6, 18.7, 18.8
"""

from __future__ import annotations

import logging
import random
from typing import Optional

import redis.asyncio as aioredis

from src.pipeline.fetcher_protocol import PageFetcher

logger = logging.getLogger(__name__)

BANDIT_KEY_PREFIX = "bandit:{site_id}"
EXPLORATION_FLAG_KEY = "bandit:{site_id}:exploring"

# Sliding Window for non-stationary environments.
# Only the latest N outcomes are considered for each arm.
SLIDING_WINDOW_SIZE = 100

# Arm IDs
ARM_PLAYWRIGHT_PROXY_A = "playwright_proxy_a"
ARM_PLAYWRIGHT_PROXY_B = "playwright_proxy_b"
ARM_SAAS_ZENROWS = "saas_zenrows"
ARM_SAAS_SCRAPERAPI = "saas_scraperapi"

ALL_ARMS = [ARM_PLAYWRIGHT_PROXY_A, ARM_PLAYWRIGHT_PROXY_B, ARM_SAAS_ZENROWS, ARM_SAAS_SCRAPERAPI]
SAAS_ARMS = {ARM_SAAS_ZENROWS, ARM_SAAS_SCRAPERAPI}
PLAYWRIGHT_ARMS = {ARM_PLAYWRIGHT_PROXY_A, ARM_PLAYWRIGHT_PROXY_B}


class AdaptiveEvasionEngine:
    """Epsilon-Greedy バンディットによる適応型フェッチ戦略選択。

    - サイト単位で Arm の成功率を Redis に追跡
    - Exploration Mode: epsilon 確率でランダム Arm を選択
    - 十分な試行後、最良 Arm を winning strategy として固定
    - Req 13 準拠: hard target で SaaS 全滅時は Playwright フォールバック禁止
    """

    def __init__(
        self,
        redis_client: aioredis.Redis,
        fetchers: dict[str, PageFetcher],
        epsilon: float = 0.2,
        min_trials: int = 20,
        success_threshold: float = 0.8,
    ) -> None:
        self._redis = redis_client
        self._fetchers = fetchers
        self._epsilon = epsilon
        self._min_trials = min_trials
        self._success_threshold = success_threshold

    async def is_exploring(self, site_id: int) -> bool:
        """サイトが Exploration Mode かどうかを確認する。"""
        key = EXPLORATION_FLAG_KEY.format(site_id=site_id)
        return await self._redis.exists(key) > 0

    async def enter_exploration(self, site_id: int) -> None:
        """Exploration Mode に入る。"""
        key = EXPLORATION_FLAG_KEY.format(site_id=site_id)
        await self._redis.set(key, "1")

    async def exit_exploration(self, site_id: int) -> None:
        """Exploration Mode を終了する。"""
        key = EXPLORATION_FLAG_KEY.format(site_id=site_id)
        await self._redis.delete(key)

    async def select_arm(self, site_id: int, is_hard_target: bool) -> str:
        """Epsilon-Greedy で Arm を選択する。

        Req 13 準拠: is_hard_target=True の場合、Playwright Arm は選択不可。
        """
        available_arms = list(ALL_ARMS)
        if is_hard_target:
            available_arms = [a for a in available_arms if a in SAAS_ARMS]

        if not available_arms:
            raise RuntimeError("No available arms for hard target (SAAS_BLOCKED)")

        # Epsilon-Greedy: explore with probability epsilon
        if random.random() < self._epsilon:
            return random.choice(available_arms)

        # Exploit: pick arm with highest success rate
        best_arm = available_arms[0]
        best_rate = -1.0
        for arm in available_arms:
            rate = await self._get_arm_success_rate(site_id, arm)
            if rate > best_rate:
                best_rate = rate
                best_arm = arm
        return best_arm

    async def record_outcome(
        self, site_id: int, arm_id: str, success: bool
    ) -> None:
        """Arm の試行結果を Sliding Window で記録する。

        Redis List で直近 N 回（SLIDING_WINDOW_SIZE）の結果のみ保持する。
        非定常環境（ボット対策の変更）に対応するため、古いデータは自動的に捨てる。
        """
        prefix = BANDIT_KEY_PREFIX.format(site_id=site_id)
        results_key = f"{prefix}:arm:{arm_id}:results"
        # Push 1 (success) or 0 (failure) to the left of the list
        await self._redis.lpush(results_key, "1" if success else "0")
        # Trim to keep only the latest SLIDING_WINDOW_SIZE entries
        await self._redis.ltrim(results_key, 0, SLIDING_WINDOW_SIZE - 1)

    async def check_convergence(self, site_id: int, is_hard_target: bool) -> Optional[str]:
        """十分な試行が蓄積されたら winning strategy を返す。"""
        available_arms = list(ALL_ARMS)
        if is_hard_target:
            available_arms = [a for a in available_arms if a in SAAS_ARMS]

        for arm in available_arms:
            trials = await self._get_arm_trials(site_id, arm)
            if trials < self._min_trials:
                return None  # Not enough data yet

        # All arms have enough trials — pick the best
        best_arm = None
        best_rate = -1.0
        for arm in available_arms:
            rate = await self._get_arm_success_rate(site_id, arm)
            if rate > best_rate:
                best_rate = rate
                best_arm = arm
        return best_arm

    async def _get_arm_success_rate(self, site_id: int, arm_id: str) -> float:
        """Sliding Window 内の成功率を計算する。"""
        prefix = BANDIT_KEY_PREFIX.format(site_id=site_id)
        results_key = f"{prefix}:arm:{arm_id}:results"
        results = await self._redis.lrange(results_key, 0, SLIDING_WINDOW_SIZE - 1)
        if not results:
            return 0.0
        successes = sum(1 for r in results if r == b"1" or r == "1")
        return successes / len(results)

    async def _get_arm_trials(self, site_id: int, arm_id: str) -> int:
        """Sliding Window 内の試行回数を返す。"""
        prefix = BANDIT_KEY_PREFIX.format(site_id=site_id)
        results_key = f"{prefix}:arm:{arm_id}:results"
        return await self._redis.llen(results_key)
