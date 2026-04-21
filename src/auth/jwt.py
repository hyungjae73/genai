"""
JWT token creation and verification for Payment Compliance Monitor.

Uses PyJWT with HS256 algorithm.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt

# Secret key from environment variable
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"

# Token lifetimes
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7


def create_access_token(user_id: int, username: str, role: str) -> str:
    """Create a JWT access token.

    Args:
        user_id: The user's database ID.
        username: The user's username.
        role: The user's role (admin/reviewer/viewer).

    Returns:
        Encoded JWT string.

    Raises:
        ValueError: If role is not one of admin/reviewer/viewer.
    """
    if role not in ("admin", "reviewer", "viewer"):
        raise ValueError(f"Invalid role: {role}")

    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    """Create a JWT refresh token with a unique JTI.

    Args:
        user_id: The user's database ID.

    Returns:
        Encoded JWT string.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT access token.

    Args:
        token: The encoded JWT string.

    Returns:
        Decoded payload dict with keys: sub, username, role, iat, exp.

    Raises:
        jwt.ExpiredSignatureError: If the token has expired.
        jwt.InvalidTokenError: If the token is invalid.
    """
    return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])


def decode_refresh_token(token: str) -> dict:
    """Decode and validate a JWT refresh token.

    Args:
        token: The encoded JWT string.

    Returns:
        Decoded payload dict with keys: sub, jti, iat, exp.

    Raises:
        jwt.ExpiredSignatureError: If the token has expired.
        jwt.InvalidTokenError: If the token is invalid.
    """
    return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
