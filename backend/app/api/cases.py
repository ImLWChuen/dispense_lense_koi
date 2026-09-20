"""FastAPI route handlers for durable case lifecycle operations."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.knowledge import get_action_by_id, get_check_by_id, load_questions

from app.db.repository import CaseRepository, StaleRevisionError
from app.db.session import get_db
from app.schemas.case import (
    CaseAnswerResponse,
    CaseCauseConfirmationResponse,
    CaseCheckResponse,
    CaseCheckResultResponse,
    CaseObservationResponse,
    CaseRecoveryActionResponse,
    CaseRecoveryVerificationResponse,
    CaseRecurrenceResponse,
    CaseReportResponse,
    CauseConfirmationRecord,
    CheckExecutionRecord,
    CheckResultRecord,
    CreateCaseRequest,
    DurableCaseResponse,
    LifecycleEventRecord,
    QuestionAnswerRecord,
    SubmitAnswerRequest,
    SubmitCauseConfirmationRequest,
    SubmitCheckRequest,
    SubmitCheckResultRequest,
    SubmitRecoveryActionRequest,
    SubmitRecoveryVerificationRequest,
    SubmitRecurrenceRequest,
)
from app.schemas.diagnosis import (
    AnalysisRevision,
    CauseConclusion,
    CheckExecutionStatus,
    CheckFinding,
    CheckResult,
    DiagnosisResult,
    EvidenceSource,
    IssueCondition,
    ObservationType,
    QuestionAnswer,
    StatementType,
)
from app.knowledge import get_causes_for_defect, get_defect_by_code
from app.services.diagnosis.engine import CheckResultHandler, DiagnosticEngine, StateManager
from app.services.diagnosis.question_answer_handler import QuestionAnswerHandler
from app.services.reporting import build_case_report, render_case_report_pdf
from app.services.ai.llm_service import LLMService
from app.services.ai.prompt_manager import PromptManager
from app.api.analytics import broadcast_analytics_update

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_obs_metadata(obs: Any) -> dict[str, Any]:
    meta = getattr(obs, "observation_metadata", None)
    if isinstance(meta, dict):
        return meta
    meta = getattr(obs, "metadata", None)
    if isinstance(meta, dict):
        return meta
    return {}


def get_diagnosis_engine() -> DiagnosticEngine:
    """Dependency provider returning an instance of the diagnostic engine."""
    return DiagnosticEngine()


def get_case_repository(session: Session = Depends(get_db)) -> CaseRepository:
    """Dependency provider returning an active CaseRepository instance."""
    return CaseRepository(session)


@router.post(
    "",
    response_model=DurableCaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create and evaluate a durable diagnostic case",
    description=(
        "Submits an initial dispensing problem report, executes the deterministic "
        "diagnostic engine, and atomically persists the case context, generated/client "
        "observations, and immutable revision-1 diagnosis snapshot in PostgreSQL."
    ),
)
def create_durable_case(
    request: CreateCaseRequest,
    engine: DiagnosticEngine = Depends(get_diagnosis_engine),
    repository: CaseRepository = Depends(get_case_repository),
    session: Session = Depends(get_db),
) -> DurableCaseResponse:
    """Create a new diagnostic case, evaluate it, and persist it atomically."""
    try:
        domain_request = request.to_diagnosis_request()
        case = engine.prepare_case(domain_request)
        result = engine.diagnose(case)

        if result.analysis_revision is None:
            raise HTTPException(
                status_code=422,
                detail="Diagnostic evaluation could not identify a defect category from the provided evidence.",
            )

        defect_to_check = case.defect_code or result.defect
        if not case.defect_name and defect_to_check:
            defect_def = get_defect_by_code(defect_to_check)
            if defect_def:
                case.defect_name = defect_def.name
                if not result.defect_name:
                    result.defect_name = defect_def.name

        repository.save_initial_case(case, result)
        session.commit()
        broadcast_analytics_update("CASE_CREATED", {"case_id": case.case_id})

        observations = [
            CaseObservationResponse(
                id=obs.id,
                observation_id=obs.id,
                observation_type=obs.observation_type,
                value=obs.value,
                original_text=obs.original_text,
                statement_type=obs.statement_type,
                source=obs.source,
                confidence=obs.confidence,
                timestamp=obs.timestamp,
                created_at=obs.timestamp,
                first_seen_revision=1,
                metadata=_get_obs_metadata(obs),
            )
            for obs in case.observations
        ]

        return DurableCaseResponse(
            case_id=case.case_id,
            description=case.description or "",
            material=case.material,
            method=case.method,
            machine_context=case.machine_context,
            defect_code=case.defect_code or result.defect,
            defect_name=case.defect_name or result.defect_name,
            issue_condition=case.issue_condition,
            created_at=case.created_at,
            observations=observations,
            initial_diagnosis=result,
            diagnosis=result,
        )
    except HTTPException:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        logger.exception("Unexpected error during durable case creation")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during case creation.",
        )

@router.get(
    "",
    response_model=list[DurableCaseResponse],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
    },
    summary="Retrieve all diagnostic cases",
    description="Retrieves a list of all persisted diagnostic cases with their initial analysis.",
)
def list_durable_cases(
    repository: CaseRepository = Depends(get_case_repository),
) -> list[DurableCaseResponse]:
    """Retrieve all existing cases and their initial diagnosis from persistent storage."""
    try:
        case_models = repository.get_all_cases()
        responses = []

        for case_model in case_models:
            canonical_id = case_model.case_id
            obs_models = repository.get_case_observations(canonical_id)
            rev_model = repository.get_analysis_revision(canonical_id, revision_number=1)

            if not rev_model:
                continue

            initial_diagnosis = DiagnosisResult.model_validate(rev_model.result_snapshot)

            revisions = repository.list_case_revisions(canonical_id)
            latest_rev_num = max(revisions) if revisions else 1
            latest_rev_model = repository.get_analysis_revision(canonical_id, revision_number=latest_rev_num)
            latest_diagnosis = DiagnosisResult.model_validate(latest_rev_model.result_snapshot) if latest_rev_model else initial_diagnosis

            observations = [
                CaseObservationResponse(
                    id=obs.observation_id,
                    observation_id=obs.observation_id,
                    observation_type=(
                        ObservationType(obs.observation_type)
                        if obs.observation_type in ObservationType._value2member_map_
                        else obs.observation_type
                    ),
                    value=obs.value,
                    original_text=obs.original_text,
                    statement_type=(
                        StatementType(obs.statement_type)
                        if obs.statement_type in StatementType._value2member_map_
                        else obs.statement_type
                    ),
                    source=(
                        EvidenceSource(obs.source)
                        if obs.source in EvidenceSource._value2member_map_
                        else obs.source
                    ),
                    confidence=obs.confidence,
                    timestamp=obs.created_at,
                    created_at=obs.created_at,
                    first_seen_revision=obs.first_seen_revision,
                    metadata=_get_obs_metadata(obs),
                )
                for obs in obs_models
            ]

            issue_cond = (
                IssueCondition(case_model.issue_condition)
                if case_model.issue_condition in IssueCondition._value2member_map_
                else case_model.issue_condition
            )

            responses.append(
                DurableCaseResponse(
                    case_id=case_model.case_id,
                    description=case_model.description,
                    material=case_model.material,
                    method=case_model.method,
                    machine_context=case_model.machine_context,
                    defect_code=case_model.defect_code,
                    defect_name=case_model.defect_name or initial_diagnosis.defect_name,
                    issue_condition=issue_cond,
                    created_at=case_model.created_at,
                    observations=observations,
                    initial_diagnosis=initial_diagnosis,
                    diagnosis=latest_diagnosis,
                )
            )

        return responses
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving cases list: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving cases.",
        ) from None



@router.get(
    "/{case_id}",
    response_model=DurableCaseResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Case not found"},
    },
    summary="Retrieve a persisted diagnostic case",
    description=(
        "Retrieves a previously persisted diagnostic case by canonical UUID, "
        "including its case context, observations with provenance, and immutable "
        "initial analysis revision snapshot. Performs no diagnostic recalculation."
    ),
)
def get_durable_case(
    case_id: str,
    repository: CaseRepository = Depends(get_case_repository),
) -> DurableCaseResponse:
    """Retrieve an existing case and its initial diagnosis from persistent storage."""
    try:
        try:
            uuid_obj = uuid.UUID(case_id)
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(
                status_code=422,
                detail=f"Invalid case ID format: '{case_id}' must be a valid UUID.",
            )

        canonical_id = str(uuid_obj)
        case_model = repository.get_case(canonical_id)
        if case_model is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Case '{canonical_id}' not found.",
            )

        obs_models = repository.get_case_observations(canonical_id)
        rev_model = repository.get_analysis_revision(canonical_id, revision_number=1)
        if rev_model is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Initial diagnosis revision for case '{canonical_id}' not found.",
            )

        initial_diagnosis = DiagnosisResult.model_validate(rev_model.result_snapshot)

        revisions = repository.list_case_revisions(canonical_id)
        latest_rev_num = max(revisions) if revisions else 1
        latest_rev_model = repository.get_analysis_revision(canonical_id, revision_number=latest_rev_num)
        latest_diagnosis = DiagnosisResult.model_validate(latest_rev_model.result_snapshot) if latest_rev_model else initial_diagnosis

        ans_models = repository.get_case_question_answers(canonical_id)
        chk_models = repository.get_case_check_executions(canonical_id)

        questions_dict = {q.id: q for q in load_questions()}
        previous_answers = []
        for qm in ans_models:
            qdef = questions_dict.get(qm.question_id)
            previous_answers.append(
                QuestionAnswerRecord(
                    question_id=qm.question_id,
                    answer_value=qm.answer_value,
                    answer_text=qm.answer_text,
                    source=(
                        EvidenceSource(qm.source)
                        if qm.source in EvidenceSource._value2member_map_
                        else qm.source
                    ),
                    answered_at=qm.answered_at,
                    resulting_revision_number=qm.resulting_revision_number,
                    text=qdef.text if qdef else None,
                    reasoning=qdef.purpose if qdef else None,
                    options=list(qdef.evidence_mapping.keys()) if qdef and qdef.evidence_mapping else None,
                )
            )

        previous_check_results = []
        for cm in chk_models:
            cdef = get_check_by_id(cm.check_id)
            previous_check_results.append(
                CheckResultRecord(
                    check_id=cm.check_id,
                    execution_status=(
                        CheckExecutionStatus(cm.status)
                        if cm.status in CheckExecutionStatus._value2member_map_
                        else cm.status
                    ),
                    finding=(
                        CheckFinding(cm.finding)
                        if cm.finding in CheckFinding._value2member_map_
                        else cm.finding
                    ),
                    finding_details=cm.notes,
                    outcome=None,
                    source=EvidenceSource.USER_CHECK_RESULT,
                    checked_at=cm.executed_at,
                    resulting_revision_number=cm.resulting_revision_number,
                    name=cdef.name if cdef else f"Check {cm.check_id}",
                    description=cdef.description if cdef else None,
                    procedure=cdef.procedure if cdef else "Historical check record.",
                    effort_level=cdef.effort_level if cdef else "low",
                    target_causes=cdef.applicable_causes if cdef else [],
                )
            )

        analysis_revisions = []
        for rev_num in sorted(revisions):
            rev_model_hist = repository.get_analysis_revision(canonical_id, revision_number=rev_num)
            if rev_model_hist and rev_model_hist.result_snapshot:
                snapshot_dict = rev_model_hist.result_snapshot
                if "analysis_revision" in snapshot_dict and snapshot_dict["analysis_revision"]:
                    analysis_revisions.append(AnalysisRevision.model_validate(snapshot_dict["analysis_revision"]))

        observations = [
            CaseObservationResponse(
                id=obs.observation_id,
                observation_id=obs.observation_id,
                observation_type=(
                    ObservationType(obs.observation_type)
                    if obs.observation_type in ObservationType._value2member_map_
                    else obs.observation_type
                ),
                value=obs.value,
                original_text=obs.original_text,
                statement_type=(
                    StatementType(obs.statement_type)
                    if obs.statement_type in StatementType._value2member_map_
                    else obs.statement_type
                ),
                source=(
                    EvidenceSource(obs.source)
                    if obs.source in EvidenceSource._value2member_map_
                    else obs.source
                ),
                confidence=obs.confidence,
                timestamp=obs.created_at,
                created_at=obs.created_at,
                first_seen_revision=obs.first_seen_revision,
                metadata=_get_obs_metadata(obs),
            )
            for obs in obs_models
        ]

        issue_cond = (
            IssueCondition(case_model.issue_condition)
            if case_model.issue_condition in IssueCondition._value2member_map_
            else case_model.issue_condition
        )

        return DurableCaseResponse(
            case_id=case_model.case_id,
            description=case_model.description,
            material=case_model.material,
            method=case_model.method,
            machine_context=case_model.machine_context,
            defect_code=case_model.defect_code,
            defect_name=case_model.defect_name,
            issue_condition=issue_cond,
            created_at=case_model.created_at,
            observations=observations,
            previous_answers=previous_answers,
            previous_check_results=previous_check_results,
            analysis_revisions=analysis_revisions,
            initial_diagnosis=initial_diagnosis,
            diagnosis=latest_diagnosis,
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error during durable case retrieval")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving the case.",
        )


@router.post(
    "/{case_id}/answers",
    response_model=CaseAnswerResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Case not found"},
        status.HTTP_409_CONFLICT: {"description": "Stale expected revision"},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Validation error or invalid question/answer"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
    },
    summary="Submit a technician answer to a diagnostic question",
    description=(
        "Submits a technician answer for an active durable case, executes Member 2's "
        "question-answer workflow, evaluates the next immutable analysis revision, "
        "and atomically persists the answer, any new observations, and the revision snapshot."
    ),
)
def submit_case_answer(
    case_id: str,
    request: SubmitAnswerRequest,
    engine: DiagnosticEngine = Depends(get_diagnosis_engine),
    repository: CaseRepository = Depends(get_case_repository),
    session: Session = Depends(get_db),
) -> CaseAnswerResponse:
    """Submit a question answer against an existing durable case and advance its revision."""
    try:
        try:
            uuid_obj = uuid.UUID(case_id)
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid case ID format: '{case_id}' must be a valid UUID.",
            )

        canonical_id = str(uuid_obj)

        case = repository.load_structured_case(canonical_id)
        if case is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Case '{canonical_id}' not found.",
            )

        current_rev = (
            case.analysis_revisions[-1].revision_number
            if case.analysis_revisions
            else 1
        )
        if request.expected_revision != current_rev:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Stale revision for case '{canonical_id}': expected revision "
                    f"{request.expected_revision}, but current revision is {current_rev}."
                ),
            )

        try:
            qa_result = QuestionAnswerHandler.handle(
                question_id=request.question_id,
                answer_value=request.answer,
                answer_text=request.answer_text,
                source=EvidenceSource.USER,
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            )

        domain_answer = QuestionAnswer(
            question_id=qa_result.question_id,
            answer_value=qa_result.answer_value,
            answer_text=request.answer_text,
            source=EvidenceSource.USER,
            timestamp=datetime.now(timezone.utc),
        )

        updated_case, result = engine.submit_question_answer(case, domain_answer)

        try:
            rev_model = repository.append_question_answer_revision(
                case=updated_case,
                answer=domain_answer,
                result=result,
                expected_revision=request.expected_revision,
            )

            target_revision = rev_model.revision_number

            case_model = repository.get_case(canonical_id)
            if case_model is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Case '{canonical_id}' not found.",
                )

            obs_models = repository.get_case_observations(canonical_id, max_revision=target_revision)
            rev1_model = repository.get_analysis_revision(canonical_id, revision_number=1)
            if rev1_model is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Initial diagnosis revision for case '{canonical_id}' not found.",
                )

            initial_diagnosis = DiagnosisResult.model_validate(rev1_model.result_snapshot)
            qa_models = repository.get_case_question_answers(canonical_id, max_revision=target_revision)
            cr_models = repository.get_case_check_executions(canonical_id, max_revision=target_revision)

            observations = [
                CaseObservationResponse(
                    id=obs.observation_id,
                    observation_id=obs.observation_id,
                    observation_type=(
                        ObservationType(obs.observation_type)
                        if obs.observation_type in ObservationType._value2member_map_
                        else obs.observation_type
                    ),
                    value=obs.value,
                    original_text=obs.original_text,
                    statement_type=(
                        StatementType(obs.statement_type)
                        if obs.statement_type in StatementType._value2member_map_
                        else obs.statement_type
                    ),
                    source=(
                        EvidenceSource(obs.source)
                        if obs.source in EvidenceSource._value2member_map_
                        else obs.source
                    ),
                    confidence=obs.confidence,
                    timestamp=obs.created_at,
                    created_at=obs.created_at,
                    first_seen_revision=obs.first_seen_revision,
                    metadata=_get_obs_metadata(obs),
                )
                for obs in obs_models
                if obs.first_seen_revision <= target_revision
            ]

            previous_answers = [
                QuestionAnswerRecord(
                    question_id=qm.question_id,
                    answer_value=qm.answer_value,
                    answer_text=qm.answer_text,
                    source=(
                        EvidenceSource(qm.source)
                        if qm.source in EvidenceSource._value2member_map_
                        else qm.source
                    ),
                    answered_at=qm.answered_at,
                    resulting_revision_number=qm.resulting_revision_number,
                )
                for qm in qa_models
                if qm.resulting_revision_number <= target_revision
            ]

            previous_check_results = [
                CheckResultRecord(
                    check_id=cm.check_id,
                    execution_status=(
                        CheckExecutionStatus(cm.status)
                        if cm.status in CheckExecutionStatus._value2member_map_
                        else cm.status
                    ),
                    finding=(
                        CheckFinding(cm.finding)
                        if cm.finding in CheckFinding._value2member_map_
                        else cm.finding
                    ),
                    finding_details=cm.notes,
                    outcome=None,
                    source=EvidenceSource.USER_CHECK_RESULT,
                    checked_at=cm.executed_at,
                    resulting_revision_number=cm.resulting_revision_number,
                )
                for cm in cr_models
                if cm.resulting_revision_number <= target_revision
            ]

            matching_submitted = [
                a for a in previous_answers if a.resulting_revision_number == target_revision
            ]
            if not matching_submitted:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Submitted answer record not found for the resulting revision.",
                )
            submitted_answer = matching_submitted[-1]

            issue_cond = (
                IssueCondition(case_model.issue_condition)
                if case_model.issue_condition in IssueCondition._value2member_map_
                else case_model.issue_condition
            )

            response = CaseAnswerResponse(
                case_id=case_model.case_id,
                description=case_model.description,
                material=case_model.material,
                method=case_model.method,
                machine_context=case_model.machine_context,
                defect_code=case_model.defect_code,
                defect_name=case_model.defect_name,
                issue_condition=issue_cond,
                created_at=case_model.created_at,
                observations=observations,
                initial_diagnosis=initial_diagnosis,
                diagnosis=result,
                current_revision=target_revision,
                submitted_answer=submitted_answer,
                previous_answers=previous_answers,
                previous_check_results=previous_check_results,
                next_question=result.next_question,
                next_check=result.next_check,
            )

            session.commit()
            return response
        except StaleRevisionError as e:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            )
        except HTTPException:
            session.rollback()
            raise
        except Exception:
            session.rollback()
            logger.exception("Unexpected error during question answer persistence")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred while persisting the question answer revision.",
            )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error during question answer submission")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while submitting the question answer.",
        )


@router.post(
    "/{case_id}/check-results",
    response_model=CaseCheckResultResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Case not found"},
        status.HTTP_409_CONFLICT: {"description": "Stale expected revision"},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Validation error or invalid check result"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
    },
    summary="Submit a technician troubleshooting check result",
    description=(
        "Submits a technician troubleshooting check result for an active durable case, "
        "executes Member 2's check-result workflow, evaluates the next immutable analysis revision, "
        "and atomically persists the check result, any new observations, and the revision snapshot."
    ),
)
def submit_case_check_result(
    case_id: str,
    request: SubmitCheckResultRequest,
    engine: DiagnosticEngine = Depends(get_diagnosis_engine),
    repository: CaseRepository = Depends(get_case_repository),
    session: Session = Depends(get_db),
) -> CaseCheckResultResponse:
    """Submit a troubleshooting check result against an existing durable case and advance its revision."""
    try:
        try:
            uuid_obj = uuid.UUID(case_id)
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid case ID format: '{case_id}' must be a valid UUID.",
            )

        canonical_id = str(uuid_obj)

        case = repository.load_structured_case(canonical_id)
        if case is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Case '{canonical_id}' not found.",
            )

        current_rev = (
            case.analysis_revisions[-1].revision_number
            if case.analysis_revisions
            else 1
        )
        if request.expected_revision != current_rev:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Stale revision for case '{canonical_id}': expected revision "
                    f"{request.expected_revision}, but current revision is {current_rev}."
                ),
            )

        # Reject unfinished execution statuses before domain execution or persistence
        if request.execution_status in (
            CheckExecutionStatus.PENDING,
            CheckExecutionStatus.IN_PROGRESS,
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Cannot submit check result with unfinished execution status: '{request.execution_status.value}'. "
                    "Check must be completed, blocked, failed, skipped, unknown, or not applicable."
                ),
            )

        # Validate check_id and outcome using existing domain CheckResultHandler
        domain_check = CheckResult(
            check_id=request.check_id,
            execution_status=request.execution_status,
            finding=request.finding,
            finding_details=request.finding_details,
            outcome=request.outcome,
            source=EvidenceSource.USER_CHECK_RESULT,
            timestamp=datetime.now(timezone.utc),
        )

        try:
            # CheckResultHandler.handle validates check_id and outcome against actions.json
            CheckResultHandler.handle(domain_check)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            )

        updated_case, result = engine.submit_check_result(case, domain_check)

        try:
            rev_model = repository.append_check_result_revision(
                case=updated_case,
                check_result=domain_check,
                result=result,
                expected_revision=request.expected_revision,
            )

            target_revision = rev_model.revision_number

            case_model = repository.get_case(canonical_id)
            if case_model is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Case '{canonical_id}' not found.",
                )

            obs_models = repository.get_case_observations(canonical_id, max_revision=target_revision)
            rev1_model = repository.get_analysis_revision(canonical_id, revision_number=1)
            if rev1_model is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Initial diagnosis revision for case '{canonical_id}' not found.",
                )

            initial_diagnosis = DiagnosisResult.model_validate(rev1_model.result_snapshot)
            qa_models = repository.get_case_question_answers(canonical_id, max_revision=target_revision)
            cr_models = repository.get_case_check_results(canonical_id, max_revision=target_revision)

            observations = [
                CaseObservationResponse(
                    id=obs.observation_id,
                    observation_id=obs.observation_id,
                    observation_type=(
                        ObservationType(obs.observation_type)
                        if obs.observation_type in ObservationType._value2member_map_
                        else obs.observation_type
                    ),
                    value=obs.value,
                    original_text=obs.original_text,
                    statement_type=(
                        StatementType(obs.statement_type)
                        if obs.statement_type in StatementType._value2member_map_
                        else obs.statement_type
                    ),
                    source=(
                        EvidenceSource(obs.source)
                        if obs.source in EvidenceSource._value2member_map_
                        else obs.source
                    ),
                    confidence=obs.confidence,
                    timestamp=obs.created_at,
                    created_at=obs.created_at,
                    first_seen_revision=obs.first_seen_revision,
                    metadata=_get_obs_metadata(obs),
                )
                for obs in obs_models
                if obs.first_seen_revision <= target_revision
            ]

            previous_answers = [
                QuestionAnswerRecord(
                    question_id=qm.question_id,
                    answer_value=qm.answer_value,
                    answer_text=qm.answer_text,
                    source=(
                        EvidenceSource(qm.source)
                        if qm.source in EvidenceSource._value2member_map_
                        else qm.source
                    ),
                    answered_at=qm.answered_at,
                    resulting_revision_number=qm.resulting_revision_number,
                )
                for qm in qa_models
                if qm.resulting_revision_number <= target_revision
            ]

            previous_check_results = [
                CheckResultRecord(
                    check_id=cm.check_id,
                    execution_status=(
                        CheckExecutionStatus(cm.execution_status)
                        if cm.execution_status in CheckExecutionStatus._value2member_map_
                        else cm.execution_status
                    ),
                    finding=(
                        CheckFinding(cm.finding)
                        if cm.finding in CheckFinding._value2member_map_
                        else cm.finding
                    ),
                    finding_details=cm.finding_details,
                    outcome=cm.outcome,
                    source=(
                        EvidenceSource(cm.source)
                        if cm.source in EvidenceSource._value2member_map_
                        else cm.source
                    ),
                    checked_at=cm.checked_at,
                    resulting_revision_number=cm.resulting_revision_number,
                )
                for cm in cr_models
                if cm.resulting_revision_number <= target_revision
            ]

            matching_submitted = [
                c for c in previous_check_results if c.resulting_revision_number == target_revision
            ]
            if not matching_submitted:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Submitted check result record not found for the resulting revision.",
                )
            submitted_check_result = matching_submitted[-1]

            issue_cond = (
                IssueCondition(case_model.issue_condition)
                if case_model.issue_condition in IssueCondition._value2member_map_
                else case_model.issue_condition
            )

            response = CaseCheckResultResponse(
                case_id=case_model.case_id,
                description=case_model.description,
                material=case_model.material,
                method=case_model.method,
                machine_context=case_model.machine_context,
                defect_code=case_model.defect_code,
                defect_name=case_model.defect_name,
                issue_condition=issue_cond,
                created_at=case_model.created_at,
                observations=observations,
                initial_diagnosis=initial_diagnosis,
                diagnosis=result,
                current_revision=target_revision,
                submitted_check_result=submitted_check_result,
                previous_check_results=previous_check_results,
                previous_answers=previous_answers,
                next_question=result.next_question,
                next_check=result.next_check,
            )

            session.commit()
            return response
        except StaleRevisionError as e:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            )
        except HTTPException:
            session.rollback()
            raise
        except Exception:
            session.rollback()
            logger.exception("Unexpected error during check result persistence")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred while persisting the check result revision.",
            )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error during check result submission")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while submitting the check result.",
        )


@router.post(
    "/{case_id}/checks",
    response_model=CaseCheckResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Case not found"},
        status.HTTP_409_CONFLICT: {"description": "Stale expected revision"},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Validation error or invalid check/status/finding"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
    },
    summary="Submit a technician troubleshooting check execution result",
    description=(
        "Submits an executed troubleshooting check result for an active durable case, "
        "executes Member 2's check result handler, evaluates the next immutable analysis revision, "
        "and atomically persists the check execution, any new observations, and the revision snapshot."
    ),
)
def submit_case_check(
    case_id: str,
    request: SubmitCheckRequest,
    engine: DiagnosticEngine = Depends(get_diagnosis_engine),
    repository: CaseRepository = Depends(get_case_repository),
    session: Session = Depends(get_db),
) -> CaseCheckResponse:
    """Process a troubleshooting check execution, re-evaluate diagnosis, and persist Revision N+1."""
    try:
        try:
            uuid_obj = uuid.UUID(case_id)
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid case ID format: '{case_id}' must be a valid UUID.",
            )

        canonical_id = str(uuid_obj)

        try:
            status_enum = CheckExecutionStatus(request.status.upper())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid check execution status: '{request.status}'.",
            )

        if status_enum in (CheckExecutionStatus.PENDING, CheckExecutionStatus.IN_PROGRESS):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Cannot submit check result with unfinished execution status: '{status_enum.value}'. "
                    "Check must be completed, blocked, failed, skipped, unknown, or not applicable."
                ),
            )

        try:
            finding_enum = CheckFinding(request.finding.upper())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid check finding: '{request.finding}'.",
            )

        check_def = get_action_by_id(request.check_id)
        if check_def is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Unknown check_id '{request.check_id}'. "
                    f"Must be a supported troubleshooting check from actions.json."
                ),
            )

        case = repository.load_structured_case(canonical_id)
        if case is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Case '{canonical_id}' not found.",
            )

        current_rev = (
            case.analysis_revisions[-1].revision_number
            if case.analysis_revisions
            else 1
        )
        if request.expected_revision != current_rev:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Stale revision for case '{canonical_id}': expected revision "
                    f"{request.expected_revision}, but current revision is {current_rev}."
                ),
            )

        domain_check = CheckResult(
            check_id=request.check_id,
            execution_status=status_enum,
            finding=finding_enum,
            finding_details=request.notes,
            outcome=None,
            source=EvidenceSource.USER_CHECK_RESULT,
            timestamp=datetime.now(timezone.utc),
        )

        try:
            CheckResultHandler.handle(domain_check)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            )

        updated_case, result = engine.submit_check_result(case, domain_check)

        try:
            rev_model = repository.append_check_result_revision(
                case=updated_case,
                check_result=domain_check,
                result=result,
                expected_revision=request.expected_revision,
            )

            target_revision = rev_model.revision_number

            case_model = repository.get_case(canonical_id)
            if case_model is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Case '{canonical_id}' not found.",
                )

            obs_models = repository.get_case_observations(canonical_id, max_revision=target_revision)
            rev1_model = repository.get_analysis_revision(canonical_id, revision_number=1)
            if rev1_model is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Initial diagnosis revision for case '{canonical_id}' not found.",
                )

            initial_diagnosis = DiagnosisResult.model_validate(rev1_model.result_snapshot)
            qa_models = repository.get_case_question_answers(canonical_id, max_revision=target_revision)
            cr_models = repository.get_case_check_results(canonical_id, max_revision=target_revision)
            ce_models = repository.get_case_check_executions(canonical_id, max_revision=target_revision)

            observations = [
                CaseObservationResponse(
                    id=obs.observation_id,
                    observation_id=obs.observation_id,
                    observation_type=(
                        ObservationType(obs.observation_type)
                        if obs.observation_type in ObservationType._value2member_map_
                        else obs.observation_type
                    ),
                    value=obs.value,
                    original_text=obs.original_text,
                    statement_type=(
                        StatementType(obs.statement_type)
                        if obs.statement_type in StatementType._value2member_map_
                        else obs.statement_type
                    ),
                    source=(
                        EvidenceSource(obs.source)
                        if obs.source in EvidenceSource._value2member_map_
                        else obs.source
                    ),
                    confidence=obs.confidence,
                    timestamp=obs.created_at,
                    created_at=obs.created_at,
                    first_seen_revision=obs.first_seen_revision,
                    metadata=_get_obs_metadata(obs),
                )
                for obs in obs_models
                if obs.first_seen_revision <= target_revision
            ]

            previous_answers = [
                QuestionAnswerRecord(
                    question_id=qm.question_id,
                    answer_value=qm.answer_value,
                    answer_text=qm.answer_text,
                    source=(
                        EvidenceSource(qm.source)
                        if qm.source in EvidenceSource._value2member_map_
                        else qm.source
                    ),
                    answered_at=qm.answered_at,
                    resulting_revision_number=qm.resulting_revision_number,
                )
                for qm in qa_models
                if qm.resulting_revision_number <= target_revision
            ]

            previous_check_results = [
                CheckResultRecord(
                    check_id=cm.check_id,
                    execution_status=(
                        CheckExecutionStatus(cm.execution_status)
                        if cm.execution_status in CheckExecutionStatus._value2member_map_
                        else cm.execution_status
                    ),
                    finding=(
                        CheckFinding(cm.finding)
                        if cm.finding in CheckFinding._value2member_map_
                        else cm.finding
                    ),
                    finding_details=cm.finding_details,
                    outcome=cm.outcome,
                    source=(
                        EvidenceSource(cm.source)
                        if cm.source in EvidenceSource._value2member_map_
                        else cm.source
                    ),
                    checked_at=cm.checked_at,
                    resulting_revision_number=cm.resulting_revision_number,
                )
                for cm in cr_models
                if cm.resulting_revision_number <= target_revision
            ]

            previous_checks = [
                CheckExecutionRecord(
                    check_id=cm.check_id,
                    status=cm.status,
                    finding=cm.finding,
                    notes=cm.notes,
                    executed_at=cm.executed_at,
                    resulting_revision_number=cm.resulting_revision_number,
                )
                for cm in ce_models
                if cm.resulting_revision_number <= target_revision
            ]

            matching_submitted = [
                c for c in previous_checks if c.resulting_revision_number == target_revision
            ]
            if not matching_submitted:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Submitted check execution record not found for the resulting revision.",
                )
            submitted_check = matching_submitted[-1]

            revisions = repository.list_case_revisions(canonical_id)
            analysis_revisions = []
            for rev_num in sorted(revisions):
                if rev_num <= target_revision:
                    rev_model_hist = repository.get_analysis_revision(canonical_id, revision_number=rev_num)
                    if rev_model_hist and rev_model_hist.result_snapshot:
                        snapshot_dict = rev_model_hist.result_snapshot
                        if "analysis_revision" in snapshot_dict and snapshot_dict["analysis_revision"]:
                            analysis_revisions.append(AnalysisRevision.model_validate(snapshot_dict["analysis_revision"]))

            issue_cond = (
                IssueCondition(case_model.issue_condition)
                if case_model.issue_condition in IssueCondition._value2member_map_
                else case_model.issue_condition
            )

            response = CaseCheckResponse(
                case_id=case_model.case_id,
                description=case_model.description,
                material=case_model.material,
                method=case_model.method,
                machine_context=case_model.machine_context,
                defect_code=case_model.defect_code,
                defect_name=case_model.defect_name,
                issue_condition=issue_cond,
                created_at=case_model.created_at,
                observations=observations,
                current_revision=target_revision,
                initial_diagnosis=initial_diagnosis,
                diagnosis=result,
                submitted_check=submitted_check,
                previous_checks=previous_checks,
                previous_check_results=previous_check_results,
                previous_answers=previous_answers,
                analysis_revisions=analysis_revisions,
                next_question=result.next_question,
                next_check=result.next_check,
            )

            session.commit()
            return response
        except StaleRevisionError as sre:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(sre),
            )
        except HTTPException:
            session.rollback()
            raise
        except Exception:
            session.rollback()
            logger.exception("Unexpected error persisting check execution revision")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred while persisting the check execution revision.",
            )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error during check execution submission")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while submitting the check execution.",
        )


@router.post(
    "/{case_id}/cause-confirmations",
    response_model=CaseCauseConfirmationResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Case not found"},
        status.HTTP_409_CONFLICT: {"description": "Stale expected revision"},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Validation error or invalid cause"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
    },
    summary="Explicitly confirm a diagnostic root cause",
    description=(
        "Explicitly confirms a candidate cause as the root cause for an active durable case. "
        "Enforces optimistic locking via expected_revision, invokes Member 2's confirm_cause() "
        "workflow, produces immutable Revision N+1, and atomically persists the confirmation "
        "record and revision snapshot. Does not automatically resolve the case issue."
    ),
)
def submit_case_cause_confirmation(
    case_id: str,
    request: SubmitCauseConfirmationRequest,
    engine: DiagnosticEngine = Depends(get_diagnosis_engine),
    repository: CaseRepository = Depends(get_case_repository),
    session: Session = Depends(get_db),
) -> CaseCauseConfirmationResponse:
    """Submit an explicit root-cause confirmation and evaluate the resulting revision."""
    try:
        try:
            uuid_obj = uuid.UUID(case_id)
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid case ID format: '{case_id}' must be a valid UUID.",
            )

        canonical_id = str(uuid_obj)

        case = repository.load_structured_case(canonical_id)
        if case is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Case '{canonical_id}' not found.",
            )

        current_rev = (
            case.analysis_revisions[-1].revision_number
            if case.analysis_revisions
            else 1
        )
        if request.expected_revision != current_rev:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Stale revision for case '{canonical_id}': expected revision "
                    f"{request.expected_revision}, but current revision is {current_rev}."
                ),
            )

        # Validate cause_id against candidate causes for the defect before persistence
        candidate_cause_ids: list[str] = []
        if case.analysis_revisions and case.analysis_revisions[-1].ranked_causes:
            candidate_cause_ids = [c.cause_id for c in case.analysis_revisions[-1].ranked_causes]
        elif case.defect_code:
            candidate_cause_ids = [c.id for c in get_causes_for_defect(case.defect_code)]

        if request.cause_id not in candidate_cause_ids:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Cannot confirm cause '{request.cause_id}': not found in current ranked causes. "
                    f"Available causes: {candidate_cause_ids}"
                ),
            )

        updated_case, result = engine.confirm_cause(
            case=case,
            cause_id=request.cause_id,
            confirmed_by=request.confirmed_by,
            confirmation_details=request.notes or "",
        )

        try:
            rev_model = repository.append_cause_confirmation_revision(
                case=updated_case,
                cause_id=request.cause_id,
                confirmed_by=request.confirmed_by,
                notes=request.notes,
                result=result,
                expected_revision=request.expected_revision,
            )

            target_revision = rev_model.revision_number

            case_model = repository.get_case(canonical_id)
            if case_model is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Case '{canonical_id}' not found.",
                )

            obs_models = repository.get_case_observations(canonical_id, max_revision=target_revision)
            rev1_model = repository.get_analysis_revision(canonical_id, revision_number=1)
            if rev1_model is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Initial diagnosis revision for case '{canonical_id}' not found.",
                )

            initial_diagnosis = DiagnosisResult.model_validate(rev1_model.result_snapshot)
            qa_models = repository.get_case_question_answers(canonical_id, max_revision=target_revision)
            cr_models = repository.get_case_check_results(canonical_id, max_revision=target_revision)
            conf_models = repository.get_case_cause_confirmations(canonical_id, max_revision=target_revision)

            observations = [
                CaseObservationResponse(
                    id=obs.observation_id,
                    observation_id=obs.observation_id,
                    observation_type=(
                        ObservationType(obs.observation_type)
                        if obs.observation_type in ObservationType._value2member_map_
                        else obs.observation_type
                    ),
                    value=obs.value,
                    original_text=obs.original_text,
                    statement_type=(
                        StatementType(obs.statement_type)
                        if obs.statement_type in StatementType._value2member_map_
                        else obs.statement_type
                    ),
                    source=(
                        EvidenceSource(obs.source)
                        if obs.source in EvidenceSource._value2member_map_
                        else obs.source
                    ),
                    confidence=obs.confidence,
                    timestamp=obs.created_at,
                    created_at=obs.created_at,
                    first_seen_revision=obs.first_seen_revision,
                    metadata=_get_obs_metadata(obs),
                )
                for obs in obs_models
                if obs.first_seen_revision <= target_revision
            ]

            previous_answers = [
                QuestionAnswerRecord(
                    question_id=qm.question_id,
                    answer_value=qm.answer_value,
                    answer_text=qm.answer_text,
                    source=(
                        EvidenceSource(qm.source)
                        if qm.source in EvidenceSource._value2member_map_
                        else qm.source
                    ),
                    answered_at=qm.answered_at,
                    resulting_revision_number=qm.resulting_revision_number,
                )
                for qm in qa_models
                if qm.resulting_revision_number <= target_revision
            ]

            previous_check_results = [
                CheckResultRecord(
                    check_id=cm.check_id,
                    execution_status=(
                        CheckExecutionStatus(cm.execution_status)
                        if cm.execution_status in CheckExecutionStatus._value2member_map_
                        else cm.execution_status
                    ),
                    finding=(
                        CheckFinding(cm.finding)
                        if cm.finding in CheckFinding._value2member_map_
                        else cm.finding
                    ),
                    finding_details=cm.finding_details,
                    outcome=cm.outcome,
                    source=(
                        EvidenceSource(cm.source)
                        if cm.source in EvidenceSource._value2member_map_
                        else cm.source
                    ),
                    checked_at=cm.checked_at,
                    resulting_revision_number=cm.resulting_revision_number,
                )
                for cm in cr_models
                if cm.resulting_revision_number <= target_revision
            ]

            previous_confirmations = [
                CauseConfirmationRecord(
                    cause_id=cfm.cause_id,
                    confirmed_by=cfm.confirmed_by,
                    notes=cfm.notes,
                    confirmed_at=cfm.confirmed_at,
                    resulting_revision_number=cfm.resulting_revision_number,
                )
                for cfm in conf_models
                if cfm.resulting_revision_number <= target_revision
            ]

            matching_submitted = [
                c for c in previous_confirmations if c.resulting_revision_number == target_revision
            ]
            if not matching_submitted:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Submitted confirmation record not found for the resulting revision.",
                )
            submitted_confirmation = matching_submitted[-1]

            issue_cond = (
                IssueCondition(case_model.issue_condition)
                if case_model.issue_condition in IssueCondition._value2member_map_
                else case_model.issue_condition
            )

            response = CaseCauseConfirmationResponse(
                case_id=case_model.case_id,
                description=case_model.description,
                material=case_model.material,
                method=case_model.method,
                machine_context=case_model.machine_context,
                defect_code=case_model.defect_code,
                defect_name=case_model.defect_name,
                issue_condition=issue_cond,
                created_at=case_model.created_at,
                observations=observations,
                initial_diagnosis=initial_diagnosis,
                diagnosis=result,
                current_revision=target_revision,
                submitted_confirmation=submitted_confirmation,
                previous_confirmations=previous_confirmations,
                previous_check_results=previous_check_results,
                previous_answers=previous_answers,
                confirmed_cause=request.cause_id,
                selected_cause_conclusion=CauseConclusion.CONFIRMED,
                next_question=result.next_question,
                next_check=result.next_check,
            )

            session.commit()
            broadcast_analytics_update("CAUSE_CONFIRMED", {"case_id": canonical_id, "cause_id": request.cause_id})
            return response
        except StaleRevisionError as e:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            )
        except HTTPException:
            session.rollback()
            raise
        except Exception:
            session.rollback()
            logger.exception("Unexpected error during cause confirmation persistence")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred while persisting the cause confirmation revision.",
            )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error during cause confirmation submission")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while submitting the cause confirmation.",
        )


@router.post(
    "/{case_id}/recovery-actions",
    response_model=CaseRecoveryActionResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Case not found"},
        status.HTTP_409_CONFLICT: {"description": "Stale expected revision"},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Illegal lifecycle transition or validation error"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
    },
    summary="Record an applied corrective/recovery action",
    description=(
        "Records that a corrective action has been applied to an active durable case, transitions "
        "the issue condition to RECOVERY_PENDING_VERIFICATION via the domain state manager, "
        "evaluates the next analysis revision, and atomically persists the lifecycle event and revision snapshot."
    ),
)
def submit_case_recovery_action(
    case_id: str,
    request: SubmitRecoveryActionRequest,
    engine: DiagnosticEngine = Depends(get_diagnosis_engine),
    repository: CaseRepository = Depends(get_case_repository),
    session: Session = Depends(get_db),
) -> CaseRecoveryActionResponse:
    """Record that a corrective/recovery action has been applied and transition to RECOVERY_PENDING_VERIFICATION."""
    try:
        try:
            uuid_obj = uuid.UUID(case_id)
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid case ID format: '{case_id}' must be a valid UUID.",
            )

        canonical_id = str(uuid_obj)

        case = repository.load_structured_case(canonical_id)
        if case is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Case '{canonical_id}' not found.",
            )

        current_rev = (
            case.analysis_revisions[-1].revision_number
            if case.analysis_revisions
            else 1
        )
        if request.expected_revision != current_rev:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Stale revision for case '{canonical_id}': expected revision "
                    f"{request.expected_revision}, but current revision is {current_rev}."
                ),
            )

        # Enforce legal state machine transition via StateManager
        target_condition = IssueCondition.RECOVERY_PENDING_VERIFICATION
        valid_targets = StateManager._VALID_ISSUE_TRANSITIONS.get(case.issue_condition, set())
        if target_condition not in valid_targets:
            curr_cond_val = (
                case.issue_condition.value
                if hasattr(case.issue_condition, "value")
                else str(case.issue_condition)
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Illegal issue condition transition: cannot apply recovery action from condition "
                    f"'{curr_cond_val}'."
                ),
            )

        new_condition, transition_explanation = StateManager.transition_issue_condition(
            current_condition=case.issue_condition,
            target_condition=target_condition,
            verification_passed=False,
            verification_details=request.recovery_details,
        )

        # Transition issue condition on structured case
        case.issue_condition = new_condition

        # Evaluate diagnosis for next revision
        result = engine.diagnose(case)
        result.issue_condition = new_condition

        summary_note = f"Recovery action applied by {request.performed_by}: {request.recovery_details}"
        if result.analysis_revision:
            result.analysis_revision.new_evidence_summary = summary_note
        if case.analysis_revisions:
            case.analysis_revisions[-1].new_evidence_summary = summary_note

        try:
            rev_model = repository.append_recovery_action_revision(
                case=case,
                performed_by=request.performed_by,
                recovery_details=request.recovery_details,
                result=result,
                expected_revision=request.expected_revision,
            )

            target_revision = rev_model.revision_number

            case_model = repository.get_case(canonical_id)
            if case_model is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Case '{canonical_id}' not found.",
                )

            obs_models = repository.get_case_observations(canonical_id, max_revision=target_revision)
            rev1_model = repository.get_analysis_revision(canonical_id, revision_number=1)
            if rev1_model is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Initial diagnosis revision for case '{canonical_id}' not found.",
                )

            initial_diagnosis = DiagnosisResult.model_validate(rev1_model.result_snapshot)
            qa_models = repository.get_case_question_answers(canonical_id, max_revision=target_revision)
            cr_models = repository.get_case_check_results(canonical_id, max_revision=target_revision)
            conf_models = repository.get_case_cause_confirmations(canonical_id, max_revision=target_revision)
            le_models = repository.get_case_lifecycle_events(canonical_id, max_revision=target_revision)

            observations = [
                CaseObservationResponse(
                    id=obs.observation_id,
                    observation_id=obs.observation_id,
                    observation_type=(
                        ObservationType(obs.observation_type)
                        if obs.observation_type in ObservationType._value2member_map_
                        else obs.observation_type
                    ),
                    value=obs.value,
                    original_text=obs.original_text,
                    statement_type=(
                        StatementType(obs.statement_type)
                        if obs.statement_type in StatementType._value2member_map_
                        else obs.statement_type
                    ),
                    source=(
                        EvidenceSource(obs.source)
                        if obs.source in EvidenceSource._value2member_map_
                        else obs.source
                    ),
                    confidence=obs.confidence,
                    timestamp=obs.created_at,
                    created_at=obs.created_at,
                    first_seen_revision=obs.first_seen_revision,
                    metadata=_get_obs_metadata(obs),
                )
                for obs in obs_models
                if obs.first_seen_revision <= target_revision
            ]

            previous_answers = [
                QuestionAnswerRecord(
                    question_id=qm.question_id,
                    answer_value=qm.answer_value,
                    answer_text=qm.answer_text,
                    source=(
                        EvidenceSource(qm.source)
                        if qm.source in EvidenceSource._value2member_map_
                        else qm.source
                    ),
                    answered_at=qm.answered_at,
                    resulting_revision_number=qm.resulting_revision_number,
                )
                for qm in qa_models
                if qm.resulting_revision_number <= target_revision
            ]

            previous_check_results = [
                CheckResultRecord(
                    check_id=cm.check_id,
                    execution_status=(
                        CheckExecutionStatus(cm.execution_status)
                        if cm.execution_status in CheckExecutionStatus._value2member_map_
                        else cm.execution_status
                    ),
                    finding=(
                        CheckFinding(cm.finding)
                        if cm.finding in CheckFinding._value2member_map_
                        else cm.finding
                    ),
                    finding_details=cm.finding_details,
                    outcome=cm.outcome,
                    source=(
                        EvidenceSource(cm.source)
                        if cm.source in EvidenceSource._value2member_map_
                        else cm.source
                    ),
                    checked_at=cm.checked_at,
                    resulting_revision_number=cm.resulting_revision_number,
                )
                for cm in cr_models
                if cm.resulting_revision_number <= target_revision
            ]

            previous_confirmations = [
                CauseConfirmationRecord(
                    cause_id=cfm.cause_id,
                    confirmed_by=cfm.confirmed_by,
                    notes=cfm.notes,
                    confirmed_at=cfm.confirmed_at,
                    resulting_revision_number=cfm.resulting_revision_number,
                )
                for cfm in conf_models
                if cfm.resulting_revision_number <= target_revision
            ]

            lifecycle_events = [
                LifecycleEventRecord(
                    id=lem.id,
                    case_id=lem.case_id,
                    event_type=lem.event_type,
                    prior_issue_condition=(
                        IssueCondition(lem.prior_issue_condition)
                        if lem.prior_issue_condition in IssueCondition._value2member_map_
                        else lem.prior_issue_condition
                    ),
                    resulting_issue_condition=(
                        IssueCondition(lem.resulting_issue_condition)
                        if lem.resulting_issue_condition in IssueCondition._value2member_map_
                        else lem.resulting_issue_condition
                    ),
                    resulting_revision_number=lem.resulting_revision_number,
                    actor=lem.actor,
                    details=lem.details,
                    verification_passed=lem.verification_passed,
                    created_at=lem.created_at,
                )
                for lem in le_models
                if lem.resulting_revision_number <= target_revision
            ]

            matching_submitted = [
                e for e in lifecycle_events if e.resulting_revision_number == target_revision
            ]
            if not matching_submitted:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Submitted recovery action event record not found for the resulting revision.",
                )
            submitted_event = matching_submitted[-1]

            issue_cond = (
                IssueCondition(case_model.issue_condition)
                if case_model.issue_condition in IssueCondition._value2member_map_
                else case_model.issue_condition
            )

            confirmed_cause_id = case.confirmed_causes[-1] if case.confirmed_causes else None

            response = CaseRecoveryActionResponse(
                case_id=case_model.case_id,
                description=case_model.description,
                material=case_model.material,
                method=case_model.method,
                machine_context=case_model.machine_context,
                defect_code=case_model.defect_code,
                defect_name=case_model.defect_name,
                issue_condition=issue_cond,
                created_at=case_model.created_at,
                observations=observations,
                initial_diagnosis=initial_diagnosis,
                diagnosis=result,
                current_revision=target_revision,
                submitted_recovery_action=submitted_event,
                submitted_event=submitted_event,
                lifecycle_events=lifecycle_events,
                previous_confirmations=previous_confirmations,
                previous_check_results=previous_check_results,
                previous_answers=previous_answers,
                confirmed_cause=confirmed_cause_id,
                next_question=result.next_question,
                next_check=result.next_check,
            )

            session.commit()
            return response
        except StaleRevisionError as e:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            )
        except HTTPException:
            session.rollback()
            raise
        except Exception:
            session.rollback()
            logger.exception("Unexpected error during recovery action persistence")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred while persisting the recovery action revision.",
            )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error during recovery action submission")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while submitting the recovery action.",
        )


@router.post(
    "/{case_id}/recovery-verifications",
    response_model=CaseRecoveryVerificationResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Case not found"},
        status.HTTP_409_CONFLICT: {"description": "Stale expected revision"},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Illegal lifecycle transition or validation error"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
    },
    summary="Record post-correction recovery verification",
    description=(
        "Records post-correction verification outcome (passed -> RESOLVED, failed -> UNRESOLVED) "
        "via the domain state manager, evaluates the next analysis revision, and atomically persists "
        "the verification event and revision snapshot."
    ),
)
def submit_case_recovery_verification(
    case_id: str,
    request: SubmitRecoveryVerificationRequest,
    engine: DiagnosticEngine = Depends(get_diagnosis_engine),
    repository: CaseRepository = Depends(get_case_repository),
    session: Session = Depends(get_db),
) -> CaseRecoveryVerificationResponse:
    """Record post-correction verification outcome and transition to RESOLVED or UNRESOLVED."""
    try:
        try:
            uuid_obj = uuid.UUID(case_id)
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid case ID format: '{case_id}' must be a valid UUID.",
            )

        canonical_id = str(uuid_obj)

        case = repository.load_structured_case(canonical_id)
        if case is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Case '{canonical_id}' not found.",
            )

        current_rev = (
            case.analysis_revisions[-1].revision_number
            if case.analysis_revisions
            else 1
        )
        if request.expected_revision != current_rev:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Stale revision for case '{canonical_id}': expected revision "
                    f"{request.expected_revision}, but current revision is {current_rev}."
                ),
            )

        # R1: Operation-specific precondition: recovery verification requires RECOVERY_PENDING_VERIFICATION
        current_condition = (
            case.issue_condition
            if isinstance(case.issue_condition, IssueCondition)
            else IssueCondition(case.issue_condition)
        )
        if current_condition != IssueCondition.RECOVERY_PENDING_VERIFICATION:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Illegal issue condition transition: cannot verify recovery for case '{canonical_id}' from condition "
                    f"'{current_condition.value}': recovery verification requires "
                    f"'{IssueCondition.RECOVERY_PENDING_VERIFICATION.value}'."
                ),
            )

        # Select target condition based on verification_passed
        target_condition = (
            IssueCondition.RESOLVED
            if request.verification_passed
            else IssueCondition.UNRESOLVED
        )

        # Enforce legal state machine transition via StateManager
        valid_targets = StateManager._VALID_ISSUE_TRANSITIONS.get(current_condition, set())
        if target_condition not in valid_targets:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Illegal issue condition transition: cannot verify recovery from condition "
                    f"'{current_condition.value}' to '{target_condition.value}'."
                ),
            )

        new_condition, transition_explanation = StateManager.transition_issue_condition(
            current_condition=current_condition,
            target_condition=target_condition,
            verification_passed=request.verification_passed,
            verification_details=request.verification_details,
        )

        # Transition issue condition on structured case
        case.issue_condition = new_condition

        # Evaluate diagnosis for next revision
        result = engine.diagnose(case)
        result.issue_condition = new_condition

        v_status = "PASSED" if request.verification_passed else "FAILED"
        summary_note = f"Recovery verification {v_status} by {request.verified_by}."
        if request.verification_details:
            summary_note += f" Details: {request.verification_details}"
        if result.analysis_revision:
            result.analysis_revision.new_evidence_summary = summary_note
        if case.analysis_revisions:
            case.analysis_revisions[-1].new_evidence_summary = summary_note

        try:
            rev_model = repository.append_recovery_verification_revision(
                case=case,
                verified_by=request.verified_by,
                verification_passed=request.verification_passed,
                verification_details=request.verification_details,
                result=result,
                expected_revision=request.expected_revision,
            )

            target_revision = rev_model.revision_number

            case_model = repository.get_case(canonical_id)
            if case_model is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Case '{canonical_id}' not found.",
                )

            obs_models = repository.get_case_observations(canonical_id, max_revision=target_revision)
            rev1_model = repository.get_analysis_revision(canonical_id, revision_number=1)
            if rev1_model is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Initial diagnosis revision for case '{canonical_id}' not found.",
                )

            initial_diagnosis = DiagnosisResult.model_validate(rev1_model.result_snapshot)
            qa_models = repository.get_case_question_answers(canonical_id, max_revision=target_revision)
            cr_models = repository.get_case_check_results(canonical_id, max_revision=target_revision)
            conf_models = repository.get_case_cause_confirmations(canonical_id, max_revision=target_revision)
            le_models = repository.get_case_lifecycle_events(canonical_id, max_revision=target_revision)

            observations = [
                CaseObservationResponse(
                    id=obs.observation_id,
                    observation_id=obs.observation_id,
                    observation_type=(
                        ObservationType(obs.observation_type)
                        if obs.observation_type in ObservationType._value2member_map_
                        else obs.observation_type
                    ),
                    value=obs.value,
                    original_text=obs.original_text,
                    statement_type=(
                        StatementType(obs.statement_type)
                        if obs.statement_type in StatementType._value2member_map_
                        else obs.statement_type
                    ),
                    source=(
                        EvidenceSource(obs.source)
                        if obs.source in EvidenceSource._value2member_map_
                        else obs.source
                    ),
                    confidence=obs.confidence,
                    timestamp=obs.created_at,
                    created_at=obs.created_at,
                    first_seen_revision=obs.first_seen_revision,
                    metadata=_get_obs_metadata(obs),
                )
                for obs in obs_models
                if obs.first_seen_revision <= target_revision
            ]

            previous_answers = [
                QuestionAnswerRecord(
                    question_id=qm.question_id,
                    answer_value=qm.answer_value,
                    answer_text=qm.answer_text,
                    source=(
                        EvidenceSource(qm.source)
                        if qm.source in EvidenceSource._value2member_map_
                        else qm.source
                    ),
                    answered_at=qm.answered_at,
                    resulting_revision_number=qm.resulting_revision_number,
                )
                for qm in qa_models
                if qm.resulting_revision_number <= target_revision
            ]

            previous_check_results = [
                CheckResultRecord(
                    check_id=cm.check_id,
                    execution_status=(
                        CheckExecutionStatus(cm.execution_status)
                        if cm.execution_status in CheckExecutionStatus._value2member_map_
                        else cm.execution_status
                    ),
                    finding=(
                        CheckFinding(cm.finding)
                        if cm.finding in CheckFinding._value2member_map_
                        else cm.finding
                    ),
                    finding_details=cm.finding_details,
                    outcome=cm.outcome,
                    source=(
                        EvidenceSource(cm.source)
                        if cm.source in EvidenceSource._value2member_map_
                        else cm.source
                    ),
                    checked_at=cm.checked_at,
                    resulting_revision_number=cm.resulting_revision_number,
                )
                for cm in cr_models
                if cm.resulting_revision_number <= target_revision
            ]

            previous_confirmations = [
                CauseConfirmationRecord(
                    cause_id=cfm.cause_id,
                    confirmed_by=cfm.confirmed_by,
                    notes=cfm.notes,
                    confirmed_at=cfm.confirmed_at,
                    resulting_revision_number=cfm.resulting_revision_number,
                )
                for cfm in conf_models
                if cfm.resulting_revision_number <= target_revision
            ]

            lifecycle_events = [
                LifecycleEventRecord(
                    id=lem.id,
                    case_id=lem.case_id,
                    event_type=lem.event_type,
                    prior_issue_condition=(
                        IssueCondition(lem.prior_issue_condition)
                        if lem.prior_issue_condition in IssueCondition._value2member_map_
                        else lem.prior_issue_condition
                    ),
                    resulting_issue_condition=(
                        IssueCondition(lem.resulting_issue_condition)
                        if lem.resulting_issue_condition in IssueCondition._value2member_map_
                        else lem.resulting_issue_condition
                    ),
                    resulting_revision_number=lem.resulting_revision_number,
                    actor=lem.actor,
                    details=lem.details,
                    verification_passed=lem.verification_passed,
                    created_at=lem.created_at,
                )
                for lem in le_models
                if lem.resulting_revision_number <= target_revision
            ]

            matching_submitted = [
                e for e in lifecycle_events if e.resulting_revision_number == target_revision
            ]
            if not matching_submitted:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Submitted recovery verification event record not found for the resulting revision.",
                )
            submitted_event = matching_submitted[-1]

            issue_cond = (
                IssueCondition(case_model.issue_condition)
                if case_model.issue_condition in IssueCondition._value2member_map_
                else case_model.issue_condition
            )

            confirmed_cause_id = case.confirmed_causes[-1] if case.confirmed_causes else None

            response = CaseRecoveryVerificationResponse(
                case_id=case_model.case_id,
                description=case_model.description,
                material=case_model.material,
                method=case_model.method,
                machine_context=case_model.machine_context,
                defect_code=case_model.defect_code,
                defect_name=case_model.defect_name,
                issue_condition=issue_cond,
                created_at=case_model.created_at,
                observations=observations,
                initial_diagnosis=initial_diagnosis,
                diagnosis=result,
                current_revision=target_revision,
                submitted_verification=submitted_event,
                submitted_event=submitted_event,
                lifecycle_events=lifecycle_events,
                previous_confirmations=previous_confirmations,
                previous_check_results=previous_check_results,
                previous_answers=previous_answers,
                confirmed_cause=confirmed_cause_id,
                next_question=result.next_question,
                next_check=result.next_check,
            )

            session.commit()
            if request.verification_passed:
                broadcast_analytics_update("CASE_COMPLETED", {"case_id": canonical_id, "status": "RESOLVED"})
            else:
                broadcast_analytics_update("CASE_UPDATED", {"case_id": canonical_id, "status": "UNRESOLVED"})
            return response
        except StaleRevisionError as e:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            )
        except HTTPException:
            session.rollback()
            raise
        except Exception:
            session.rollback()
            logger.exception("Unexpected error during recovery verification persistence")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred while persisting the recovery verification revision.",
            )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error during recovery verification submission")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while submitting the recovery verification.",
        )


@router.post(
    "/{case_id}/recurrences",
    response_model=CaseRecurrenceResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Case not found"},
        status.HTTP_409_CONFLICT: {"description": "Stale expected revision"},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Illegal lifecycle transition or validation error"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
    },
    summary="Report recurrence of a resolved issue",
    description=(
        "Records that a previously RESOLVED issue has recurred, transitioning condition "
        "from RESOLVED to RECURRED, appending a RECURRENCE lifecycle event and immutable "
        "revision snapshot, preserving cause conclusions, and enforcing optimistic concurrency."
    ),
)
def submit_case_recurrence(
    case_id: str,
    request: SubmitRecurrenceRequest,
    engine: DiagnosticEngine = Depends(get_diagnosis_engine),
    repository: CaseRepository = Depends(get_case_repository),
    session: Session = Depends(get_db),
) -> CaseRecurrenceResponse:
    """Record that a previously RESOLVED issue has recurred and transition to RECURRED."""
    try:
        try:
            uuid_obj = uuid.UUID(case_id)
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid case ID format: '{case_id}' must be a valid UUID.",
            )

        canonical_id = str(uuid_obj)

        case = repository.load_structured_case(canonical_id)
        if case is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Case '{canonical_id}' not found.",
            )

        current_rev = (
            case.analysis_revisions[-1].revision_number
            if case.analysis_revisions
            else 1
        )
        if request.expected_revision != current_rev:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Stale revision for case '{canonical_id}': expected revision "
                    f"{request.expected_revision}, but current revision is {current_rev}."
                ),
            )

        # Operation-specific precondition: recurrence requires RESOLVED
        current_condition = (
            case.issue_condition
            if isinstance(case.issue_condition, IssueCondition)
            else IssueCondition(case.issue_condition)
        )
        if current_condition != IssueCondition.RESOLVED:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Illegal issue condition transition: cannot report recurrence for case '{canonical_id}' from condition "
                    f"'{current_condition.value}': issue recurrence requires "
                    f"'{IssueCondition.RESOLVED.value}'."
                ),
            )

        target_condition = IssueCondition.RECURRED

        # Enforce legal state machine transition via StateManager
        valid_targets = StateManager._VALID_ISSUE_TRANSITIONS.get(current_condition, set())
        if target_condition not in valid_targets:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Illegal issue condition transition: cannot report recurrence from condition "
                    f"'{current_condition.value}' to '{target_condition.value}'."
                ),
            )

        new_condition, transition_explanation = StateManager.transition_issue_condition(
            current_condition=current_condition,
            target_condition=target_condition,
            verification_passed=False,
            verification_details=request.recurrence_details,
        )

        # Transition issue condition on structured case
        case.issue_condition = new_condition

        # Evaluate diagnosis for next revision
        result = engine.diagnose(case)
        result.issue_condition = new_condition

        summary_note = f"Defect recurrence reported by {request.reported_by}."
        if request.recurrence_details:
            summary_note += f" Details: {request.recurrence_details}"
        if result.analysis_revision:
            result.analysis_revision.new_evidence_summary = summary_note
        if case.analysis_revisions:
            case.analysis_revisions[-1].new_evidence_summary = summary_note

        try:
            rev_model = repository.append_recurrence_revision(
                case=case,
                reported_by=request.reported_by,
                recurrence_details=request.recurrence_details,
                result=result,
                expected_revision=request.expected_revision,
            )

            target_revision = rev_model.revision_number

            case_model = repository.get_case(canonical_id)
            if case_model is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Case '{canonical_id}' not found.",
                )

            obs_models = repository.get_case_observations(canonical_id, max_revision=target_revision)
            rev1_model = repository.get_analysis_revision(canonical_id, revision_number=1)
            if rev1_model is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Initial diagnosis revision for case '{canonical_id}' not found.",
                )

            initial_diagnosis = DiagnosisResult.model_validate(rev1_model.result_snapshot)
            qa_models = repository.get_case_question_answers(canonical_id, max_revision=target_revision)
            cr_models = repository.get_case_check_results(canonical_id, max_revision=target_revision)
            conf_models = repository.get_case_cause_confirmations(canonical_id, max_revision=target_revision)
            le_models = repository.get_case_lifecycle_events(canonical_id, max_revision=target_revision)

            observations = [
                CaseObservationResponse(
                    id=obs.observation_id,
                    observation_id=obs.observation_id,
                    observation_type=(
                        ObservationType(obs.observation_type)
                        if obs.observation_type in ObservationType._value2member_map_
                        else obs.observation_type
                    ),
                    value=obs.value,
                    original_text=obs.original_text,
                    statement_type=(
                        StatementType(obs.statement_type)
                        if obs.statement_type in StatementType._value2member_map_
                        else obs.statement_type
                    ),
                    source=(
                        EvidenceSource(obs.source)
                        if obs.source in EvidenceSource._value2member_map_
                        else obs.source
                    ),
                    confidence=obs.confidence,
                    timestamp=obs.created_at,
                    created_at=obs.created_at,
                    first_seen_revision=obs.first_seen_revision,
                    metadata=_get_obs_metadata(obs),
                )
                for obs in obs_models
                if obs.first_seen_revision <= target_revision
            ]

            previous_answers = [
                QuestionAnswerRecord(
                    question_id=qm.question_id,
                    answer_value=qm.answer_value,
                    answer_text=qm.answer_text,
                    source=(
                        EvidenceSource(qm.source)
                        if qm.source in EvidenceSource._value2member_map_
                        else qm.source
                    ),
                    answered_at=qm.answered_at,
                    resulting_revision_number=qm.resulting_revision_number,
                )
                for qm in qa_models
                if qm.resulting_revision_number <= target_revision
            ]

            previous_check_results = [
                CheckResultRecord(
                    check_id=cm.check_id,
                    execution_status=(
                        CheckExecutionStatus(cm.execution_status)
                        if cm.execution_status in CheckExecutionStatus._value2member_map_
                        else cm.execution_status
                    ),
                    finding=(
                        CheckFinding(cm.finding)
                        if cm.finding in CheckFinding._value2member_map_
                        else cm.finding
                    ),
                    finding_details=cm.finding_details,
                    outcome=cm.outcome,
                    source=(
                        EvidenceSource(cm.source)
                        if cm.source in EvidenceSource._value2member_map_
                        else cm.source
                    ),
                    checked_at=cm.checked_at,
                    resulting_revision_number=cm.resulting_revision_number,
                )
                for cm in cr_models
                if cm.resulting_revision_number <= target_revision
            ]

            previous_confirmations = [
                CauseConfirmationRecord(
                    cause_id=cfm.cause_id,
                    confirmed_by=cfm.confirmed_by,
                    notes=cfm.notes,
                    confirmed_at=cfm.confirmed_at,
                    resulting_revision_number=cfm.resulting_revision_number,
                )
                for cfm in conf_models
                if cfm.resulting_revision_number <= target_revision
            ]

            lifecycle_events = [
                LifecycleEventRecord(
                    id=lem.id,
                    case_id=lem.case_id,
                    event_type=lem.event_type,
                    prior_issue_condition=(
                        IssueCondition(lem.prior_issue_condition)
                        if lem.prior_issue_condition in IssueCondition._value2member_map_
                        else lem.prior_issue_condition
                    ),
                    resulting_issue_condition=(
                        IssueCondition(lem.resulting_issue_condition)
                        if lem.resulting_issue_condition in IssueCondition._value2member_map_
                        else lem.resulting_issue_condition
                    ),
                    resulting_revision_number=lem.resulting_revision_number,
                    actor=lem.actor,
                    details=lem.details,
                    verification_passed=lem.verification_passed,
                    created_at=lem.created_at,
                )
                for lem in le_models
                if lem.resulting_revision_number <= target_revision
            ]

            matching_submitted = [
                e for e in lifecycle_events if e.resulting_revision_number == target_revision
            ]
            if not matching_submitted:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Submitted recurrence event record not found for the resulting revision.",
                )
            submitted_event = matching_submitted[-1]

            issue_cond = (
                IssueCondition(case_model.issue_condition)
                if case_model.issue_condition in IssueCondition._value2member_map_
                else case_model.issue_condition
            )

            confirmed_cause_id = case.confirmed_causes[-1] if case.confirmed_causes else None

            response = CaseRecurrenceResponse(
                case_id=case_model.case_id,
                description=case_model.description,
                material=case_model.material,
                method=case_model.method,
                machine_context=case_model.machine_context,
                defect_code=case_model.defect_code,
                defect_name=case_model.defect_name,
                issue_condition=issue_cond,
                created_at=case_model.created_at,
                observations=observations,
                initial_diagnosis=initial_diagnosis,
                diagnosis=result,
                current_revision=target_revision,
                submitted_recurrence=submitted_event,
                submitted_event=submitted_event,
                lifecycle_events=lifecycle_events,
                previous_confirmations=previous_confirmations,
                previous_check_results=previous_check_results,
                previous_answers=previous_answers,
                confirmed_cause=confirmed_cause_id,
                next_question=result.next_question,
                next_check=result.next_check,
            )

            session.commit()
            return response
        except StaleRevisionError as e:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            )
        except HTTPException:
            session.rollback()
            raise
        except Exception:
            session.rollback()
            logger.exception("Unexpected error during issue recurrence persistence")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred while persisting the issue recurrence revision.",
            )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error during issue recurrence submission")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while submitting the issue recurrence.",
        )


@router.get(
    "/{case_id}/report",
    response_model=CaseReportResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Case not found"},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Invalid case ID format"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
    },
    summary="Export deterministic durable case report",
    description=(
        "Assembles a deterministic read-only report of a durable case from persisted state "
        "and audit history. Performs no diagnostic recalculation and creates no database mutations."
    ),
)
def get_case_report(
    case_id: str,
    repository: CaseRepository = Depends(get_case_repository),
) -> CaseReportResponse:
    """Export a deterministic read-only case report from persisted storage."""
    try:
        try:
            uuid_obj = uuid.UUID(case_id)
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid case ID format: '{case_id}' must be a valid UUID.",
            )

        canonical_id = str(uuid_obj)
        report = build_case_report(canonical_id, repository)
        if report is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Case '{canonical_id}' not found.",
            )
        return report
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error during case report export for case '%s'", case_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while generating the case report.",
        )


@router.get(
    "/{case_id}/report.pdf",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_200_OK: {
            "content": {"application/pdf": {}},
            "description": "Deterministic downloadable PDF case report",
        },
        status.HTTP_404_NOT_FOUND: {"description": "Case not found"},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Invalid case ID format"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
    },
    summary="Download deterministic PDF case report",
    description=(
        "Renders and downloads a deterministic PDF report of a durable case from the "
        "same accepted persisted report model as the JSON report. Performs zero diagnostic "
        "recalculation, reads no independent secondary paths, and creates no database mutations."
    ),
)
def get_case_report_pdf(
    case_id: str,
    repository: CaseRepository = Depends(get_case_repository),
) -> Response:
    """Render and download a deterministic PDF case report from persisted storage."""
    try:
        try:
            uuid_obj = uuid.UUID(case_id)
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid case ID format: '{case_id}' must be a valid UUID.",
            )

        canonical_id = str(uuid_obj)
        report = build_case_report(canonical_id, repository)
        if report is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Case '{canonical_id}' not found.",
            )

        try:
            pdf_bytes = render_case_report_pdf(report)
        except Exception:
            logger.exception("Unexpected error during PDF rendering for case '%s'", case_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred while generating the PDF case report.",
            )

        filename = f"dispenseiq-case-{canonical_id}-r{report.current_revision}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error during case report PDF export for case '%s'", case_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while generating the PDF case report.",
        )


@router.post(
    "/{case_id}/ai-summary",
    status_code=status.HTTP_200_OK,
    summary="Generate AI Executive Summary for a case report",
    description=(
        "Generates a concise, professional executive summary of the case using "
        "bounded LLM generation or deterministic fallback."
    ),
)
def generate_case_ai_summary(
    case_id: str,
    repository: CaseRepository = Depends(get_case_repository),
) -> dict[str, Any]:
    """Generate or retrieve an AI executive summary for a case report."""
    try:
        try:
            uuid_obj = uuid.UUID(case_id)
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid case ID format: '{case_id}' must be a valid UUID.",
            )

        canonical_id = str(uuid_obj)
        report = build_case_report(canonical_id, repository)
        if report is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Case '{canonical_id}' not found.",
            )

        # Attempt LLM-based summary with PromptManager
        llm = LLMService()
        prompt_mgr = PromptManager()
        summary_text: str | None = None
        source = "deterministic"

        confirmed_causes = (
            report.outcome_summary.confirmed_causes
            if report.outcome_summary
            else []
        )
        attempted_checks = [
            {
                "check_id": cr.check_id,
                "status": cr.execution_status,
                "finding": cr.finding,
                "outcome": cr.outcome,
            }
            for cr in report.check_results
        ]

        if llm.is_available:
            try:
                sys_prompt, user_prompt = prompt_mgr.get_case_summary_prompt(
                    case_id=report.case_id,
                    defect_name=report.defect_name,
                    description=report.description or "",
                    total_revisions=report.current_revision,
                    confirmed_causes=confirmed_causes,
                    attempted_checks=attempted_checks,
                    issue_condition=str(report.issue_condition),
                )
                generated = llm.generate_text(user_prompt, system_prompt=sys_prompt)
                if generated and generated.strip():
                    summary_text = generated.strip()
                    source = "llm"
            except Exception:
                logger.warning("LLM generation failed for case summary; falling back to deterministic summary", exc_info=True)

        # Deterministic summary fallback
        if not summary_text:
            defect_title = report.defect_name or report.defect_code or "Unspecified Defect"
            raw_condition = getattr(report.issue_condition, "value", str(report.issue_condition))
            condition_display = raw_condition.replace("IssueCondition.", "").replace("Issuecondition.", "").replace("_", " ").title()
            confirmed_display = ", ".join(confirmed_causes) if confirmed_causes else "None confirmed yet"
            
            lines = [
                f"Diagnostic Case Report for {defect_title} (Case ID: {report.case_id}).",
                f"Initial problem observed: {report.description or 'No initial description provided.'}",
            ]
            if report.material or report.method:
                lines.append(f"Operating Context: Material '{report.material or 'N/A'}', dispensing method '{report.method or 'N/A'}'.")
            
            if confirmed_causes:
                lines.append(f"Root cause confirmed: {confirmed_display}.")
            elif report.current_diagnosis and report.current_diagnosis.ranked_causes:
                top = report.current_diagnosis.ranked_causes[0]
                lines.append(f"Top diagnostic candidate is '{top.cause_name}' with evidence support score {top.score:.0f}/100.")
            
            if report.check_results:
                lines.append(f"A total of {len(report.check_results)} troubleshooting check(s) have been conducted across {report.current_revision} diagnostic revision(s).")
            
            lines.append(f"Current Issue Condition: {condition_display}.")
            summary_text = " ".join(lines)
            source = "deterministic"

        return {
            "case_id": canonical_id,
            "summary": summary_text,
            "source": source,
            "revision": report.current_revision,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error generating AI summary for case '%s'", case_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while generating the AI summary.",
        )

