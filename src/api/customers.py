"""
API endpoints for customer management.
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import (
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse
)
from src.auth.dependencies import get_current_user_or_api_key
from src.database import get_async_db
from src.models import Customer

router = APIRouter()


@router.post("/", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(customer: CustomerCreate, db: AsyncSession = Depends(get_async_db), current_user = Depends(get_current_user_or_api_key)):
    """Create a new customer."""
    # Check if email already exists
    result = await db.execute(select(Customer).where(Customer.email == customer.email))
    existing = result.scalar_one_or_none()
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
    await db.commit()
    await db.refresh(db_customer)
    
    return db_customer


@router.get("/", response_model=List[CustomerResponse])
async def get_customers(
    active_only: bool = False,
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user_or_api_key),
):
    """Get all customers."""
    if active_only:
        result = await db.execute(
            select(Customer).where(Customer.is_active == True).order_by(Customer.created_at.desc())
        )
    else:
        result = await db.execute(
            select(Customer).order_by(Customer.created_at.desc())
        )
    
    customers = result.scalars().all()
    return customers


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(customer_id: int, db: AsyncSession = Depends(get_async_db), current_user = Depends(get_current_user_or_api_key)):
    """Get a specific customer."""
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    
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
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user_or_api_key),
):
    """Update a customer."""
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with id {customer_id} not found"
        )
    
    update_data = customer_update.model_dump(exclude_unset=True)
    
    # Check email uniqueness if email is being updated
    if 'email' in update_data and update_data['email'] != customer.email:
        email_result = await db.execute(
            select(Customer).where(
                Customer.email == update_data['email'],
                Customer.id != customer_id
            )
        )
        existing = email_result.scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
    
    for field, value in update_data.items():
        setattr(customer, field, value)
    
    await db.commit()
    await db.refresh(customer)
    
    return customer


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(customer_id: int, db: AsyncSession = Depends(get_async_db), current_user = Depends(get_current_user_or_api_key)):
    """
    Delete a customer.
    
    Note: This is a soft delete. The customer is marked as inactive.
    """
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with id {customer_id} not found"
        )
    
    customer.is_active = False
    await db.commit()
    
    return None
