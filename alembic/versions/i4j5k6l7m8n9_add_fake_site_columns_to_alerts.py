"""add fake site detection columns to alerts

Revision ID: i4j5k6l7m8n9
Revises: h3i4j5k6l7m8
Create Date: 2026-03-25 09:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'i4j5k6l7m8n9'
down_revision: Union[str, None] = 'h3i4j5k6l7m8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('alerts', sa.Column('fake_domain', sa.String(255), nullable=True))
    op.add_column('alerts', sa.Column('legitimate_domain', sa.String(255), nullable=True))
    op.add_column('alerts', sa.Column('domain_similarity_score', sa.Float(), nullable=True))
    op.add_column('alerts', sa.Column('content_similarity_score', sa.Float(), nullable=True))
    op.create_index('ix_alerts_fake_domain', 'alerts', ['fake_domain'])


def downgrade() -> None:
    op.drop_index('ix_alerts_fake_domain', table_name='alerts')
    op.drop_column('alerts', 'content_similarity_score')
    op.drop_column('alerts', 'domain_similarity_score')
    op.drop_column('alerts', 'legitimate_domain')
    op.drop_column('alerts', 'fake_domain')
