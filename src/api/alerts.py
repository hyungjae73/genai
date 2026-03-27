"""
API endpoints for alert management.
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional

from sqlalchemy.orm import Session

from src.api.schemas import AlertResponse
from src.database import get_db
from src.models import Alert, MonitoringSite, Violation

router = APIRouter()


def _resolve_alert_fields(alert: Alert, db: Session) -> dict:
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
        site = db.query(MonitoringSite).filter(MonitoringSite.id == alert.site_id).first()
        if site:
            data["site_name"] = site.name

    # Resolve violation_type
    if alert.alert_type == "fake_site":
        data["violation_type"] = "fake_site"
    elif alert.violation_id is not None:
        violation = db.query(Violation).filter(Violation.id == alert.violation_id).first()
        if violation:
            data["violation_type"] = violation.violation_type

    return data


@router.get("/", response_model=List[AlertResponse])
async def list_alerts(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    alert_type: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get list of alerts."""
    query = db.query(Alert).order_by(Alert.created_at.desc())
    if alert_type is not None:
        query = query.filter(Alert.alert_type == alert_type)
    alerts = query.offset(offset).limit(limit).all()
    return [_resolve_alert_fields(alert, db) for alert in alerts]


@router.get("/site/{site_id}", response_model=List[AlertResponse])
async def get_site_alerts(
    site_id: int,
    is_resolved: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """Get alerts for a specific site, optionally filtered by resolution status."""
    query = db.query(Alert).filter(Alert.site_id == site_id)

    if is_resolved is not None:
        query = query.filter(Alert.is_resolved == is_resolved)

    alerts = query.order_by(Alert.created_at.desc()).all()
    return [_resolve_alert_fields(alert, db) for alert in alerts]


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(alert_id: int, db: Session = Depends(get_db)):
    """Get a specific alert."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with id {alert_id} not found"
        )
    return _resolve_alert_fields(alert, db)
