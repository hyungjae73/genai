"""
Tests for authentication and authorization utilities.
"""

import pytest
from datetime import timedelta
from fastapi import HTTPException

from src.security.auth import (
    hash_password,
    verify_password,
    create_access_token,
    verify_access_token,
    register_user,
    authenticate_user,
    get_user,
    User,
    _users,
)


@pytest.fixture(autouse=True)
def clear_users():
    """Clear user store before each test."""
    _users.clear()
    yield
    _users.clear()


def test_hash_password():
    """Test password hashing."""
    password = "mypassword123"
    hashed = hash_password(password)
    
    # Hash should be different from password
    assert hashed != password
    
    # Hash should be a string
    assert isinstance(hashed, str)
    
    # Hashing same password twice should produce different hashes
    hashed2 = hash_password(password)
    assert hashed != hashed2


def test_verify_password():
    """Test password verification."""
    password = "mypassword123"
    hashed = hash_password(password)
    
    # Correct password should verify
    assert verify_password(password, hashed) is True
    
    # Wrong password should not verify
    assert verify_password("wrongpassword", hashed) is False


def test_verify_password_with_invalid_hash():
    """Test password verification with invalid hash."""
    # Should return False for invalid hash
    assert verify_password("password", "invalid-hash") is False


def test_create_access_token():
    """Test JWT token creation."""
    data = {"sub": "user@example.com", "role": "admin"}
    token = create_access_token(data)
    
    # Token should be a string
    assert isinstance(token, str)
    
    # Token should have 3 parts (header.payload.signature)
    assert len(token.split('.')) == 3


def test_verify_access_token():
    """Test JWT token verification."""
    data = {"sub": "user@example.com", "role": "admin"}
    token = create_access_token(data)
    
    # Verify token
    payload = verify_access_token(token)
    
    # Payload should contain original data
    assert payload["sub"] == "user@example.com"
    assert payload["role"] == "admin"
    
    # Payload should contain expiration
    assert "exp" in payload


def test_verify_expired_token():
    """Test verification of expired token."""
    data = {"sub": "user@example.com"}
    
    # Create token that expires immediately
    token = create_access_token(data, expires_delta=timedelta(seconds=-1))
    
    # Verification should raise HTTPException
    with pytest.raises(HTTPException) as exc_info:
        verify_access_token(token)
    
    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()


def test_verify_invalid_token():
    """Test verification of invalid token."""
    invalid_token = "invalid.token.here"
    
    # Verification should raise HTTPException
    with pytest.raises(HTTPException) as exc_info:
        verify_access_token(invalid_token)
    
    assert exc_info.value.status_code == 401


def test_register_user():
    """Test user registration."""
    user = register_user("testuser", "test@example.com", "password123")
    
    assert user.username == "testuser"
    assert user.email == "test@example.com"
    assert user.role == "user"
    
    # Password should be hashed
    assert user.hashed_password != "password123"
    
    # User should be in store
    assert get_user("testuser") == user


def test_register_user_with_role():
    """Test user registration with custom role."""
    user = register_user("admin", "admin@example.com", "password123", role="admin")
    
    assert user.role == "admin"


def test_register_duplicate_username():
    """Test that duplicate username raises error."""
    register_user("testuser", "test1@example.com", "password123")
    
    with pytest.raises(ValueError, match="already exists"):
        register_user("testuser", "test2@example.com", "password456")


def test_register_duplicate_email():
    """Test that duplicate email raises error."""
    register_user("user1", "test@example.com", "password123")
    
    with pytest.raises(ValueError, match="already registered"):
        register_user("user2", "test@example.com", "password456")


def test_authenticate_user():
    """Test user authentication."""
    register_user("testuser", "test@example.com", "password123")
    
    # Correct credentials should authenticate
    user = authenticate_user("testuser", "password123")
    assert user is not None
    assert user.username == "testuser"
    
    # Wrong password should not authenticate
    user = authenticate_user("testuser", "wrongpassword")
    assert user is None
    
    # Non-existent user should not authenticate
    user = authenticate_user("nonexistent", "password123")
    assert user is None


def test_user_verify_password():
    """Test User.verify_password method."""
    user = register_user("testuser", "test@example.com", "password123")
    
    assert user.verify_password("password123") is True
    assert user.verify_password("wrongpassword") is False


def test_user_to_dict():
    """Test User.to_dict method."""
    user = register_user("testuser", "test@example.com", "password123", role="admin")
    
    user_dict = user.to_dict()
    
    assert user_dict["username"] == "testuser"
    assert user_dict["email"] == "test@example.com"
    assert user_dict["role"] == "admin"
    
    # Password should not be in dict
    assert "password" not in user_dict
    assert "hashed_password" not in user_dict


def test_get_user():
    """Test getting user by username."""
    user = register_user("testuser", "test@example.com", "password123")
    
    # Should return user
    retrieved = get_user("testuser")
    assert retrieved == user
    
    # Non-existent user should return None
    assert get_user("nonexistent") is None
