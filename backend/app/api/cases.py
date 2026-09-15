"""FastAPI route handlers for durable case lifecycle operations."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.repository import CaseRepository, StaleRevisionError
from app.db.session import get_db
from app.schemas.case import (
    CaseAnswerResponse,
    CaseCauseConfirmationResponse,
    CaseCheckResultResponse,
    CaseObservationResponse,
    CauseConfirmationRecord,
    CheckResultRecord,
    CreateCaseRequest,
    DurableCaseResponse,
    QuestionAnswerRecord,
    SubmitAnswerRequest,
    SubmitCauseConfirmationRequest,
    SubmitCheckResultRequest,
)
from app.schemas.diagnosis import (
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
from app.knowledge import get_causes_for_defect
from app.services.diagnosis.engine import CheckResultHandler, DiagnosticEngine
from app.services.diagnosis.question_answer_handler import QuestionAnswerHandler

logger = logging.getLogger(__name__)

router = APIRouter()


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

        repository.save_initial_case(case, result)
        session.commit()

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
            initial_diagnosis=initial_diagnosis,
            diagnosis=initial_diagnosis,
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
