"""
Authentication and authorization utilities.

This module provides JWT token generation/verification and password hashing.
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import jwt
import bcrypt
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials


# JWT configuration
SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'dev-secret-key-change-in-production')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Security scheme
security = HTTPBearer()


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password as string
        
    Example:
        >>> hashed = hash_password("mypassword")
        >>> verify_password("mypassword", hashed)
        True
    """
    # Generate salt and hash password
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to compare against
        
    Returns:
        True if password matches, False otherwise
        
    Example:
        >>> hashed = hash_password("mypassword")
        >>> verify_password("mypassword", hashed)
        True
        >>> verify_password("wrongpassword", hashed)
        False
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    except Exception:
        return False


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Data to encode in the token (e.g., {"sub": "user@example.com"})
        expires_delta: Token expiration time (default: 30 minutes)
        
    Returns:
        JWT token as string
        
    Example:
        >>> token = create_access_token({"sub": "user@example.com"})
        >>> payload = verify_access_token(token)
        >>> payload["sub"]
        'user@example.com'
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_access_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode a JWT access token.
    
    Args:
        token: JWT token to verify
        
    Returns:
        Decoded token payload
        
    Raises:
        HTTPException: If token is invalid or expired
        
    Example:
        >>> token = create_access_token({"sub": "user@example.com"})
        >>> payload = verify_access_token(token)
        >>> payload["sub"]
        'user@example.com'
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> Dict[str, Any]:
    """
    Dependency to get current authenticated user from JWT token.
    
    Args:
        credentials: HTTP Bearer credentials from request
        
    Returns:
        User data from token payload
        
    Raises:
        HTTPException: If token is invalid
        
    Example:
        @app.get("/protected")
        async def protected_route(user: dict = Depends(get_current_user)):
            return {"user": user["sub"]}
    """
    token = credentials.credentials
    payload = verify_access_token(token)
    
    if "sub" not in payload:
        raise HTTPException(
            status_code=401,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return payload


def require_role(required_role: str):
    """
    Dependency factory to require specific role for endpoint access.
    
    Args:
        required_role: Role required to access the endpoint
        
    Returns:
        Dependency function that checks user role
        
    Example:
        @app.get("/admin")
        async def admin_route(user: dict = Depends(require_role("admin"))):
            return {"message": "Admin access granted"}
    """
    def role_checker(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        user_role = user.get("role")
        if user_role != required_role:
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Required role: {required_role}",
            )
        return user
    
    return role_checker


class User:
    """
    User model for authentication.
    
    This is a simple in-memory user model. In production, this should be
    replaced with a database-backed user model.
    """
    
    def __init__(self, username: str, email: str, hashed_password: str, role: str = "user"):
        self.username = username
        self.email = email
        self.hashed_password = hashed_password
        self.role = role
    
    def verify_password(self, password: str) -> bool:
        """Verify password against stored hash."""
        return verify_password(password, self.hashed_password)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert user to dictionary (excluding password)."""
        return {
            "username": self.username,
            "email": self.email,
            "role": self.role
        }


# In-memory user store (for demonstration)
# In production, use a database
_users: Dict[str, User] = {}


def register_user(username: str, email: str, password: str, role: str = "user") -> User:
    """
    Register a new user.
    
    Args:
        username: Username
        email: Email address
        password: Plain text password
        role: User role (default: "user")
        
    Returns:
        Created user object
        
    Raises:
        ValueError: If username or email already exists
    """
    if username in _users:
        raise ValueError(f"Username '{username}' already exists")
    
    if any(u.email == email for u in _users.values()):
        raise ValueError(f"Email '{email}' already registered")
    
    hashed_password = hash_password(password)
    user = User(username, email, hashed_password, role)
    _users[username] = user
    
    return user


def authenticate_user(username: str, password: str) -> Optional[User]:
    """
    Authenticate a user with username and password.
    
    Args:
        username: Username
        password: Plain text password
        
    Returns:
        User object if authentication successful, None otherwise
    """
    user = _users.get(username)
    if not user:
        return None
    
    if not user.verify_password(password):
        return None
    
    return user


def get_user(username: str) -> Optional[User]:
    """
    Get user by username.
    
    Args:
        username: Username
        
    Returns:
        User object if found, None otherwise
    """
    return _users.get(username)
