"""add_price_change_columns_to_alerts

Revision ID: g2h3i4j5k6l7
Revises: f1g2h3i4j5k6
Create Date: 2026-03-13 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'g2h3i4j5k6l7'
down_revision: Union[str, None] = 'f1g2h3i4j5k6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add price change related columns to alerts table
    op.add_column('alerts', sa.Column('old_price', sa.Float(), nullable=True))
    op.add_column('alerts', sa.Column('new_price', sa.Float(), nullable=True))
    op.add_column('alerts', sa.Column('change_percentage', sa.Float(), nullable=True))


def downgrade() -> None:
    # Remove price change related columns from alerts table
    op.drop_column('alerts', 'change_percentage')
    op.drop_column('alerts', 'new_price')
    op.drop_column('alerts', 'old_price')
