"""add_extracted_payment_info_table

Revision ID: d8a9b2c3e4f5
Revises: c7f1f5cab04d
Create Date: 2026-03-11 00:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd8a9b2c3e4f5'
down_revision: Union[str, None] = 'c7f1f5cab04d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create extracted_payment_info table
    op.create_table(
        'extracted_payment_info',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('crawl_result_id', sa.Integer(), nullable=False),
        sa.Column('site_id', sa.Integer(), nullable=False),
        sa.Column('extracted_at', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('language', sa.String(length=10), nullable=True),
        sa.Column('overall_confidence_score', sa.Float(), nullable=True),
        sa.Column('product_info', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('price_info', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('payment_methods', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('fees', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('confidence_scores', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['crawl_result_id'], ['crawl_results.id'], name='fk_extracted_payment_info_crawl_result_id'),
        sa.ForeignKeyConstraint(['site_id'], ['monitoring_sites.id'], name='fk_extracted_payment_info_site_id'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for efficient querying
    op.create_index('ix_extracted_payment_info_site_id', 'extracted_payment_info', ['site_id'], unique=False)
    op.create_index('ix_extracted_payment_info_crawl_result_id', 'extracted_payment_info', ['crawl_result_id'], unique=False)
    op.create_index('ix_extracted_payment_info_extracted_at', 'extracted_payment_info', ['extracted_at'], unique=False)
    op.create_index('ix_extracted_payment_info_status', 'extracted_payment_info', ['status'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_extracted_payment_info_status', table_name='extracted_payment_info')
    op.drop_index('ix_extracted_payment_info_extracted_at', table_name='extracted_payment_info')
    op.drop_index('ix_extracted_payment_info_crawl_result_id', table_name='extracted_payment_info')
    op.drop_index('ix_extracted_payment_info_site_id', table_name='extracted_payment_info')
    
    # Drop table
    op.drop_table('extracted_payment_info')
