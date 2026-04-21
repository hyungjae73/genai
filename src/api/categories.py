"""
API endpoints for category management.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from src.api.schemas import (
    CategoryCreate,
    CategoryUpdate,
    CategoryResponse,
)
from src.auth.dependencies import get_current_user_or_api_key
from src.database import get_async_db
from src.models import Category, MonitoringSite, ContractCondition

router = APIRouter()


@router.get("/", response_model=List[CategoryResponse])
async def get_categories(db: AsyncSession = Depends(get_async_db), current_user = Depends(get_current_user_or_api_key)):
    """Get all categories ordered by name."""
    result = await db.execute(select(Category).order_by(Category.name))
    return result.scalars().all()


@router.post("/", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(category: CategoryCreate, db: AsyncSession = Depends(get_async_db), current_user = Depends(get_current_user_or_api_key)):
    """Create a new category. Returns 409 if name already exists."""
    result = await db.execute(select(Category).where(Category.name == category.name))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="同名のカテゴリが既に存在します",
        )

    db_category = Category(
        name=category.name,
        description=category.description,
        color=category.color,
    )

    db.add(db_category)
    await db.commit()
    await db.refresh(db_category)

    return db_category


@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: int,
    category_update: CategoryUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user_or_api_key),
):
    """Update a category. Returns 404 if not found, 409 if name conflict."""
    result = await db.execute(select(Category).where(Category.id == category_id))
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="カテゴリが見つかりません",
        )

    update_data = category_update.model_dump(exclude_unset=True)

    # Check name uniqueness if name is being updated
    if "name" in update_data and update_data["name"] != category.name:
        result = await db.execute(
            select(Category).where(
                Category.name == update_data["name"],
                Category.id != category_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="同名のカテゴリが既に存在します",
            )

    for field, value in update_data.items():
        setattr(category, field, value)

    await db.commit()
    await db.refresh(category)

    return category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(category_id: int, db: AsyncSession = Depends(get_async_db), current_user = Depends(get_current_user_or_api_key)):
    """
    Delete a category.

    Before deleting, sets category_id=NULL on all MonitoringSite and
    ContractCondition records that reference this category.
    Returns 404 if not found.
    """
    result = await db.execute(select(Category).where(Category.id == category_id))
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="カテゴリが見つかりません",
        )

    # Set category_id to NULL on related records
    from sqlalchemy import update
    await db.execute(
        update(MonitoringSite)
        .where(MonitoringSite.category_id == category_id)
        .values(category_id=None)
    )
    await db.execute(
        update(ContractCondition)
        .where(ContractCondition.category_id == category_id)
        .values(category_id=None)
    )

    await db.delete(category)
    await db.commit()

    return None
