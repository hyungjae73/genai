"""
Session management using Redis for refresh token storage.

Provides whitelist-based refresh token management with TTL.
"""

from redis.asyncio import Redis


REFRESH_TOKEN_PREFIX = "refresh_token"


def _key(user_id: int, jti: str) -> str:
    """Build the Redis key for a refresh token."""
    return f"{REFRESH_TOKEN_PREFIX}:{user_id}:{jti}"


def _pattern(user_id: int) -> str:
    """Build the Redis SCAN pattern for all tokens of a user."""
    return f"{REFRESH_TOKEN_PREFIX}:{user_id}:*"


async def store_refresh_token(
    user_id: int, jti: str, ttl_seconds: int, redis: Redis
) -> None:
    """Store a refresh token in Redis with a TTL.

    Args:
        user_id: The user's database ID.
        jti: The unique token identifier (JWT ID).
        ttl_seconds: Time-to-live in seconds (should match token expiry).
        redis: An async Redis connection.
    """
    await redis.setex(_key(user_id, jti), ttl_seconds, "1")


async def validate_refresh_token(
    user_id: int, jti: str, redis: Redis
) -> bool:
    """Check whether a refresh token exists in Redis.

    Args:
        user_id: The user's database ID.
        jti: The unique token identifier.
        redis: An async Redis connection.

    Returns:
        True if the token is present (valid), False otherwise.
    """
    result = await redis.get(_key(user_id, jti))
    return result is not None


async def revoke_refresh_token(
    user_id: int, jti: str, redis: Redis
) -> None:
    """Remove a single refresh token from Redis.

    Args:
        user_id: The user's database ID.
        jti: The unique token identifier.
        redis: An async Redis connection.
    """
    await redis.delete(_key(user_id, jti))


async def revoke_all_user_tokens(user_id: int, redis: Redis) -> None:
    """Remove all refresh tokens for a user from Redis using SCAN + DELETE.

    Args:
        user_id: The user's database ID.
        redis: An async Redis connection.
    """
    pattern = _pattern(user_id)
    cursor = 0
    while True:
        cursor, keys = await redis.scan(cursor=cursor, match=pattern, count=100)
        if keys:
            await redis.delete(*keys)
        if cursor == 0:
            break
