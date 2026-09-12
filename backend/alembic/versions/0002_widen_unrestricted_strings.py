"""Widen unrestricted domain strings to Text

Revision ID: 0002_widen_unrestricted_strings
Revises: 0001_initial_persistence
Create Date: 2026-09-12 14:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002_widen_unrestricted_strings"
down_revision: Union[str, None] = "0001_initial_persistence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Widen observation_id and value in case_observations
    op.alter_column(
        "case_observations",
        "observation_id",
        existing_type=sa.String(length=64),
        type_=sa.Text(),
        existing_nullable=False,
    )
    op.alter_column(
        "case_observations",
        "value",
        existing_type=sa.String(length=255),
        type_=sa.Text(),
        existing_nullable=False,
    )

    # 2. Widen material, method, and defect_name in cases
    op.alter_column(
        "cases",
        "material",
        existing_type=sa.String(length=255),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        "cases",
        "method",
        existing_type=sa.String(length=255),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        "cases",
        "defect_name",
        existing_type=sa.String(length=255),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "cases",
        "defect_name",
        existing_type=sa.Text(),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
    op.alter_column(
        "cases",
        "method",
        existing_type=sa.Text(),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
    op.alter_column(
        "cases",
        "material",
        existing_type=sa.Text(),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
    op.alter_column(
        "case_observations",
        "value",
        existing_type=sa.Text(),
        type_=sa.String(length=255),
        existing_nullable=False,
    )
    op.alter_column(
        "case_observations",
        "observation_id",
        existing_type=sa.Text(),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
