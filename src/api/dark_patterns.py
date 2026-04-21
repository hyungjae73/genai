"""
Dark Pattern Detection API endpoints.

Provides read access to dark pattern detection results stored in
VerificationResult records.

Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user_or_api_key
from src.database import get_db
from src.models import MonitoringSite, VerificationResult

router = APIRouter()


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class DarkPatternResponse(BaseModel):
    """Latest dark pattern detection result for a site."""

    site_id: int
    verification_result_id: int
    dark_pattern_score: Optional[float]
    dark_pattern_subscores: Optional[Dict[str, Any]]
    dark_pattern_types: Optional[Dict[str, Any]]
    detected_at: datetime

    class Config:
        from_attributes = True


class DarkPatternHistoryItem(BaseModel):
    """Single history entry."""

    verification_result_id: int
    dark_pattern_score: Optional[float]
    dark_pattern_subscores: Optional[Dict[str, Any]]
    dark_pattern_types: Optional[Dict[str, Any]]
    detected_at: datetime

    class Config:
        from_attributes = True


class DarkPatternHistoryResponse(BaseModel):
    """Paginated history of dark pattern detection results."""

    site_id: int
    results: List[DarkPatternHistoryItem]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_site_or_404(site_id: int, db: Session) -> MonitoringSite:
    site = db.query(MonitoringSite).filter(MonitoringSite.id == site_id).first()
    if site is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site {site_id} not found",
        )
    return site


def _to_history_item(vr: VerificationResult) -> DarkPatternHistoryItem:
    return DarkPatternHistoryItem(
        verification_result_id=vr.id,
        dark_pattern_score=vr.dark_pattern_score,
        dark_pattern_subscores=vr.dark_pattern_subscores,
        dark_pattern_types=vr.dark_pattern_types,
        detected_at=vr.created_at,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/sites/{site_id}/dark-patterns",
    response_model=Optional[DarkPatternResponse],
    summary="Get latest dark pattern detection result",
)
async def get_latest_dark_patterns(
    site_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_or_api_key),
) -> Optional[DarkPatternResponse]:
    """Return the most recent dark pattern detection result for a site.

    Returns null (HTTP 200 with null body) when no detection data exists yet.
    Returns HTTP 404 when the site itself does not exist.
    """
    _get_site_or_404(site_id, db)

    vr = (
        db.query(VerificationResult)
        .filter(
            VerificationResult.site_id == site_id,
            VerificationResult.dark_pattern_score.isnot(None),
        )
        .order_by(VerificationResult.created_at.desc())
        .first()
    )

    if vr is None:
        return None

    return DarkPatternResponse(
        site_id=site_id,
        verification_result_id=vr.id,
        dark_pattern_score=vr.dark_pattern_score,
        dark_pattern_subscores=vr.dark_pattern_subscores,
        dark_pattern_types=vr.dark_pattern_types,
        detected_at=vr.created_at,
    )


@router.get(
    "/sites/{site_id}/dark-patterns/history",
    response_model=DarkPatternHistoryResponse,
    summary="Get paginated dark pattern detection history",
)
async def get_dark_pattern_history(
    site_id: int,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_or_api_key),
) -> DarkPatternHistoryResponse:
    """Return paginated history of dark pattern detection results for a site.

    Returns HTTP 404 when the site does not exist.
    Returns an empty results list when no detection data exists.
    """
    _get_site_or_404(site_id, db)

    query = (
        db.query(VerificationResult)
        .filter(
            VerificationResult.site_id == site_id,
            VerificationResult.dark_pattern_score.isnot(None),
        )
        .order_by(VerificationResult.created_at.desc())
    )

    total = query.count()
    rows = query.offset(offset).limit(limit).all()

    return DarkPatternHistoryResponse(
        site_id=site_id,
        results=[_to_history_item(vr) for vr in rows],
        total=total,
        limit=limit,
        offset=offset,
    )
