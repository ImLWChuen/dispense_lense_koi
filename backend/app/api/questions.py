"""
FastAPI route handler for diagnostic questions knowledge catalog.
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException, Query, status

from app.knowledge import (
    get_questions_for_causes,
    get_questions_for_defect,
    load_questions,
)
from app.schemas.diagnosis import QuestionDefinition

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "",
    response_model=list[QuestionDefinition],
    status_code=status.HTTP_200_OK,
    summary="List diagnostic questions",
    description=(
        "Returns the knowledge base catalog of authorized diagnostic questions. "
        "Supports optional filtering by cause ID or defect code."
    ),
)
def list_questions(
    cause_id: str | None = Query(
        default=None,
        description="Filter questions applicable to a specific cause ID (e.g. 'CAU01_NOZZLE_CLOG')",
    ),
    defect_code: str | None = Query(
        default=None,
        description="Filter questions applicable to a specific defect code (e.g. 'D03_INCONSISTENT_SIZE')",
    ),
) -> list[QuestionDefinition]:
    """Return authorized diagnostic questions from the knowledge catalog."""
    try:
        if cause_id:
            questions = get_questions_for_causes([cause_id])
            if defect_code:
                questions = [q for q in questions if defect_code in q.applicable_defects]
            return questions

        if defect_code:
            return get_questions_for_defect(defect_code)

        return load_questions()
    except Exception:
        logger.exception("Failed to load questions from knowledge catalog")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load diagnostic questions catalog.",
        )
