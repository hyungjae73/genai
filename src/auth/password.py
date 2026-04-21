"""
Password hashing and policy validation for Payment Compliance Monitor.

Uses passlib with bcrypt for secure password hashing.
"""

import re

from passlib.context import CryptContext

# bcrypt context for password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Hash a plain-text password using bcrypt.

    Args:
        plain_password: The plain-text password to hash.

    Returns:
        The bcrypt hash string.
    """
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a bcrypt hash.

    Args:
        plain_password: The plain-text password to verify.
        hashed_password: The bcrypt hash to verify against.

    Returns:
        True if the password matches, False otherwise.
    """
    return pwd_context.verify(plain_password, hashed_password)


def validate_password_policy(password: str) -> list[str]:
    """Validate a password against the password policy.

    Policy rules:
    - Minimum 8 characters
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    - At least 1 digit

    Args:
        password: The password to validate.

    Returns:
        A list of violation messages. Empty list means the password is valid.
    """
    violations: list[str] = []

    if len(password) < 8:
        violations.append("パスワードは8文字以上である必要があります")

    if not re.search(r"[A-Z]", password):
        violations.append("パスワードには英大文字を1文字以上含める必要があります")

    if not re.search(r"[a-z]", password):
        violations.append("パスワードには英小文字を1文字以上含める必要があります")

    if not re.search(r"\d", password):
        violations.append("パスワードには数字を1文字以上含める必要があります")

    return violations
