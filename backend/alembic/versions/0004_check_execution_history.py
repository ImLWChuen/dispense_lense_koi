"""Add troubleshooting check execution history persistence table

Revision ID: 0004_check_execution_history
Revises: 0003_question_answer_history
Create Date: 2026-09-16 10:20:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0004_check_execution_history"
down_revision: Union[str, None] = "0003_question_answer_history"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "case_check_executions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("check_id", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("finding", sa.String(length=64), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resulting_revision_number", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "resulting_revision_number > 1",
            name="ck_case_check_executions_rev_gt_1",
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.case_id"],
            name="fk_case_check_executions_case_id_cases",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_case_check_executions"),
        sa.UniqueConstraint(
            "case_id",
            "resulting_revision_number",
            name="uq_case_check_executions_case_id_rev",
        ),
    )
    op.create_index(
        "ix_case_check_executions_case_id",
        "case_check_executions",
        ["case_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_case_check_executions_case_id", table_name="case_check_executions")
    op.drop_table("case_check_executions")
