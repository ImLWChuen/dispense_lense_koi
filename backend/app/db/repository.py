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
from app.models.case import (
    AnalysisRevisionModel,
    CaseModel,
    ObservationModel,
    QuestionAnswerModel,
)
from app.schemas.diagnosis import (
    AnalysisRevision,
    DiagnosisResult,
    EvidenceSource,
    IssueCondition,
    Observation,
    ObservationType,
    QuestionAnswer,
    StatementType,
    StructuredCase,
)


class StaleRevisionError(Exception):
    """Raised when an append operation specifies a stale or conflicting expected revision."""

    def __init__(self, case_id: str, expected_revision: int, current_revision: int) -> None:
        super().__init__(
            f"Stale revision for case '{case_id}': expected revision {expected_revision}, "
            f"but latest persisted revision is {current_revision}."
        )
        self.case_id = case_id
        self.expected_revision = expected_revision
        self.current_revision = current_revision


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

    def get_case_question_answers(self, case_id: str) -> list[QuestionAnswerModel]:
        """Retrieve all question answers associated with a case ordered by resulting_revision_number."""
        session, should_close = self._get_active_session()
        try:
            stmt = (
                select(QuestionAnswerModel)
                .where(QuestionAnswerModel.case_id == case_id)
                .order_by(
                    QuestionAnswerModel.resulting_revision_number,
                    QuestionAnswerModel.id,
                )
            )
            return list(session.scalars(stmt).all())
        finally:
            if should_close:
                session.close()

    def load_structured_case(self, case_id: str) -> StructuredCase | None:
        """Reconstruct a complete StructuredCase from persisted state without recalculation."""
        session, should_close = self._get_active_session()
        try:
            case_model = session.get(CaseModel, case_id)
            if case_model is None:
                return None

            # 1. Observations
            obs_models = list(
                session.scalars(
                    select(ObservationModel)
                    .where(ObservationModel.case_id == case_id)
                    .order_by(ObservationModel.id)
                ).all()
            )
            observations: list[Observation] = []
            for om in obs_models:
                try:
                    obs_type = ObservationType(om.observation_type)
                except ValueError:
                    try:
                        obs_type = ObservationType(om.observation_type.lower())
                    except ValueError:
                        obs_type = ObservationType.OTHER

                try:
                    stmt_type = StatementType(om.statement_type)
                except ValueError:
                    stmt_type = StatementType.USER_OBSERVATION

                try:
                    src = EvidenceSource(om.source)
                except ValueError:
                    src = EvidenceSource.USER

                obs = Observation(
                    id=om.observation_id,
                    observation_type=obs_type,
                    value=om.value,
                    original_text=om.original_text,
                    statement_type=stmt_type,
                    source=src,
                    confidence=om.confidence,
                    timestamp=om.created_at,
                )
                observations.append(obs)

            # 2. Question Answers
            qa_models = list(
                session.scalars(
                    select(QuestionAnswerModel)
                    .where(QuestionAnswerModel.case_id == case_id)
                    .order_by(
                        QuestionAnswerModel.resulting_revision_number,
                        QuestionAnswerModel.id,
                    )
                ).all()
            )
            previous_answers: list[QuestionAnswer] = []
            for qm in qa_models:
                try:
                    qa_src = EvidenceSource(qm.source)
                except ValueError:
                    qa_src = EvidenceSource.USER

                qa = QuestionAnswer(
                    question_id=qm.question_id,
                    answer_value=qm.answer_value,
                    answer_text=qm.answer_text,
                    source=qa_src,
                    timestamp=qm.answered_at,
                )
                previous_answers.append(qa)

            # 3. Analysis Revisions (reconstruct from immutable snapshot)
            rev_models = list(
                session.scalars(
                    select(AnalysisRevisionModel)
                    .where(AnalysisRevisionModel.case_id == case_id)
                    .order_by(AnalysisRevisionModel.revision_number)
                ).all()
            )
            analysis_revisions: list[AnalysisRevision] = []
            for rm in rev_models:
                rev_snapshot = rm.result_snapshot.get("analysis_revision")
                if rev_snapshot is not None:
                    rev = AnalysisRevision.model_validate(rev_snapshot)
                else:
                    rev = AnalysisRevision(
                        revision_number=rm.revision_number,
                        timestamp=rm.analyzed_at,
                        defect_code=rm.defect_code,
                    )
                analysis_revisions.append(rev)

            # 4. Issue condition
            try:
                issue_cond = IssueCondition(case_model.issue_condition)
            except ValueError:
                issue_cond = IssueCondition.UNRESOLVED

            return StructuredCase(
                case_id=case_model.case_id,
                description=case_model.description,
                material=case_model.material,
                method=case_model.method,
                machine_context=case_model.machine_context,
                defect_code=case_model.defect_code,
                defect_name=case_model.defect_name,
                observations=observations,
                previous_answers=previous_answers,
                previous_check_results=[],
                analysis_revisions=analysis_revisions,
                issue_condition=issue_cond,
                created_at=case_model.created_at,
            )
        finally:
            if should_close:
                session.close()

    def append_question_answer_revision(
        self,
        case: StructuredCase,
        answer: QuestionAnswer,
        result: DiagnosisResult,
        expected_revision: int,
    ) -> AnalysisRevisionModel:
        """Atomically append a question answer, new observations, and the resulting analysis revision.

        Enforces optimistic concurrency via expected_revision and locks the case row
        against concurrent updates.

        Args:
            case: StructuredCase containing updated observations and previous answers.
            answer: The QuestionAnswer submitted by the technician.
            result: DiagnosisResult resulting from the question answer and re-ranking.
            expected_revision: The latest revision expected by the caller before appending.

        Returns:
            The newly created AnalysisRevisionModel.

        Raises:
            ValueError: On identity mismatch or missing analysis revision.
            StaleRevisionError: If expected_revision does not match the latest persisted revision.
        """
        if case.case_id != result.case_id:
            raise ValueError(
                f"Mismatched case IDs: case.case_id='{case.case_id}' != "
                f"result.case_id='{result.case_id}'"
            )

        if result.analysis_revision is None:
            raise ValueError(
                "DiagnosisResult must include an analysis_revision for append."
            )

        session, should_close = self._get_active_session()
        try:
            # 1. Lock the case row in PostgreSQL
            stmt = select(CaseModel).where(CaseModel.case_id == case.case_id).with_for_update()
            db_case = session.scalars(stmt).first()
            if db_case is None:
                raise ValueError(f"Case '{case.case_id}' not found.")

            # 2. Get latest revision while holding row lock
            stmt_rev = (
                select(AnalysisRevisionModel.revision_number)
                .where(AnalysisRevisionModel.case_id == case.case_id)
                .order_by(AnalysisRevisionModel.revision_number.desc())
            )
            latest_revision = session.scalars(stmt_rev).first()
            if latest_revision is None:
                raise ValueError(f"Case '{case.case_id}' has no existing revisions.")

            # 3. Optimistic concurrency check
            if expected_revision != latest_revision:
                raise StaleRevisionError(
                    case_id=case.case_id,
                    expected_revision=expected_revision,
                    current_revision=latest_revision,
                )

            new_revision_number = latest_revision + 1
            if result.analysis_revision.revision_number != new_revision_number:
                raise ValueError(
                    f"Contract mismatch: result.analysis_revision.revision_number is "
                    f"{result.analysis_revision.revision_number}, but expected next revision {new_revision_number}."
                )

            # 4. Persist the QuestionAnswer linked to new_revision_number
            qa_source_val = (
                answer.source.value
                if hasattr(answer.source, "value")
                else str(answer.source)
            )
            qa_model = QuestionAnswerModel(
                case_id=case.case_id,
                question_id=answer.question_id,
                answer_value=answer.answer_value,
                answer_text=answer.answer_text,
                source=qa_source_val,
                answered_at=answer.timestamp,
                resulting_revision_number=new_revision_number,
            )
            session.add(qa_model)

            # 5. Insert only observations not already persisted for this case
            existing_obs_ids = set(
                session.scalars(
                    select(ObservationModel.observation_id).where(
                        ObservationModel.case_id == case.case_id
                    )
                ).all()
            )
            for obs in case.observations:
                if obs.id not in existing_obs_ids:
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
                        first_seen_revision=new_revision_number,
                    )
                    session.add(obs_model)
                    existing_obs_ids.add(obs.id)

            # 6. Append immutable AnalysisRevisionModel
            rev_issue_cond_val = (
                result.issue_condition.value
                if hasattr(result.issue_condition, "value")
                else str(result.issue_condition)
            )
            snapshot_dict = result.model_dump(mode="json")
            rev_model = AnalysisRevisionModel(
                case_id=case.case_id,
                revision_number=new_revision_number,
                analyzed_at=result.analysis_revision.timestamp,
                defect_code=result.defect,
                issue_condition=rev_issue_cond_val,
                result_snapshot=snapshot_dict,
            )
            session.add(rev_model)

            # 7. Update top-level case state if evolved
            if result.issue_condition:
                db_case.issue_condition = rev_issue_cond_val
            if result.defect and not db_case.defect_code:
                db_case.defect_code = result.defect
                db_case.defect_name = result.defect_name

            if should_close:
                session.commit()
            else:
                session.flush()

            return rev_model
        except Exception:
            session.rollback()
            raise
        finally:
            if should_close:
                session.close()
