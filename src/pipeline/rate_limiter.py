"""
Domain-level rate limiter for crawl pipeline.

Uses Redis SETNX + TTL for distributed domain locks.
Falls back to in-memory dict when Redis is unavailable.

Requirements: 17.3, 17.4
"""

import asyncio
import logging
import time
from typing import Any, Optional, Protocol

logger = logging.getLogger(__name__)


class RedisClient(Protocol):
    """Protocol for Redis client dependency injection."""

    def set(self, name: str, value: Any, nx: bool = False, ex: Optional[int] = None, px: Optional[int] = None) -> Any:
        ...

    def ttl(self, name: str) -> int:
        ...

    def pttl(self, name: str) -> int:
        ...


class DomainRateLimiter:
    """
    Domain-level rate limiter using Redis SETNX + TTL.

    Controls minimum interval between requests to the same domain.
    Falls back to in-memory dict when Redis is unavailable.

    Args:
        min_interval_seconds: Minimum seconds between requests to same domain (default 2.0).
        redis_client: Optional Redis client for distributed locking.
        key_prefix: Redis key prefix for domain locks.
    """

    def __init__(
        self,
        min_interval_seconds: float = 2.0,
        redis_client: Optional[Any] = None,
        key_prefix: str = "ratelimit:domain:",
    ):
        self._min_interval = min_interval_seconds
        self._redis = redis_client
        self._key_prefix = key_prefix
        # In-memory fallback: domain -> last_request_time (monotonic)
        self._memory_locks: dict[str, float] = {}

    @property
    def min_interval_seconds(self) -> float:
        return self._min_interval

    async def acquire(self, domain: str) -> None:
        """
        Acquire permission to make a request to the given domain.

        Blocks via asyncio.sleep() until the minimum interval has elapsed
        since the last request to this domain.

        Args:
            domain: The target domain (e.g. "example.com").
        """
        if self._redis is not None:
            await self._acquire_redis(domain)
        else:
            await self._acquire_memory(domain)

    async def _acquire_redis(self, domain: str) -> None:
        """Acquire using Redis SETNX + TTL."""
        key = f"{self._key_prefix}{domain}"
        ttl_ms = int(self._min_interval * 1000)

        while True:
            try:
                # Try to set the key with NX (only if not exists) and PX (millisecond TTL)
                result = self._redis.set(key, "1", nx=True, px=ttl_ms)
                if result:
                    # Lock acquired — we can proceed
                    return

                # Key exists — another request is in-flight or recently completed.
                # Check remaining TTL and sleep for that duration.
                remaining_ms = self._redis.pttl(key)
                if remaining_ms > 0:
                    await asyncio.sleep(remaining_ms / 1000.0)
                else:
                    # Key expired or doesn't exist anymore, retry immediately
                    await asyncio.sleep(0.01)
            except Exception as e:
                # Redis unavailable — fall back to memory
                logger.warning("Redis unavailable for rate limiting, falling back to memory: %s", e)
                await self._acquire_memory(domain)
                return

    async def _acquire_memory(self, domain: str) -> None:
        """Acquire using in-memory dict fallback."""
        now = time.monotonic()
        last_request = self._memory_locks.get(domain)

        if last_request is not None:
            elapsed = now - last_request
            if elapsed < self._min_interval:
                wait_time = self._min_interval - elapsed
                await asyncio.sleep(wait_time)

        self._memory_locks[domain] = time.monotonic()
