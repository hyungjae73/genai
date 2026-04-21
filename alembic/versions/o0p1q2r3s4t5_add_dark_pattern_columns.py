"""add dark pattern columns and tables

Revision ID: o0p1q2r3s4t5
Revises: n9o0p1q2r3s4
Create Date: 2026-03-31 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = 'o0p1q2r3s4t5'
down_revision: Union[str, None] = 'n9o0p1q2r3s4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Column additions ---

    # MonitoringSite.merchant_category
    op.add_column(
        'monitoring_sites',
        sa.Column('merchant_category', sa.String(50), nullable=True),
    )

    # VerificationResult dark pattern columns
    op.add_column(
        'verification_results',
        sa.Column('dark_pattern_score', sa.Float(), nullable=True),
    )
    op.add_column(
        'verification_results',
        sa.Column('dark_pattern_subscores', JSONB, nullable=True),
    )
    op.add_column(
        'verification_results',
        sa.Column('dark_pattern_types', JSONB, nullable=True),
    )

    # Violation.dark_pattern_category
    op.add_column(
        'violations',
        sa.Column('dark_pattern_category', sa.String(50), nullable=True),
    )

    # --- New tables ---

    # dynamic_compliance_rules
    op.create_table(
        'dynamic_compliance_rules',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('rule_name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('prompt_template', sa.Text(), nullable=False),
        sa.Column('severity', sa.String(20), nullable=False, server_default='warning'),
        sa.Column('dark_pattern_category', sa.String(50), nullable=False, server_default='other'),
        sa.Column('confidence_threshold', sa.Float(), nullable=False, server_default='0.7'),
        sa.Column('applicable_categories', JSONB, nullable=True),
        sa.Column('applicable_site_ids', JSONB, nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('execution_order', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('created_by', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('rule_name', name='uq_dynamic_compliance_rules_rule_name'),
    )
    op.create_index('ix_dcr_rule_name', 'dynamic_compliance_rules', ['rule_name'])
    op.create_index('ix_dcr_is_active', 'dynamic_compliance_rules', ['is_active'])
    op.create_index('ix_dcr_severity', 'dynamic_compliance_rules', ['severity'])
    op.create_index('ix_dcr_category', 'dynamic_compliance_rules', ['dark_pattern_category'])
    op.create_index('ix_dcr_execution_order', 'dynamic_compliance_rules', ['execution_order'])

    # content_fingerprints
    # text_embedding stored as JSONB (pgvector fallback)
    op.create_table(
        'content_fingerprints',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('site_id', sa.Integer(), sa.ForeignKey('monitoring_sites.id'), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('text_embedding', JSONB, nullable=True),
        sa.Column('text_hash', sa.String(64), nullable=False),
        sa.Column('image_phashes', JSONB, nullable=True),
        sa.Column('product_names', JSONB, nullable=True),
        sa.Column('price_info', JSONB, nullable=True),
        sa.Column('is_canonical_product', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('captured_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_cfp_site_id', 'content_fingerprints', ['site_id'])
    op.create_index('ix_cfp_text_hash', 'content_fingerprints', ['text_hash'])
    op.create_index('ix_cfp_is_canonical', 'content_fingerprints', ['is_canonical_product'])
    op.create_index('ix_cfp_captured_at', 'content_fingerprints', ['captured_at'])
    op.create_index('ix_cfp_site_canonical', 'content_fingerprints', ['site_id', 'is_canonical_product'])


def downgrade() -> None:
    # Drop tables
    op.drop_index('ix_cfp_site_canonical', table_name='content_fingerprints')
    op.drop_index('ix_cfp_captured_at', table_name='content_fingerprints')
    op.drop_index('ix_cfp_is_canonical', table_name='content_fingerprints')
    op.drop_index('ix_cfp_text_hash', table_name='content_fingerprints')
    op.drop_index('ix_cfp_site_id', table_name='content_fingerprints')
    op.drop_table('content_fingerprints')

    op.drop_index('ix_dcr_execution_order', table_name='dynamic_compliance_rules')
    op.drop_index('ix_dcr_category', table_name='dynamic_compliance_rules')
    op.drop_index('ix_dcr_severity', table_name='dynamic_compliance_rules')
    op.drop_index('ix_dcr_is_active', table_name='dynamic_compliance_rules')
    op.drop_index('ix_dcr_rule_name', table_name='dynamic_compliance_rules')
    op.drop_table('dynamic_compliance_rules')

    # Drop columns
    op.drop_column('violations', 'dark_pattern_category')
    op.drop_column('verification_results', 'dark_pattern_types')
    op.drop_column('verification_results', 'dark_pattern_subscores')
    op.drop_column('verification_results', 'dark_pattern_score')
    op.drop_column('monitoring_sites', 'merchant_category')
