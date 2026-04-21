"""add notification_records table

Revision ID: m8n9o0p1q2r3
Revises: l7m8n9o0p1q2
Create Date: 2026-03-28 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'm8n9o0p1q2r3'
down_revision: Union[str, None] = 'l7m8n9o0p1q2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'notification_records',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('site_id', sa.Integer, sa.ForeignKey('monitoring_sites.id'), nullable=False),
        sa.Column('alert_id', sa.Integer, sa.ForeignKey('alerts.id'), nullable=True),
        sa.Column('violation_type', sa.String(50), nullable=False),
        sa.Column('channel', sa.String(10), nullable=False),
        sa.Column('recipient', sa.String(255), nullable=False),
        sa.Column('status', sa.String(10), nullable=False),
        sa.Column('sent_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        'ix_notification_records_site_violation_sent',
        'notification_records',
        ['site_id', 'violation_type', 'sent_at'],
    )
    op.create_index(
        'ix_notification_records_alert_id',
        'notification_records',
        ['alert_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_notification_records_alert_id', table_name='notification_records')
    op.drop_index('ix_notification_records_site_violation_sent', table_name='notification_records')
    op.drop_table('notification_records')
