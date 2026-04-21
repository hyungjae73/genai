"""
Authentication and authorization package for Payment Compliance Monitor.

Provides API key authentication (legacy), JWT-based authentication,
password hashing, RBAC, session management, and rate limiting.
"""

import os
from fastapi import Header, HTTPException, status

# API key loaded from environment variable; falls back to a dev default
API_KEY = os.getenv("API_KEY", "dev-api-key")


async def verify_api_key(
    x_api_key: str = Header(default=None, alias="X-API-Key"),
) -> str:
    """
    FastAPI dependency that validates the X-API-Key header.

    Returns the API key value (used as a simple user identifier)
    when valid. Raises 401 when the header is missing and 403
    when the key is invalid.
    """
    if x_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="認証が必要です。X-API-Key ヘッダーを指定してください。",
        )
    if x_api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="無効なAPIキーです。",
        )
    return x_api_key
