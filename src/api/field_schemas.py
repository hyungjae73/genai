"""
API endpoints for field schema management.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from typing import List

from src.api.schemas import (
    FieldSchemaCreate,
    FieldSchemaUpdate,
    FieldSchemaResponse,
)
from src.auth.dependencies import get_current_user_or_api_key
from src.database import get_db
from src.models import FieldSchema

router = APIRouter()


@router.get("/category/{category_id}", response_model=List[FieldSchemaResponse])
async def get_field_schemas_by_category(
    category_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user_or_api_key),
):
    """Get all field schemas for a category, ordered by display_order."""
    schemas = (
        db.query(FieldSchema)
        .filter(FieldSchema.category_id == category_id)
        .order_by(FieldSchema.display_order)
        .all()
    )
    return schemas


@router.post("/", response_model=FieldSchemaResponse, status_code=status.HTTP_201_CREATED)
async def create_field_schema(
    field_schema: FieldSchemaCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user_or_api_key),
):
    """Create a new field schema. Returns 409 if field_name already exists within the same category."""
    existing = (
        db.query(FieldSchema)
        .filter(
            FieldSchema.category_id == field_schema.category_id,
            FieldSchema.field_name == field_schema.field_name,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="同一カテゴリ内に同名のフィールドが既に存在します",
        )

    db_field_schema = FieldSchema(
        category_id=field_schema.category_id,
        field_name=field_schema.field_name,
        field_type=field_schema.field_type,
        is_required=field_schema.is_required,
        validation_rules=field_schema.validation_rules,
        display_order=field_schema.display_order,
    )

    db.add(db_field_schema)
    db.commit()
    db.refresh(db_field_schema)

    return db_field_schema


@router.put("/{field_schema_id}", response_model=FieldSchemaResponse)
async def update_field_schema(
    field_schema_id: int,
    field_schema_update: FieldSchemaUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_or_api_key),
):
    """Update a field schema. Returns 404 if not found, 409 if name conflict within same category."""
    field_schema = (
        db.query(FieldSchema).filter(FieldSchema.id == field_schema_id).first()
    )

    if not field_schema:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="フィールドスキーマが見つかりません",
        )

    update_data = field_schema_update.model_dump(exclude_unset=True)

    # Check name uniqueness within the same category if name is being updated
    if "field_name" in update_data and update_data["field_name"] != field_schema.field_name:
        existing = (
            db.query(FieldSchema)
            .filter(
                FieldSchema.category_id == field_schema.category_id,
                FieldSchema.field_name == update_data["field_name"],
                FieldSchema.id != field_schema_id,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="同一カテゴリ内に同名のフィールドが既に存在します",
            )

    for field, value in update_data.items():
        setattr(field_schema, field, value)

    db.commit()
    db.refresh(field_schema)

    return field_schema


@router.delete("/{field_schema_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_field_schema(
    field_schema_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user_or_api_key),
):
    """Delete a field schema. Returns 404 if not found."""
    field_schema = (
        db.query(FieldSchema).filter(FieldSchema.id == field_schema_id).first()
    )

    if not field_schema:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="フィールドスキーマが見つかりません",
        )

    db.delete(field_schema)
    db.commit()

    return None
