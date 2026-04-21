"""
Property-based tests for password hashing and policy validation.

Feature: user-auth-rbac
"""

import re
import string

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from src.auth.password import hash_password, verify_password, validate_password_policy


# ---------------------------------------------------------------------------
# Property 1: パスワードハッシュのラウンドトリップ
# Feature: user-auth-rbac, Property 1: パスワードハッシュのラウンドトリップ
# **Validates: Requirements 1.6, 1.7**
# ---------------------------------------------------------------------------

class TestPasswordHashRoundtrip:
    """Property 1: hash → verify roundtrip always True, hash ≠ plaintext."""

    # bcrypt does not allow NULL bytes, and surrogates can't be UTF-8 encoded
    _password_strategy = st.text(
        min_size=1,
        max_size=128,
        alphabet=st.characters(
            blacklist_characters="\x00",
            blacklist_categories=("Cs",),  # exclude surrogates
        ),
    )

    @given(password=_password_strategy)
    @settings(max_examples=100, deadline=None)
    def test_hash_verify_roundtrip(self, password: str):
        """Any non-empty password hashed then verified returns True."""
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    @given(password=_password_strategy)
    @settings(max_examples=100, deadline=None)
    def test_hash_differs_from_plaintext(self, password: str):
        """The hash value is never equal to the plain-text password."""
        hashed = hash_password(password)
        assert hashed != password


# ---------------------------------------------------------------------------
# Property 4: パスワードポリシーバリデーション
# Feature: user-auth-rbac, Property 4: パスワードポリシーバリデーション
# **Validates: Requirements 9.1, 9.2, 9.3**
# ---------------------------------------------------------------------------

class TestPasswordPolicyValidation:
    """Property 4: validate_password_policy correctly detects each violation type."""

    @given(password=st.text(min_size=0, max_size=256))
    @settings(max_examples=100)
    def test_length_violation_detected(self, password: str):
        """Passwords shorter than 8 chars report a length violation."""
        violations = validate_password_policy(password)
        has_length_violation = any("8文字以上" in v for v in violations)
        assert has_length_violation == (len(password) < 8)

    @given(password=st.text(min_size=0, max_size=256))
    @settings(max_examples=100)
    def test_uppercase_violation_detected(self, password: str):
        """Passwords without uppercase report an uppercase violation."""
        violations = validate_password_policy(password)
        has_upper_violation = any("英大文字" in v for v in violations)
        assert has_upper_violation == (not bool(re.search(r"[A-Z]", password)))

    @given(password=st.text(min_size=0, max_size=256))
    @settings(max_examples=100)
    def test_lowercase_violation_detected(self, password: str):
        """Passwords without lowercase report a lowercase violation."""
        violations = validate_password_policy(password)
        has_lower_violation = any("英小文字" in v for v in violations)
        assert has_lower_violation == (not bool(re.search(r"[a-z]", password)))

    @given(password=st.text(min_size=0, max_size=256))
    @settings(max_examples=100)
    def test_digit_violation_detected(self, password: str):
        """Passwords without digits report a digit violation."""
        violations = validate_password_policy(password)
        has_digit_violation = any("数字" in v for v in violations)
        assert has_digit_violation == (not bool(re.search(r"\d", password)))

    @given(
        password=st.from_regex(
            r"[A-Z][a-z][0-9][A-Za-z0-9]{5,}",
            fullmatch=True,
        )
    )
    @settings(max_examples=50)
    def test_valid_password_returns_empty(self, password: str):
        """Passwords meeting all criteria return an empty violations list."""
        violations = validate_password_policy(password)
        assert violations == []
