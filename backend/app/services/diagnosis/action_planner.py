"""
Dispense Lens - Action Planner

Selects the next most useful troubleshooting check when enough
diagnostic information is available.

Design rules:
- Actions come from actions.json via the knowledge interface.
- A high-ranked cause does NOT automatically determine the first action.
- The planner independently considers applicability, information gain,
  effort, and prior attempts.
- Scoring weights come from the centralized ScoringConfig.
- The planner does NOT duplicate knowledge - it consumes it.
"""

from __future__ import annotations

from typing import Any

from app.knowledge import (
    get_actions_for_causes,
    load_actions,
)
from app.schemas.diagnosis import (
    CandidateCause,
    CheckResult,
    TroubleshootingCheck,
)
from app.utils.scoring import SCORING_CONFIG, effort_penalty


# ---------------------------------------------------------------------------
# Action selection result
# ---------------------------------------------------------------------------

class ActionSelectionResult:
    """Result from the action planner."""

    def __init__(
        self,
        selected_check: TroubleshootingCheck | None,
        all_candidates: list[TroubleshootingCheck],
        reason: str = "",
    ):
        self.selected_check = selected_check
        self.all_candidates = all_candidates
        self.reason = reason

    @property
    def should_check(self) -> bool:
        """Whether a troubleshooting check should be performed."""
        return self.selected_check is not None

    def __repr__(self) -> str:
        if self.selected_check:
            return (
                f"ActionSelectionResult(check={self.selected_check.check_id}, "
                f"score={self.selected_check.priority_score:.1f})"
            )
        return f"ActionSelectionResult(no check: {self.reason})"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class ActionPlanner:
    """Selects the next troubleshooting check to perform.

    The planner ranks actions by a composite score:
    1. Cause coverage - how many top-ranked causes does this check address?
    2. Information gain - how many distinct evidence outcomes does it have?
    3. Effort penalty - higher-effort checks are penalized.
    4. Already-attempted penalty - completed checks are heavily penalized.
    """

    def select_next_action(
        self,
        ranked_causes: list[CandidateCause],
        previous_check_results: list[CheckResult] | None = None,
        defect_code: str | None = None,
    ) -> ActionSelectionResult:
        """Select the next most useful troubleshooting check.

        Args:
            ranked_causes: Current ranked causes from the cause ranker.
            previous_check_results: Checks already performed.
            defect_code: The identified defect code (for filtering).

        Returns:
            ActionSelectionResult with the selected check or empty.
        """
        if previous_check_results is None:
            previous_check_results = []

        attempted_ids = {r.check_id for r in previous_check_results}

        if not ranked_causes:
            return ActionSelectionResult(
                selected_check=None,
                all_candidates=[],
                reason="No ranked causes to base action selection on.",
            )

        # --- Retrieve candidate actions ---
        cause_ids = [c.cause_id for c in ranked_causes]
        action_definitions = get_actions_for_causes(cause_ids)

        # Also include defect-specific actions if defect_code provided
        if defect_code:
            all_actions = load_actions()
            defect_actions = [
                a for a in all_actions
                if defect_code in a.applicable_defects
            ]
            existing_ids = {a.id for a in action_definitions}
            for a in defect_actions:
                if a.id not in existing_ids:
                    action_definitions.append(a)

        if not action_definitions:
            return ActionSelectionResult(
                selected_check=None,
                all_candidates=[],
                reason="No applicable checks found for current causes.",
            )

        # --- Score each action ---
        scored_checks: list[TroubleshootingCheck] = []

        for act_def in action_definitions:
            is_attempted = act_def.id in attempted_ids

            # 1. Cause coverage: how many of the top causes does this check address?
            cause_coverage = len(
                set(act_def.applicable_causes) & set(cause_ids)
            )

            # Bonus: weight by cause score - addressing top-scored causes is more valuable
            weighted_coverage = 0.0
            for cause in ranked_causes:
                if cause.cause_id in act_def.applicable_causes:
                    weighted_coverage += cause.score / 100.0

            # 2. Information gain: how many distinct evidence outcomes?
            info_gain = _estimate_information_gain(act_def)

            # 3. Effort penalty
            eff_penalty = effort_penalty(act_def.effort_level)

            # 4. Already-attempted penalty
            attempted_penalty = (
                SCORING_CONFIG.action_already_attempted_penalty
                if is_attempted else 0.0
            )

            # Composite priority score
            priority = (
                (cause_coverage + weighted_coverage)
                * SCORING_CONFIG.action_cause_coverage_weight
                + info_gain * SCORING_CONFIG.action_information_gain_weight
                - eff_penalty
                - attempted_penalty
            )

            # Build reasoning
            reasoning_parts = []
            if cause_coverage > 0:
                reasoning_parts.append(
                    f"Addresses {cause_coverage} applicable cause(s)."
                )
            if info_gain > 0:
                reasoning_parts.append(
                    f"Can produce {info_gain} distinct evidence outcome(s)."
                )
            if eff_penalty > 0:
                reasoning_parts.append(
                    f"Effort level: {act_def.effort_level} (penalty: {eff_penalty:.0f})."
                )
            if is_attempted:
                reasoning_parts.append("Already attempted (heavily penalized).")

            possible_outcomes = (
                list(act_def.evidence_mapping.keys())
                if hasattr(act_def, "evidence_mapping") and act_def.evidence_mapping
                else []
            )

            scored_checks.append(TroubleshootingCheck(
                check_id=act_def.id,
                name=act_def.name,
                description=act_def.description,
                procedure=act_def.procedure,
                priority_score=priority,
                target_causes=act_def.applicable_causes,
                reasoning=" ".join(reasoning_parts),
                required_access=act_def.required_access,
                effort_level=act_def.effort_level,
                possible_outcomes=possible_outcomes,
            ))

        # Sort by priority descending
        scored_checks.sort(key=lambda c: c.priority_score, reverse=True)

        # Select the best non-attempted check
        unattempted = [c for c in scored_checks if c.check_id not in attempted_ids]

        if not unattempted:
            return ActionSelectionResult(
                selected_check=None,
                all_candidates=scored_checks,
                reason="All applicable checks have already been attempted.",
            )

        best = unattempted[0]
        if best.priority_score <= 0:
            return ActionSelectionResult(
                selected_check=None,
                all_candidates=scored_checks,
                reason=(
                    f"Best available check ({best.name}) has non-positive "
                    f"priority score ({best.priority_score:.1f})."
                ),
            )

        return ActionSelectionResult(
            selected_check=best,
            all_candidates=scored_checks,
            reason=best.reasoning,
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _estimate_information_gain(action_def: Any) -> float:
    """Estimate information gain from the action's evidence mapping.

    Counts the number of distinct evidence outcomes this check can produce.
    More outcomes = more discriminating power.
    """
    evidence_mapping = getattr(action_def, "evidence_mapping", None)
    if not evidence_mapping or not isinstance(evidence_mapping, dict):
        return 1.0  # minimal default - at least some information

    # Count distinct outcomes
    return float(len(evidence_mapping))
