"""
API endpoints for contract condition management.
"""

from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import (
    ContractConditionCreate,
    ContractConditionUpdate,
    ContractConditionResponse
)
from src.auth.dependencies import get_current_user_or_api_key
from src.database import get_async_db
from src.models import ContractCondition

router = APIRouter()


@router.post("/", response_model=ContractConditionResponse, status_code=status.HTTP_201_CREATED)
async def create_contract(contract: ContractConditionCreate, db: AsyncSession = Depends(get_async_db), current_user = Depends(get_current_user_or_api_key)):
    """
    Create a new contract condition.
    
    This creates a new version of contract conditions for a site.
    Previous versions are marked as not current.
    """
    # Mark existing contracts for this site as not current
    result = await db.execute(
        select(ContractCondition).where(
            ContractCondition.site_id == contract.site_id,
            ContractCondition.is_current == True
        )
    )
    existing_contracts = result.scalars().all()
    for c in existing_contracts:
        c.is_current = False
    
    # Determine version number
    count_result = await db.execute(
        select(func.count(ContractCondition.id)).where(
            ContractCondition.site_id == contract.site_id
        )
    )
    max_version = count_result.scalar()
    version = max_version + 1
    
    # Create new contract
    db_contract = ContractCondition(
        site_id=contract.site_id,
        prices=contract.prices,
        payment_methods=contract.payment_methods,
        fees=contract.fees,
        subscription_terms=contract.subscription_terms,
        version=version,
        is_current=True
    )
    
    db.add(db_contract)
    await db.commit()
    await db.refresh(db_contract)
    
    return db_contract


@router.get("/", response_model=List[ContractConditionResponse])
async def get_all_contracts(db: AsyncSession = Depends(get_async_db), current_user = Depends(get_current_user_or_api_key)):
    """Get all contract conditions."""
    result = await db.execute(select(ContractCondition))
    contracts = result.scalars().all()
    return contracts


@router.get("/{contract_id}", response_model=ContractConditionResponse)
async def get_contract(contract_id: int, db: AsyncSession = Depends(get_async_db), current_user = Depends(get_current_user_or_api_key)):
    """Get a specific contract condition."""
    result = await db.execute(
        select(ContractCondition).where(ContractCondition.id == contract_id)
    )
    contract = result.scalar_one_or_none()
    
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with id {contract_id} not found"
        )
    
    return contract


@router.get("/site/{site_id}", response_model=List[ContractConditionResponse])
async def get_site_contracts(site_id: int, current_only: bool = False, db: AsyncSession = Depends(get_async_db), current_user = Depends(get_current_user_or_api_key)):
    """
    Get all contract conditions for a site.
    
    Args:
        site_id: Site ID
        current_only: If True, return only current contract
    """
    stmt = select(ContractCondition).where(ContractCondition.site_id == site_id)
    
    if current_only:
        stmt = stmt.where(ContractCondition.is_current == True)
    
    stmt = stmt.order_by(ContractCondition.version.desc())
    result = await db.execute(stmt)
    contracts = result.scalars().all()
    return contracts


@router.put("/{contract_id}", response_model=ContractConditionResponse)
async def update_contract(contract_id: int, contract_update: ContractConditionUpdate, db: AsyncSession = Depends(get_async_db), current_user = Depends(get_current_user_or_api_key)):
    """
    Update a contract condition.
    
    Note: This updates the existing contract. To create a new version,
    use POST endpoint instead.
    """
    result = await db.execute(
        select(ContractCondition).where(ContractCondition.id == contract_id)
    )
    contract = result.scalar_one_or_none()
    
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with id {contract_id} not found"
        )
    
    update_data = contract_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(contract, field, value)
    
    await db.commit()
    await db.refresh(contract)
    
    return contract


@router.delete("/{contract_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contract(contract_id: int, db: AsyncSession = Depends(get_async_db), current_user = Depends(get_current_user_or_api_key)):
    """
    Delete a contract condition.
    
    Note: This is a soft delete. The contract is marked as not current
    but not removed from the database.
    """
    result = await db.execute(
        select(ContractCondition).where(ContractCondition.id == contract_id)
    )
    contract = result.scalar_one_or_none()
    
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with id {contract_id} not found"
        )
    
    contract.is_current = False
    await db.commit()
    
    return None
