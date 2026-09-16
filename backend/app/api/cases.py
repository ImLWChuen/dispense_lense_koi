"""FastAPI route handlers for durable case lifecycle operations."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.knowledge import get_check_by_id, load_questions

from app.db.repository import CaseRepository, StaleRevisionError
from app.db.session import get_db
from app.schemas.case import (
    CaseAnswerResponse,
    CaseCheckResponse,
    CaseObservationResponse,
    CheckExecutionRecord,
    CreateCaseRequest,
    DurableCaseResponse,
    LifecycleEventRecord,
    QuestionAnswerRecord,
    SubmitAnswerRequest,
    SubmitCheckRequest,
)
from app.schemas.diagnosis import (
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
from app.services.diagnosis.engine import CheckResultHandler, DiagnosticEngine, StateManager
from app.services.diagnosis.question_answer_handler import QuestionAnswerHandler
from app.services.reporting import build_case_report, render_case_report_pdf

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
    "",
    response_model=list[DurableCaseResponse],
    status_code=status.HTTP_200_OK,
    summary="Retrieve all diagnostic cases",
    description="Retrieves a list of all persisted diagnostic cases with their initial analysis.",
)
def list_durable_cases(
    repository: CaseRepository = Depends(get_case_repository),
) -> list[DurableCaseResponse]:
    """Retrieve all existing cases and their initial diagnosis from persistent storage."""
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
            )
            for obs in obs_models
        ]
        
        responses.append(
            DurableCaseResponse(
                case_id=case_model.case_id,
                description=case_model.description,
                material=case_model.material,
                method=case_model.method,
                machine_context=case_model.machine_context,
                defect_code=case_model.defect_code,
                defect_name=initial_diagnosis.defect_name,
                issue_condition=case_model.issue_condition,
                created_at=case_model.created_at,
                observations=observations,
                initial_diagnosis=initial_diagnosis,
                diagnosis=latest_diagnosis,
            )
        )
        
    return responses



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
        chk_models = repository.get_case_check_results(canonical_id)

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
        # 1. Parse execution status and finding
        try:
            status_enum = CheckExecutionStatus(request.status.upper())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid check execution status: '{request.status}'.",
            )

        try:
            finding_enum = CheckFinding(request.finding.upper())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid check finding: '{request.finding}'.",
            )

        # 2. Acquire locked case snapshot
        case = repository.load_structured_case(case_id, for_update=True)
        if case is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Diagnostic case '{case_id}' was not found.",
            )

        # 3. Execute domain check submission workflow
        try:
            result = engine.submit_check_result(
                case=case,
                check_id=request.check_id,
                status=status_enum,
                finding=finding_enum,
                notes=request.notes,
                source=EvidenceSource.USER_CHECK_RESULT,
            )
        except ValueError as ve:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(ve),
            )

        if result.analysis_revision is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Check execution evaluation did not produce a valid analysis revision.",
            )

        # 4. Atomically persist check revision
        check_record = CheckResult(
            check_id=request.check_id,
            status=status_enum,
            finding=finding_enum,
            notes=request.notes,
        )

        try:
            target_revision = request.expected_revision + 1
            repository.append_check_result_revision(
                case=case,
                check_result=check_record,
                result=result,
                expected_revision=request.expected_revision,
            )

            # 5. Build response
            case_model = repository.get_case(case_id)
            if case_model is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Case '{case_id}' was not found.",
                )

            initial_rev = repository.get_analysis_revision(case_id, revision_number=1)
            if initial_rev is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Initial diagnostic assessment revision (rev 1) not found.",
                )
            initial_diagnosis = DiagnosisResult.model_validate(initial_rev.result_snapshot)

            obs_models = repository.get_case_observations(case_id, max_revision=target_revision)
            check_models = repository.get_case_check_executions(case_id, max_revision=target_revision)

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

            previous_checks = [
                CheckExecutionRecord(
                    check_id=cm.check_id,
                    status=cm.status,
                    finding=cm.finding,
                    notes=cm.notes,
                    executed_at=cm.executed_at,
                    resulting_revision_number=cm.resulting_revision_number,
                )
                for cm in check_models
                if cm.resulting_revision_number <= target_revision
            ]

            matching_submitted = [
                c for c in previous_checks if c.resulting_revision_number == target_revision
            ]
            if not matching_submitted:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Submitted check record not found for the resulting revision.",
                )
            submitted_check = matching_submitted[-1]

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
                initial_diagnosis=initial_diagnosis,
                diagnosis=result,
                current_revision=target_revision,
                submitted_check=submitted_check,
                previous_checks=previous_checks,
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
            logger.exception("Unexpected error during check execution persistence")
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
            detail="An unexpected error occurred while submitting the troubleshooting check.",
        )
