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
    # screenshot_path already added in fdc38e236687 — no-op
    pass


def downgrade() -> None:
    # no-op (column managed by fdc38e236687)
    pass
