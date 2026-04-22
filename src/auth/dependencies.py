"""
FastAPI dependency functions for authentication and authorization.

Provides JWT-based auth, role checking, and a migration-period
dependency that accepts both JWT and X-API-Key.
"""

import logging
import os
from typing import Generator, Optional

logger = logging.getLogger(__name__)

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy.orm import Session

from src.auth.jwt import decode_access_token
from src.auth.rbac import Role
from src.database import get_db
from src.models import User

# OAuth2 scheme for extracting Bearer token from Authorization header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

# Redis URL from environment
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Legacy API key
API_KEY = os.getenv("API_KEY", "dev-api-key")


async def get_redis() -> Generator[AsyncRedis, None, None]:
    """Yield an async Redis connection."""
    redis = AsyncRedis.from_url(REDIS_URL, decode_responses=True)
    try:
        yield redis
    finally:
        await redis.aclose()


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Decode JWT and return the authenticated User.

    Raises:
        HTTPException 401: If token is missing, invalid, expired,
            or the user is inactive / not found.
    """
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="認証情報が無効です",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="認証情報が無効です",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: int = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="認証情報が無効です",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="認証情報が無効です",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_role(*roles: Role):
    """Dependency factory that checks the current user's role.

    Usage::

        @router.post("/")
        def create_item(
            current_user: User = Depends(require_role(Role.ADMIN, Role.REVIEWER)),
        ):
            ...

    Returns:
        A FastAPI dependency function.
    """
    allowed_values = [r.value for r in roles]

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_values:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="権限がありません",
            )
        return current_user

    return dependency


def get_current_user_or_api_key(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Migration-period dependency: try JWT first, fall back to X-API-Key.

    During the migration period both authentication methods are accepted.
    - If a Bearer token is present, JWT authentication is used.
    - Otherwise, the legacy X-API-Key header is checked.

    Returns:
        The authenticated User object (JWT) or None (API key — legacy).

    Raises:
        HTTPException 401: If neither authentication method succeeds.
    """
    # 1. Try JWT if a Bearer token is present
    if token:
        try:
            payload = decode_access_token(token)
            user_id = payload.get("sub")
            if user_id is not None:
                user = db.query(User).filter(User.id == user_id).first()
                if user is not None and user.is_active:
                    return user
        except Exception as e:
            logger.debug("JWT auth failed, falling through to API key: %s", e)

    # 2. Fall back to X-API-Key
    api_key = request.headers.get("X-API-Key")
    if api_key and api_key == API_KEY:
        return None  # legacy mode — no User object

    # 3. Neither method succeeded
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="認証情報が無効です",
        headers={"WWW-Authenticate": "Bearer"},
    )
