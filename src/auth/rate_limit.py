"""
Login rate limiting using Redis.

Limits login attempts to 10 per 5 minutes per username.
"""

from redis.asyncio import Redis

LOGIN_ATTEMPTS_PREFIX = "login_attempts"
MAX_ATTEMPTS = 10
WINDOW_SECONDS = 300  # 5 minutes


async def check_login_rate_limit(
    username: str, redis: Redis
) -> tuple[bool, int]:
    """Check whether a login attempt is allowed under the rate limit.

    Uses a simple counter with TTL in Redis. Each call increments the
    counter; if the count exceeds MAX_ATTEMPTS the request is denied.

    Args:
        username: The username being used for login.
        redis: An async Redis connection.

    Returns:
        A tuple of (allowed, retry_after_seconds).
        - allowed: True if the attempt is permitted.
        - retry_after_seconds: Seconds until the window resets (0 if allowed).
    """
    key = f"{LOGIN_ATTEMPTS_PREFIX}:{username}"

    current = await redis.get(key)
    count = int(current) if current else 0

    if count >= MAX_ATTEMPTS:
        ttl = await redis.ttl(key)
        retry_after = max(ttl, 0)
        return False, retry_after

    pipe = redis.pipeline()
    pipe.incr(key)
    # Set TTL only on the first attempt (when key doesn't exist yet)
    if count == 0:
        pipe.expire(key, WINDOW_SECONDS)
    await pipe.execute()

    return True, 0
