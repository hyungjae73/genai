"""
Property-based tests for login rate limiting.

Feature: user-auth-rbac
"""

import asyncio

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from unittest.mock import AsyncMock, MagicMock

from src.auth.rate_limit import (
    check_login_rate_limit,
    MAX_ATTEMPTS,
    WINDOW_SECONDS,
)


# ---------------------------------------------------------------------------
# Property 18: ログインレート制限
# Feature: user-auth-rbac, Property 18: ログインレート制限
# **Validates: Requirements 9.4, 9.5**
# ---------------------------------------------------------------------------


def _make_fake_redis():
    """Create a fake Redis that tracks keys in memory for testing."""
    store: dict[str, int] = {}
    ttls: dict[str, int] = {}

    redis = AsyncMock()

    async def fake_get(key):
        val = store.get(key)
        return str(val).encode() if val is not None else None

    async def fake_ttl(key):
        return ttls.get(key, -1)

    def fake_pipeline():
        ops: list = []

        pipe = MagicMock()

        def fake_incr(key):
            ops.append(("incr", key))
            return pipe

        def fake_expire(key, seconds):
            ops.append(("expire", key, seconds))
            return pipe

        async def fake_execute():
            for op in ops:
                if op[0] == "incr":
                    key = op[1]
                    store[key] = store.get(key, 0) + 1
                elif op[0] == "expire":
                    key, seconds = op[1], op[2]
                    ttls[key] = seconds
            ops.clear()
            return []

        pipe.incr = fake_incr
        pipe.expire = fake_expire
        pipe.execute = fake_execute
        return pipe

    redis.get = fake_get
    redis.ttl = fake_ttl
    redis.pipeline = fake_pipeline

    return redis


class TestLoginRateLimit:
    """Property 18: after 10 failures in 5min, 11th returns (False, retry_after > 0)."""

    @given(
        username=st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(whitelist_categories=("L", "N")),
        ),
    )
    @settings(max_examples=30)
    def test_rate_limit_blocks_after_max_attempts(self, username: str):
        """After MAX_ATTEMPTS calls, the next call returns (False, retry_after > 0)."""

        async def _run():
            redis = _make_fake_redis()

            # Exhaust the allowed attempts
            for _ in range(MAX_ATTEMPTS):
                allowed, _ = await check_login_rate_limit(username, redis)
                assert allowed is True

            # The next attempt should be blocked
            allowed, retry_after = await check_login_rate_limit(username, redis)
            assert allowed is False
            assert retry_after > 0

        asyncio.get_event_loop().run_until_complete(_run())

    @given(
        username=st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(whitelist_categories=("L", "N")),
        ),
    )
    @settings(max_examples=30)
    def test_first_attempt_always_allowed(self, username: str):
        """The very first login attempt for any username is always allowed."""

        async def _run():
            redis = _make_fake_redis()
            allowed, retry_after = await check_login_rate_limit(username, redis)
            assert allowed is True
            assert retry_after == 0

        asyncio.get_event_loop().run_until_complete(_run())
