"""
Property-based tests for JWT token creation and validation.

Feature: user-auth-rbac
"""

from datetime import timedelta

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from src.auth.jwt import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
)


# ---------------------------------------------------------------------------
# Property 5: トークン有効期限の設定
# Feature: user-auth-rbac, Property 5: トークン有効期限の設定
# **Validates: Requirements 2.5, 2.6**
# ---------------------------------------------------------------------------

class TestTokenExpiry:
    """Property 5: access token exp = iat + 30min, refresh token exp = iat + 7days."""

    @given(
        user_id=st.integers(min_value=1, max_value=10_000_000),
        username=st.text(min_size=3, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N"))),
        role=st.sampled_from(["admin", "reviewer", "viewer"]),
    )
    @settings(max_examples=100)
    def test_access_token_expiry(self, user_id: int, username: str, role: str):
        """Access token exp equals iat + 30 minutes."""
        token = create_access_token(user_id, username, role)
        payload = decode_access_token(token)

        iat = payload["iat"]
        exp = payload["exp"]
        expected_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES).total_seconds()

        assert abs((exp - iat) - expected_delta) <= 2  # ±2 seconds tolerance

    @given(
        user_id=st.integers(min_value=1, max_value=10_000_000),
    )
    @settings(max_examples=100)
    def test_refresh_token_expiry(self, user_id: int):
        """Refresh token exp equals iat + 7 days."""
        token = create_refresh_token(user_id)
        payload = decode_refresh_token(token)

        iat = payload["iat"]
        exp = payload["exp"]
        expected_delta = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS).total_seconds()

        assert abs((exp - iat) - expected_delta) <= 2  # ±2 seconds tolerance


# ---------------------------------------------------------------------------
# Property 2: ロール値のバリデーション
# Feature: user-auth-rbac, Property 2: ロール値のバリデーション
# **Validates: Requirements 1.4**
# ---------------------------------------------------------------------------

class TestRoleValidation:
    """Property 2: only 'admin'/'reviewer'/'viewer' accepted as role."""

    @given(
        role=st.sampled_from(["admin", "reviewer", "viewer"]),
    )
    @settings(max_examples=50)
    def test_valid_roles_accepted(self, role: str):
        """Valid role values are accepted without error."""
        token = create_access_token(user_id=1, username="testuser", role=role)
        payload = decode_access_token(token)
        assert payload["role"] == role

    @given(
        role=st.text(min_size=0, max_size=50),
    )
    @settings(max_examples=100)
    def test_invalid_roles_rejected(self, role: str):
        """Any string not in {admin, reviewer, viewer} raises ValueError."""
        assume(role not in ("admin", "reviewer", "viewer"))
        with pytest.raises(ValueError, match="Invalid role"):
            create_access_token(user_id=1, username="testuser", role=role)
