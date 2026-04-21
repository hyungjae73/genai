"""
API endpoints for customer management.
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session

from src.api.schemas import (
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse
)
from src.auth.dependencies import get_current_user_or_api_key
from src.database import get_db
from src.models import Customer

router = APIRouter()


@router.post("/", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(customer: CustomerCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user_or_api_key)):
    """Create a new customer."""
    # Check if email already exists
    existing = db.query(Customer).filter(Customer.email == customer.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    db_customer = Customer(
        name=customer.name,
        company_name=customer.company_name,
        email=customer.email,
        phone=customer.phone,
        address=customer.address,
        is_active=customer.is_active if customer.is_active is not None else True
    )
    
    db.add(db_customer)
    db.commit()
    db.refresh(db_customer)
    
    return db_customer


@router.get("/", response_model=List[CustomerResponse])
async def get_customers(
    active_only: bool = False,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_or_api_key),
):
    """Get all customers."""
    query = db.query(Customer)
    
    if active_only:
        query = query.filter(Customer.is_active == True)
    
    customers = query.order_by(Customer.created_at.desc()).all()
    return customers


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(customer_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user_or_api_key)):
    """Get a specific customer."""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with id {customer_id} not found"
        )
    
    return customer


@router.put("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: int,
    customer_update: CustomerUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_or_api_key),
):
    """Update a customer."""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with id {customer_id} not found"
        )
    
    update_data = customer_update.model_dump(exclude_unset=True)
    
    # Check email uniqueness if email is being updated
    if 'email' in update_data and update_data['email'] != customer.email:
        existing = db.query(Customer).filter(
            Customer.email == update_data['email'],
            Customer.id != customer_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
    
    for field, value in update_data.items():
        setattr(customer, field, value)
    
    db.commit()
    db.refresh(customer)
    
    return customer


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(customer_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user_or_api_key)):
    """
    Delete a customer.
    
    Note: This is a soft delete. The customer is marked as inactive.
    """
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with id {customer_id} not found"
        )
    
    customer.is_active = False
    db.commit()
    
    return None
