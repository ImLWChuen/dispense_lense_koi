"""Add question-answer history persistence table

Revision ID: 0003_question_answer_history
Revises: 0002_widen_unrestricted_strings
Create Date: 2026-09-13 06:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0003_question_answer_history"
down_revision: Union[str, None] = "0002_widen_unrestricted_strings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "case_question_answers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("question_id", sa.Text(), nullable=False),
        sa.Column("answer_value", sa.Text(), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resulting_revision_number", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "resulting_revision_number > 1",
            name="ck_case_question_answers_rev_gt_1",
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.case_id"],
            name="fk_case_question_answers_case_id_cases",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_case_question_answers"),
        sa.UniqueConstraint(
            "case_id",
            "resulting_revision_number",
            name="uq_case_question_answers_case_id_rev",
        ),
    )
    op.create_index(
        "ix_case_question_answers_case_id",
        "case_question_answers",
        ["case_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_case_question_answers_case_id", table_name="case_question_answers")
    op.drop_table("case_question_answers")
