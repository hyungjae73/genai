"""
API endpoints for crawl schedule management.

Provides CRUD operations for CrawlSchedule and site settings updates
(pre_capture_script, crawl_priority, plugin_config).
"""

import json
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user_or_api_key
from src.database import get_db
from src.models import CrawlSchedule, MonitoringSite

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class CrawlScheduleResponse(BaseModel):
    """Response schema for CrawlSchedule."""
    id: int
    site_id: int
    priority: str
    next_crawl_at: datetime
    interval_minutes: int
    last_etag: Optional[str] = None
    last_modified: Optional[str] = None

    class Config:
        from_attributes = True


class CrawlScheduleCreate(BaseModel):
    """Schema for creating a CrawlSchedule."""
    priority: str = Field(default="normal")
    interval_minutes: int = Field(default=1440, ge=1)

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        if v not in ("high", "normal", "low"):
            raise ValueError("priority must be 'high', 'normal', or 'low'")
        return v


class CrawlScheduleUpdate(BaseModel):
    """Schema for updating a CrawlSchedule."""
    priority: Optional[str] = None
    interval_minutes: Optional[int] = Field(default=None, ge=1)

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("high", "normal", "low"):
            raise ValueError("priority must be 'high', 'normal', or 'low'")
        return v


class SiteSettingsUpdate(BaseModel):
    """Schema for updating MonitoringSite pipeline settings."""
    pre_capture_script: Optional[Any] = None
    crawl_priority: Optional[str] = None
    plugin_config: Optional[Any] = None

    @field_validator("crawl_priority")
    @classmethod
    def validate_crawl_priority(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("high", "normal", "low"):
            raise ValueError("crawl_priority must be 'high', 'normal', or 'low'")
        return v


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _get_site_or_404(site_id: int, db: Session) -> MonitoringSite:
    site = db.query(MonitoringSite).filter(MonitoringSite.id == site_id).first()
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site with id {site_id} not found",
        )
    return site


# ---------------------------------------------------------------------------
# Schedule CRUD  (Req 26.1, 26.2, 26.3, 26.6)
# ---------------------------------------------------------------------------

@router.get(
    "/sites/{site_id}/schedule",
    response_model=CrawlScheduleResponse,
)
async def get_schedule(site_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user_or_api_key)):
    """Get the CrawlSchedule for a site."""
    _get_site_or_404(site_id, db)
    schedule = (
        db.query(CrawlSchedule)
        .filter(CrawlSchedule.site_id == site_id)
        .first()
    )
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule for site {site_id} not found",
        )
    return schedule


@router.post(
    "/sites/{site_id}/schedule",
    response_model=CrawlScheduleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_schedule(
    site_id: int,
    body: CrawlScheduleCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_or_api_key),
):
    """Create a new CrawlSchedule for a site."""
    _get_site_or_404(site_id, db)

    existing = (
        db.query(CrawlSchedule)
        .filter(CrawlSchedule.site_id == site_id)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Schedule for site {site_id} already exists",
        )

    schedule = CrawlSchedule(
        site_id=site_id,
        priority=body.priority,
        interval_minutes=body.interval_minutes,
        next_crawl_at=datetime.utcnow() + timedelta(minutes=body.interval_minutes),
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


@router.put(
    "/sites/{site_id}/schedule",
    response_model=CrawlScheduleResponse,
)
async def update_schedule(
    site_id: int,
    body: CrawlScheduleUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_or_api_key),
):
    """Update an existing CrawlSchedule."""
    _get_site_or_404(site_id, db)

    schedule = (
        db.query(CrawlSchedule)
        .filter(CrawlSchedule.site_id == site_id)
        .first()
    )
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule for site {site_id} not found",
        )

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(schedule, field, value)

    db.commit()
    db.refresh(schedule)
    return schedule


# ---------------------------------------------------------------------------
# Site settings update  (Req 26.4, 26.5)
# ---------------------------------------------------------------------------

@router.put("/sites/{site_id}/settings")
async def update_site_settings(
    site_id: int,
    body: SiteSettingsUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_or_api_key),
):
    """Update MonitoringSite pipeline settings (pre_capture_script, crawl_priority, plugin_config)."""
    site = _get_site_or_404(site_id, db)

    update_data = body.model_dump(exclude_unset=True)

    # Validate pre_capture_script is valid JSON structure
    if "pre_capture_script" in update_data:
        pcs = update_data["pre_capture_script"]
        if pcs is not None:
            # If it's a string, try to parse it as JSON
            if isinstance(pcs, str):
                try:
                    pcs = json.loads(pcs)
                    update_data["pre_capture_script"] = pcs
                except (json.JSONDecodeError, TypeError):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="pre_capture_script must be valid JSON",
                    )
            # Must be a list of action objects
            if not isinstance(pcs, list):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="pre_capture_script must be a JSON array of action objects",
                )

    # Validate plugin_config is valid JSON structure
    if "plugin_config" in update_data:
        pc = update_data["plugin_config"]
        if pc is not None:
            if isinstance(pc, str):
                try:
                    pc = json.loads(pc)
                    update_data["plugin_config"] = pc
                except (json.JSONDecodeError, TypeError):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="plugin_config must be valid JSON",
                    )
            if not isinstance(pc, dict):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="plugin_config must be a JSON object",
                )

    for field, value in update_data.items():
        setattr(site, field, value)

    db.commit()
    db.refresh(site)

    return {
        "id": site.id,
        "pre_capture_script": site.pre_capture_script,
        "crawl_priority": site.crawl_priority,
        "plugin_config": site.plugin_config,
    }
