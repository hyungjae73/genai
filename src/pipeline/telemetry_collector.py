"""
TelemetryCollector — Redis-based fetch telemetry collection.

Stores fetch outcomes in Redis Sorted Sets (score=timestamp) for
time-series analysis of success rates per site.

Requirements: 17.1, 17.2, 17.3
"""

from __future__ import annotations

import json
import time
from typing import Any

import redis.asyncio as aioredis

TELEMETRY_KEY = "telemetry:{site_id}:results"
TELEMETRY_TTL = 86400  # 24 hours


class TelemetryCollector:
    """Redis ベースのフェッチテレメトリ収集。

    Sorted Set (score=timestamp) で時系列データを格納。
    """

    def __init__(self, redis_client: aioredis.Redis, ttl: int = TELEMETRY_TTL) -> None:
        self._redis = redis_client
        self._ttl = ttl

    async def record(self, site_id: int, entry: dict[str, Any]) -> None:
        """テレメトリエントリを記録する。"""
        key = TELEMETRY_KEY.format(site_id=site_id)
        now = time.time()
        entry["timestamp"] = now
        await self._redis.zadd(key, {json.dumps(entry): now})
        await self._redis.expire(key, self._ttl)
        # Prune entries older than TTL
        cutoff = now - self._ttl
        await self._redis.zremrangebyscore(key, "-inf", cutoff)

    async def get_success_rate(
        self, site_id: int, window_seconds: int = 3600
    ) -> dict[str, Any]:
        """直近 window_seconds の成功率を計算する。"""
        key = TELEMETRY_KEY.format(site_id=site_id)
        now = time.time()
        cutoff = now - window_seconds
        entries_raw = await self._redis.zrangebyscore(key, cutoff, "+inf")
        entries = [json.loads(e) for e in entries_raw]

        total = len(entries)
        if total == 0:
            return {"success_rate": 1.0, "total": 0, "breakdown": {}}

        successes = sum(1 for e in entries if e.get("status_code") == 200)
        breakdown: dict[str, int] = {}
        for e in entries:
            label = e.get("label", str(e.get("status_code", "unknown")))
            breakdown[label] = breakdown.get(label, 0) + 1

        return {
            "success_rate": successes / total,
            "total": total,
            "successes": successes,
            "breakdown": breakdown,
        }
