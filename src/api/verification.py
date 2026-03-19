"""
API endpoints for verification system.
"""

from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import MonitoringSite, VerificationResult
from src.verification_service import VerificationService
from src.analyzer import ContentAnalyzer
from src.validator import ValidationEngine
from src.ocr_engine import OCREngine
from src.screenshot_capture import ScreenshotCapture


router = APIRouter()


# Request/Response Schemas
class VerificationTriggerRequest(BaseModel):
    """Request schema for triggering verification."""
    site_id: int
    screenshot_resolution: Optional[tuple[int, int]] = None
    ocr_language: Optional[str] = "eng+jpn"


class DiscrepancyResponse(BaseModel):
    """Response schema for discrepancy."""
    field_name: str
    html_value: Any
    ocr_value: Any
    difference_type: str
    severity: str


class ViolationResponse(BaseModel):
    """Response schema for violation."""
    violation_type: str
    severity: str
    field_name: str
    expected_value: Any
    actual_value: Any
    message: str
    data_source: str


class VerificationResultResponse(BaseModel):
    """Response schema for verification result."""
    id: int
    site_id: int
    site_name: str
    html_data: dict
    ocr_data: dict
    discrepancies: List[dict]
    html_violations: List[dict]
    ocr_violations: List[dict]
    screenshot_path: str
    ocr_confidence: float
    status: str
    error_message: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class VerificationResultsListResponse(BaseModel):
    """Response schema for list of verification results."""
    results: List[VerificationResultResponse]
    total: int
    limit: int
    offset: int


class VerificationStatusResponse(BaseModel):
    """Response schema for verification status."""
    job_id: int
    status: str
    result: Optional[VerificationResultResponse] = None


# Global dictionary to track running verifications
_running_verifications = {}


async def _run_verification_task(site_id: int, db: Session):
    """Background task to run verification."""
    try:
        # Create service instances
        content_analyzer = ContentAnalyzer()
        validation_engine = ValidationEngine()
        ocr_engine = OCREngine()
        
        async with ScreenshotCapture() as screenshot_capture:
            verification_service = VerificationService(
                content_analyzer=content_analyzer,
                validation_engine=validation_engine,
                ocr_engine=ocr_engine,
                screenshot_capture=screenshot_capture,
                db_session=db
            )
            
            # Run verification
            await verification_service.run_verification(site_id)
    
    finally:
        # Remove from running verifications
        if site_id in _running_verifications:
            del _running_verifications[site_id]


@router.post("/run", status_code=status.HTTP_202_ACCEPTED)
async def trigger_verification(
    request: VerificationTriggerRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Trigger verification for a site.
    
    Returns:
        {
            "job_id": "verification_result_id",
            "status": "processing",
            "message": "Verification started"
        }
    """
    site_id = request.site_id
    
    # Check if site exists
    site = db.query(MonitoringSite).filter(MonitoringSite.id == site_id).first()
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site with id {site_id} not found"
        )
    
    # Check if verification is already running
    if site_id in _running_verifications:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Verification already running for site {site_id}"
        )
    
    # Mark as running
    _running_verifications[site_id] = {
        'started_at': datetime.utcnow(),
        'status': 'processing'
    }
    
    # Add background task
    background_tasks.add_task(_run_verification_task, site_id, db)
    
    return {
        "job_id": site_id,  # Using site_id as job_id for simplicity
        "status": "processing",
        "message": f"Verification started for site {site_id}"
    }


@router.get("/results/{site_id}")
async def get_verification_results(
    site_id: int,
    limit: int = 1,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    Get verification results for a site.
    
    Returns:
        {
            "results": [VerificationResult],
            "total": int,
            "limit": int,
            "offset": int
        }
    """
    # Check if site exists
    site = db.query(MonitoringSite).filter(MonitoringSite.id == site_id).first()
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site with id {site_id} not found"
        )
    
    # Query verification results
    query = db.query(VerificationResult).filter(
        VerificationResult.site_id == site_id
    ).order_by(VerificationResult.created_at.desc())
    
    total = query.count()
    
    if total == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No verification results found for site {site_id}"
        )
    
    results = query.offset(offset).limit(limit).all()
    
    # Format results
    formatted_results = []
    for result in results:
        formatted_results.append({
            'id': result.id,
            'site_id': result.site_id,
            'site_name': site.name,
            'html_data': result.html_data,
            'ocr_data': result.ocr_data,
            'discrepancies': result.discrepancies.get('items', []),
            'html_violations': result.html_violations.get('items', []),
            'ocr_violations': result.ocr_violations.get('items', []),
            'screenshot_path': result.screenshot_path,
            'ocr_confidence': result.ocr_confidence,
            'status': result.status,
            'error_message': result.error_message,
            'created_at': result.created_at
        })
    
    return {
        'results': formatted_results,
        'total': total,
        'limit': limit,
        'offset': offset
    }


@router.get("/status/{job_id}")
async def get_verification_status(
    job_id: int,
    db: Session = Depends(get_db)
):
    """
    Get status of a verification job.
    
    Returns:
        {
            "job_id": int,
            "status": "processing" | "completed" | "failed",
            "result": VerificationResult | null
        }
    """
    # job_id is site_id in our implementation
    site_id = job_id
    
    # Check if currently running
    if site_id in _running_verifications:
        return {
            'job_id': job_id,
            'status': 'processing',
            'result': None
        }
    
    # Check for completed result
    result = db.query(VerificationResult).filter(
        VerificationResult.site_id == site_id
    ).order_by(VerificationResult.created_at.desc()).first()
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No verification found for job {job_id}"
        )
    
    # Get site name
    site = db.query(MonitoringSite).filter(MonitoringSite.id == site_id).first()
    
    return {
        'job_id': job_id,
        'status': 'completed' if result.status == 'success' else 'failed',
        'result': {
            'id': result.id,
            'site_id': result.site_id,
            'site_name': site.name if site else 'Unknown',
            'html_data': result.html_data,
            'ocr_data': result.ocr_data,
            'discrepancies': result.discrepancies.get('items', []),
            'html_violations': result.html_violations.get('items', []),
            'ocr_violations': result.ocr_violations.get('items', []),
            'screenshot_path': result.screenshot_path,
            'ocr_confidence': result.ocr_confidence,
            'status': result.status,
            'error_message': result.error_message,
            'created_at': result.created_at
        }
    }
