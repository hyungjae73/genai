"""
API endpoints for alert management.
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import AlertResponse
from src.auth.dependencies import get_current_user_or_api_key
from src.database import get_async_db
from src.models import Alert, MonitoringSite, Violation

router = APIRouter()


async def _resolve_alert_fields(alert: Alert, db: AsyncSession) -> dict:
    """Resolve site_name and violation_type from related models.

    Returns a dict representation of the alert with resolved fields.
    """
    # Build base dict from ORM object
    data = {
        "id": alert.id,
        "violation_id": alert.violation_id,
        "alert_type": alert.alert_type,
        "severity": alert.severity,
        "message": alert.message,
        "email_sent": alert.email_sent,
        "slack_sent": alert.slack_sent,
        "created_at": alert.created_at,
        "is_resolved": alert.is_resolved,
        "site_id": alert.site_id,
        "old_price": alert.old_price,
        "new_price": alert.new_price,
        "change_percentage": alert.change_percentage,
        "fake_domain": alert.fake_domain,
        "legitimate_domain": alert.legitimate_domain,
        "domain_similarity_score": alert.domain_similarity_score,
        "content_similarity_score": alert.content_similarity_score,
        "site_name": None,
        "violation_type": None,
    }

    # Resolve site_name from MonitoringSite
    if alert.site_id is not None:
        result = await db.execute(select(MonitoringSite).where(MonitoringSite.id == alert.site_id))
        site = result.scalar_one_or_none()
        if site:
            data["site_name"] = site.name

    # Resolve violation_type
    if alert.alert_type == "fake_site":
        data["violation_type"] = "fake_site"
    elif alert.violation_id is not None:
        result = await db.execute(select(Violation).where(Violation.id == alert.violation_id))
        violation = result.scalar_one_or_none()
        if violation:
            data["violation_type"] = violation.violation_type

    return data


@router.get("/", response_model=List[AlertResponse])
async def list_alerts(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    alert_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user_or_api_key),
):
    """Get list of alerts."""
    stmt = select(Alert).order_by(Alert.created_at.desc())
    if alert_type is not None:
        stmt = stmt.where(Alert.alert_type == alert_type)
    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    alerts = result.scalars().all()
    return [await _resolve_alert_fields(alert, db) for alert in alerts]


@router.get("/site/{site_id}", response_model=List[AlertResponse])
async def get_site_alerts(
    site_id: int,
    is_resolved: Optional[bool] = None,
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user_or_api_key),
):
    """Get alerts for a specific site, optionally filtered by resolution status."""
    stmt = select(Alert).where(Alert.site_id == site_id)

    if is_resolved is not None:
        stmt = stmt.where(Alert.is_resolved == is_resolved)

    stmt = stmt.order_by(Alert.created_at.desc())
    result = await db.execute(stmt)
    alerts = result.scalars().all()
    return [await _resolve_alert_fields(alert, db) for alert in alerts]


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(alert_id: int, db: AsyncSession = Depends(get_async_db), current_user = Depends(get_current_user_or_api_key)):
    """Get a specific alert."""
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with id {alert_id} not found"
        )
    return await _resolve_alert_fields(alert, db)
