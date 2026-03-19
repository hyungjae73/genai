"""
API endpoints for alert management.
"""

from fastapi import APIRouter, HTTPException, status
from typing import List, Optional

from src.api.schemas import AlertResponse

router = APIRouter()

# In-memory storage for demonstration
alerts_db = {}


@router.get("/", response_model=List[AlertResponse])
async def list_alerts(limit: int = 100, offset: int = 0):
    """Get list of alerts."""
    alerts = list(alerts_db.values())
    return [AlertResponse(**alert) for alert in alerts[offset:offset + limit]]


@router.get("/site/{site_id}", response_model=List[AlertResponse])
async def get_site_alerts(site_id: int, is_resolved: Optional[bool] = None):
    """Get alerts for a specific site, optionally filtered by resolution status."""
    site_alerts = [
        alert for alert in alerts_db.values()
        if alert.get("site_id") == site_id
    ]

    if is_resolved is not None:
        site_alerts = [
            alert for alert in site_alerts
            if alert.get("is_resolved") == is_resolved
        ]

    # Order by created_at descending
    site_alerts.sort(key=lambda a: a.get("created_at", ""), reverse=True)

    return [AlertResponse(**alert) for alert in site_alerts]


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(alert_id: int):
    """Get a specific alert."""
    if alert_id not in alerts_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with id {alert_id} not found"
        )
    
    return AlertResponse(**alerts_db[alert_id])

