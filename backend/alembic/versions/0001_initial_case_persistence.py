"""Establish initial case, observation, and analysis revision persistence tables

Revision ID: 0001_initial_persistence
Revises: None
Create Date: 2026-09-12 12:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial_persistence"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. cases table
    op.create_table(
        "cases",
        sa.Column(
            "case_id",
            sa.UUID(as_uuid=False),
            nullable=False,
            comment="Unique identifier preserving domain case UUID",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=False,
            server_default="",
            comment="Original problem description provided by technician",
        ),
        sa.Column(
            "material",
            sa.String(length=255),
            nullable=True,
            comment="Dispensed fluid material name or category",
        ),
        sa.Column(
            "method",
            sa.String(length=255),
            nullable=True,
            comment="Dispensing method (e.g. time_pressure, jetting)",
        ),
        sa.Column(
            "machine_context",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Structured equipment/process parameters",
        ),
        sa.Column(
            "defect_code",
            sa.String(length=64),
            nullable=True,
            comment="Identified defect category code",
        ),
        sa.Column(
            "defect_name",
            sa.String(length=255),
            nullable=True,
            comment="Human-readable defect title",
        ),
        sa.Column(
            "issue_condition",
            sa.String(length=64),
            nullable=False,
            comment="Lifecycle state (UNRESOLVED, RECOVERY_PENDING_VERIFICATION, etc.)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Timezone-aware creation timestamp",
        ),
        sa.PrimaryKeyConstraint("case_id", name="pk_cases"),
    )

    # 2. case_observations table
    op.create_table(
        "case_observations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "case_id",
            sa.UUID(as_uuid=False),
            nullable=False,
            comment="Owning case reference",
        ),
        sa.Column(
            "observation_id",
            sa.String(length=64),
            nullable=False,
            comment="Domain-assigned stable observation ID",
        ),
        sa.Column(
            "observation_type",
            sa.String(length=64),
            nullable=False,
            comment="Observation category enum value",
        ),
        sa.Column(
            "value",
            sa.String(length=255),
            nullable=False,
            comment="Normalized observation value",
        ),
        sa.Column(
            "original_text",
            sa.Text(),
            nullable=True,
            comment="Source snippet or user phrasing",
        ),
        sa.Column(
            "statement_type",
            sa.String(length=64),
            nullable=False,
            comment="Statement type (USER_OBSERVATION, AI_INFERENCE, etc.)",
        ),
        sa.Column(
            "source",
            sa.String(length=64),
            nullable=False,
            comment="Provenance source (USER, MEASUREMENT, IMAGE, SYSTEM, etc.)",
        ),
        sa.Column(
            "confidence",
            sa.Float(),
            nullable=True,
            comment="Confidence score for inferred observation",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Timezone-aware timestamp of the observation",
        ),
        sa.Column(
            "first_seen_revision",
            sa.Integer(),
            nullable=False,
            server_default="1",
            comment="First analysis revision that incorporated this observation",
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.case_id"],
            name="fk_case_observations_case_id_cases",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_case_observations"),
        sa.UniqueConstraint(
            "case_id",
            "observation_id",
            name="uq_case_observations_case_id_obs_id",
        ),
        sa.CheckConstraint(
            "first_seen_revision > 0",
            name="ck_case_observations_first_seen_rev_pos",
        ),
    )
    op.create_index(
        "ix_case_observations_case_id",
        "case_observations",
        ["case_id"],
        unique=False,
    )

    # 3. analysis_revisions table
    op.create_table(
        "analysis_revisions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "case_id",
            sa.UUID(as_uuid=False),
            nullable=False,
            comment="Owning case reference",
        ),
        sa.Column(
            "revision_number",
            sa.Integer(),
            nullable=False,
            comment="1-based append-only revision sequence number",
        ),
        sa.Column(
            "analyzed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Timezone-aware analysis generation timestamp",
        ),
        sa.Column(
            "defect_code",
            sa.String(length=64),
            nullable=True,
            comment="Defect code identified at this revision",
        ),
        sa.Column(
            "issue_condition",
            sa.String(length=64),
            nullable=False,
            comment="IssueCondition state at this revision",
        ),
        sa.Column(
            "result_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Complete immutable DiagnosisResult serialized in JSON mode",
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.case_id"],
            name="fk_analysis_revisions_case_id_cases",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_analysis_revisions"),
        sa.UniqueConstraint(
            "case_id",
            "revision_number",
            name="uq_analysis_revisions_case_id_revision_number",
        ),
        sa.CheckConstraint(
            "revision_number > 0",
            name="ck_analysis_revisions_revision_number_pos",
        ),
    )
    op.create_index(
        "ix_analysis_revisions_case_id",
        "analysis_revisions",
        ["case_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_analysis_revisions_case_id", table_name="analysis_revisions")
    op.drop_table("analysis_revisions")
    op.drop_index("ix_case_observations_case_id", table_name="case_observations")
    op.drop_table("case_observations")
    op.drop_table("cases")
