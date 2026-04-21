"""
Users management router — all endpoints require the admin role.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy.orm import Session

from src.auth.dependencies import get_redis, require_role
from src.auth.password import hash_password, validate_password_policy
from src.auth.rbac import Role
from src.auth.schemas import AdminResetPasswordRequest, UserCreate, UserResponse, UserUpdate
from src.auth.session import revoke_all_user_tokens
from src.database import get_db
from src.models import AuditLog, User

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _audit(
    db: Session,
    username: str,
    action: str,
    resource_id: Optional[int] = None,
    details: Optional[dict] = None,
    request: Optional[Request] = None,
) -> None:
    log = AuditLog(
        user=username,
        action=action,
        resource_type="user",
        resource_id=resource_id,
        details=details,
        ip_address=request.client.host if request and request.client else None,
        user_agent=request.headers.get("user-agent") if request else None,
    )
    db.add(log)
    db.flush()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN)),
):
    """Create a new user (admin only)."""
    # Password policy
    violations = validate_password_policy(body.password)
    if violations:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=violations,
        )

    # Duplicate checks
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="このユーザ名は既に使用されています",
        )
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="このメールアドレスは既に使用されています",
        )

    user = User(
        username=body.username,
        email=body.email,
        hashed_password=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    db.flush()  # populate user.id

    _audit(db, current_user.username, "create", user.id,
           {"username": body.username, "role": body.role}, request)

    return user


@router.get("/", response_model=List[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN)),
):
    """List all users (admin only). hashed_password is excluded by the schema."""
    return db.query(User).all()


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN)),
):
    """Get a single user by ID (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ユーザが見つかりません")
    return user


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    body: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN)),
):
    """Update a user (admin only). Username changes are not allowed."""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ユーザが見つかりません")

    update_data = body.model_dump(exclude_unset=True)

    # Apply each provided field
    if "email" in update_data and update_data["email"] is not None:
        existing = db.query(User).filter(
            User.email == update_data["email"], User.id != user_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="このメールアドレスは既に使用されています",
            )
        user.email = update_data["email"]

    if "role" in update_data and update_data["role"] is not None:
        user.role = update_data["role"]

    if "is_active" in update_data and update_data["is_active"] is not None:
        user.is_active = update_data["is_active"]

    db.flush()

    _audit(db, current_user.username, "update", user.id, update_data, request)

    return user


@router.post("/{user_id}/deactivate", response_model=UserResponse)
async def deactivate_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN)),
    redis: Redis = Depends(get_redis),
):
    """Deactivate a user and revoke all their sessions (admin only)."""
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="自分自身を無効化することはできません",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ユーザが見つかりません")

    user.is_active = False
    db.flush()

    # Revoke all refresh tokens in Redis
    await revoke_all_user_tokens(user.id, redis)

    _audit(db, current_user.username, "deactivate", user.id,
           {"username": user.username}, request)

    return user


@router.post("/{user_id}/reset-password", response_model=UserResponse)
async def reset_password(
    user_id: int,
    body: AdminResetPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN)),
    redis: Redis = Depends(get_redis),
):
    """Reset a user's password (admin only). Sets must_change_password flag."""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ユーザが見つかりません")

    # Validate new password policy
    violations = validate_password_policy(body.new_password)
    if violations:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=violations,
        )

    user.hashed_password = hash_password(body.new_password)
    user.must_change_password = True
    db.flush()

    # Revoke all sessions for the target user
    await revoke_all_user_tokens(user.id, redis)

    _audit(db, current_user.username, "reset_password", user.id,
           {"username": user.username}, request)

    return user
