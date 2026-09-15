"""
DispenseIQ — Case, Observation, and Analysis Revision ORM Models

Defines the relational schema for cases, structured observations, and append-only
immutable analysis revisions in PostgreSQL.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UUID,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class CaseModel(Base):
    """Represents a diagnostic investigation case."""

    __tablename__ = "cases"

    case_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        comment="Unique identifier preserving domain case UUID",
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        comment="Original problem description provided by technician",
    )
    material: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Dispensed fluid material name or category",
    )
    method: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Dispensing method (e.g. time_pressure, jetting)",
    )
    machine_context: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Structured equipment/process parameters",
    )
    defect_code: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="Identified defect category code (e.g. D03_INCONSISTENT_SIZE)",
    )
    defect_name: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable defect title",
    )
    issue_condition: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Lifecycle state (UNRESOLVED, RECOVERY_PENDING_VERIFICATION, etc.)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Timezone-aware creation timestamp",
    )

    observations: Mapped[list[ObservationModel]] = relationship(
        "ObservationModel",
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="ObservationModel.id",
    )

    analysis_revisions: Mapped[list[AnalysisRevisionModel]] = relationship(
        "AnalysisRevisionModel",
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="AnalysisRevisionModel.revision_number",
    )

    question_answers: Mapped[list[QuestionAnswerModel]] = relationship(
        "QuestionAnswerModel",
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="QuestionAnswerModel.resulting_revision_number",
    )

    check_results: Mapped[list[CaseCheckResultModel]] = relationship(
        "CaseCheckResultModel",
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="CaseCheckResultModel.resulting_revision_number",
    )

    cause_confirmations: Mapped[list[CaseCauseConfirmationModel]] = relationship(
        "CaseCauseConfirmationModel",
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="CaseCauseConfirmationModel.resulting_revision_number",
    )

    lifecycle_events: Mapped[list[CaseLifecycleEventModel]] = relationship(
        "CaseLifecycleEventModel",
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="CaseLifecycleEventModel.resulting_revision_number",
    )


class ObservationModel(Base):
    """Structured observation extracted from user text or entered directly."""

    __tablename__ = "case_observations"
    __table_args__ = (
        UniqueConstraint(
            "case_id",
            "observation_id",
            name="uq_case_observations_case_id_obs_id",
        ),
        CheckConstraint(
            "first_seen_revision > 0",
            name="ck_case_observations_first_seen_rev_pos",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    case_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("cases.case_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    observation_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Domain-assigned stable observation ID",
    )
    observation_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Observation category enum value",
    )
    value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Normalized observation value",
    )
    original_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Source snippet or user phrasing",
    )
    statement_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Statement type (USER_OBSERVATION, AI_INFERENCE, etc.)",
    )
    source: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Provenance source (USER, MEASUREMENT, IMAGE, SYSTEM, etc.)",
    )
    confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Confidence score for inferred observation",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Timezone-aware timestamp of the observation",
    )
    first_seen_revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="First analysis revision number that incorporated this observation",
    )

    case: Mapped[CaseModel] = relationship(
        "CaseModel",
        back_populates="observations",
    )


class AnalysisRevisionModel(Base):
    """Append-only snapshot of a diagnostic evaluation revision."""

    __tablename__ = "analysis_revisions"
    __table_args__ = (
        UniqueConstraint(
            "case_id",
            "revision_number",
            name="uq_analysis_revisions_case_id_revision_number",
        ),
        CheckConstraint(
            "revision_number > 0",
            name="ck_analysis_revisions_revision_number_pos",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    case_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("cases.case_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    revision_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="1-based append-only revision sequence number",
    )
    analyzed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Timezone-aware analysis generation timestamp",
    )
    defect_code: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="Defect code identified at this revision",
    )
    issue_condition: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="IssueCondition state at this revision",
    )
    result_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        comment="Complete immutable DiagnosisResult serialized in JSON mode",
    )

    case: Mapped[CaseModel] = relationship(
        "CaseModel",
        back_populates="analysis_revisions",
    )


class QuestionAnswerModel(Base):
    """Technician question answer event associated with a diagnostic case revision."""

    __tablename__ = "case_question_answers"
    __table_args__ = (
        UniqueConstraint(
            "case_id",
            "resulting_revision_number",
            name="uq_case_question_answers_case_id_rev",
        ),
        CheckConstraint(
            "resulting_revision_number > 1",
            name="ck_case_question_answers_rev_gt_1",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    case_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("cases.case_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Diagnostic question identifier (unrestricted domain text)",
    )
    answer_value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Answer value (unrestricted domain text, e.g. YES, NO, after_prolonged_operation)",
    )
    answer_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Optional technician verbatim or clarifying text",
    )
    source: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Provenance source (USER, SYSTEM, etc.)",
    )
    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Timezone-aware answer timestamp",
    )
    resulting_revision_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Analysis revision number produced by this answer (> 1)",
    )

    case: Mapped[CaseModel] = relationship(
        "CaseModel",
        back_populates="question_answers",
    )


class CaseCheckResultModel(Base):
    """Technician troubleshooting check result event associated with a diagnostic case revision."""

    __tablename__ = "case_check_results"
    __table_args__ = (
        UniqueConstraint(
            "case_id",
            "resulting_revision_number",
            name="uq_case_check_results_case_id_rev",
        ),
        CheckConstraint(
            "resulting_revision_number > 1",
            name="ck_case_check_results_rev_gt_1",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    case_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("cases.case_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    check_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Troubleshooting check identifier (e.g. ACT01)",
    )
    execution_status: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Normalized check execution status (COMPLETED, BLOCKED, etc.)",
    )
    finding: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Normalized check finding (SUPPORTS, CONTRADICTS, INCONCLUSIVE, etc.)",
    )
    finding_details: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Optional technician verbatim notes or findings",
    )
    outcome: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Specific outcome key (e.g. blockage_found, consistent_but_wrong_size)",
    )
    source: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Provenance source (USER_CHECK_RESULT, etc.)",
    )
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Timezone-aware check timestamp",
    )
    resulting_revision_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Analysis revision number produced by this check (> 1)",
    )

    case: Mapped[CaseModel] = relationship(
        "CaseModel",
        back_populates="check_results",
    )


class CaseCauseConfirmationModel(Base):
    """Technician root cause confirmation event associated with a diagnostic case revision."""

    __tablename__ = "case_cause_confirmations"
    __table_args__ = (
        UniqueConstraint(
            "case_id",
            "resulting_revision_number",
            name="uq_case_cause_confirmations_case_id_rev",
        ),
        CheckConstraint(
            "resulting_revision_number > 1",
            name="ck_case_cause_confirmations_rev_gt_1",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    case_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("cases.case_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    cause_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Root cause identifier confirmed by technician",
    )
    confirmed_by: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="technician",
        comment="Technician identifier or role (e.g. technician)",
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Optional technician notes or observations explaining confirmation",
    )
    confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Timezone-aware confirmation timestamp",
    )
    resulting_revision_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Analysis revision number produced by this confirmation (> 1)",
    )

    case: Mapped[CaseModel] = relationship(
        "CaseModel",
        back_populates="cause_confirmations",
    )


class CaseLifecycleEventModel(Base):
    """Technician issue lifecycle event (recovery action or verification) associated with a diagnostic case revision."""

    __tablename__ = "case_lifecycle_events"
    __table_args__ = (
        UniqueConstraint(
            "case_id",
            "resulting_revision_number",
            name="uq_case_lifecycle_events_case_id_rev",
        ),
        CheckConstraint(
            "resulting_revision_number > 1",
            name="ck_case_lifecycle_events_rev_gt_1",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    case_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("cases.case_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Lifecycle event type (e.g. RECOVERY_ACTION, RECOVERY_VERIFICATION)",
    )
    prior_issue_condition: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Issue condition before this event",
    )
    resulting_issue_condition: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Issue condition after this event",
    )
    resulting_revision_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Analysis revision number produced by this event (> 1)",
    )
    actor: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="technician",
        comment="Technician identifier or role performing/verifying recovery",
    )
    details: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        comment="Details of recovery action or verification notes",
    )
    verification_passed: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        comment="True if verification succeeded, False if failed, None for recovery action",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Timezone-aware event timestamp",
    )

    case: Mapped[CaseModel] = relationship(
        "CaseModel",
        back_populates="lifecycle_events",
    )
