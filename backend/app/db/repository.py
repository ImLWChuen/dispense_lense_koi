"""
DispenseIQ — Case Persistence Repository

Provides atomic persistence operations for cases, structured observations,
and append-only immutable analysis revisions in PostgreSQL.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session_factory
from app.models.case import AnalysisRevisionModel, CaseModel, ObservationModel
from app.schemas.diagnosis import DiagnosisResult, StructuredCase


class CaseRepository:
    """Repository managing persistence for diagnostic cases, observations, and revisions."""

    def __init__(self, session: Session | None = None) -> None:
        self._session = session

    def _get_active_session(self) -> tuple[Session, bool]:
        """Return active session and boolean indicating whether it should be closed."""
        if self._session is not None:
            return self._session, False
        factory = get_session_factory()
        return factory(), True

    def save_initial_case(
        self,
        case: StructuredCase,
        result: DiagnosisResult,
    ) -> CaseModel:
        """Atomically persist a prepared StructuredCase and initial DiagnosisResult (Revision 1).

        Args:
            case: Mutated StructuredCase containing extracted observations.
            result: Result of the initial diagnostic evaluation.

        Raises:
            ValueError: If case/result IDs mismatch, or if result does not represent revision 1.
            sqlalchemy.exc.IntegrityError: If case or revision 1 already exists or violates constraints.
        """
        # 1. Identity validation
        if case.case_id != result.case_id:
            raise ValueError(
                f"Mismatched case IDs: case.case_id='{case.case_id}' != "
                f"result.case_id='{result.case_id}'"
            )

        # 2. Initial revision validation
        if result.analysis_revision is None:
            raise ValueError(
                "DiagnosisResult must include an analysis_revision for initial persistence."
            )

        if result.analysis_revision.revision_number != 1:
            raise ValueError(
                f"Initial persistence requires analysis_revision.revision_number == 1, "
                f"got {result.analysis_revision.revision_number}."
            )

        session, should_close = self._get_active_session()
        try:
            issue_cond_val = (
                case.issue_condition.value
                if hasattr(case.issue_condition, "value")
                else str(case.issue_condition)
            )
            rev_issue_cond_val = (
                result.issue_condition.value
                if hasattr(result.issue_condition, "value")
                else str(result.issue_condition)
            )

            # Construct Case record
            case_model = CaseModel(
                case_id=case.case_id,
                description=case.description or "",
                material=case.material,
                method=case.method,
                machine_context=case.machine_context,
                defect_code=case.defect_code or result.defect,
                defect_name=case.defect_name or result.defect_name,
                issue_condition=issue_cond_val,
                created_at=case.created_at,
            )
            session.add(case_model)

            # Construct Observation records
            for obs in case.observations:
                obs_type = (
                    obs.observation_type.value
                    if hasattr(obs.observation_type, "value")
                    else str(obs.observation_type)
                )
                stmt_type = (
                    obs.statement_type.value
                    if hasattr(obs.statement_type, "value")
                    else str(obs.statement_type)
                )
                src = (
                    obs.source.value
                    if hasattr(obs.source, "value")
                    else str(obs.source)
                )
                obs_model = ObservationModel(
                    case_id=case.case_id,
                    observation_id=obs.id,
                    observation_type=obs_type,
                    value=obs.value,
                    original_text=obs.original_text,
                    statement_type=stmt_type,
                    source=src,
                    confidence=obs.confidence,
                    created_at=obs.timestamp,
                    first_seen_revision=1,
                )
                session.add(obs_model)

            # Snapshot complete DiagnosisResult via mode='json'
            snapshot_dict = result.model_dump(mode="json")
            rev_model = AnalysisRevisionModel(
                case_id=case.case_id,
                revision_number=1,
                analyzed_at=result.analysis_revision.timestamp,
                defect_code=result.defect,
                issue_condition=rev_issue_cond_val,
                result_snapshot=snapshot_dict,
            )
            session.add(rev_model)

            if should_close:
                session.commit()
            else:
                session.flush()

            return case_model
        except Exception:
            session.rollback()
            raise
        finally:
            if should_close:
                session.close()

    def get_case(self, case_id: str) -> CaseModel | None:
        """Retrieve a case by ID."""
        session, should_close = self._get_active_session()
        try:
            stmt = select(CaseModel).where(CaseModel.case_id == case_id)
            return session.scalars(stmt).first()
        finally:
            if should_close:
                session.close()

    def get_case_observations(self, case_id: str) -> list[ObservationModel]:
        """Retrieve all observations associated with a case ordered by ID."""
        session, should_close = self._get_active_session()
        try:
            stmt = (
                select(ObservationModel)
                .where(ObservationModel.case_id == case_id)
                .order_by(ObservationModel.id)
            )
            return list(session.scalars(stmt).all())
        finally:
            if should_close:
                session.close()

    def get_analysis_revision(
        self,
        case_id: str,
        revision_number: int = 1,
    ) -> AnalysisRevisionModel | None:
        """Retrieve a specific analysis revision for a case."""
        session, should_close = self._get_active_session()
        try:
            stmt = select(AnalysisRevisionModel).where(
                AnalysisRevisionModel.case_id == case_id,
                AnalysisRevisionModel.revision_number == revision_number,
            )
            return session.scalars(stmt).first()
        finally:
            if should_close:
                session.close()

    def list_case_revisions(self, case_id: str) -> list[int]:
        """List all revision numbers available for a case."""
        session, should_close = self._get_active_session()
        try:
            stmt = (
                select(AnalysisRevisionModel.revision_number)
                .where(AnalysisRevisionModel.case_id == case_id)
                .order_by(AnalysisRevisionModel.revision_number)
            )
            return list(session.scalars(stmt).all())
        finally:
            if should_close:
                session.close()
