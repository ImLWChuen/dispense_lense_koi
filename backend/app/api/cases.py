"""FastAPI route handlers for durable case lifecycle operations."""

from __future__ import annotations

import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.repository import CaseRepository
from app.db.session import get_db
from app.schemas.case import (
    CaseObservationResponse,
    CreateCaseRequest,
    DurableCaseResponse,
)
from app.schemas.diagnosis import (
    DiagnosisResult,
    EvidenceSource,
    IssueCondition,
    ObservationType,
    StatementType,
)
from app.services.diagnosis.engine import DiagnosticEngine

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
