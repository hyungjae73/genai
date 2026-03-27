"""
API endpoints for monitoring history and statistics.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import func

from src.api.schemas import (
    MonitoringHistoryFilter,
    CrawlResultResponse,
    ViolationResponse,
    MonitoringStatistics
)
from src.database import get_db
from src.models import MonitoringSite, CrawlResult, Violation, Alert

router = APIRouter()


@router.get("/history", response_model=List[CrawlResultResponse])
async def get_monitoring_history(
    site_id: Optional[int] = Query(None, description="Filter by site ID"),
    start_date: Optional[datetime] = Query(None, description="Start date for filtering"),
    end_date: Optional[datetime] = Query(None, description="End date for filtering"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db)
):
    """
    Get monitoring history with optional filtering.
    
    Returns crawl results filtered by site, date range, etc.
    """
    query = db.query(CrawlResult)
    
    if site_id is not None:
        query = query.filter(CrawlResult.site_id == site_id)
    
    if start_date is not None:
        query = query.filter(CrawlResult.crawled_at >= start_date)
    
    if end_date is not None:
        query = query.filter(CrawlResult.crawled_at <= end_date)
    
    query = query.order_by(CrawlResult.crawled_at.desc())
    
    results = query.offset(offset).limit(limit).all()
    
    return results


@router.get("/violations", response_model=List[ViolationResponse])
async def get_violations(
    site_id: Optional[int] = Query(None, description="Filter by site ID"),
    violation_type: Optional[str] = Query(None, description="Filter by violation type"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    start_date: Optional[datetime] = Query(None, description="Start date for filtering"),
    end_date: Optional[datetime] = Query(None, description="End date for filtering"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db)
):
    """
    Get violations with optional filtering.
    
    Returns violations filtered by site, type, severity, date range, etc.
    """
    query = db.query(Violation)
    
    if violation_type is not None:
        query = query.filter(Violation.violation_type == violation_type)
    
    if severity is not None:
        query = query.filter(Violation.severity == severity)
    
    if start_date is not None:
        query = query.filter(Violation.detected_at >= start_date)
    
    if end_date is not None:
        query = query.filter(Violation.detected_at <= end_date)
    
    query = query.order_by(Violation.detected_at.desc())
    
    results = query.offset(offset).limit(limit).all()
    
    return results


@router.get("/statistics", response_model=MonitoringStatistics)
async def get_statistics(db: Session = Depends(get_db)):
    """
    Get monitoring statistics.
    
    Returns overall statistics about monitoring sites, violations, and success rates.
    """
    total_sites = db.query(func.count(MonitoringSite.id)).scalar() or 0
    active_sites = db.query(func.count(MonitoringSite.id)).filter(
        MonitoringSite.is_active == True
    ).scalar() or 0

    total_violations = db.query(func.count(Violation.id)).scalar() or 0
    high_severity_violations = db.query(func.count(Violation.id)).filter(
        Violation.severity == "high"
    ).scalar() or 0

    # Calculate success rate from crawl results
    total_crawls = db.query(func.count(CrawlResult.id)).scalar() or 0
    successful_crawls = db.query(func.count(CrawlResult.id)).filter(
        CrawlResult.status_code >= 200,
        CrawlResult.status_code < 400
    ).scalar() or 0
    success_rate = (successful_crawls / total_crawls * 100.0) if total_crawls > 0 else 100.0

    last_crawl_result = db.query(func.max(CrawlResult.crawled_at)).scalar()

    # Count fake site alerts
    fake_site_alerts = db.query(func.count(Alert.id)).filter(
        Alert.alert_type == "fake_site"
    ).scalar() or 0
    unresolved_fake_site_alerts = db.query(func.count(Alert.id)).filter(
        Alert.alert_type == "fake_site",
        Alert.is_resolved == False
    ).scalar() or 0

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
