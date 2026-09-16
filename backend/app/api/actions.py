"""
FastAPI route handler for troubleshooting actions / checks (Phase 14 Placeholder).
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException, status

from app.knowledge import load_actions
from app.schemas.diagnosis import CheckDefinition

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "",
    response_model=list[CheckDefinition],
    status_code=status.HTTP_200_OK,
    summary="List all troubleshooting checks",
    description="Returns the knowledge base catalog of authorized troubleshooting checks.",
)
def list_actions() -> list[CheckDefinition]:
    """Return all authorized troubleshooting checks."""
    try:
        return load_actions()
    except Exception:
        logger.exception("Failed to load actions from knowledge catalog")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load troubleshooting actions catalog.",
        )
