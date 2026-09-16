"""
FastAPI route handler for defect categories knowledge catalog.
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException, status

from app.knowledge import load_defects
from app.schemas.diagnosis import DefectDefinition

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "",
    response_model=list[DefectDefinition],
    status_code=status.HTTP_200_OK,
    summary="List defect categories",
    description="Returns the knowledge base catalog of authorized dispensing defect categories.",
)
def list_defects() -> list[DefectDefinition]:
    """Return all authorized dispensing defect definitions."""
    try:
        return load_defects()
    except Exception:
        logger.exception("Failed to load defects from knowledge catalog")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load defect definitions catalog.",
        )
