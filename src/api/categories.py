"""
API endpoints for category management.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from typing import List

from src.api.schemas import (
    CategoryCreate,
    CategoryUpdate,
    CategoryResponse,
)
from src.auth.dependencies import get_current_user_or_api_key
from src.database import get_db
from src.models import Category, MonitoringSite, ContractCondition

router = APIRouter()


@router.get("/", response_model=List[CategoryResponse])
async def get_categories(db: Session = Depends(get_db), current_user = Depends(get_current_user_or_api_key)):
    """Get all categories ordered by name."""
    categories = db.query(Category).order_by(Category.name).all()
    return categories


@router.post("/", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(category: CategoryCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user_or_api_key)):
    """Create a new category. Returns 409 if name already exists."""
    existing = db.query(Category).filter(Category.name == category.name).first()
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
    db.commit()
    db.refresh(db_category)

    return db_category


@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: int,
    category_update: CategoryUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_or_api_key),
):
    """Update a category. Returns 404 if not found, 409 if name conflict."""
    category = db.query(Category).filter(Category.id == category_id).first()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="カテゴリが見つかりません",
        )

    update_data = category_update.model_dump(exclude_unset=True)

    # Check name uniqueness if name is being updated
    if "name" in update_data and update_data["name"] != category.name:
        existing = db.query(Category).filter(
            Category.name == update_data["name"],
            Category.id != category_id,
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="同名のカテゴリが既に存在します",
            )

    for field, value in update_data.items():
        setattr(category, field, value)

    db.commit()
    db.refresh(category)

    return category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(category_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user_or_api_key)):
    """
    Delete a category.

    Before deleting, sets category_id=NULL on all MonitoringSite and
    ContractCondition records that reference this category.
    Returns 404 if not found.
    """
    category = db.query(Category).filter(Category.id == category_id).first()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="カテゴリが見つかりません",
        )

    # Set category_id to NULL on related records
    db.query(MonitoringSite).filter(
        MonitoringSite.category_id == category_id
    ).update({"category_id": None})

    db.query(ContractCondition).filter(
        ContractCondition.category_id == category_id
    ).update({"category_id": None})

    db.delete(category)
    db.commit()

    return None
