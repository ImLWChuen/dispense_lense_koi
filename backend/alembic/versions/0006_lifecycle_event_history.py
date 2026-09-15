"""Add issue lifecycle event history persistence table

Revision ID: 0006_lifecycle_event_history
Revises: 0005_cause_confirmation_history
Create Date: 2026-09-15 10:35:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0006_lifecycle_event_history"
down_revision: Union[str, None] = "0005_cause_confirmation_history"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "case_lifecycle_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("prior_issue_condition", sa.String(length=64), nullable=False),
        sa.Column("resulting_issue_condition", sa.String(length=64), nullable=False),
        sa.Column("resulting_revision_number", sa.Integer(), nullable=False),
        sa.Column("actor", sa.String(length=64), nullable=False, server_default="technician"),
        sa.Column("details", sa.Text(), nullable=False, server_default=""),
        sa.Column("verification_passed", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "resulting_revision_number > 1",
            name="ck_case_lifecycle_events_rev_gt_1",
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.case_id"],
            name="fk_case_lifecycle_events_case_id_cases",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_case_lifecycle_events"),
        sa.UniqueConstraint(
            "case_id",
            "resulting_revision_number",
            name="uq_case_lifecycle_events_case_id_rev",
        ),
    )
    op.create_index(
        "ix_case_lifecycle_events_case_id",
        "case_lifecycle_events",
        ["case_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_case_lifecycle_events_case_id", table_name="case_lifecycle_events")
    op.drop_table("case_lifecycle_events")
