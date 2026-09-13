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
    CaseObservationResponse,
    CreateCaseRequest,
    DurableCaseResponse,
    QuestionAnswerRecord,
    SubmitAnswerRequest,
)
from app.schemas.diagnosis import (
    DiagnosisResult,
    EvidenceSource,
    IssueCondition,
    ObservationType,
    QuestionAnswer,
    StatementType,
)
from app.services.diagnosis.engine import DiagnosticEngine
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

        try:
            updated_case, result = engine.submit_question_answer(case, domain_answer)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            )

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
        except ValueError as e:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
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
