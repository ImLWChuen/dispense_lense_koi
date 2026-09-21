"""
FastAPI route handler for diagnostic evidence rules knowledge catalog.
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException, Query, status

from app.knowledge import load_evidence_rules
from app.schemas.diagnosis import EvidenceRule

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "",
    response_model=list[EvidenceRule],
    status_code=status.HTTP_200_OK,
    summary="List evidence evaluation rules",
    description=(
        "Returns the knowledge base catalog of authorized diagnostic evidence rules. "
        "Supports optional filtering by target cause ID or observation type."
    ),
)
def list_rules(
    cause_id: str | None = Query(
        default=None,
        description="Filter rules applicable to a specific root cause (e.g. 'nozzle_restriction')",
    ),
    observation_type: str | None = Query(
        default=None,
        description="Filter rules applicable to a specific observation type (e.g. 'deposit_size')",
    ),
) -> list[EvidenceRule]:
    """Return authorized evidence evaluation rules from the knowledge catalog."""
    try:
        rules = load_evidence_rules()
        if cause_id:
            rules = [r for r in rules if r.cause_id == cause_id]
        if observation_type:
            rules = [r for r in rules if r.observation_type == observation_type]
        return rules
    except Exception:
        logger.exception("Failed to load evidence rules from knowledge catalog")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load evidence rules catalog.",
        )
