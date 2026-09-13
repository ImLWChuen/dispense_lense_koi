"""FastAPI route handler for initial diagnosis operations."""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.diagnosis import DiagnosisResult
from app.schemas.diagnosis_api import InitialDiagnosisRequest
from app.services.diagnosis.engine import DiagnosticEngine

logger = logging.getLogger(__name__)

router = APIRouter()


def get_diagnosis_engine() -> DiagnosticEngine:
    """Dependency provider returning an instance of the diagnostic engine."""
    return DiagnosticEngine()


@router.post(
    "",
    response_model=DiagnosisResult,
    status_code=status.HTTP_200_OK,
    summary="Evaluate initial dispensing diagnosis",
    description=(
        "Submits an initial dispensing defect problem for diagnostic evaluation. "
        "Returns the engine's structured analysis including candidate causes, score "
        "explanations, and recommended next questions or troubleshooting checks. "
        "This endpoint is stateless: the returned case ID identifies this analysis run "
        "only and is neither persistent nor retrievable."
    ),
)
def create_initial_diagnosis(
    request: InitialDiagnosisRequest,
    engine: DiagnosticEngine = Depends(get_diagnosis_engine),
) -> DiagnosisResult:
    """Analyze initial problem evidence and produce diagnostic assessment."""
    try:
        domain_request = request.to_diagnosis_request()
        return engine.diagnose(domain_request)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error during diagnostic engine evaluation")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during diagnosis evaluation.",
        )
