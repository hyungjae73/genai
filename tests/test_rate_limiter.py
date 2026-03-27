"""
Unit tests for DomainRateLimiter.

Tests Redis-based and in-memory fallback rate limiting.
Requirements: 17.3, 17.4
"""

import asyncio
import time
from unittest.mock import MagicMock

import pytest

from src.pipeline.rate_limiter import DomainRateLimiter


class TestDomainRateLimiterMemory:
    """Tests for in-memory fallback rate limiting."""

    @pytest.mark.asyncio
    async def test_first_request_not_delayed(self):
        """First request to a domain should not be delayed."""
        limiter = DomainRateLimiter(min_interval_seconds=2.0)
        start = time.monotonic()
        await limiter.acquire("example.com")
        elapsed = time.monotonic() - start
        assert elapsed < 0.1, "First request should not be delayed"

    @pytest.mark.asyncio
    async def test_second_request_delayed(self):
        """Second request to same domain should be delayed by min_interval."""
        interval = 0.2  # Use short interval for test speed
        limiter = DomainRateLimiter(min_interval_seconds=interval)

        await limiter.acquire("example.com")
        start = time.monotonic()
        await limiter.acquire("example.com")
        elapsed = time.monotonic() - start

        # Should have waited approximately the interval
        assert elapsed >= interval * 0.8, (
            f"Expected delay >= {interval * 0.8}s, got {elapsed}s"
        )

    @pytest.mark.asyncio
    async def test_different_domains_not_delayed(self):
        """Requests to different domains should not delay each other."""
        limiter = DomainRateLimiter(min_interval_seconds=1.0)

        await limiter.acquire("example.com")
        start = time.monotonic()
        await limiter.acquire("other.com")
        elapsed = time.monotonic() - start

        assert elapsed < 0.1, "Different domains should not delay each other"

    @pytest.mark.asyncio
    async def test_default_min_interval(self):
        """Default min_interval_seconds should be 2.0."""
        limiter = DomainRateLimiter()
        assert limiter.min_interval_seconds == 2.0

    @pytest.mark.asyncio
    async def test_custom_min_interval(self):
        """Custom min_interval_seconds should be respected."""
        limiter = DomainRateLimiter(min_interval_seconds=5.0)
        assert limiter.min_interval_seconds == 5.0


class TestDomainRateLimiterRedis:
    """Tests for Redis-based rate limiting."""

    @pytest.mark.asyncio
    async def test_redis_setnx_called(self):
        """Redis SETNX should be called with correct key and TTL."""
        mock_redis = MagicMock()
        mock_redis.set.return_value = True  # Lock acquired

        limiter = DomainRateLimiter(
            min_interval_seconds=2.0,
            redis_client=mock_redis,
        )

        await limiter.acquire("example.com")

        mock_redis.set.assert_called_once_with(
            "ratelimit:domain:example.com",
            "1",
            nx=True,
            px=2000,
        )

    @pytest.mark.asyncio
    async def test_redis_waits_when_locked(self):
        """Should wait when Redis key exists (lock held)."""
        mock_redis = MagicMock()
        # First call: lock exists; second call: lock acquired
        mock_redis.set.side_effect = [None, True]
        mock_redis.pttl.return_value = 100  # 100ms remaining

        limiter = DomainRateLimiter(
            min_interval_seconds=0.2,
            redis_client=mock_redis,
        )

        await limiter.acquire("example.com")

        assert mock_redis.set.call_count == 2
        mock_redis.pttl.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis_fallback_on_error(self):
        """Should fall back to memory when Redis raises an exception."""
        mock_redis = MagicMock()
        mock_redis.set.side_effect = ConnectionError("Redis down")

        limiter = DomainRateLimiter(
            min_interval_seconds=0.1,
            redis_client=mock_redis,
        )

        # Should not raise, falls back to memory
        await limiter.acquire("example.com")

        # Memory fallback should have recorded the domain
        assert "example.com" in limiter._memory_locks

    @pytest.mark.asyncio
    async def test_redis_custom_key_prefix(self):
        """Custom key prefix should be used in Redis keys."""
        mock_redis = MagicMock()
        mock_redis.set.return_value = True

        limiter = DomainRateLimiter(
            min_interval_seconds=1.0,
            redis_client=mock_redis,
            key_prefix="custom:",
        )

        await limiter.acquire("test.com")

        mock_redis.set.assert_called_once_with(
            "custom:test.com",
            "1",
            nx=True,
            px=1000,
        )
