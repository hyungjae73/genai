"""
API endpoints for manual crawl execution.
"""

import uuid
from typing import Dict, List

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy import desc
from sqlalchemy.orm import Session

from src.api.schemas import (
    CrawlJobResponse,
    CrawlStatusResponse,
    CrawlResultResponse,
)
from src.database import get_db
from src.models import MonitoringSite, CrawlResult, ContractCondition
from src.celery_app import celery_app

router = APIRouter()

# In-memory job tracking for active crawls
_site_running_jobs: Dict[int, str] = {}


@router.post("/site/{site_id}", response_model=CrawlJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_crawl(site_id: int, db: Session = Depends(get_db)):
    """
    Start a crawl job for the specified site using Celery.

    Returns 404 if the site does not exist.
    Returns 409 if a crawl is already running for this site.
    """
    site = db.query(MonitoringSite).filter(MonitoringSite.id == site_id).first()
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="サイトが見つかりません",
        )

    # Check for already-running crawl on this site
    if site_id in _site_running_jobs:
        existing_job_id = _site_running_jobs[site_id]
        # Check if task is still active
        task_result = celery_app.AsyncResult(existing_job_id)
        if task_result.state in ('PENDING', 'STARTED', 'RETRY'):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="クロールが実行中です",
            )
        else:
            # Task completed or failed, remove from tracking
            del _site_running_jobs[site_id]

    # Get contract conditions for validation
    contract = (
        db.query(ContractCondition)
        .filter(ContractCondition.site_id == site_id, ContractCondition.is_current == True)
        .first()
    )
    
    contract_conditions = {}
    if contract:
        contract_conditions = {
            'prices': contract.prices or {},
            'payment_methods': contract.payment_methods or [],
            'fees': contract.fees or {},
            'subscription_terms': contract.subscription_terms or {}
        }

    # Notification config (simplified for now)
    notification_config = {
        'email_enabled': False,
        'slack_enabled': False,
        'email_recipients': [],
        'slack_webhook_url': None
    }

    # Start Celery task
    task = celery_app.send_task(
        'src.tasks.crawl_and_validate_site',
        args=[site_id, site.url, contract_conditions, notification_config]
    )
    
    _site_running_jobs[site_id] = task.id

    return CrawlJobResponse(job_id=task.id, status="pending")


@router.get("/status/{job_id}", response_model=CrawlStatusResponse)
async def get_crawl_status(job_id: str):
    """
    Get the status of a crawl job from Celery.

    Returns 404 if the job is not found.
    """
    task_result = celery_app.AsyncResult(job_id)
    
    # Map Celery states to our status
    status_mapping = {
        'PENDING': 'pending',
        'STARTED': 'running',
        'RETRY': 'running',
        'SUCCESS': 'completed',
        'FAILURE': 'failed',
        'REVOKED': 'failed',
    }
    
    status_value = status_mapping.get(task_result.state, 'pending')
    result_data = None
    
    if task_result.state == 'SUCCESS':
        result_data = task_result.result
    elif task_result.state == 'FAILURE':
        result_data = {'error': str(task_result.info)}

    return CrawlStatusResponse(
        job_id=job_id,
        status=status_value,
        result=result_data,
    )


@router.get("/results/{site_id}", response_model=List[CrawlResultResponse])
async def get_crawl_results(site_id: int, db: Session = Depends(get_db)):
    """
    Get crawl result history for a site, ordered by crawled_at descending.

    Returns 404 if the site does not exist.
    """
    site = db.query(MonitoringSite).filter(MonitoringSite.id == site_id).first()
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="サイトが見つかりません",
        )

    results = (
        db.query(CrawlResult)
        .filter(CrawlResult.site_id == site_id)
        .order_by(desc(CrawlResult.crawled_at))
        .all()
    )

    return results


@router.get("/results/{site_id}/latest", response_model=CrawlResultResponse)
async def get_latest_crawl_result(site_id: int, db: Session = Depends(get_db)):
    """
    Get the most recent crawl result for a site.

    Returns 404 if the site does not exist or has no crawl results.
    """
    site = db.query(MonitoringSite).filter(MonitoringSite.id == site_id).first()
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="サイトが見つかりません",
        )

    result = (
        db.query(CrawlResult)
        .filter(CrawlResult.site_id == site_id)
        .order_by(desc(CrawlResult.crawled_at))
        .first()
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="クロール結果が見つかりません",
        )

    return result
