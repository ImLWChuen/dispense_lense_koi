"""
DispenseIQ — Cause Ranker

Higher-level ranking API that wraps the Evidence Engine.

Responsibilities:
- Accepts observations + defect code + optional context/historical evidence
- Delegates evidence evaluation to EvidenceEngine
- Labels scores as "Evidence Support: XX/100" (not probability)
- Produces ranked causes with per-cause score explanation
- Detects high-confidence causes
- Supports re-ranking with new evidence (preserves revision history)

Design rules:
- Consumes knowledge from JSON via the knowledge interface — never duplicates rules.
- Scores do NOT sum to 100 across causes.
- Scoring weights come from the centralized ScoringConfig.
"""

from __future__ import annotations

from typing import Any

from backend.app.schemas.diagnosis import (
    AnalysisRevision,
    CandidateCause,
    CauseConclusion,
    Observation,
    QuestionAnswer,
    CheckResult,
)
from backend.app.services.diagnosis.evidence_engine import EvidenceEngine
from backend.app.utils.scoring import SCORING_CONFIG


# ---------------------------------------------------------------------------
# Ranking result
# ---------------------------------------------------------------------------

class RankingResult:
    """Result of cause ranking with full explanation support."""

    def __init__(
        self,
        defect_code: str,
        ranked_causes: list[CandidateCause],
        high_confidence_causes: list[CandidateCause],
        has_sufficient_evidence: bool,
    ):
        self.defect_code = defect_code
        self.ranked_causes = ranked_causes
        self.high_confidence_causes = high_confidence_causes
        self.has_sufficient_evidence = has_sufficient_evidence

    @property
    def top_cause(self) -> CandidateCause | None:
        """Return the highest-ranked cause, if any."""
        return self.ranked_causes[0] if self.ranked_causes else None

    def get_cause_explanation(self, cause_id: str) -> dict[str, Any]:
        """Return a structured explanation for a specific cause.

        Output format matches the implementation plan §10.3:
        {
            "cause": "air_supply_issue",
            "cause_name": "Air / Supply Issue",
            "score": 82,
            "score_label": "Evidence Support: 82/100",
            "supporting_evidence": ["..."],
            "contradicting_evidence": ["..."],
            "missing_evidence": ["..."],
            "score_breakdown": {...}
        }
        """
        for cause in self.ranked_causes:
            if cause.cause_id == cause_id:
                return {
                    "cause": cause.cause_id,
                    "cause_name": cause.cause_name,
                    "score": cause.score,
                    "score_label": f"Evidence Support: {cause.score:.0f}/100",
                    "supporting_evidence": [
                        e.explanation for e in cause.supporting_evidence
                        if e.explanation
                    ],
                    "contradicting_evidence": [
                        e.explanation for e in cause.contradicting_evidence
                        if e.explanation
                    ],
                    "missing_evidence": cause.missing_evidence,
                    "score_breakdown": cause.score_breakdown,
                }
        return {}

    def __repr__(self) -> str:
        top = self.top_cause
        top_str = f"{top.cause_name}={top.score:.0f}" if top else "none"
        return (
            f"RankingResult(defect={self.defect_code}, "
            f"causes={len(self.ranked_causes)}, top={top_str})"
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class CauseRanker:
    """Ranks candidate causes by evidence support.

    This is a thin orchestration layer over EvidenceEngine.
    It adds:
    - High-confidence detection
    - Score explanation formatting
    - Re-ranking with new evidence
    - Revision history management
    """

    def __init__(self, evidence_engine: EvidenceEngine | None = None) -> None:
        self._engine = evidence_engine or EvidenceEngine()

    def rank(
        self,
        observations: list[Observation],
        defect_code: str,
    ) -> RankingResult:
        """Rank candidate causes for a defect given current observations.

        Args:
            observations: All structured observations collected so far.
            defect_code: The identified defect code (e.g. "D03_INCONSISTENT_SIZE").

        Returns:
            RankingResult with ranked causes and explanation support.
        """
        candidates = self._engine.evaluate(observations, defect_code)
        return self._build_result(defect_code, candidates)

    def rerank(
        self,
        observations: list[Observation],
        defect_code: str,
        previous_revision: AnalysisRevision | None = None,
    ) -> tuple[RankingResult, AnalysisRevision]:
        """Re-rank causes after new evidence and produce a new revision.

        Args:
            observations: ALL observations (old + new).
            defect_code: The identified defect code.
            previous_revision: The prior analysis revision, if any.

        Returns:
            Tuple of (new RankingResult, new AnalysisRevision).
        """
        result = self.rank(observations, defect_code)

        # Determine revision number
        prev_num = previous_revision.revision_number if previous_revision else 0
        revision = AnalysisRevision(
            revision_number=prev_num + 1,
            defect_code=defect_code,
            ranked_causes=result.ranked_causes,
        )

        # Track what changed from the previous revision
        if previous_revision and previous_revision.ranked_causes:
            changes = _detect_changes(
                previous_revision.ranked_causes,
                result.ranked_causes,
            )
            revision.changes_from_previous = changes
            revision.new_evidence_summary = (
                f"Re-evaluated with {len(observations)} observations."
            )

        return result, revision

    # -----------------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------------

    def _build_result(
        self,
        defect_code: str,
        candidates: list[CandidateCause],
    ) -> RankingResult:
        """Build a RankingResult from evaluated candidates."""
        high_confidence = [
            c for c in candidates
            if c.score >= SCORING_CONFIG.high_confidence_threshold
        ]

        # Mark high-confidence causes
        for c in candidates:
            if c.score >= SCORING_CONFIG.high_confidence_threshold:
                c.conclusion = CauseConclusion.SUSPECTED  # still suspected, not confirmed

        has_sufficient = len(high_confidence) > 0

        return RankingResult(
            defect_code=defect_code,
            ranked_causes=candidates,
            high_confidence_causes=high_confidence,
            has_sufficient_evidence=has_sufficient,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect_changes(
    previous: list[CandidateCause],
    current: list[CandidateCause],
) -> list[str]:
    """Compare two rankings and describe what changed."""
    changes: list[str] = []

    prev_scores = {c.cause_id: c.score for c in previous}
    prev_order = [c.cause_id for c in previous]
    curr_order = [c.cause_id for c in current]

    for c in current:
        old_score = prev_scores.get(c.cause_id)
        if old_score is None:
            changes.append(f"{c.cause_name} is newly ranked at {c.score:.0f}/100.")
        elif abs(c.score - old_score) >= 1.0:
            direction = "increased" if c.score > old_score else "decreased"
            changes.append(
                f"{c.cause_name} {direction} from {old_score:.0f} to {c.score:.0f}."
            )

    # Rank order change
    if prev_order and curr_order and prev_order[0] != curr_order[0]:
        new_top = current[0]
        changes.append(
            f"{new_top.cause_name} is now the top-ranked cause."
        )

    return changes
