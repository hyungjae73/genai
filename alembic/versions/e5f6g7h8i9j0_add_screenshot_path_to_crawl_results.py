"""add_screenshot_path_to_crawl_results

Revision ID: e5f6g7h8i9j0
Revises: d8a9b2c3e4f5
Create Date: 2026-03-13 13:51:36.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e5f6g7h8i9j0'
down_revision: Union[str, None] = 'd8a9b2c3e4f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add screenshot_path column to crawl_results table
    op.add_column('crawl_results', sa.Column('screenshot_path', sa.String(length=500), nullable=True))


def downgrade() -> None:
    # Remove screenshot_path column from crawl_results table
    op.drop_column('crawl_results', 'screenshot_path')
