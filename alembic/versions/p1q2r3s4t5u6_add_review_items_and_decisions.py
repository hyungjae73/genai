"""add review_items and review_decisions tables

Revision ID: p1q2r3s4t5u6
Revises: q1r2s3t4u5v6
Create Date: 2026-04-10 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'p1q2r3s4t5u6'
down_revision: Union[str, None] = 'q1r2s3t4u5v6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "review_items",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("alert_id", sa.Integer, sa.ForeignKey("alerts.id"), nullable=True),
        sa.Column("site_id", sa.Integer, sa.ForeignKey("monitoring_sites.id"), nullable=False),
        sa.Column("review_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("priority", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("assigned_to", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_review_items_status", "review_items", ["status"])
    op.create_index("ix_review_items_priority", "review_items", ["priority"])
    op.create_index("ix_review_items_alert_id", "review_items", ["alert_id"])
    op.create_index("ix_review_items_site_id", "review_items", ["site_id"])
    op.create_index("ix_review_items_assigned_to", "review_items", ["assigned_to"])
    op.create_index(
        "ix_review_items_status_priority_created",
        "review_items",
        ["status", "priority", "created_at"],
    )

    op.create_table(
        "review_decisions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("review_item_id", sa.Integer, sa.ForeignKey("review_items.id"), nullable=False),
        sa.Column("reviewer_id", sa.Integer, nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("comment", sa.Text, nullable=False),
        sa.Column("review_stage", sa.String(20), nullable=False),
        sa.Column("decided_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_review_decisions_review_item_id", "review_decisions", ["review_item_id"])
    op.create_index("ix_review_decisions_reviewer_id", "review_decisions", ["reviewer_id"])


def downgrade() -> None:
    op.drop_index("ix_review_decisions_reviewer_id", table_name="review_decisions")
    op.drop_index("ix_review_decisions_review_item_id", table_name="review_decisions")
    op.drop_table("review_decisions")

    op.drop_index("ix_review_items_status_priority_created", table_name="review_items")
    op.drop_index("ix_review_items_assigned_to", table_name="review_items")
    op.drop_index("ix_review_items_site_id", table_name="review_items")
    op.drop_index("ix_review_items_alert_id", table_name="review_items")
    op.drop_index("ix_review_items_priority", table_name="review_items")
    op.drop_index("ix_review_items_status", table_name="review_items")
    op.drop_table("review_items")
