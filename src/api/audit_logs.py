"""
API endpoints for audit log retrieval.

Provides read access to the audit_logs table so the frontend
can display change history for any entity.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user_or_api_key
from src.database import get_async_db
from src.models import AuditLog

router = APIRouter()


@router.get("/{entity_type}/{entity_id}")
async def get_audit_logs(
    entity_type: str,
    entity_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user_or_api_key),
):
    """
    Get audit logs for a specific entity.

    Returns change history ordered by most recent first (max 100).
    """
    result = await db.execute(
        select(AuditLog)
        .where(
            AuditLog.resource_type == entity_type,
            AuditLog.resource_id == entity_id,
        )
        .order_by(AuditLog.timestamp.desc())
        .limit(100)
    )
    logs = result.scalars().all()
    return [
        {
            "id": log.id,
            "user": log.user,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "details": log.details,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
        }
        for log in logs
    ]
