"""
Auth router for login, refresh, logout, and current-user endpoints.
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user, get_redis
from src.auth.jwt import create_access_token, create_refresh_token, decode_refresh_token
from src.auth.password import hash_password, verify_password, validate_password_policy
from src.auth.rate_limit import check_login_rate_limit
from src.auth.schemas import ChangePasswordRequest, LoginRequest, MeResponse, TokenResponse
from src.auth.session import (
    revoke_all_user_tokens,
    revoke_refresh_token,
    store_refresh_token,
    validate_refresh_token,
)
from src.database import get_async_db
from src.models import AuditLog, User

router = APIRouter()

# Cookie settings
_SECURE_COOKIE = bool(os.getenv("PRODUCTION", ""))
_REFRESH_TTL = 7 * 24 * 3600  # 7 days in seconds

# Dummy hash used for timing-attack mitigation when user is not found
_DUMMY_HASH = "$2b$12$LJ3m4ys3Lg2HEOiRiCa05OB/hFNJmBGnmcOaIGkCmSbof8FP1dDu"


def _set_refresh_cookie(response: Response, token: str) -> None:
    """Set the refresh_token HttpOnly cookie on *response*."""
    response.set_cookie(
        key="refresh_token",
        value=token,
        httponly=True,
        samesite="strict",
        secure=_SECURE_COOKIE,
        max_age=_REFRESH_TTL,
        path="/",
    )


def _clear_refresh_cookie(response: Response) -> None:
    """Clear the refresh_token cookie."""
    response.set_cookie(
        key="refresh_token",
        value="",
        httponly=True,
        samesite="strict",
        secure=_SECURE_COOKIE,
        max_age=0,
        path="/",
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_async_db),
    redis: Redis = Depends(get_redis),
):
    """Authenticate user and issue tokens."""
    # Rate-limit check
    allowed, retry_after = await check_login_rate_limit(body.username, redis)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="ログイン試行回数の上限に達しました",
            headers={"Retry-After": str(retry_after)},
        )

    result = await db.execute(select(User).where(User.username == body.username))
    user: Optional[User] = result.scalar_one_or_none()

    if user is None:
        # Timing-attack mitigation: run a dummy verify so the response
        # time is indistinguishable from a real password check.
        verify_password(body.password, _DUMMY_HASH)
        await _record_auth_event(db, body.username, "login_failure", request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="認証情報が無効です",
        )

    if not verify_password(body.password, user.hashed_password):
        await _record_auth_event(db, body.username, "login_failure", request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="認証情報が無効です",
        )

    if not user.is_active:
        await _record_auth_event(db, body.username, "login_failure", request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="認証情報が無効です",
        )

    # Issue tokens
    access_token = create_access_token(user.id, user.username, user.role)
    refresh_token = create_refresh_token(user.id)

    # Decode to get jti for Redis storage
    refresh_payload = decode_refresh_token(refresh_token)
    jti = refresh_payload["jti"]
    await store_refresh_token(user.id, jti, _REFRESH_TTL, redis)

    # Set HttpOnly cookie
    _set_refresh_cookie(response, refresh_token)

    # Audit log
    await _record_auth_event(db, body.username, "login_success", request)

    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    refresh_token: Optional[str] = Cookie(default=None),
    db: AsyncSession = Depends(get_async_db),
    redis: Redis = Depends(get_redis),
):
    """Rotate tokens using the refresh_token cookie."""
    if refresh_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="認証情報が無効です",
        )

    try:
        payload = decode_refresh_token(refresh_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="認証情報が無効です",
        )

    user_id: int = payload["sub"]
    jti: str = payload["jti"]

    # Validate token exists in Redis whitelist
    valid = await validate_refresh_token(user_id, jti, redis)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="認証情報が無効です",
        )

    # Revoke old token
    await revoke_refresh_token(user_id, jti, redis)

    # Look up user for new access token claims
    result = await db.execute(select(User).where(User.id == user_id))
    user: Optional[User] = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="認証情報が無効です",
        )

    # Issue new pair
    new_access = create_access_token(user.id, user.username, user.role)
    new_refresh = create_refresh_token(user.id)
    new_payload = decode_refresh_token(new_refresh)
    await store_refresh_token(user.id, new_payload["jti"], _REFRESH_TTL, redis)

    _set_refresh_cookie(response, new_refresh)
    return TokenResponse(access_token=new_access)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    refresh_token: Optional[str] = Cookie(default=None),
    current_user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
):
    """Revoke the refresh token and clear the cookie."""
    if refresh_token:
        try:
            payload = decode_refresh_token(refresh_token)
            await revoke_refresh_token(payload["sub"], payload["jti"], redis)
        except Exception as e:
            logger.debug("Refresh token already invalid during logout: %s", e)

    _clear_refresh_cookie(response)
    return None


@router.get("/me", response_model=MeResponse)
async def me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user's info."""
    return MeResponse(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        must_change_password=current_user.must_change_password,
    )


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
):
    """Change the current user's password. Requires current password verification."""
    # Verify current password
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="現在のパスワードが正しくありません",
        )

    # Validate new password policy
    violations = validate_password_policy(body.new_password)
    if violations:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=violations,
        )

    # Update password
    current_user.hashed_password = hash_password(body.new_password)
    current_user.must_change_password = False
    await db.flush()

    # Revoke all sessions (force re-login with new password)
    await revoke_all_user_tokens(current_user.id, redis)

    # Audit log
    await _record_auth_event(db, current_user.username, "password_changed", request)

    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _record_auth_event(
    db: AsyncSession,
    username: str,
    action: str,
    request: Optional[Request] = None,
) -> None:
    """Write an authentication audit-log entry."""
    log = AuditLog(
        user="system",
        action=action,
        resource_type="auth",
        resource_id=None,
        details={"username": username},
        ip_address=request.client.host if request and request.client else None,
        user_agent=request.headers.get("user-agent") if request else None,
    )
    db.add(log)
    # Flush so the log is persisted even if the caller raises an HTTPException
    await db.flush()
