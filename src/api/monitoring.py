"""
API endpoints for monitoring history and statistics.
"""

import os
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Depends
import redis.asyncio as aioredis
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import (
    MonitoringHistoryFilter,
    CrawlResultResponse,
    ViolationResponse,
    MonitoringStatistics
)
from src.auth.dependencies import get_current_user_or_api_key
from src.database import get_async_db
from src.models import MonitoringSite, CrawlResult, Violation, Alert
from src.pipeline.telemetry_collector import TelemetryCollector

router = APIRouter()


@router.get("/history", response_model=List[CrawlResultResponse])
async def get_monitoring_history(
    site_id: Optional[int] = Query(None, description="Filter by site ID"),
    start_date: Optional[datetime] = Query(None, description="Start date for filtering"),
    end_date: Optional[datetime] = Query(None, description="End date for filtering"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user_or_api_key),
):
    """
    Get monitoring history with optional filtering.
    
    Returns crawl results filtered by site, date range, etc.
    """
    stmt = select(CrawlResult)
    
    if site_id is not None:
        stmt = stmt.where(CrawlResult.site_id == site_id)
    
    if start_date is not None:
        stmt = stmt.where(CrawlResult.crawled_at >= start_date)
    
    if end_date is not None:
        stmt = stmt.where(CrawlResult.crawled_at <= end_date)
    
    stmt = stmt.order_by(CrawlResult.crawled_at.desc())
    stmt = stmt.offset(offset).limit(limit)
    
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/violations", response_model=List[ViolationResponse])
async def get_violations(
    site_id: Optional[int] = Query(None, description="Filter by site ID"),
    violation_type: Optional[str] = Query(None, description="Filter by violation type"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    start_date: Optional[datetime] = Query(None, description="Start date for filtering"),
    end_date: Optional[datetime] = Query(None, description="End date for filtering"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user_or_api_key),
):
    """
    Get violations with optional filtering.
    
    Returns violations filtered by site, type, severity, date range, etc.
    """
    stmt = select(Violation)
    
    if violation_type is not None:
        stmt = stmt.where(Violation.violation_type == violation_type)
    
    if severity is not None:
        stmt = stmt.where(Violation.severity == severity)
    
    if start_date is not None:
        stmt = stmt.where(Violation.detected_at >= start_date)
    
    if end_date is not None:
        stmt = stmt.where(Violation.detected_at <= end_date)
    
    stmt = stmt.order_by(Violation.detected_at.desc())
    stmt = stmt.offset(offset).limit(limit)
    
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/statistics", response_model=MonitoringStatistics)
async def get_statistics(db: AsyncSession = Depends(get_async_db), current_user = Depends(get_current_user_or_api_key)):
    """
    Get monitoring statistics.
    
    Returns overall statistics about monitoring sites, violations, and success rates.
    """
    total_sites = (await db.execute(select(func.count(MonitoringSite.id)))).scalar() or 0
    active_sites = (await db.execute(
        select(func.count(MonitoringSite.id)).where(MonitoringSite.is_active == True)
    )).scalar() or 0

    total_violations = (await db.execute(select(func.count(Violation.id)))).scalar() or 0
    high_severity_violations = (await db.execute(
        select(func.count(Violation.id)).where(Violation.severity == "high")
    )).scalar() or 0

    # Calculate success rate from crawl results
    total_crawls = (await db.execute(select(func.count(CrawlResult.id)))).scalar() or 0
    successful_crawls = (await db.execute(
        select(func.count(CrawlResult.id)).where(
            CrawlResult.status_code >= 200,
            CrawlResult.status_code < 400,
        )
    )).scalar() or 0
    success_rate = (successful_crawls / total_crawls * 100.0) if total_crawls > 0 else 100.0

    last_crawl_result = (await db.execute(select(func.max(CrawlResult.crawled_at)))).scalar()

    # Count fake site alerts
    fake_site_alerts = (await db.execute(
        select(func.count(Alert.id)).where(Alert.alert_type == "fake_site")
    )).scalar() or 0
    unresolved_fake_site_alerts = (await db.execute(
        select(func.count(Alert.id)).where(
            Alert.alert_type == "fake_site",
            Alert.is_resolved == False,
        )
    )).scalar() or 0

    return MonitoringStatistics(
        total_sites=total_sites,
        active_sites=active_sites,
        total_violations=total_violations,
        high_severity_violations=high_severity_violations,
        success_rate=success_rate,
        last_crawl=last_crawl_result,
        fake_site_alerts=fake_site_alerts,
        unresolved_fake_site_alerts=unresolved_fake_site_alerts
    )


@router.get("/sites/{site_id}/fetch-telemetry")
async def get_fetch_telemetry(site_id: int, current_user = Depends(get_current_user_or_api_key)):
    """Get fetch telemetry for a site (trailing 1-hour window).

    Returns current success rate, total attempts, and block breakdown.
    Requirements: 17.5
    """
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        redis_client = aioredis.from_url(redis_url, decode_responses=True)
        try:
            collector = TelemetryCollector(redis_client)
            result = await collector.get_success_rate(site_id, window_seconds=3600)
            return result
        finally:
            await redis_client.aclose()
    except (ConnectionError, OSError, aioredis.RedisError) as exc:
        raise HTTPException(status_code=503, detail=f"Redis unavailable: {exc}")
