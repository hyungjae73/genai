"""
API endpoints for monitoring history and statistics.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import datetime

from src.api.schemas import (
    MonitoringHistoryFilter,
    CrawlResultResponse,
    ViolationResponse,
    MonitoringStatistics
)

router = APIRouter()

# In-memory storage for demonstration
crawl_results_db = {}
violations_db = {}


@router.get("/history", response_model=List[CrawlResultResponse])
async def get_monitoring_history(
    site_id: Optional[int] = Query(None, description="Filter by site ID"),
    start_date: Optional[datetime] = Query(None, description="Start date for filtering"),
    end_date: Optional[datetime] = Query(None, description="End date for filtering"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """
    Get monitoring history with optional filtering.
    
    Returns crawl results filtered by site, date range, etc.
    """
    results = list(crawl_results_db.values())
    
    # Apply filters
    if site_id is not None:
        results = [r for r in results if r['site_id'] == site_id]
    
    if start_date is not None:
        results = [r for r in results if r['crawled_at'] >= start_date]
    
    if end_date is not None:
        results = [r for r in results if r['crawled_at'] <= end_date]
    
    # Sort by date (newest first)
    results.sort(key=lambda x: x['crawled_at'], reverse=True)
    
    # Apply pagination
    paginated_results = results[offset:offset + limit]
    
    return [CrawlResultResponse(**r) for r in paginated_results]


@router.get("/violations", response_model=List[ViolationResponse])
async def get_violations(
    site_id: Optional[int] = Query(None, description="Filter by site ID"),
    violation_type: Optional[str] = Query(None, description="Filter by violation type"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    start_date: Optional[datetime] = Query(None, description="Start date for filtering"),
    end_date: Optional[datetime] = Query(None, description="End date for filtering"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """
    Get violations with optional filtering.
    
    Returns violations filtered by site, type, severity, date range, etc.
    """
    results = list(violations_db.values())
    
    # Apply filters
    if violation_type is not None:
        results = [r for r in results if r['violation_type'] == violation_type]
    
    if severity is not None:
        results = [r for r in results if r['severity'] == severity]
    
    if start_date is not None:
        results = [r for r in results if r['detected_at'] >= start_date]
    
    if end_date is not None:
        results = [r for r in results if r['detected_at'] <= end_date]
    
    # Sort by date (newest first)
    results.sort(key=lambda x: x['detected_at'], reverse=True)
    
    # Apply pagination
    paginated_results = results[offset:offset + limit]
    
    return [ViolationResponse(**r) for r in paginated_results]


@router.get("/statistics", response_model=MonitoringStatistics)
async def get_statistics():
    """
    Get monitoring statistics.
    
    Returns overall statistics about monitoring sites, violations, and success rates.
    """
    # Return mock statistics for now
    return MonitoringStatistics(
        total_sites=0,
        active_sites=0,
        total_violations=0,
        high_severity_violations=0,
        success_rate=100.0,
        last_crawl=None
    )
