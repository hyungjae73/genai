"""
API endpoints for data extraction from screenshots.
"""

import re
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import (
    ExtractedDataResponse,
    ExtractedDataUpdate,
    FieldSuggestionResponse,
)
from src.auth.dependencies import get_current_user_or_api_key
from src.database import get_async_db
from src.models import ExtractedData, CrawlResult
from src.ocr_engine import OCREngine

router = APIRouter()


def _infer_field_type(value: str) -> str:
    """Infer the field type from a string value."""
    if not isinstance(value, str):
        value = str(value)

    stripped = value.strip()

    # Boolean
    if stripped.lower() in ("true", "false", "yes", "no", "はい", "いいえ"):
        return "boolean"

    # Currency (e.g. ¥1,000  $9.99  €12.50  1,000円)
    if re.match(r'^[¥$€£][\d,]+\.?\d*$', stripped) or re.match(r'^[\d,]+\.?\d*\s*[円ドルユーロ]$', stripped):
        return "currency"

    # Percentage (e.g. 10%, 3.5％)
    if re.match(r'^[\d.]+\s*[%％]$', stripped):
        return "percentage"

    # Date (e.g. 2024-01-01, 2024/01/01)
    if re.match(r'^\d{4}[-/]\d{1,2}[-/]\d{1,2}$', stripped):
        return "date"

    # Number (integer or decimal, with optional commas)
    if re.match(r'^[\d,]+\.?\d*$', stripped):
        return "number"

    return "text"


@router.post("/extract/{screenshot_id}", response_model=ExtractedDataResponse, status_code=status.HTTP_201_CREATED)
async def extract_data(screenshot_id: int, db: AsyncSession = Depends(get_async_db), current_user = Depends(get_current_user_or_api_key)):
    """
    Run OCR extraction on a screenshot.

    Creates an ExtractedData record with the extracted fields and confidence scores.
    Returns 409 if extraction already exists for this screenshot.
    Returns 404 if the screenshot is not found.
    """
    # Check if extraction already exists
    result = await db.execute(
        select(ExtractedData).where(ExtractedData.screenshot_id == screenshot_id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="データ抽出が既に存在します",
        )

    # Verify screenshot exists
    result = await db.execute(
        select(CrawlResult).where(CrawlResult.id == screenshot_id)
    )
    crawl_result = result.scalar_one_or_none()
    if not crawl_result or not crawl_result.screenshot_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="スクリーンショットが見つかりません",
        )

    # Run OCR extraction
    ocr_engine = OCREngine()
    image_path = Path(crawl_result.screenshot_path)
    ocr_result = ocr_engine.extract_text(image_path)

    if not ocr_result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"データ抽出に失敗しました: {ocr_result.error_message}",
        )

    # Build extracted fields and confidence scores from OCR regions
    extracted_fields: dict = {}
    confidence_scores: dict = {}

    for i, region in enumerate(ocr_result.regions):
        field_key = f"field_{i}"
        extracted_fields[field_key] = region.text
        confidence_scores[field_key] = region.confidence

    # Also store the full text
    extracted_fields["full_text"] = ocr_result.full_text
    confidence_scores["full_text"] = ocr_result.average_confidence

    extracted_data = ExtractedData(
        screenshot_id=screenshot_id,
        site_id=crawl_result.site_id,
        extracted_fields=extracted_fields,
        confidence_scores=confidence_scores,
        status="pending",
    )

    db.add(extracted_data)
    await db.commit()
    await db.refresh(extracted_data)

    return extracted_data


@router.get("/results/{screenshot_id}", response_model=ExtractedDataResponse)
async def get_extraction_results(screenshot_id: int, db: AsyncSession = Depends(get_async_db), current_user = Depends(get_current_user_or_api_key)):
    """
    Get extracted data for a screenshot.

    Returns 404 if no extraction results found.
    """
    result = await db.execute(
        select(ExtractedData).where(ExtractedData.screenshot_id == screenshot_id)
    )
    extracted = result.scalar_one_or_none()
    if not extracted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="抽出結果が見つかりません",
        )

    return extracted


@router.put("/results/{extracted_data_id}", response_model=ExtractedDataResponse)
async def update_extraction_results(
    extracted_data_id: int,
    update: ExtractedDataUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user_or_api_key),
):
    """
    Update extracted data (user corrections).

    Returns 404 if not found.
    """
    result = await db.execute(
        select(ExtractedData).where(ExtractedData.id == extracted_data_id)
    )
    extracted = result.scalar_one_or_none()
    if not extracted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="抽出結果が見つかりません",
        )

    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(extracted, field, value)

    await db.commit()
    await db.refresh(extracted)

    return extracted


@router.post(
    "/suggest-fields/{screenshot_id}",
    response_model=List[FieldSuggestionResponse],
)
async def suggest_fields(screenshot_id: int, db: AsyncSession = Depends(get_async_db), current_user = Depends(get_current_user_or_api_key)):
    """
    Analyze extracted data and suggest field schemas.

    Returns field suggestions based on the extracted_fields data types.
    Returns 404 if no extraction results found for this screenshot.
    """
    result = await db.execute(
        select(ExtractedData).where(ExtractedData.screenshot_id == screenshot_id)
    )
    extracted = result.scalar_one_or_none()
    if not extracted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="抽出結果が見つかりません",
        )

    suggestions: list[FieldSuggestionResponse] = []
    fields = extracted.extracted_fields or {}
    confidence_scores = extracted.confidence_scores or {}

    for field_name, value in fields.items():
        # Skip the full_text meta-field
        if field_name == "full_text":
            continue

        inferred_type = _infer_field_type(str(value))
        confidence = confidence_scores.get(field_name, 0.0)

        suggestions.append(
            FieldSuggestionResponse(
                field_name=field_name,
                field_type=inferred_type,
                sample_value=value,
                confidence=confidence,
            )
        )

    return suggestions
