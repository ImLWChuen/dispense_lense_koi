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
    CaseCauseConfirmationModel,
    CaseCheckResultModel,
    CaseLifecycleEventModel,
    CaseModel,
    ObservationModel,
    QuestionAnswerModel,
)
from app.schemas.diagnosis import (
    AnalysisRevision,
    CheckExecutionStatus,
    CheckFinding,
    CheckResult,
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
            stmt = (
                select(CaseModel)
                .where(CaseModel.case_id == case_id)
                .execution_options(populate_existing=True)
            )
            return session.scalars(stmt).first()
        finally:
            if should_close:
                session.close()

    def get_all_cases(self) -> list[CaseModel]:
        """Retrieve all cases ordered by descending creation time."""
        session, should_close = self._get_active_session()
        try:
            stmt = (
                select(CaseModel)
                .order_by(CaseModel.created_at.desc())
                .execution_options(populate_existing=True)
            )
            return list(session.scalars(stmt).all())
        finally:
            if should_close:
                session.close()

    def get_case_observations(
        self, case_id: str, max_revision: int | None = None
    ) -> list[ObservationModel]:
        """Retrieve all observations associated with a case ordered by ID."""
        session, should_close = self._get_active_session()
        try:
            stmt = (
                select(ObservationModel)
                .where(ObservationModel.case_id == case_id)
            )
            if max_revision is not None:
                stmt = stmt.where(ObservationModel.first_seen_revision <= max_revision)
            stmt = stmt.order_by(ObservationModel.id).execution_options(populate_existing=True)
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
            stmt = (
                select(AnalysisRevisionModel)
                .where(
                    AnalysisRevisionModel.case_id == case_id,
                    AnalysisRevisionModel.revision_number == revision_number,
                )
                .execution_options(populate_existing=True)
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
                .execution_options(populate_existing=True)
            )
            return list(session.scalars(stmt).all())
        finally:
            if should_close:
                session.close()

    def get_case_question_answers(
        self, case_id: str, max_revision: int | None = None
    ) -> list[QuestionAnswerModel]:
        """Retrieve all question answers associated with a case ordered by resulting_revision_number."""
        session, should_close = self._get_active_session()
        try:
            stmt = (
                select(QuestionAnswerModel)
                .where(QuestionAnswerModel.case_id == case_id)
            )
            if max_revision is not None:
                stmt = stmt.where(QuestionAnswerModel.resulting_revision_number <= max_revision)
            stmt = stmt.order_by(
                QuestionAnswerModel.resulting_revision_number,
                QuestionAnswerModel.id,
            ).execution_options(populate_existing=True)
            return list(session.scalars(stmt).all())
        finally:
            if should_close:
                session.close()

    def get_case_check_results(
        self, case_id: str, max_revision: int | None = None
    ) -> list[CaseCheckResultModel]:
        """Retrieve all check results associated with a case ordered by resulting_revision_number."""
        session, should_close = self._get_active_session()
        try:
            stmt = (
                select(CaseCheckResultModel)
                .where(CaseCheckResultModel.case_id == case_id)
            )
            if max_revision is not None:
                stmt = stmt.where(CaseCheckResultModel.resulting_revision_number <= max_revision)
            stmt = stmt.order_by(
                CaseCheckResultModel.resulting_revision_number,
                CaseCheckResultModel.id,
            ).execution_options(populate_existing=True)
            return list(session.scalars(stmt).all())
        finally:
            if should_close:
                session.close()

    def get_case_cause_confirmations(
        self, case_id: str, max_revision: int | None = None
    ) -> list[CaseCauseConfirmationModel]:
        """Retrieve all cause confirmations associated with a case ordered by resulting_revision_number."""
        session, should_close = self._get_active_session()
        try:
            stmt = (
                select(CaseCauseConfirmationModel)
                .where(CaseCauseConfirmationModel.case_id == case_id)
            )
            if max_revision is not None:
                stmt = stmt.where(CaseCauseConfirmationModel.resulting_revision_number <= max_revision)
            stmt = stmt.order_by(
                CaseCauseConfirmationModel.resulting_revision_number,
                CaseCauseConfirmationModel.id,
            ).execution_options(populate_existing=True)
            return list(session.scalars(stmt).all())
        finally:
            if should_close:
                session.close()

    def get_case_lifecycle_events(
        self, case_id: str, max_revision: int | None = None
    ) -> list[CaseLifecycleEventModel]:
        """Retrieve all lifecycle events associated with a case ordered by resulting_revision_number."""
        session, should_close = self._get_active_session()
        try:
            stmt = (
                select(CaseLifecycleEventModel)
                .where(CaseLifecycleEventModel.case_id == case_id)
            )
            if max_revision is not None:
                stmt = stmt.where(CaseLifecycleEventModel.resulting_revision_number <= max_revision)
            stmt = stmt.order_by(
                CaseLifecycleEventModel.resulting_revision_number,
                CaseLifecycleEventModel.id,
            ).execution_options(populate_existing=True)
            return list(session.scalars(stmt).all())
        finally:
            if should_close:
                session.close()

    def load_structured_case(
        self,
        case_id: str,
        for_update: bool = False,
    ) -> StructuredCase | None:
        """Reconstruct a complete StructuredCase from persisted state without recalculation.

        Ensures case context, observations, answers, and revisions come from one consistent
        database state without taking shared locks that cause upgrade deadlocks.
        Refreshes ORM identity map cache via populate_existing=True.

        Args:
            case_id: The unique identifier of the case.
            for_update: If True, acquire an exclusive FOR UPDATE lock. Default is False.

        Returns:
            StructuredCase if found, None otherwise.
        """
        session, should_close = self._get_active_session()
        try:
            # 1. Acquire exclusive FOR UPDATE lock only if caller explicitly requested it
            if for_update:
                stmt_lock = (
                    select(CaseModel)
                    .where(CaseModel.case_id == case_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
                if session.scalars(stmt_lock).first() is None:
                    return None

            # 2. Consistent snapshot reconstruction loop (without holding FOR SHARE)
            case_model: CaseModel | None = None
            rev_models: list[AnalysisRevisionModel] = []
            obs_models: list[ObservationModel] = []
            qa_models: list[QuestionAnswerModel] = []
            cr_models: list[CaseCheckResultModel] = []
            conf_models: list[CaseCauseConfirmationModel] = []
            verified_snapshot = False

            max_retries = 3
            for attempt in range(max_retries):
                # Read revision marker BEFORE reading CaseModel or any case state
                start_rev = session.scalar(
                    select(AnalysisRevisionModel.revision_number)
                    .where(AnalysisRevisionModel.case_id == case_id)
                    .order_by(AnalysisRevisionModel.revision_number.desc())
                    .execution_options(populate_existing=True)
                )

                stmt_case = (
                    select(CaseModel)
                    .where(CaseModel.case_id == case_id)
                    .execution_options(populate_existing=True)
                )
                case_model = session.scalars(stmt_case).first()
                if case_model is None:
                    return None

                target_revision = start_rev if start_rev is not None else 1

                rev_models = list(
                    session.scalars(
                        select(AnalysisRevisionModel)
                        .where(
                            AnalysisRevisionModel.case_id == case_id,
                            AnalysisRevisionModel.revision_number <= target_revision,
                        )
                        .order_by(AnalysisRevisionModel.revision_number)
                        .execution_options(populate_existing=True)
                    ).all()
                )

                obs_models = list(
                    session.scalars(
                        select(ObservationModel)
                        .where(
                            ObservationModel.case_id == case_id,
                            ObservationModel.first_seen_revision <= target_revision,
                        )
                        .order_by(ObservationModel.id)
                        .execution_options(populate_existing=True)
                    ).all()
                )

                qa_models = list(
                    session.scalars(
                        select(QuestionAnswerModel)
                        .where(
                            QuestionAnswerModel.case_id == case_id,
                            QuestionAnswerModel.resulting_revision_number <= target_revision,
                        )
                        .order_by(
                            QuestionAnswerModel.resulting_revision_number,
                            QuestionAnswerModel.id,
                        )
                        .execution_options(populate_existing=True)
                    ).all()
                )

                cr_models = list(
                    session.scalars(
                        select(CaseCheckResultModel)
                        .where(
                            CaseCheckResultModel.case_id == case_id,
                            CaseCheckResultModel.resulting_revision_number <= target_revision,
                        )
                        .order_by(
                            CaseCheckResultModel.resulting_revision_number,
                            CaseCheckResultModel.id,
                        )
                        .execution_options(populate_existing=True)
                    ).all()
                )

                conf_models = list(
                    session.scalars(
                        select(CaseCauseConfirmationModel)
                        .where(
                            CaseCauseConfirmationModel.case_id == case_id,
                            CaseCauseConfirmationModel.resulting_revision_number <= target_revision,
                        )
                        .order_by(
                            CaseCauseConfirmationModel.resulting_revision_number,
                            CaseCauseConfirmationModel.id,
                        )
                        .execution_options(populate_existing=True)
                    ).all()
                )

                # Read revision marker AFTER all case state queries to verify snapshot integrity
                end_rev = session.scalar(
                    select(AnalysisRevisionModel.revision_number)
                    .where(AnalysisRevisionModel.case_id == case_id)
                    .order_by(AnalysisRevisionModel.revision_number.desc())
                    .execution_options(populate_existing=True)
                )

                # If an interleaved write committed during reconstruction, retry
                if end_rev != start_rev:
                    continue

                verified_snapshot = True
                break

            if not verified_snapshot:
                raise RuntimeError(
                    f"Could not obtain a verified consistent snapshot for case '{case_id}' "
                    f"after {max_retries} attempts due to concurrent modifications."
                )

            if case_model is None:
                return None

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

            previous_check_results: list[CheckResult] = []
            for cm in cr_models:
                try:
                    exec_status = CheckExecutionStatus(cm.execution_status)
                except ValueError:
                    try:
                        exec_status = CheckExecutionStatus(cm.execution_status.upper())
                    except ValueError:
                        exec_status = CheckExecutionStatus.COMPLETED

                try:
                    finding = CheckFinding(cm.finding)
                except ValueError:
                    try:
                        finding = CheckFinding(cm.finding.upper())
                    except ValueError:
                        finding = CheckFinding.INCONCLUSIVE

                try:
                    cr_src = EvidenceSource(cm.source)
                except ValueError:
                    cr_src = EvidenceSource.USER_CHECK_RESULT

                cr = CheckResult(
                    check_id=cm.check_id,
                    execution_status=exec_status,
                    finding=finding,
                    finding_details=cm.finding_details,
                    outcome=cm.outcome,
                    source=cr_src,
                    timestamp=cm.checked_at,
                )
                previous_check_results.append(cr)

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

            # 5. Issue condition
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
                previous_check_results=previous_check_results,
                analysis_revisions=analysis_revisions,
                issue_condition=issue_cond,
                confirmed_causes=[c.cause_id for c in conf_models],
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
        against concurrent updates. Validates that the input case reflects a consistent
        snapshot of persisted state and rejects torn or stale case state.

        Args:
            case: StructuredCase containing updated observations and previous answers.
            answer: The QuestionAnswer submitted by the technician.
            result: DiagnosisResult resulting from the question answer and re-ranking.
            expected_revision: The latest revision expected by the caller before appending.

        Returns:
            The newly created AnalysisRevisionModel.

        Raises:
            ValueError: On identity mismatch, contract violations, or inconsistent case state.
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
            stmt = (
                select(CaseModel)
                .where(CaseModel.case_id == case.case_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            db_case = session.scalars(stmt).first()
            if db_case is None:
                raise ValueError(f"Case '{case.case_id}' not found.")

            # 2. Get latest revision while holding row lock
            stmt_rev = (
                select(AnalysisRevisionModel.revision_number)
                .where(AnalysisRevisionModel.case_id == case.case_id)
                .order_by(AnalysisRevisionModel.revision_number.desc())
                .execution_options(populate_existing=True)
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

            # 3b. Consistency check: ensure case is not built on a torn or stale snapshot
            # All observations persisted up to latest_revision must be present in case.observations
            persisted_obs_ids = set(
                session.scalars(
                    select(ObservationModel.observation_id)
                    .where(
                        ObservationModel.case_id == case.case_id,
                        ObservationModel.first_seen_revision <= latest_revision,
                    )
                    .execution_options(populate_existing=True)
                ).all()
            )
            case_obs_ids = {o.id for o in case.observations}
            missing_obs = persisted_obs_ids - case_obs_ids
            if missing_obs:
                raise ValueError(
                    f"Inconsistent case state: case is missing persisted observations "
                    f"{sorted(missing_obs)} from revision {latest_revision} or earlier."
                )

            # All question answers persisted up to latest_revision must be represented in case.previous_answers
            persisted_qas = list(
                session.scalars(
                    select(QuestionAnswerModel)
                    .where(
                        QuestionAnswerModel.case_id == case.case_id,
                        QuestionAnswerModel.resulting_revision_number <= latest_revision,
                    )
                    .order_by(
                        QuestionAnswerModel.resulting_revision_number,
                        QuestionAnswerModel.id,
                    )
                    .execution_options(populate_existing=True)
                ).all()
            )
            if len(case.previous_answers) < len(persisted_qas):
                raise ValueError(
                    f"Inconsistent case state: case previous_answers has {len(case.previous_answers)} "
                    f"entries, but {len(persisted_qas)} answers are persisted up to revision {latest_revision}."
                )
            case_q_ids = [q.question_id for q in case.previous_answers]
            for pq in persisted_qas:
                if pq.question_id not in case_q_ids:
                    raise ValueError(
                        f"Inconsistent case state: case previous_answers is missing "
                        f"persisted question '{pq.question_id}' from revision {latest_revision} or earlier."
                    )

            # All check results persisted up to latest_revision must be represented in case.previous_check_results
            persisted_crs = list(
                session.scalars(
                    select(CaseCheckResultModel)
                    .where(
                        CaseCheckResultModel.case_id == case.case_id,
                        CaseCheckResultModel.resulting_revision_number <= latest_revision,
                    )
                    .order_by(
                        CaseCheckResultModel.resulting_revision_number,
                        CaseCheckResultModel.id,
                    )
                    .execution_options(populate_existing=True)
                ).all()
            )
            if len(case.previous_check_results) < len(persisted_crs):
                raise ValueError(
                    f"Inconsistent case state: case previous_check_results has {len(case.previous_check_results)} "
                    f"entries, but {len(persisted_crs)} check results are persisted up to revision {latest_revision}."
                )
            case_cr_ids = [c.check_id for c in case.previous_check_results]
            for pcr in persisted_crs:
                if pcr.check_id not in case_cr_ids:
                    raise ValueError(
                        f"Inconsistent case state: case previous_check_results is missing "
                        f"persisted check '{pcr.check_id}' from revision {latest_revision} or earlier."
                    )

            if case.analysis_revisions:
                case_rev_nums = {r.revision_number for r in case.analysis_revisions}
                persisted_rev_nums = set(
                    session.scalars(
                        select(AnalysisRevisionModel.revision_number)
                        .where(
                            AnalysisRevisionModel.case_id == case.case_id,
                            AnalysisRevisionModel.revision_number <= latest_revision,
                        )
                        .execution_options(populate_existing=True)
                    ).all()
                )
                missing_revs = persisted_rev_nums - case_rev_nums
                if missing_revs:
                    raise ValueError(
                        f"Inconsistent case state: case analysis_revisions is missing "
                        f"persisted revisions {sorted(missing_revs)}."
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
                    ).execution_options(populate_existing=True)
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

    def append_check_result_revision(
        self,
        case: StructuredCase,
        check_result: CheckResult,
        result: DiagnosisResult,
        expected_revision: int,
    ) -> AnalysisRevisionModel:
        """Atomically append a check result, new observations, and the resulting analysis revision.

        Enforces optimistic concurrency via expected_revision and locks the case row
        against concurrent updates. Validates that the input case reflects a consistent
        snapshot of persisted state and rejects torn or stale case state.

        Args:
            case: StructuredCase containing updated observations and previous check results.
            check_result: The CheckResult submitted by the technician.
            result: DiagnosisResult resulting from the check result and re-ranking.
            expected_revision: The latest revision expected by the caller before appending.

        Returns:
            The newly created AnalysisRevisionModel.

        Raises:
            ValueError: On identity mismatch, contract violations, or inconsistent case state.
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
            stmt = (
                select(CaseModel)
                .where(CaseModel.case_id == case.case_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            db_case = session.scalars(stmt).first()
            if db_case is None:
                raise ValueError(f"Case '{case.case_id}' not found.")

            # 2. Get latest revision while holding row lock
            stmt_rev = (
                select(AnalysisRevisionModel.revision_number)
                .where(AnalysisRevisionModel.case_id == case.case_id)
                .order_by(AnalysisRevisionModel.revision_number.desc())
                .execution_options(populate_existing=True)
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

            # 3b. Consistency check: ensure case is not built on a torn or stale snapshot
            # All observations persisted up to latest_revision must be present in case.observations
            persisted_obs_ids = set(
                session.scalars(
                    select(ObservationModel.observation_id)
                    .where(
                        ObservationModel.case_id == case.case_id,
                        ObservationModel.first_seen_revision <= latest_revision,
                    )
                    .execution_options(populate_existing=True)
                ).all()
            )
            case_obs_ids = {o.id for o in case.observations}
            missing_obs = persisted_obs_ids - case_obs_ids
            if missing_obs:
                raise ValueError(
                    f"Inconsistent case state: case is missing persisted observations "
                    f"{sorted(missing_obs)} from revision {latest_revision} or earlier."
                )

            # All question answers persisted up to latest_revision must be represented in case.previous_answers
            persisted_qas = list(
                session.scalars(
                    select(QuestionAnswerModel)
                    .where(
                        QuestionAnswerModel.case_id == case.case_id,
                        QuestionAnswerModel.resulting_revision_number <= latest_revision,
                    )
                    .order_by(
                        QuestionAnswerModel.resulting_revision_number,
                        QuestionAnswerModel.id,
                    )
                    .execution_options(populate_existing=True)
                ).all()
            )
            if len(case.previous_answers) < len(persisted_qas):
                raise ValueError(
                    f"Inconsistent case state: case previous_answers has {len(case.previous_answers)} "
                    f"entries, but {len(persisted_qas)} answers are persisted up to revision {latest_revision}."
                )
            case_q_ids = [q.question_id for q in case.previous_answers]
            for pq in persisted_qas:
                if pq.question_id not in case_q_ids:
                    raise ValueError(
                        f"Inconsistent case state: case previous_answers is missing "
                        f"persisted question '{pq.question_id}' from revision {latest_revision} or earlier."
                    )

            # All check results persisted up to latest_revision must be represented in case.previous_check_results
            persisted_crs = list(
                session.scalars(
                    select(CaseCheckResultModel)
                    .where(
                        CaseCheckResultModel.case_id == case.case_id,
                        CaseCheckResultModel.resulting_revision_number <= latest_revision,
                    )
                    .order_by(
                        CaseCheckResultModel.resulting_revision_number,
                        CaseCheckResultModel.id,
                    )
                    .execution_options(populate_existing=True)
                ).all()
            )
            if len(case.previous_check_results) < len(persisted_crs):
                raise ValueError(
                    f"Inconsistent case state: case previous_check_results has {len(case.previous_check_results)} "
                    f"entries, but {len(persisted_crs)} check results are persisted up to revision {latest_revision}."
                )
            case_cr_ids = [c.check_id for c in case.previous_check_results]
            for pcr in persisted_crs:
                if pcr.check_id not in case_cr_ids:
                    raise ValueError(
                        f"Inconsistent case state: case previous_check_results is missing "
                        f"persisted check '{pcr.check_id}' from revision {latest_revision} or earlier."
                    )

            if case.analysis_revisions:
                case_rev_nums = {r.revision_number for r in case.analysis_revisions}
                persisted_rev_nums = set(
                    session.scalars(
                        select(AnalysisRevisionModel.revision_number)
                        .where(
                            AnalysisRevisionModel.case_id == case.case_id,
                            AnalysisRevisionModel.revision_number <= latest_revision,
                        )
                        .execution_options(populate_existing=True)
                    ).all()
                )
                missing_revs = persisted_rev_nums - case_rev_nums
                if missing_revs:
                    raise ValueError(
                        f"Inconsistent case state: case analysis_revisions is missing "
                        f"persisted revisions {sorted(missing_revs)}."
                    )

            # 4. Persist the CaseCheckResultModel linked to new_revision_number
            cr_status_val = (
                check_result.execution_status.value
                if hasattr(check_result.execution_status, "value")
                else str(check_result.execution_status)
            )
            cr_finding_val = (
                check_result.finding.value
                if hasattr(check_result.finding, "value")
                else str(check_result.finding)
            )
            cr_source_val = (
                check_result.source.value
                if hasattr(check_result.source, "value")
                else str(check_result.source)
            )
            cr_model = CaseCheckResultModel(
                case_id=case.case_id,
                check_id=check_result.check_id,
                execution_status=cr_status_val,
                finding=cr_finding_val,
                finding_details=check_result.finding_details,
                outcome=check_result.outcome,
                source=cr_source_val,
                checked_at=check_result.timestamp,
                resulting_revision_number=new_revision_number,
            )
            session.add(cr_model)

            # 5. Insert only observations not already persisted for this case
            existing_obs_ids = set(
                session.scalars(
                    select(ObservationModel.observation_id).where(
                        ObservationModel.case_id == case.case_id
                    ).execution_options(populate_existing=True)
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

    def append_cause_confirmation_revision(
        self,
        case: StructuredCase,
        cause_id: str,
        confirmed_by: str,
        notes: str | None,
        result: DiagnosisResult,
        expected_revision: int,
    ) -> AnalysisRevisionModel:
        """Atomically append a root-cause confirmation event and the resulting analysis revision.

        Enforces optimistic concurrency via expected_revision and locks the case row
        against concurrent updates. Validates that the input case reflects a consistent
        snapshot of persisted state and rejects torn or stale case state.

        Args:
            case: StructuredCase containing confirmed causes and prior case history.
            cause_id: The cause identifier confirmed by the technician.
            confirmed_by: Identifier or role of the technician confirming the cause.
            notes: Optional technician notes or observations.
            result: DiagnosisResult resulting from explicit cause confirmation.
            expected_revision: The latest revision expected by the caller before appending.

        Returns:
            The newly created AnalysisRevisionModel.

        Raises:
            ValueError: On identity mismatch, contract violations, or inconsistent case state.
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
            stmt = (
                select(CaseModel)
                .where(CaseModel.case_id == case.case_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            db_case = session.scalars(stmt).first()
            if db_case is None:
                raise ValueError(f"Case '{case.case_id}' not found.")

            # 2. Get latest revision while holding row lock
            stmt_rev = (
                select(AnalysisRevisionModel.revision_number)
                .where(AnalysisRevisionModel.case_id == case.case_id)
                .order_by(AnalysisRevisionModel.revision_number.desc())
                .execution_options(populate_existing=True)
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

            # 3b. Consistency check: ensure case is not built on a torn or stale snapshot
            persisted_obs_ids = set(
                session.scalars(
                    select(ObservationModel.observation_id)
                    .where(
                        ObservationModel.case_id == case.case_id,
                        ObservationModel.first_seen_revision <= latest_revision,
                    )
                    .execution_options(populate_existing=True)
                ).all()
            )
            case_obs_ids = {o.id for o in case.observations}
            missing_obs = persisted_obs_ids - case_obs_ids
            if missing_obs:
                raise ValueError(
                    f"Inconsistent case state: case is missing persisted observations "
                    f"{sorted(missing_obs)} from revision {latest_revision} or earlier."
                )

            persisted_qas = list(
                session.scalars(
                    select(QuestionAnswerModel)
                    .where(
                        QuestionAnswerModel.case_id == case.case_id,
                        QuestionAnswerModel.resulting_revision_number <= latest_revision,
                    )
                    .order_by(
                        QuestionAnswerModel.resulting_revision_number,
                        QuestionAnswerModel.id,
                    )
                    .execution_options(populate_existing=True)
                ).all()
            )
            if len(case.previous_answers) < len(persisted_qas):
                raise ValueError(
                    f"Inconsistent case state: case previous_answers has {len(case.previous_answers)} "
                    f"entries, but {len(persisted_qas)} answers are persisted up to revision {latest_revision}."
                )
            case_q_ids = [q.question_id for q in case.previous_answers]
            for pq in persisted_qas:
                if pq.question_id not in case_q_ids:
                    raise ValueError(
                        f"Inconsistent case state: case previous_answers is missing "
                        f"persisted question '{pq.question_id}' from revision {latest_revision} or earlier."
                    )

            persisted_crs = list(
                session.scalars(
                    select(CaseCheckResultModel)
                    .where(
                        CaseCheckResultModel.case_id == case.case_id,
                        CaseCheckResultModel.resulting_revision_number <= latest_revision,
                    )
                    .order_by(
                        CaseCheckResultModel.resulting_revision_number,
                        CaseCheckResultModel.id,
                    )
                    .execution_options(populate_existing=True)
                ).all()
            )
            if len(case.previous_check_results) < len(persisted_crs):
                raise ValueError(
                    f"Inconsistent case state: case previous_check_results has {len(case.previous_check_results)} "
                    f"entries, but {len(persisted_crs)} check results are persisted up to revision {latest_revision}."
                )
            case_cr_ids = [c.check_id for c in case.previous_check_results]
            for pcr in persisted_crs:
                if pcr.check_id not in case_cr_ids:
                    raise ValueError(
                        f"Inconsistent case state: case previous_check_results is missing "
                        f"persisted check '{pcr.check_id}' from revision {latest_revision} or earlier."
                    )

            if case.analysis_revisions:
                case_rev_nums = {r.revision_number for r in case.analysis_revisions}
                persisted_rev_nums = set(
                    session.scalars(
                        select(AnalysisRevisionModel.revision_number)
                        .where(
                            AnalysisRevisionModel.case_id == case.case_id,
                            AnalysisRevisionModel.revision_number <= latest_revision,
                        )
                        .execution_options(populate_existing=True)
                    ).all()
                )
                missing_revs = persisted_rev_nums - case_rev_nums
                if missing_revs:
                    raise ValueError(
                        f"Inconsistent case state: case analysis_revisions is missing "
                        f"persisted revisions {sorted(missing_revs)}."
                    )

            # 4. Persist the CaseCauseConfirmationModel linked to new_revision_number
            conf_model = CaseCauseConfirmationModel(
                case_id=case.case_id,
                cause_id=cause_id,
                confirmed_by=confirmed_by or "technician",
                notes=notes,
                confirmed_at=result.analysis_revision.timestamp,
                resulting_revision_number=new_revision_number,
            )
            session.add(conf_model)

            # 5. Insert only observations not already persisted for this case (if any)
            existing_obs_ids = set(
                session.scalars(
                    select(ObservationModel.observation_id).where(
                        ObservationModel.case_id == case.case_id
                    ).execution_options(populate_existing=True)
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

    def append_lifecycle_event_revision(
        self,
        case: StructuredCase,
        event_type: str,
        prior_issue_condition: str,
        resulting_issue_condition: str,
        actor: str,
        details: str,
        verification_passed: bool | None,
        result: DiagnosisResult,
        expected_revision: int,
    ) -> AnalysisRevisionModel:
        """Atomically append an issue lifecycle event and the resulting analysis revision.

        Enforces optimistic concurrency via expected_revision and locks the case row
        against concurrent updates. Validates that the input case reflects a consistent
        snapshot of persisted state and rejects torn or stale case state.

        Args:
            case: StructuredCase containing current case state.
            event_type: "RECOVERY_ACTION" or "RECOVERY_VERIFICATION".
            prior_issue_condition: Condition before transition.
            resulting_issue_condition: Condition after transition.
            actor: Performer or verifier role/name.
            details: Details or notes.
            verification_passed: Verification boolean or None.
            result: DiagnosisResult from diagnostic engine.
            expected_revision: Expected current revision for optimistic locking.

        Returns:
            The newly created AnalysisRevisionModel.

        Raises:
            ValueError: On identity mismatch, contract violations, or inconsistent case state.
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
            stmt = (
                select(CaseModel)
                .where(CaseModel.case_id == case.case_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            db_case = session.scalars(stmt).first()
            if db_case is None:
                raise ValueError(f"Case '{case.case_id}' not found.")

            # 2. Get latest revision while holding row lock
            stmt_rev = (
                select(AnalysisRevisionModel.revision_number)
                .where(AnalysisRevisionModel.case_id == case.case_id)
                .order_by(AnalysisRevisionModel.revision_number.desc())
                .execution_options(populate_existing=True)
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

            # 3b. Consistency checks (observations, answers, check results, revisions)
            persisted_obs_ids = set(
                session.scalars(
                    select(ObservationModel.observation_id)
                    .where(
                        ObservationModel.case_id == case.case_id,
                        ObservationModel.first_seen_revision <= latest_revision,
                    )
                    .execution_options(populate_existing=True)
                ).all()
            )
            case_obs_ids = {o.id for o in case.observations}
            missing_obs = persisted_obs_ids - case_obs_ids
            if missing_obs:
                raise ValueError(
                    f"Inconsistent case state: case is missing persisted observations "
                    f"{sorted(missing_obs)} from revision {latest_revision} or earlier."
                )

            persisted_qas = list(
                session.scalars(
                    select(QuestionAnswerModel)
                    .where(
                        QuestionAnswerModel.case_id == case.case_id,
                        QuestionAnswerModel.resulting_revision_number <= latest_revision,
                    )
                    .order_by(
                        QuestionAnswerModel.resulting_revision_number,
                        QuestionAnswerModel.id,
                    )
                    .execution_options(populate_existing=True)
                ).all()
            )
            if len(case.previous_answers) < len(persisted_qas):
                raise ValueError(
                    f"Inconsistent case state: case previous_answers has {len(case.previous_answers)} "
                    f"entries, but {len(persisted_qas)} answers are persisted up to revision {latest_revision}."
                )
            case_q_ids = [q.question_id for q in case.previous_answers]
            for pq in persisted_qas:
                if pq.question_id not in case_q_ids:
                    raise ValueError(
                        f"Inconsistent case state: case previous_answers is missing "
                        f"persisted question '{pq.question_id}' from revision {latest_revision} or earlier."
                    )

            persisted_crs = list(
                session.scalars(
                    select(CaseCheckResultModel)
                    .where(
                        CaseCheckResultModel.case_id == case.case_id,
                        CaseCheckResultModel.resulting_revision_number <= latest_revision,
                    )
                    .order_by(
                        CaseCheckResultModel.resulting_revision_number,
                        CaseCheckResultModel.id,
                    )
                    .execution_options(populate_existing=True)
                ).all()
            )
            if len(case.previous_check_results) < len(persisted_crs):
                raise ValueError(
                    f"Inconsistent case state: case previous_check_results has {len(case.previous_check_results)} "
                    f"entries, but {len(persisted_crs)} check results are persisted up to revision {latest_revision}."
                )
            case_cr_ids = [c.check_id for c in case.previous_check_results]
            for pcr in persisted_crs:
                if pcr.check_id not in case_cr_ids:
                    raise ValueError(
                        f"Inconsistent case state: case previous_check_results is missing "
                        f"persisted check '{pcr.check_id}' from revision {latest_revision} or earlier."
                    )

            if case.analysis_revisions:
                case_rev_nums = {r.revision_number for r in case.analysis_revisions}
                persisted_rev_nums = set(
                    session.scalars(
                        select(AnalysisRevisionModel.revision_number)
                        .where(
                            AnalysisRevisionModel.case_id == case.case_id,
                            AnalysisRevisionModel.revision_number <= latest_revision,
                        )
                        .execution_options(populate_existing=True)
                    ).all()
                )
                missing_revs = persisted_rev_nums - case_rev_nums
                if missing_revs:
                    raise ValueError(
                        f"Inconsistent case state: case analysis_revisions is missing "
                        f"persisted revisions {sorted(missing_revs)}."
                    )

            # 4. Persist the CaseLifecycleEventModel linked to new_revision_number
            resolved_prior_condition = db_case.issue_condition or prior_issue_condition
            event_model = CaseLifecycleEventModel(
                case_id=case.case_id,
                event_type=event_type,
                prior_issue_condition=resolved_prior_condition,
                resulting_issue_condition=resulting_issue_condition,
                resulting_revision_number=new_revision_number,
                actor=actor or "technician",
                details=details or "",
                verification_passed=verification_passed,
                created_at=result.analysis_revision.timestamp,
            )
            session.add(event_model)

            # 5. Insert only observations not already persisted for this case (if any)
            existing_obs_ids = set(
                session.scalars(
                    select(ObservationModel.observation_id).where(
                        ObservationModel.case_id == case.case_id
                    ).execution_options(populate_existing=True)
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

            # 7. Update top-level case state
            db_case.issue_condition = resulting_issue_condition
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

    def append_recovery_action_revision(
        self,
        case: StructuredCase,
        performed_by: str,
        recovery_details: str,
        result: DiagnosisResult,
        expected_revision: int,
    ) -> AnalysisRevisionModel:
        """Atomically append a recovery action event and the resulting analysis revision."""
        prior_cond = (
            case.issue_condition.value
            if hasattr(case.issue_condition, "value")
            else str(case.issue_condition)
        )
        resulting_cond = (
            result.issue_condition.value
            if hasattr(result.issue_condition, "value")
            else str(result.issue_condition)
        )
        return self.append_lifecycle_event_revision(
            case=case,
            event_type="RECOVERY_ACTION",
            prior_issue_condition=prior_cond,
            resulting_issue_condition=resulting_cond,
            actor=performed_by or "technician",
            details=recovery_details,
            verification_passed=None,
            result=result,
            expected_revision=expected_revision,
        )

    def append_recovery_verification_revision(
        self,
        case: StructuredCase,
        verified_by: str,
        verification_passed: bool,
        verification_details: str,
        result: DiagnosisResult,
        expected_revision: int,
    ) -> AnalysisRevisionModel:
        """Atomically append a recovery verification event and the resulting analysis revision."""
        prior_cond = (
            case.issue_condition.value
            if hasattr(case.issue_condition, "value")
            else str(case.issue_condition)
        )
        resulting_cond = (
            result.issue_condition.value
            if hasattr(result.issue_condition, "value")
            else str(result.issue_condition)
        )
        return self.append_lifecycle_event_revision(
            case=case,
            event_type="RECOVERY_VERIFICATION",
            prior_issue_condition=prior_cond,
            resulting_issue_condition=resulting_cond,
            actor=verified_by or "technician",
            details=verification_details,
            verification_passed=verification_passed,
            result=result,
            expected_revision=expected_revision,
        )
