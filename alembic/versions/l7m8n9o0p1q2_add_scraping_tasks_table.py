"""add scraping_tasks table

Revision ID: l7m8n9o0p1q2
Revises: k6l7m8n9o0p1
Create Date: 2026-03-27 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'l7m8n9o0p1q2'
down_revision: Union[str, None] = 'k6l7m8n9o0p1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'scraping_tasks',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('target_url', sa.Text, nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='PENDING'),
        sa.Column('result_minio_key', sa.String(1024), nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_scraping_tasks_status', 'scraping_tasks', ['status'])
    op.create_index('ix_scraping_tasks_target_url_status', 'scraping_tasks', ['target_url', 'status'])


def downgrade() -> None:
    op.drop_index('ix_scraping_tasks_target_url_status', table_name='scraping_tasks')
    op.drop_index('ix_scraping_tasks_status', table_name='scraping_tasks')
    op.drop_table('scraping_tasks')
