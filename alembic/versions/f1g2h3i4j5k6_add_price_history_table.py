"""add_price_history_table

Revision ID: f1g2h3i4j5k6
Revises: e5f6g7h8i9j0
Create Date: 2026-03-13 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f1g2h3i4j5k6'
down_revision: Union[str, None] = 'e5f6g7h8i9j0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create price_history table
    op.create_table(
        'price_history',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('site_id', sa.Integer(), nullable=False),
        sa.Column('product_name', sa.String(length=500), nullable=False),
        sa.Column('sku', sa.String(length=200), nullable=True),
        sa.Column('price_amount', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(length=10), nullable=False),
        sa.Column('crawled_at', sa.DateTime(), nullable=False),
        sa.Column('price_change_amount', sa.Float(), nullable=True),
        sa.Column('price_change_percentage', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['site_id'], ['monitoring_sites.id'], name='fk_price_history_site_id'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for efficient querying
    op.create_index('ix_price_history_site_id', 'price_history', ['site_id'], unique=False)
    op.create_index('ix_price_history_product_name', 'price_history', ['product_name'], unique=False)
    op.create_index('ix_price_history_crawled_at', 'price_history', ['crawled_at'], unique=False)
    op.create_index('ix_price_history_site_product', 'price_history', ['site_id', 'product_name'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_price_history_site_product', table_name='price_history')
    op.drop_index('ix_price_history_crawled_at', table_name='price_history')
    op.drop_index('ix_price_history_product_name', table_name='price_history')
    op.drop_index('ix_price_history_site_id', table_name='price_history')
    
    # Drop table
    op.drop_table('price_history')
