"""
API endpoints for verification system.
"""

import logging
from datetime import datetime
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_async_db
from src.auth.dependencies import get_current_user_or_api_key
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


async def _run_verification_task(site_id: int, db: AsyncSession):
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
            result = await verification_service.run_verification(site_id)

            # If verification failed without saving to DB, save the error result
            if result.status in ("failure", "partial_failure"):
                error_record = VerificationResult(
                    site_id=site_id,
                    html_data=result.html_payment_info or {},
                    ocr_data=result.ocr_payment_info or {},
                    html_violations={"items": []},
                    ocr_violations={"items": []},
                    discrepancies={"items": result.discrepancies or []},
                    screenshot_path=result.screenshot_path or "",
                    ocr_confidence=result.ocr_confidence or 0.0,
                    status=result.status,
                    error_message=result.error_message,
                    created_at=datetime.utcnow(),
                )
                db.add(error_record)
                await db.commit()

    except Exception as e:
        # Save error to DB so the status endpoint can report it
        try:
            error_record = VerificationResult(
                site_id=site_id,
                html_data={},
                ocr_data={},
                html_violations={"items": []},
                ocr_violations={"items": []},
                discrepancies={"items": []},
                screenshot_path="",
                ocr_confidence=0.0,
                status="failure",
                error_message=f"Verification failed: {str(e)}",
                created_at=datetime.utcnow(),
            )
            db.add(error_record)
            await db.commit()
        except Exception as e:
            logger.warning("Failed to write error verification result to DB: %s", e)
    finally:
        # Remove from running verifications
        if site_id in _running_verifications:
            del _running_verifications[site_id]


@router.post("/run", status_code=status.HTTP_202_ACCEPTED)
async def trigger_verification(
    request: VerificationTriggerRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user_or_api_key),
):
    """
    Trigger verification for a site.
    """
    site_id = request.site_id
    
    # Check if site exists
    result = await db.execute(select(MonitoringSite).where(MonitoringSite.id == site_id))
    site = result.scalar_one_or_none()
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
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user_or_api_key),
):
    """
    Get verification results for a site.
    """
    # Check if site exists
    result = await db.execute(select(MonitoringSite).where(MonitoringSite.id == site_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site with id {site_id} not found"
        )
    
    # Count total
    count_result = await db.execute(
        select(func.count(VerificationResult.id)).where(VerificationResult.site_id == site_id)
    )
    total = count_result.scalar() or 0
    
    # Query verification results
    result = await db.execute(
        select(VerificationResult)
        .where(VerificationResult.site_id == site_id)
        .order_by(VerificationResult.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    results = result.scalars().all()
    
    # Format results
    formatted_results = []
    for vr in results:
        formatted_results.append(_format_verification_result(vr, site.name))
    
    return {
        'results': formatted_results,
        'total': total,
        'limit': limit,
        'offset': offset
    }


@router.get("/status/{job_id}")
async def get_verification_status(
    job_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user_or_api_key),
):
    """
    Get status of a verification job.
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
    result = await db.execute(
        select(VerificationResult)
        .where(VerificationResult.site_id == site_id)
        .order_by(VerificationResult.created_at.desc())
        .limit(1)
    )
    vr = result.scalar_one_or_none()
    
    if not vr:
        return {
            'job_id': job_id,
            'status': 'processing',
            'result': None
        }
    
    # Get site name
    site_result = await db.execute(select(MonitoringSite).where(MonitoringSite.id == site_id))
    site = site_result.scalar_one_or_none()
    
    return {
        'job_id': job_id,
        'status': 'completed' if vr.status == 'success' else 'failed',
        'result': _format_verification_result(vr, site.name if site else 'Unknown'),
    }


def _format_verification_result(result: VerificationResult, site_name: str) -> dict:
    """Format a VerificationResult for API response.

    Handles NULL new pipeline fields gracefully so that legacy clients
    receive a structurally compatible response (Req 22.5, 22.6).
    """
    response = {
        'id': result.id,
        'site_id': result.site_id,
        'site_name': site_name,
        'html_data': result.html_data,
        'ocr_data': result.ocr_data,
        'discrepancies': result.discrepancies.get('items', []) if result.discrepancies else [],
        'html_violations': result.html_violations.get('items', []) if result.html_violations else [],
        'ocr_violations': result.ocr_violations.get('items', []) if result.ocr_violations else [],
        'screenshot_path': result.screenshot_path,
        'ocr_confidence': result.ocr_confidence,
        'status': result.status,
        'error_message': result.error_message,
        'created_at': result.created_at,
    }

    # Pipeline fields — safe defaults when NULL (backward compatibility)
    response['structured_data'] = result.structured_data if result.structured_data is not None else None
    response['structured_data_violations'] = result.structured_data_violations if result.structured_data_violations is not None else None
    response['data_source'] = result.data_source if result.data_source is not None else None
    response['structured_data_status'] = result.structured_data_status if result.structured_data_status is not None else None
    response['evidence_status'] = result.evidence_status if result.evidence_status is not None else None

    # Evidence records (verification-flow-restructure, 要件: 11.4)
    try:
        from src.models import EvidenceRecord
        evidence_records = []
        if hasattr(result, 'evidence_records'):
            for er in result.evidence_records:
                evidence_records.append({
                    'id': er.id,
                    'verification_result_id': er.verification_result_id,
                    'variant_name': er.variant_name,
                    'screenshot_path': er.screenshot_path,
                    'roi_image_path': er.roi_image_path,
                    'ocr_text': er.ocr_text,
                    'ocr_confidence': er.ocr_confidence,
                    'evidence_type': er.evidence_type,
                    'created_at': er.created_at,
                })
        response['evidence_records'] = evidence_records if evidence_records else None
    except Exception:
        response['evidence_records'] = None

    return response
