"""add crawl pipeline architecture models

Add new columns to MonitoringSite and VerificationResult,
and create new EvidenceRecord and CrawlSchedule tables
for the crawl pipeline architecture.

Revision ID: j5k6l7m8n9o0
Revises: i4j5k6l7m8n9
Create Date: 2026-04-10 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'j5k6l7m8n9o0'
down_revision: Union[str, None] = 'i4j5k6l7m8n9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- MonitoringSite: new columns (Req 21.1-21.4) ---
    op.add_column('monitoring_sites', sa.Column('pre_capture_script', sa.JSON(), nullable=True))
    op.add_column('monitoring_sites', sa.Column('crawl_priority', sa.String(20), nullable=False, server_default='normal'))
    op.add_column('monitoring_sites', sa.Column('etag', sa.String(255), nullable=True))
    op.add_column('monitoring_sites', sa.Column('last_modified_header', sa.String(255), nullable=True))
    op.add_column('monitoring_sites', sa.Column('plugin_config', sa.JSON(), nullable=True))

    # --- VerificationResult: new columns (Req 21.4) ---
    op.add_column('verification_results', sa.Column('structured_data', sa.JSON(), nullable=True))
    op.add_column('verification_results', sa.Column('structured_data_violations', sa.JSON(), nullable=True))
    op.add_column('verification_results', sa.Column('data_source', sa.String(50), nullable=True))
    op.add_column('verification_results', sa.Column('structured_data_status', sa.String(50), nullable=True))
    op.add_column('verification_results', sa.Column('evidence_status', sa.String(50), nullable=True))

    # --- EvidenceRecord: new table (Req 21.5, 21.6) ---
    op.create_table(
        'evidence_records',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('verification_result_id', sa.Integer(), nullable=False),
        sa.Column('variant_name', sa.String(255), nullable=False),
        sa.Column('screenshot_path', sa.String(512), nullable=False),
        sa.Column('roi_image_path', sa.String(512), nullable=True),
        sa.Column('ocr_text', sa.Text(), nullable=False),
        sa.Column('ocr_confidence', sa.Float(), nullable=False),
        sa.Column('evidence_type', sa.String(50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['verification_result_id'], ['verification_results.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_evidence_records_verification_result_id', 'evidence_records', ['verification_result_id'])
    op.create_index('ix_evidence_records_evidence_type', 'evidence_records', ['evidence_type'])

    # --- CrawlSchedule: new table (Req 21.7, 21.8) ---
    op.create_table(
        'crawl_schedules',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('site_id', sa.Integer(), nullable=False),
        sa.Column('priority', sa.String(20), nullable=False, server_default='normal'),
        sa.Column('next_crawl_at', sa.DateTime(), nullable=False),
        sa.Column('interval_minutes', sa.Integer(), nullable=False, server_default='1440'),
        sa.Column('last_etag', sa.String(255), nullable=True),
        sa.Column('last_modified', sa.String(255), nullable=True),
        sa.ForeignKeyConstraint(['site_id'], ['monitoring_sites.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('site_id'),
    )
    op.create_index('ix_crawl_schedules_next_crawl_at', 'crawl_schedules', ['next_crawl_at'])


def downgrade() -> None:
    # --- CrawlSchedule: drop table ---
    op.drop_index('ix_crawl_schedules_next_crawl_at', table_name='crawl_schedules')
    op.drop_table('crawl_schedules')

    # --- EvidenceRecord: drop table ---
    op.drop_index('ix_evidence_records_evidence_type', table_name='evidence_records')
    op.drop_index('ix_evidence_records_verification_result_id', table_name='evidence_records')
    op.drop_table('evidence_records')

    # --- VerificationResult: drop columns ---
    op.drop_column('verification_results', 'evidence_status')
    op.drop_column('verification_results', 'structured_data_status')
    op.drop_column('verification_results', 'data_source')
    op.drop_column('verification_results', 'structured_data_violations')
    op.drop_column('verification_results', 'structured_data')

    # --- MonitoringSite: drop columns ---
    op.drop_column('monitoring_sites', 'plugin_config')
    op.drop_column('monitoring_sites', 'last_modified_header')
    op.drop_column('monitoring_sites', 'etag')
    op.drop_column('monitoring_sites', 'crawl_priority')
    op.drop_column('monitoring_sites', 'pre_capture_script')
