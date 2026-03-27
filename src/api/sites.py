"""
API endpoints for monitoring site management.
"""

import json

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from typing import List

from src.api.schemas import (
    MonitoringSiteCreate,
    MonitoringSiteUpdate,
    MonitoringSiteResponse
)
from src.database import get_db
from src.models import MonitoringSite

router = APIRouter()


@router.post("/", response_model=MonitoringSiteResponse, status_code=status.HTTP_201_CREATED)
async def create_site(site: MonitoringSiteCreate, db: Session = Depends(get_db)):
    """Create a new monitoring site."""
    db_site = MonitoringSite(
        customer_id=site.customer_id,
        name=site.name,
        url=site.url,
        is_active=site.monitoring_enabled if hasattr(site, 'monitoring_enabled') else True
    )
    
    db.add(db_site)
    db.commit()
    db.refresh(db_site)
    
    return db_site


@router.get("/", response_model=List[MonitoringSiteResponse])
async def list_sites(db: Session = Depends(get_db)):
    """Get list of all monitoring sites."""
    sites = db.query(MonitoringSite).all()
    return sites


@router.get("/{site_id}", response_model=MonitoringSiteResponse)
async def get_site(site_id: int, db: Session = Depends(get_db)):
    """Get a specific monitoring site."""
    site = db.query(MonitoringSite).filter(MonitoringSite.id == site_id).first()
    
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site with id {site_id} not found"
        )
    
    return site


@router.put("/{site_id}", response_model=MonitoringSiteResponse)
async def update_site(site_id: int, site_update: MonitoringSiteUpdate, db: Session = Depends(get_db)):
    """Update a monitoring site."""
    site = db.query(MonitoringSite).filter(MonitoringSite.id == site_id).first()
    
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site with id {site_id} not found"
        )
    
    update_data = site_update.model_dump(exclude_unset=True)
    
    # Handle monitoring_enabled field mapping
    if 'monitoring_enabled' in update_data:
        site.is_active = update_data.pop('monitoring_enabled')

    # Validate pre_capture_script JSON (Req 26.5)
    if 'pre_capture_script' in update_data:
        pcs = update_data['pre_capture_script']
        if pcs is not None:
            if isinstance(pcs, str):
                try:
                    pcs = json.loads(pcs)
                    update_data['pre_capture_script'] = pcs
                except (json.JSONDecodeError, TypeError):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="pre_capture_script must be valid JSON",
                    )
            if not isinstance(pcs, list):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="pre_capture_script must be a JSON array of action objects",
                )

    # Validate crawl_priority
    if 'crawl_priority' in update_data:
        cp = update_data['crawl_priority']
        if cp is not None and cp not in ('high', 'normal', 'low'):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="crawl_priority must be 'high', 'normal', or 'low'",
            )

    # Validate plugin_config JSON
    if 'plugin_config' in update_data:
        pc = update_data['plugin_config']
        if pc is not None:
            if isinstance(pc, str):
                try:
                    pc = json.loads(pc)
                    update_data['plugin_config'] = pc
                except (json.JSONDecodeError, TypeError):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="plugin_config must be valid JSON",
                    )
            if not isinstance(pc, dict):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="plugin_config must be a JSON object",
                )

    for field, value in update_data.items():
        setattr(site, field, value)
    
    db.commit()
    db.refresh(site)
    
    return site


@router.delete("/{site_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_site(site_id: int, db: Session = Depends(get_db)):
    """Delete a monitoring site."""
    site = db.query(MonitoringSite).filter(MonitoringSite.id == site_id).first()
    
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site with id {site_id} not found"
        )
    
    db.delete(site)
    db.commit()
    return None
