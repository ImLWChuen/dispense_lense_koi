"""
Dispense Lens - Historical Case Retriever Service

Identifies and ranks historical cases by multi-attribute similarity,
extracting verified root causes and corrective resolutions to guide technicians.
"""

from __future__ import annotations

import logging
from typing import Sequence
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.knowledge import get_cause_by_id
from app.models.case import CaseModel
from app.schemas.retrieval import SimilarCaseItem, SimilarCasesResponse
from app.services.retrieval.similarity import calculate_case_similarity

logger = logging.getLogger(__name__)


class CaseRetriever:
    """Retrieves and ranks historical diagnostic cases based on multi-attribute similarity."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def find_similar_cases(
        self,
        target_case_id: str,
        limit: int = 5,
        min_score: float = 0.20,
    ) -> SimilarCasesResponse:
        """Find historical cases similar to the target case.

        Args:
            target_case_id: Canonical UUID of the reference case.
            limit: Maximum number of matched cases to return (default: 5).
            min_score: Minimum similarity score threshold (default: 0.20).

        Returns:
            SimilarCasesResponse with ranked candidate cases.
        """
        # 1. Fetch target case with relationships
        target_stmt = (
            select(CaseModel)
            .options(
                selectinload(CaseModel.observations),
                selectinload(CaseModel.cause_confirmations),
                selectinload(CaseModel.lifecycle_events),
                selectinload(CaseModel.check_executions),
            )
            .where(CaseModel.case_id == target_case_id)
        )
        target = self.db.scalar(target_stmt)
        if not target:
            logger.warning("Target case '%s' not found for similarity search", target_case_id)
            return SimilarCasesResponse(
                target_case_id=target_case_id,
                count=0,
                similar_cases=[],
            )

        # 2. Fetch candidate cases excluding target
        candidates_stmt = (
            select(CaseModel)
            .options(
                selectinload(CaseModel.observations),
                selectinload(CaseModel.cause_confirmations),
                selectinload(CaseModel.lifecycle_events),
                selectinload(CaseModel.check_executions),
            )
            .where(CaseModel.case_id != target_case_id)
        )
        candidates: Sequence[CaseModel] = self.db.scalars(candidates_stmt).all()

        scored_items: list[SimilarCaseItem] = []

        for cand in candidates:
            score, factors = calculate_case_similarity(target, cand)
            if score < min_score:
                continue

            # Determine resolution state
            raw_cond = str(cand.issue_condition).strip().upper()
            is_resolved = raw_cond in ("RESOLVED", "ISSUECONDITION.RESOLVED")

            # Extract confirmed causes
            confirmed_causes: list[str] = []
            for conf in (cand.cause_confirmations or []):
                cause_def = get_cause_by_id(conf.cause_id)
                name = cause_def.name if cause_def else conf.cause_id.replace("_", " ").title()
                if name not in confirmed_causes:
                    confirmed_causes.append(name)

            # Extract resolution summary
            resolution_summary: str | None = None
            resolved_at = None

            # Check lifecycle events for recovery/verification details
            for ev in reversed(cand.lifecycle_events or []):
                if ev.event_type in ("RECOVERY_VERIFICATION", "RECOVERY_ACTION") and ev.details:
                    resolution_summary = ev.details
                    resolved_at = ev.created_at
                    break

            if not resolution_summary and cand.cause_confirmations:
                # Fallback to technician confirmation notes
                notes = [c.notes for c in cand.cause_confirmations if c.notes]
                if notes:
                    resolution_summary = notes[-1]
                    resolved_at = cand.cause_confirmations[-1].confirmed_at

            if not resolution_summary and is_resolved:
                resolution_summary = "Issue verified resolved by cleanroom engineering."

            # Determine equipment line / model
            m_ctx = cand.machine_context or {}
            line_id = m_ctx.get("line_id") or m_ctx.get("line") or m_ctx.get("dispenser_model")

            scored_items.append(
                SimilarCaseItem(
                    case_id=cand.case_id,
                    short_id=cand.case_id[:8].upper(),
                    defect_code=cand.defect_code,
                    defect_name=cand.defect_name,
                    description=cand.description or "No problem description recorded.",
                    material=cand.material,
                    method=cand.method,
                    line_id=line_id,
                    issue_condition=cand.issue_condition,
                    is_resolved=is_resolved,
                    similarity_score=score,
                    similarity_percentage=int(round(score * 100)),
                    matching_factors=factors,
                    confirmed_causes=confirmed_causes,
                    resolution_summary=resolution_summary,
                    created_at=cand.created_at,
                    resolved_at=resolved_at,
                )
            )

        # 3. Sort: prioritize resolved cases and higher similarity scores
        scored_items.sort(
            key=lambda x: (x.is_resolved, x.similarity_score),
            reverse=True,
        )

        top_matches = scored_items[:limit]

        return SimilarCasesResponse(
            target_case_id=target_case_id,
            count=len(top_matches),
            similar_cases=top_matches,
        )
