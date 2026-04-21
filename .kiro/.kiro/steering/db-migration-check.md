---
inclusion: auto
---

# Database Migration & Spec Dependencies Steering

## Purpose
This steering file ensures that database migrations are never skipped and spec dependencies are tracked across all task executions.

When `models.py` is modified (columns added, removed, or changed), you MUST:

1. Check if the change requires a database migration by comparing the model definition with the current DB schema
2. Create an Alembic migration file in `genai/alembic/versions/` with:
   - A descriptive revision ID and message
   - `down_revision` pointing to the latest existing migration
   - `upgrade()` and `downgrade()` functions
3. Run `alembic upgrade head` in `genai/` to apply the migration
4. Verify the migration was applied by checking the table schema

## Migration File Template

```python
"""description of change

Revision ID: {new_id}
Revises: {previous_head}
Create Date: {date}
"""
from alembic import op
import sqlalchemy as sa

revision = '{new_id}'
down_revision = '{previous_head}'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Add migration operations here
    pass

def downgrade() -> None:
    # Add reverse operations here
    pass
```

## Current Migration Chain

Check the latest migration by reading files in `genai/alembic/versions/` and finding the one with no other migration pointing to it as `down_revision`.

## NEVER skip migration creation when models.py changes affect the database schema.


## Spec Dependencies Tracking

After completing any task that modifies backend code (models, API endpoints, schemas), update the spec dependencies map at `.kiro/specs/spec-dependencies.md`:
- Add new DB changes to the Spec Registry table
- Update the Migration Chain if a new migration was created
- Update the Dependency Graph if new cross-spec dependencies were introduced

Reference: #[[file:.kiro/specs/spec-dependencies.md]]

## Post-Task Checklist (for EVERY task)

Before marking a task as complete, verify:

1. **If `models.py` was modified**: Was an Alembic migration created and applied? Check `genai/alembic/versions/` for the new file and run `alembic upgrade head`.
2. **If `schemas.py` was modified**: Do the schema fields match the model fields? Missing fields cause 500 errors.
3. **If API endpoints were added/changed**: Are the routes registered in `main.py`?
4. **If frontend types were changed**: Do the TypeScript interfaces match the backend schemas?
5. **Update spec-dependencies.md** if any DB or API changes were made.
