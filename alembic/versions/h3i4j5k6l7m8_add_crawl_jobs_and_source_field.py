"""add crawl_jobs table and source field to extracted_payment_info

Revision ID: h3i4j5k6l7m8
Revises: g2h3i4j5k6l7
Create Date: 2026-03-20 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'h3i4j5k6l7m8'
down_revision = 'g2h3i4j5k6l7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create crawl_jobs table
    op.create_table(
        'crawl_jobs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('site_id', sa.Integer(), nullable=False),
        sa.Column('celery_task_id', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['site_id'], ['monitoring_sites.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_crawl_jobs_site_id', 'crawl_jobs', ['site_id'])
    op.create_index('ix_crawl_jobs_status', 'crawl_jobs', ['status'])
    op.create_index('ix_crawl_jobs_celery_task_id', 'crawl_jobs', ['celery_task_id'])

    # Add source column to extracted_payment_info
    op.add_column(
        'extracted_payment_info',
        sa.Column('source', sa.String(length=10), nullable=False, server_default='html'),
    )


def downgrade() -> None:
    op.drop_column('extracted_payment_info', 'source')
    op.drop_index('ix_crawl_jobs_celery_task_id', table_name='crawl_jobs')
    op.drop_index('ix_crawl_jobs_status', table_name='crawl_jobs')
    op.drop_index('ix_crawl_jobs_site_id', table_name='crawl_jobs')
    op.drop_table('crawl_jobs')
