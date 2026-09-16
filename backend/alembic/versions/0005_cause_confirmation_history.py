"""Add cause-confirmation history persistence table

Revision ID: 0005_cause_confirmation_history
Revises: 0004_check_result_history
Create Date: 2026-09-15 09:15:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0005_cause_confirmation_history"
down_revision: Union[str, None] = "0004_check_result_history"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "case_cause_confirmations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("cause_id", sa.Text(), nullable=False),
        sa.Column("confirmed_by", sa.String(length=64), nullable=False, server_default="technician"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resulting_revision_number", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "resulting_revision_number > 1",
            name="ck_case_cause_confirmations_rev_gt_1",
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.case_id"],
            name="fk_case_cause_confirmations_case_id_cases",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_case_cause_confirmations"),
        sa.UniqueConstraint(
            "case_id",
            "resulting_revision_number",
            name="uq_case_cause_confirmations_case_id_rev",
        ),
    )
    op.create_index(
        "ix_case_cause_confirmations_case_id",
        "case_cause_confirmations",
        ["case_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_case_cause_confirmations_case_id", table_name="case_cause_confirmations")
    op.drop_table("case_cause_confirmations")
