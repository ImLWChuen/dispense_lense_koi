"""
FastAPI route handler for candidate causes knowledge catalog.
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException, Query, status

from app.knowledge import get_causes_for_defect, load_causes
from app.schemas.diagnosis import CauseDefinition

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "",
    response_model=list[CauseDefinition],
    status_code=status.HTTP_200_OK,
    summary="List candidate causes",
    description=(
        "Returns the knowledge base catalog of authorized dispensing root causes. "
        "Supports optional filtering by defect code."
    ),
)
def list_causes(
    defect_code: str | None = Query(
        default=None,
        description="Filter candidate causes applicable to a specific defect code (e.g. 'D01_TOO_LITTLE')",
    ),
) -> list[CauseDefinition]:
    """Return authorized candidate causes from the knowledge catalog."""
    try:
        if defect_code:
            return get_causes_for_defect(defect_code)
        return load_causes()
    except Exception:
        logger.exception("Failed to load causes from knowledge catalog")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load candidate causes catalog.",
        )
