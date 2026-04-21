"""
Redis-based distributed Cookie/Session management.

Provides centralized cookie storage, distributed locking for login tasks,
and session status tracking across stateless crawl workers.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

# Redis key formats
COOKIE_KEY = "session:{site_id}:cookies"
LOGIN_LOCK_KEY = "login_lock:{site_id}"
SESSION_STATUS_KEY = "session:{site_id}:status"

DEFAULT_COOKIE_TTL = 3600  # 1 hour
LOGIN_LOCK_TTL = 120  # 2 minutes


class SessionManager:
    """Redis-based distributed Cookie/Session management.

    - Cookie CRUD with TTL via SETEX
    - Distributed lock for login mutual exclusion
    - Session expiry detection and status tracking
    """

    def __init__(
        self,
        redis_client: aioredis.Redis,
        cookie_ttl: int = DEFAULT_COOKIE_TTL,
    ) -> None:
        self._redis = redis_client
        self._cookie_ttl = cookie_ttl
        self._active_locks: dict[int, Any] = {}  # site_id -> Lock instance

    async def get_cookies(self, site_id: int) -> Optional[list[dict[str, Any]]]:
        """Fetch cookies for site_id from Redis."""
        key = COOKIE_KEY.format(site_id=site_id)
        data = await self._redis.get(key)
        if data is None:
            return None
        return json.loads(data)

    async def save_cookies(
        self, site_id: int, cookies: list[dict[str, Any]]
    ) -> None:
        """Persist cookies to Redis with TTL via SETEX."""
        key = COOKIE_KEY.format(site_id=site_id)
        await self._redis.setex(key, self._cookie_ttl, json.dumps(cookies))

    async def delete_cookies(self, site_id: int) -> None:
        """Delete cookies for site_id from Redis."""
        key = COOKIE_KEY.format(site_id=site_id)
        await self._redis.delete(key)

    def is_expired_response(self, status_code: int) -> bool:
        """Detect expired session from HTTP status code (401/403)."""
        return status_code in (401, 403)

    async def acquire_login_lock(self, site_id: int) -> bool:
        """Acquire a distributed lock for login. Returns True on success.

        Uses redis-py Lock with non-blocking acquire and token tracking.
        Lock TTL is 120s to prevent deadlock if the task crashes.
        """
        lock_key = LOGIN_LOCK_KEY.format(site_id=site_id)
        lock = self._redis.lock(lock_key, timeout=LOGIN_LOCK_TTL)
        acquired = await lock.acquire(blocking=False)
        if acquired:
            self._active_locks[site_id] = lock
        return acquired

    async def release_login_lock(self, site_id: int) -> None:
        """Release the distributed lock for site_id."""
        lock = self._active_locks.pop(site_id, None)
        if lock:
            try:
                await lock.release()
            except Exception:
                pass  # Lock already expired or not held

    async def verify_lock_held(self, site_id: int) -> bool:
        """Check if the login lock is still held before Cookie save.

        CTO Review Fix: Prevents race condition when lock TTL expires
        before the login task completes.
        """
        lock = self._active_locks.get(site_id)
        if lock is None:
            return False
        return await lock.locked()

    async def mark_login_failed(self, site_id: int) -> None:
        """Set session status to 'login_failed'."""
        key = SESSION_STATUS_KEY.format(site_id=site_id)
        await self._redis.setex(key, self._cookie_ttl, "login_failed")

    async def get_session_status(self, site_id: int) -> Optional[str]:
        """Get current session status string for site_id."""
        key = SESSION_STATUS_KEY.format(site_id=site_id)
        return await self._redis.get(key)
