"""
API endpoints for contract condition management.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from src.api.schemas import (
    ContractConditionCreate,
    ContractConditionUpdate,
    ContractConditionResponse
)
from src.database import get_db
from src.models import ContractCondition

router = APIRouter()


@router.post("/", response_model=ContractConditionResponse, status_code=status.HTTP_201_CREATED)
async def create_contract(contract: ContractConditionCreate, db: Session = Depends(get_db)):
    """
    Create a new contract condition.
    
    This creates a new version of contract conditions for a site.
    Previous versions are marked as not current.
    """
    # Mark existing contracts for this site as not current
    db.query(ContractCondition).filter(
        ContractCondition.site_id == contract.site_id,
        ContractCondition.is_current == True
    ).update({"is_current": False})
    
    # Determine version number
    max_version = db.query(ContractCondition).filter(
        ContractCondition.site_id == contract.site_id
    ).count()
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
    db.commit()
    db.refresh(db_contract)
    
    return db_contract


@router.get("/", response_model=List[ContractConditionResponse])
async def get_all_contracts(db: Session = Depends(get_db)):
    """Get all contract conditions."""
    contracts = db.query(ContractCondition).all()
    return contracts


@router.get("/{contract_id}", response_model=ContractConditionResponse)
async def get_contract(contract_id: int, db: Session = Depends(get_db)):
    """Get a specific contract condition."""
    contract = db.query(ContractCondition).filter(ContractCondition.id == contract_id).first()
    
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with id {contract_id} not found"
        )
    
    return contract


@router.get("/site/{site_id}", response_model=List[ContractConditionResponse])
async def get_site_contracts(site_id: int, current_only: bool = False, db: Session = Depends(get_db)):
    """
    Get all contract conditions for a site.
    
    Args:
        site_id: Site ID
        current_only: If True, return only current contract
    """
    query = db.query(ContractCondition).filter(ContractCondition.site_id == site_id)
    
    if current_only:
        query = query.filter(ContractCondition.is_current == True)
    
    contracts = query.order_by(ContractCondition.version.desc()).all()
    return contracts


@router.put("/{contract_id}", response_model=ContractConditionResponse)
async def update_contract(contract_id: int, contract_update: ContractConditionUpdate, db: Session = Depends(get_db)):
    """
    Update a contract condition.
    
    Note: This updates the existing contract. To create a new version,
    use POST endpoint instead.
    """
    contract = db.query(ContractCondition).filter(ContractCondition.id == contract_id).first()
    
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with id {contract_id} not found"
        )
    
    update_data = contract_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(contract, field, value)
    
    db.commit()
    db.refresh(contract)
    
    return contract


@router.delete("/{contract_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contract(contract_id: int, db: Session = Depends(get_db)):
    """
    Delete a contract condition.
    
    Note: This is a soft delete. The contract is marked as not current
    but not removed from the database.
    """
    contract = db.query(ContractCondition).filter(ContractCondition.id == contract_id).first()
    
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with id {contract_id} not found"
        )
    
    contract.is_current = False
    db.commit()
    
    return None
