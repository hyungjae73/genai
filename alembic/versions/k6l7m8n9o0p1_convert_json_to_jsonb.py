"""convert JSON columns to JSONB

Convert 4 JSON fields to JSONB now that tests run on PostgreSQL
via testcontainers instead of SQLite:
- monitoring_sites.pre_capture_script
- monitoring_sites.plugin_config
- verification_results.structured_data
- verification_results.structured_data_violations

Revision ID: k6l7m8n9o0p1
Revises: j5k6l7m8n9o0
Create Date: 2026-04-15 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'k6l7m8n9o0p1'
down_revision: Union[str, None] = 'j5k6l7m8n9o0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # MonitoringSite: JSON → JSONB
    op.alter_column('monitoring_sites', 'pre_capture_script',
                    type_=postgresql.JSONB, existing_type=sa.JSON)
    op.alter_column('monitoring_sites', 'plugin_config',
                    type_=postgresql.JSONB, existing_type=sa.JSON)

    # VerificationResult: JSON → JSONB
    op.alter_column('verification_results', 'structured_data',
                    type_=postgresql.JSONB, existing_type=sa.JSON)
    op.alter_column('verification_results', 'structured_data_violations',
                    type_=postgresql.JSONB, existing_type=sa.JSON)


def downgrade() -> None:
    # VerificationResult: JSONB → JSON
    op.alter_column('verification_results', 'structured_data_violations',
                    type_=sa.JSON, existing_type=postgresql.JSONB)
    op.alter_column('verification_results', 'structured_data',
                    type_=sa.JSON, existing_type=postgresql.JSONB)

    # MonitoringSite: JSONB → JSON
    op.alter_column('monitoring_sites', 'plugin_config',
                    type_=sa.JSON, existing_type=postgresql.JSONB)
    op.alter_column('monitoring_sites', 'pre_capture_script',
                    type_=sa.JSON, existing_type=postgresql.JSONB)
