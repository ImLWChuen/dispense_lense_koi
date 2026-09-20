"""
Dispense Lens - Diagnostic Question Engine

Selects the next most useful diagnostic question to distinguish
competing hypotheses. Does NOT simply generate five generic questions.

Design rules:
- Questions come from questions.json via the knowledge interface.
- Ranking uses the centralized ScoringConfig weights.
- The engine has explicit stopping conditions (no endless questioning).
- Already-answered questions are heavily penalized.
- The engine estimates information gain using evidence_mapping from
  the knowledge base.
"""

from __future__ import annotations

from typing import Any

from app.knowledge import (
    get_questions_for_causes,
    load_questions,
)
from app.schemas.diagnosis import (
    CandidateCause,
    Question,
    QuestionAnswer,
)
from app.utils.scoring import SCORING_CONFIG


# ---------------------------------------------------------------------------
# Question selection result
# ---------------------------------------------------------------------------

class QuestionSelectionResult:
    """Result from the question engine."""

    def __init__(
        self,
        selected_question: Question | None,
        all_candidates: list[Question],
        reason_stopped: str | None = None,
    ):
        self.selected_question = selected_question
        self.all_candidates = all_candidates
        self.reason_stopped = reason_stopped

    @property
    def should_ask(self) -> bool:
        """Whether a question should be asked."""
        return self.selected_question is not None

    def __repr__(self) -> str:
        if self.selected_question:
            return (
                f"QuestionSelectionResult(question={self.selected_question.question_id}, "
                f"score={self.selected_question.usefulness_score:.1f})"
            )
        return f"QuestionSelectionResult(stopped: {self.reason_stopped})"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class QuestionEngine:
    """Selects the next most useful diagnostic question.

    The engine ranks questions by their ability to distinguish
    between the current competing causes. It considers:

    1. Cause coverage - how many top-ranked causes does the question address?
    2. Uncertainty reduction - does the question fill a gap in missing evidence?
    3. Already-answered penalty - avoid re-asking the same question.

    Stopping conditions:
    - A cause already has high confidence (≥ threshold)
    - No useful unanswered questions remain
    - Best question score is negligible
    """

    def select_next_question(
        self,
        ranked_causes: list[CandidateCause],
        previous_answers: list[QuestionAnswer] | None = None,
        defect_code: str | None = None,
    ) -> QuestionSelectionResult:
        """Select the next most useful question to ask.

        Args:
            ranked_causes: Current ranked causes from the cause ranker.
            previous_answers: Questions already answered by the technician.
            defect_code: The identified defect code (for question filtering).

        Returns:
            QuestionSelectionResult with the selected question or stop reason.
        """
        if previous_answers is None:
            previous_answers = []

        answered_ids = {a.question_id for a in previous_answers}

        # --- Stopping condition 1: high-confidence cause exists ---
        for cause in ranked_causes:
            if cause.score >= SCORING_CONFIG.high_confidence_threshold:
                return QuestionSelectionResult(
                    selected_question=None,
                    all_candidates=[],
                    reason_stopped=(
                        f"Sufficient evidence: {cause.cause_name} has "
                        f"evidence support {cause.score:.0f}/100 "
                        f"(threshold: {SCORING_CONFIG.high_confidence_threshold:.0f})."
                    ),
                )

        # --- Retrieve candidate questions ---
        cause_ids = [c.cause_id for c in ranked_causes]
        candidate_definitions = get_questions_for_causes(cause_ids)

        # Also filter by defect if provided
        if defect_code:
            all_questions = load_questions()
            defect_questions = {
                q.id for q in all_questions
                if defect_code in q.applicable_defects
            }
            # Include questions applicable to either causes or defect
            candidate_ids = {q.id for q in candidate_definitions} | defect_questions
            candidate_definitions = [
                q for q in load_questions() if q.id in candidate_ids
            ]

        if not candidate_definitions:
            return QuestionSelectionResult(
                selected_question=None,
                all_candidates=[],
                reason_stopped="No applicable questions found for current causes.",
            )

        # --- Score each question ---
        scored_questions: list[Question] = []

        for q_def in candidate_definitions:
            is_answered = q_def.id in answered_ids

            # 1. Cause coverage: how many of the top causes does this question affect?
            cause_coverage = len(
                set(q_def.applicable_causes) & set(cause_ids)
            )

            # 2. Uncertainty reduction: does the question address missing evidence?
            uncertainty_score = _estimate_uncertainty_reduction(
                q_def, ranked_causes
            )

            # 3. Already-answered penalty
            answered_penalty = (
                SCORING_CONFIG.question_already_answered_penalty
                if is_answered else 0.0
            )

            usefulness = (
                cause_coverage * SCORING_CONFIG.question_cause_coverage_weight
                + uncertainty_score * SCORING_CONFIG.question_uncertainty_weight
                - answered_penalty
            )

            # Determine allowed options dynamically from question definition
            opts: list[str] = (
                list(q_def.evidence_mapping.keys())
                if hasattr(q_def, "evidence_mapping") and q_def.evidence_mapping
                else []
            )

            scored_questions.append(Question(
                question_id=q_def.id,
                text=q_def.text,
                purpose=q_def.purpose,
                usefulness_score=usefulness,
                target_causes=q_def.applicable_causes,
                already_answered=is_answered,
                options=opts,
            ))

        # Sort by usefulness descending
        scored_questions.sort(key=lambda q: q.usefulness_score, reverse=True)

        # --- Stopping condition 2: no useful unanswered questions ---
        unanswered = [q for q in scored_questions if not q.already_answered]
        if not unanswered:
            return QuestionSelectionResult(
                selected_question=None,
                all_candidates=scored_questions,
                reason_stopped="All applicable questions have been answered.",
            )

        # --- Stopping condition 3: best question score is negligible ---
        best = unanswered[0]
        if best.usefulness_score < 1.0:
            return QuestionSelectionResult(
                selected_question=None,
                all_candidates=scored_questions,
                reason_stopped=(
                    "No remaining question has enough discriminating value "
                    f"(best score: {best.usefulness_score:.1f})."
                ),
            )

        return QuestionSelectionResult(
            selected_question=best,
            all_candidates=scored_questions,
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _estimate_uncertainty_reduction(
    question_def: Any,
    ranked_causes: list[CandidateCause],
) -> float:
    """Estimate how much uncertainty this question could reduce.

    Looks at the evidence_mapping in the question definition to see
    how many causes would be affected by different answers, and
    whether those causes currently have missing evidence.
    """
    score = 0.0

    # Check if the question has evidence_mapping (from questions.json)
    evidence_mapping = getattr(question_def, "evidence_mapping", None)
    if not evidence_mapping:
        # Fall back: score based on how many missing-evidence items
        # on the ranked causes match this question's applicable causes
        cause_ids_with_missing = set()
        for cause in ranked_causes:
            if cause.missing_evidence:
                cause_ids_with_missing.add(cause.cause_id)

        overlap = cause_ids_with_missing & set(question_def.applicable_causes)
        return float(len(overlap))

    # Count how many distinct (cause, relation) pairs the question could produce
    affected_causes: set[str] = set()
    for _answer_value, cause_effects in evidence_mapping.items():
        if isinstance(cause_effects, dict):
            affected_causes.update(cause_effects.keys())

    # More affected causes = more information gain
    score = float(len(affected_causes))

    # Bonus if the question could distinguish between the top-2 causes
    if len(ranked_causes) >= 2:
        top_two_ids = {ranked_causes[0].cause_id, ranked_causes[1].cause_id}
        if top_two_ids & affected_causes:
            score += 2.0

    return score
