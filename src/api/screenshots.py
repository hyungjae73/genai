"""
API endpoints for screenshot management.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from src.api.schemas import ScreenshotResponse
from src.auth.dependencies import get_current_user_or_api_key
from src.database import get_db
from src.models import CrawlResult, MonitoringSite
from src.screenshot_capture import capture_site_screenshot

router = APIRouter()

# Screenshot storage directory
SCREENSHOT_DIR = Path("screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)


@router.post("/upload", response_model=ScreenshotResponse, status_code=status.HTTP_201_CREATED)
async def upload_screenshot(
    site_id: int = Form(...),
    screenshot_type: str = Form(...),  # 'baseline' or 'violation'
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_or_api_key),
):
    """
    Upload a screenshot for a monitoring site.
    
    Args:
        site_id: Site ID
        screenshot_type: Type of screenshot ('baseline' or 'violation')
        file: Screenshot file (PNG or PDF)
    """
    # Validate site exists
    site = db.query(MonitoringSite).filter(MonitoringSite.id == site_id).first()
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site with id {site_id} not found"
        )
    
    # Validate screenshot type
    if screenshot_type not in ['baseline', 'violation']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="screenshot_type must be 'baseline' or 'violation'"
        )
    
    # Validate file format
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ['.png', '.pdf']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be PNG or PDF format"
        )
    
    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"site_{site_id}_{screenshot_type}_{timestamp}{file_ext}"
    file_path = SCREENSHOT_DIR / filename
    
    # Save file
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # Create crawl result record
    crawl_result = CrawlResult(
        site_id=site_id,
        url=site.url,
        html_content=f"Screenshot upload: {screenshot_type}",
        screenshot_path=str(file_path),
        status_code=200,
        crawled_at=datetime.now()
    )
    
    db.add(crawl_result)
    db.commit()
    db.refresh(crawl_result)
    
    return ScreenshotResponse(
        id=crawl_result.id,
        site_id=site_id,
        site_name=site.name,
        screenshot_type=screenshot_type,
        file_path=str(file_path),
        file_format=file_ext[1:],  # Remove the dot
        crawled_at=crawl_result.crawled_at
    )


@router.get("/site/{site_id}", response_model=List[ScreenshotResponse])
async def get_site_screenshots(
    site_id: int,
    screenshot_type: str = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_or_api_key),
):
    """
    Get all screenshots for a specific site.
    
    Args:
        site_id: Site ID
        screenshot_type: Optional filter by type ('baseline' or 'violation')
    """
    site = db.query(MonitoringSite).filter(MonitoringSite.id == site_id).first()
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site with id {site_id} not found"
        )
    
    query = db.query(CrawlResult).filter(
        CrawlResult.site_id == site_id,
        CrawlResult.screenshot_path.isnot(None)
    )
    
    crawl_results = query.order_by(CrawlResult.crawled_at.desc()).all()
    
    screenshots = []
    for result in crawl_results:
        # Determine screenshot type from filename
        if result.screenshot_path:
            if 'baseline' in result.screenshot_path:
                ss_type = 'baseline'
            elif 'violation' in result.screenshot_path:
                ss_type = 'violation'
            else:
                ss_type = 'unknown'
            
            # Filter by type if specified
            if screenshot_type and ss_type != screenshot_type:
                continue
            
            file_ext = Path(result.screenshot_path).suffix[1:]  # Remove dot
            
            screenshots.append(ScreenshotResponse(
                id=result.id,
                site_id=site_id,
                site_name=site.name,
                screenshot_type=ss_type,
                file_path=result.screenshot_path,
                file_format=file_ext,
                crawled_at=result.crawled_at
            ))
    
    return screenshots


@router.get("/view/{screenshot_id}")
async def view_screenshot(screenshot_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user_or_api_key)):
    """
    View a screenshot file.
    
    Args:
        screenshot_id: Screenshot (CrawlResult) ID
    """
    crawl_result = db.query(CrawlResult).filter(CrawlResult.id == screenshot_id).first()
    
    if not crawl_result or not crawl_result.screenshot_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Screenshot not found"
        )
    
    file_path = Path(crawl_result.screenshot_path)
    
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Screenshot file not found on disk"
        )
    
    # Determine media type
    file_ext = file_path.suffix.lower()
    media_type = "image/png" if file_ext == ".png" else "application/pdf"
    
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=file_path.name
    )


@router.delete("/{crawl_result_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_screenshot(crawl_result_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user_or_api_key)):
    """
    Delete a screenshot associated with a crawl result.

    Removes the screenshot file from disk and clears the screenshot_path
    on the crawl result record. The crawl result itself is preserved.

    Args:
        crawl_result_id: CrawlResult ID whose screenshot should be deleted.
    """
    crawl_result = db.query(CrawlResult).filter(CrawlResult.id == crawl_result_id).first()

    if not crawl_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="クロール結果が見つかりません",
        )

    if not crawl_result.screenshot_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="スクリーンショットが見つかりません",
        )

    # Delete file from disk
    file_path = Path(crawl_result.screenshot_path)
    if file_path.exists():
        file_path.unlink()

    # Clear screenshot path but keep the crawl result
    crawl_result.screenshot_path = None
    db.commit()

    return None



@router.post("/capture", response_model=ScreenshotResponse, status_code=status.HTTP_201_CREATED)
async def capture_screenshot(
    site_id: int,
    screenshot_type: str,  # 'baseline' or 'violation'
    file_format: str = "png",  # 'png' or 'pdf'
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_or_api_key),
):
    """
    Capture a screenshot by crawling the site URL.
    
    Args:
        site_id: Site ID
        screenshot_type: Type of screenshot ('baseline' or 'violation')
        file_format: File format ('png' or 'pdf')
    """
    # Validate site exists
    site = db.query(MonitoringSite).filter(MonitoringSite.id == site_id).first()
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site with id {site_id} not found"
        )
    
    # Validate screenshot type
    if screenshot_type not in ['baseline', 'violation']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="screenshot_type must be 'baseline' or 'violation'"
        )
    
    # Validate file format
    if file_format not in ['png', 'pdf']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file_format must be 'png' or 'pdf'"
        )
    
    try:
        # Capture screenshot
        file_path = await capture_site_screenshot(
            url=site.url,
            site_id=site_id,
            screenshot_type=screenshot_type,
            file_format=file_format
        )
        
        # Create crawl result record
        crawl_result = CrawlResult(
            site_id=site_id,
            url=site.url,
            html_content=f"Screenshot capture: {screenshot_type}",
            screenshot_path=str(file_path),
            status_code=200,
            crawled_at=datetime.now()
        )
        
        db.add(crawl_result)
        db.commit()
        db.refresh(crawl_result)
        
        return ScreenshotResponse(
            id=crawl_result.id,
            site_id=site_id,
            site_name=site.name,
            screenshot_type=screenshot_type,
            file_path=str(file_path),
            file_format=file_format,
            crawled_at=crawl_result.crawled_at
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to capture screenshot: {str(e)}"
        )
