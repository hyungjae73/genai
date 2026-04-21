"""
Notification configuration and history API endpoints.

GET  /api/sites/{site_id}/notification-config  — merged config (masked webhook)
PUT  /api/sites/{site_id}/notification-config  — update site plugin_config
GET  /api/sites/{site_id}/notifications        — notification history with filters

Requirements: 9.1-9.6, 10.1-10.6
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.api.schemas import (
    NotificationConfigResponse,
    NotificationConfigUpdate,
    NotificationHistoryResponse,
    PaginatedNotificationHistoryResponse,
)
from src.auth.dependencies import get_current_user_or_api_key
from src.database import get_db
from src.models import MonitoringSite, NotificationRecord
from src.pipeline.plugins.notification_config import (
    mask_webhook_url,
    merge_notification_config,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_site_or_404(site_id: int, db: Session) -> MonitoringSite:
    """Fetch MonitoringSite or raise 404."""
    site = db.query(MonitoringSite).filter(MonitoringSite.id == site_id).first()
    if site is None:
        raise HTTPException(status_code=404, detail=f"Site {site_id} not found")
    return site


@router.get(
    "/sites/{site_id}/notification-config",
    response_model=NotificationConfigResponse,
)
def get_notification_config(
    site_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_or_api_key),
) -> NotificationConfigResponse:
    """Return merged notification config with masked webhook URL.

    Req 9.1, 9.3, 9.4
    """
    site = _get_site_or_404(site_id, db)

    customer_email = ""
    try:
        customer_email = site.customer.email
    except (AttributeError, TypeError):
        pass

    config = merge_notification_config(customer_email, site.plugin_config)

    return NotificationConfigResponse(
        slack_enabled=config.slack_enabled,
        slack_webhook_url=mask_webhook_url(config.slack_webhook_url),
        slack_channel=config.slack_channel,
        email_enabled=config.email_enabled,
        email_recipients=config.email_recipients,
        suppression_window_hours=config.suppression_window_hours,
    )


@router.put(
    "/sites/{site_id}/notification-config",
    response_model=NotificationConfigResponse,
)
def update_notification_config(
    site_id: int,
    body: NotificationConfigUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_or_api_key),
) -> NotificationConfigResponse:
    """Update site plugin_config.params.NotificationPlugin and return merged config.

    Req 9.2, 9.5, 9.6
    """
    site = _get_site_or_404(site_id, db)

    # Build current plugin_config (or empty)
    plugin_config = dict(site.plugin_config) if site.plugin_config else {}
    params = dict(plugin_config.get("params", {}))
    np_params = dict(params.get("NotificationPlugin", {}))

    # Apply updates from body (only non-None fields)
    update_data = body.model_dump(exclude_none=True)
    for key in ("slack_enabled", "slack_webhook_url", "slack_channel", "email_enabled", "suppression_window_hours"):
        if key in update_data:
            np_params[key] = update_data[key]
    if "additional_email_recipients" in update_data:
        np_params["additional_email_recipients"] = update_data["additional_email_recipients"]

    params["NotificationPlugin"] = np_params
    plugin_config["params"] = params

    # Persist
    site.plugin_config = plugin_config
    db.add(site)
    db.flush()

    # Re-merge to return the effective config
    customer_email = ""
    try:
        customer_email = site.customer.email
    except (AttributeError, TypeError):
        pass

    config = merge_notification_config(customer_email, site.plugin_config)

    return NotificationConfigResponse(
        slack_enabled=config.slack_enabled,
        slack_webhook_url=mask_webhook_url(config.slack_webhook_url),
        slack_channel=config.slack_channel,
        email_enabled=config.email_enabled,
        email_recipients=config.email_recipients,
        suppression_window_hours=config.suppression_window_hours,
    )


@router.get(
    "/sites/{site_id}/notifications",
    response_model=PaginatedNotificationHistoryResponse,
)
def get_notification_history(
    site_id: int,
    channel: Optional[str] = Query(None, description="Filter by channel (slack/email)"),
    status: Optional[str] = Query(None, description="Filter by status (sent/failed/skipped)"),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_or_api_key),
) -> PaginatedNotificationHistoryResponse:
    """Return paginated notification history with optional filters.

    Req 10.1-10.6
    """
    _get_site_or_404(site_id, db)

    query = db.query(NotificationRecord).filter(
        NotificationRecord.site_id == site_id
    )

    if channel is not None:
        query = query.filter(NotificationRecord.channel == channel)
    if status is not None:
        query = query.filter(NotificationRecord.status == status)

    total = query.count()

    records = (
        query.order_by(NotificationRecord.sent_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items = [
        NotificationHistoryResponse(
            id=r.id,
            violation_type=r.violation_type,
            channel=r.channel,
            recipient=r.recipient,
            status=r.status,
            sent_at=r.sent_at,
        )
        for r in records
    ]

    return PaginatedNotificationHistoryResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )
