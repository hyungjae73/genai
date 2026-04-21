"""
API endpoints for manual crawl execution.
"""

import logging
from typing import List

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import (
    CrawlJobResponse,
    CrawlStatusResponse,
    CrawlResultResponse,
    ManualExtractionInput,
)
from src.database import get_async_db
from src.auth.dependencies import get_current_user_or_api_key
from src.models import MonitoringSite, CrawlResult, CrawlJob, ContractCondition, ExtractedPaymentInfo, AuditLog
from src.auth import verify_api_key
from src.sanitize import sanitize_dict, strip_html_tags
from src.celery_app import celery_app

router = APIRouter()

logger = logging.getLogger(__name__)


@router.post("/site/{site_id}", response_model=CrawlJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_crawl(site_id: int, db: AsyncSession = Depends(get_async_db), current_user = Depends(get_current_user_or_api_key)):
    """
    Start a crawl job for the specified site using Celery.

    Returns 404 if the site does not exist.
    Returns 409 if a crawl is already running for this site.
    """
    result = await db.execute(select(MonitoringSite).where(MonitoringSite.id == site_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="サイトが見つかりません",
        )

    # Check for already-running crawl on this site (in DB)
    result = await db.execute(
        select(CrawlJob).where(
            CrawlJob.site_id == site_id,
            CrawlJob.status.in_(["pending", "running"]),
        )
    )
    running_job = result.scalar_one_or_none()
    if running_job:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="クロールが実行中です",
        )

    # Get contract conditions for validation
    result = await db.execute(
        select(ContractCondition).where(
            ContractCondition.site_id == site_id,
            ContractCondition.is_current == True,
        )
    )
    contract = result.scalar_one_or_none()

    contract_conditions = {}
    if contract:
        contract_conditions = {
            'prices': contract.prices or {},
            'payment_methods': contract.payment_methods or [],
            'fees': contract.fees or {},
            'subscription_terms': contract.subscription_terms or {}
        }

    # Notification config
    notification_config = {
        'email_recipients': [],
        'slack_webhook_url': None,
        'slack_channel': None,
    }

    # Create CrawlJob record in DB
    crawl_job = CrawlJob(site_id=site_id, status="pending")
    db.add(crawl_job)
    await db.flush()

    # Start Celery task, passing crawl_job.id
    task = celery_app.send_task(
        'src.tasks.crawl_and_validate_site',
        args=[site_id, site.url, contract_conditions, notification_config],
        kwargs={'crawl_job_id': crawl_job.id},
    )

    # Store celery task id
    crawl_job.celery_task_id = task.id
    await db.commit()

    return CrawlJobResponse(job_id=str(crawl_job.id), status="pending")


@router.get("/status/{job_id}", response_model=CrawlStatusResponse)
async def get_crawl_status(job_id: str, db: AsyncSession = Depends(get_async_db), current_user = Depends(get_current_user_or_api_key)):
    """
    Get the status of a crawl job from DB.
    """
    result = await db.execute(select(CrawlJob).where(CrawlJob.id == int(job_id)))
    crawl_job = result.scalar_one_or_none()
    if not crawl_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ジョブが見つかりません",
        )

    result_data = None
    if crawl_job.status == "completed":
        result_data = crawl_job.result
    elif crawl_job.status == "failed":
        result_data = {"error": crawl_job.error_message}

    return CrawlStatusResponse(
        job_id=job_id,
        status=crawl_job.status,
        result=result_data,
    )


@router.get("/results/{site_id}", response_model=List[CrawlResultResponse])
async def get_crawl_results(site_id: int, db: AsyncSession = Depends(get_async_db), current_user = Depends(get_current_user_or_api_key)):
    """
    Get crawl result history for a site, ordered by crawled_at descending.
    """
    result = await db.execute(select(MonitoringSite).where(MonitoringSite.id == site_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="サイトが見つかりません",
        )

    result = await db.execute(
        select(CrawlResult)
        .where(CrawlResult.site_id == site_id)
        .order_by(desc(CrawlResult.crawled_at))
    )
    return result.scalars().all()


@router.get("/results/{site_id}/latest", response_model=CrawlResultResponse)
async def get_latest_crawl_result(site_id: int, db: AsyncSession = Depends(get_async_db), current_user = Depends(get_current_user_or_api_key)):
    """
    Get the most recent crawl result for a site.
    """
    result = await db.execute(select(MonitoringSite).where(MonitoringSite.id == site_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="サイトが見つかりません",
        )

    result = await db.execute(
        select(CrawlResult)
        .where(CrawlResult.site_id == site_id)
        .order_by(desc(CrawlResult.crawled_at))
        .limit(1)
    )
    cr = result.scalar_one_or_none()
    if not cr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="クロール結果が見つかりません",
        )

    return cr


@router.get("/extracted/{crawl_result_id}/compare")
async def get_extracted_data_comparison(crawl_result_id: int, db: AsyncSession = Depends(get_async_db), current_user = Depends(get_current_user_or_api_key)):
    """
    Get both HTML and OCR extracted data for a crawl result, for side-by-side comparison.
    """
    result = await db.execute(
        select(ExtractedPaymentInfo)
        .where(ExtractedPaymentInfo.crawl_result_id == crawl_result_id)
        .order_by(ExtractedPaymentInfo.extracted_at.desc())
    )
    records = result.scalars().all()

    html_record = next((r for r in records if r.source == "html"), None)
    ocr_record = next((r for r in records if r.source == "ocr"), None)

    def _to_dict(record):
        if not record:
            return None
        return {
            "id": record.id,
            "crawl_result_id": record.crawl_result_id,
            "site_id": record.site_id,
            "source": record.source,
            "product_info": record.product_info,
            "price_info": record.price_info,
            "payment_methods": record.payment_methods,
            "fees": record.fees,
            "metadata": record.extraction_metadata,
            "confidence_scores": record.confidence_scores,
            "overall_confidence_score": record.overall_confidence_score,
            "status": record.status,
            "language": record.language,
            "extracted_at": record.extracted_at,
        }

    return {
        "html_data": _to_dict(html_record),
        "ocr_data": _to_dict(ocr_record),
    }

def _determine_extraction_status(records: list) -> str:
    """
    Determine the extraction status based on extracted records.
    """
    if not records:
        return "no_data"

    def _has_product_name(r) -> bool:
        return bool(r.product_info and r.product_info.get("name"))

    def _has_price(r) -> bool:
        if not r.price_info:
            return False
        if isinstance(r.price_info, list):
            return len(r.price_info) > 0
        return bool(r.price_info)

    def _has_payment_methods(r) -> bool:
        if not r.payment_methods:
            return False
        if isinstance(r.payment_methods, list):
            return len(r.payment_methods) > 0
        return bool(r.payment_methods)

    def _has_fees(r) -> bool:
        if not r.fees:
            return False
        if isinstance(r.fees, list):
            return len(r.fees) > 0
        return bool(r.fees)

    any_data = False
    for r in records:
        has_name = _has_product_name(r)
        has_price = _has_price(r)
        has_methods = _has_payment_methods(r)
        has_fees = _has_fees(r)

        if has_name or has_price or has_methods or has_fees:
            any_data = True

        # "complete" requires at least product_name and price in one record
        if has_name and has_price:
            return "complete"

    if any_data:
        return "partial"

    return "no_data"


@router.get("/extracted/{crawl_result_id}/visual-confirmation")
async def get_visual_confirmation_data(crawl_result_id: int, db: AsyncSession = Depends(get_async_db), current_user = Depends(get_current_user_or_api_key)):
    """
    Get visual confirmation data for a crawl result.
    """
    result = await db.execute(select(CrawlResult).where(CrawlResult.id == crawl_result_id))
    crawl_result = result.scalar_one_or_none()
    if not crawl_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="クロール結果が見つかりません",
        )

    result = await db.execute(
        select(ExtractedPaymentInfo)
        .where(ExtractedPaymentInfo.crawl_result_id == crawl_result_id)
        .order_by(ExtractedPaymentInfo.extracted_at.desc())
    )
    records = result.scalars().all()

    html_record = next((r for r in records if r.source == "html"), None)
    ocr_record = next((r for r in records if r.source == "ocr"), None)

    def _to_dict(record):
        if not record:
            return None
        return {
            "id": record.id,
            "crawl_result_id": record.crawl_result_id,
            "site_id": record.site_id,
            "source": record.source,
            "product_info": record.product_info,
            "price_info": record.price_info,
            "payment_methods": record.payment_methods,
            "fees": record.fees,
            "metadata": record.extraction_metadata,
            "confidence_scores": record.confidence_scores,
            "overall_confidence_score": record.overall_confidence_score,
            "status": record.status,
            "language": record.language,
            "extracted_at": record.extracted_at,
        }

    screenshot_url = None
    if crawl_result.screenshot_path:
        screenshot_url = f"/api/screenshots/{crawl_result.screenshot_path}"

    return {
        "screenshot_url": screenshot_url,
        "raw_html": crawl_result.html_content,
        "extraction_status": _determine_extraction_status(records),
        "html_data": _to_dict(html_record),
        "ocr_data": _to_dict(ocr_record),
    }


@router.post("/extracted/{crawl_result_id}/manual-input")
async def save_manual_extraction(
    crawl_result_id: int,
    manual_data: ManualExtractionInput,
    db: AsyncSession = Depends(get_async_db),
    api_key: str = Depends(verify_api_key),
    current_user = Depends(get_current_user_or_api_key),
):
    """
    Save manually entered extraction data after visual confirmation.
    """
    result = await db.execute(select(CrawlResult).where(CrawlResult.id == crawl_result_id))
    crawl_result = result.scalar_one_or_none()
    if not crawl_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="クロール結果が見つかりません",
        )

    # Build JSONB structures from flat input
    product_info = {}
    if manual_data.product_name:
        product_info["name"] = strip_html_tags(manual_data.product_name)

    price_info = []
    if manual_data.price is not None:
        price_entry = {
            "amount": manual_data.price,
            "currency": strip_html_tags(manual_data.currency) if manual_data.currency else "JPY",
            "price_type": "base_price",
        }
        price_info.append(price_entry)

    payment_methods = []
    if manual_data.payment_methods:
        for method_name in manual_data.payment_methods:
            payment_methods.append({"method_name": strip_html_tags(method_name)})

    fees = []
    if manual_data.additional_fees:
        fees.append({
            "fee_type": "その他",
            "description": strip_html_tags(manual_data.additional_fees),
        })

    confidence_scores = {
        "product_name": 1.0,
        "price": 1.0,
        "currency": 1.0,
        "payment_methods": 1.0,
        "fees": 1.0,
    }

    record = ExtractedPaymentInfo(
        crawl_result_id=crawl_result_id,
        site_id=crawl_result.site_id,
        source="manual",
        product_info=product_info,
        price_info=price_info,
        payment_methods=payment_methods,
        fees=fees,
        extraction_metadata={"input_method": "manual_visual_confirmation"},
        confidence_scores=confidence_scores,
        overall_confidence_score=1.0,
        status="approved",
    )
    db.add(record)
    await db.flush()

    # Audit log
    audit_entry = AuditLog(
        user=api_key,
        action="manual_input",
        resource_type="extracted_payment_info",
        resource_id=record.id,
        details={
            "crawl_result_id": crawl_result_id,
            "source": "manual",
            "input_data": sanitize_dict(manual_data.model_dump(exclude_unset=True)),
        },
    )
    db.add(audit_entry)
    await db.commit()
    await db.refresh(record)

    logger.info(
        "Manual extraction saved: record_id=%d, crawl_result_id=%d, site_id=%d",
        record.id,
        crawl_result_id,
        crawl_result.site_id,
    )

    return {
        "id": record.id,
        "crawl_result_id": record.crawl_result_id,
        "site_id": record.site_id,
        "source": record.source,
        "product_info": record.product_info,
        "price_info": record.price_info,
        "payment_methods": record.payment_methods,
        "fees": record.fees,
        "metadata": record.extraction_metadata,
        "confidence_scores": record.confidence_scores,
        "overall_confidence_score": record.overall_confidence_score,
        "status": record.status,
        "language": record.language,
        "extracted_at": record.extracted_at,
    }
