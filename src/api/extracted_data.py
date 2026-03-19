"""
API endpoints for extracted payment information.

Provides CRUD operations for extracted payment data
associated with crawl results.
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from src.api.schemas import (
    ExtractedPaymentInfoResponse,
    ExtractedPaymentInfoUpdate,
    PaginatedExtractedPaymentInfoResponse,
)
from src.auth import verify_api_key
from src.database import get_db
from src.models import ExtractedPaymentInfo, AuditLog
from src.sanitize import sanitize_dict, strip_html_tags

router = APIRouter()


@router.get(
    "/{crawl_result_id}",
    response_model=ExtractedPaymentInfoResponse,
)
async def get_extracted_data_by_crawl_result(
    crawl_result_id: int,
    db: Session = Depends(get_db),
):
    """
    Get extracted payment info for a specific crawl result.

    Returns the most recent extraction record linked to the given
    crawl_result_id.
    """
    record = (
        db.query(ExtractedPaymentInfo)
        .filter(ExtractedPaymentInfo.crawl_result_id == crawl_result_id)
        .order_by(ExtractedPaymentInfo.extracted_at.desc())
        .first()
    )

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="抽出データが見つかりません",
        )

    return _to_response(record)


@router.get(
    "/site/{site_id}",
    response_model=PaginatedExtractedPaymentInfoResponse,
)
async def get_extracted_data_by_site(
    site_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Get all extracted payment info for a site with pagination.

    Default page size is 50 records.
    """
    base_query = db.query(ExtractedPaymentInfo).filter(
        ExtractedPaymentInfo.site_id == site_id,
    )

    total = base_query.count()

    records = (
        base_query
        .order_by(ExtractedPaymentInfo.extracted_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return PaginatedExtractedPaymentInfoResponse(
        items=[_to_response(r) for r in records],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.put(
    "/{id}",
    response_model=ExtractedPaymentInfoResponse,
)
async def update_extracted_data(
    id: int,
    updates: ExtractedPaymentInfoUpdate,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    """
    Update extracted payment info fields (manual correction).

    Requires a valid X-API-Key header. Records changes in audit_logs.
    """
    record = (
        db.query(ExtractedPaymentInfo)
        .filter(ExtractedPaymentInfo.id == id)
        .first()
    )

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="抽出データが見つかりません",
        )

    update_data = updates.model_dump(exclude_unset=True)

    # Sanitize string values in nested dicts/lists to prevent XSS
    update_data = sanitize_dict(update_data)

    # Capture old values for audit log
    old_values = {}
    for field in update_data:
        old_values[field] = getattr(record, field, None)

    for field, value in update_data.items():
        setattr(record, field, value)

    # Write audit log
    audit_entry = AuditLog(
        user=api_key,
        action="update",
        resource_type="extracted_payment_info",
        resource_id=record.id,
        details={
            "old_values": _serialize_for_json(old_values),
            "new_values": _serialize_for_json(update_data),
        },
    )
    db.add(audit_entry)

    db.commit()
    db.refresh(record)

    return _to_response(record)


def _serialize_for_json(obj: object) -> object:
    """Make an object JSON-serialisable for audit log details."""
    from datetime import datetime as _dt

    if isinstance(obj, dict):
        return {k: _serialize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize_for_json(v) for v in obj]
    if isinstance(obj, _dt):
        return obj.isoformat()
    try:
        # Catch non-serialisable types gracefully
        import json as _json
        _json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return str(obj)


def _to_response(record: ExtractedPaymentInfo) -> ExtractedPaymentInfoResponse:
    """Convert an ExtractedPaymentInfo model to its response schema."""
    return ExtractedPaymentInfoResponse(
        id=record.id,
        crawl_result_id=record.crawl_result_id,
        site_id=record.site_id,
        product_info=record.product_info,
        price_info=record.price_info,
        payment_methods=record.payment_methods,
        fees=record.fees,
        metadata=record.extraction_metadata,
        confidence_scores=record.confidence_scores,
        overall_confidence_score=record.overall_confidence_score,
        status=record.status,
        language=record.language,
        extracted_at=record.extracted_at,
    )


# ------------------------------------------------------------------
# Approve / Reject endpoints (require auth)
# ------------------------------------------------------------------

from pydantic import BaseModel, Field as PydanticField


class RejectRequest(BaseModel):
    """Request body for rejecting extracted data."""
    reason: str = PydanticField(..., min_length=1, max_length=1000)


@router.post("/{id}/approve")
async def approve_extracted_data(
    id: int,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    """
    Approve extracted payment info.

    Requires a valid X-API-Key header.
    """
    record = (
        db.query(ExtractedPaymentInfo)
        .filter(ExtractedPaymentInfo.id == id)
        .first()
    )
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="抽出データが見つかりません",
        )

    old_status = record.status
    record.status = "approved"

    audit_entry = AuditLog(
        user=api_key,
        action="approve",
        resource_type="extracted_payment_info",
        resource_id=record.id,
        details={"old_status": old_status, "new_status": "approved"},
    )
    db.add(audit_entry)
    db.commit()

    return {"status": "approved"}


@router.post("/{id}/reject")
async def reject_extracted_data(
    id: int,
    body: RejectRequest,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    """
    Reject extracted payment info with a reason.

    Requires a valid X-API-Key header.
    """
    record = (
        db.query(ExtractedPaymentInfo)
        .filter(ExtractedPaymentInfo.id == id)
        .first()
    )
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="抽出データが見つかりません",
        )

    old_status = record.status
    record.status = "rejected"

    sanitized_reason = strip_html_tags(body.reason)

    audit_entry = AuditLog(
        user=api_key,
        action="reject",
        resource_type="extracted_payment_info",
        resource_id=record.id,
        details={
            "old_status": old_status,
            "new_status": "rejected",
            "reason": sanitized_reason,
        },
    )
    db.add(audit_entry)
    db.commit()

    return {"status": "rejected"}


# ------------------------------------------------------------------
# Price history endpoints
# ------------------------------------------------------------------

from datetime import datetime
from src.api.schemas import PriceHistoryResponse, PriceHistoryListResponse
from src.models import PriceHistory

price_history_router = APIRouter()


@price_history_router.get(
    "/{site_id}/{product_id}",
    response_model=PriceHistoryListResponse,
)
async def get_price_history(
    site_id: int,
    product_id: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
):
    """
    Get price history for a specific product on a site.

    Supports optional date range filtering via start_date / end_date
    query parameters.
    """
    query = db.query(PriceHistory).filter(
        PriceHistory.site_id == site_id,
        PriceHistory.product_identifier == product_id,
    )

    if start_date:
        query = query.filter(PriceHistory.recorded_at >= start_date)
    if end_date:
        query = query.filter(PriceHistory.recorded_at <= end_date)

    records = query.order_by(PriceHistory.recorded_at.asc()).all()

    return PriceHistoryListResponse(
        items=[
            PriceHistoryResponse.model_validate(r)
            for r in records
        ],
        total=len(records),
    )
