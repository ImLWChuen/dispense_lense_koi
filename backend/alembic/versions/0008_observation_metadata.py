"""Add metadata column to case_observations

Revision ID: 0008_observation_metadata
Revises: 0007_check_execution_history
Create Date: 2026-09-19 14:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0008_observation_metadata"
down_revision: Union[str, None] = "0007_check_execution_history"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "case_observations",
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Structured observation metadata (e.g. image measurement, analysis status, ROI)",
        ),
    )


def downgrade() -> None:
    op.drop_column("case_observations", "metadata")
