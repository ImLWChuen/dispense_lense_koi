"""
Dispense Lens - Centralized Scoring Configuration

All score weights and thresholds used by the cause ranker.
Kept in one place so the team can review and tune without
digging through algorithm code.

The scores represent *evidence support* (not calibrated probability).
They do NOT need to sum to 100 across causes.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ScoringConfig:
    """Centralized scoring weights for the evidence-based cause ranker.

    Adjusting these values changes how aggressively evidence moves
    cause scores up or down.  The defaults below are initial estimates;
    the team should tune them after reviewing representative scenarios.
    """

    # --- positive evidence weights ---
    strong_support: float = 20.0
    moderate_support: float = 12.0
    weak_support: float = 5.0

    # --- contradiction penalties (subtracted) ---
    strong_contradiction: float = 18.0
    moderate_contradiction: float = 10.0
    weak_contradiction: float = 4.0

    # --- duplicate evidence ---
    duplicate_weight: float = 0.0  # duplicates contribute nothing

    # --- base score for every applicable cause ---
    base_score: float = 30.0

    # --- uncertainty penalty per missing evidence item ---
    missing_evidence_penalty: float = 2.0

    # --- score boundaries (each cause score is at most max_score) ---
    min_score: float = 0.0
    max_score: float = 100.0

    # --- thresholds ---
    high_confidence_threshold: float = 75.0
    low_confidence_threshold: float = 30.0

    # --- question engine weights ---
    question_cause_coverage_weight: float = 2.0
    question_uncertainty_weight: float = 1.5
    question_already_answered_penalty: float = 100.0

    # --- action planner weights ---
    action_cause_coverage_weight: float = 2.0
    action_information_gain_weight: float = 1.5
    action_effort_penalty_high: float = 5.0
    action_effort_penalty_medium: float = 2.0
    action_effort_penalty_low: float = 0.0
    action_already_attempted_penalty: float = 100.0


# Singleton instance used across the engine
SCORING_CONFIG = ScoringConfig()


# ---------------------------------------------------------------------------
# Helper look-ups
# ---------------------------------------------------------------------------

_STRENGTH_TO_SUPPORT = {
    "STRONG": SCORING_CONFIG.strong_support,
    "MODERATE": SCORING_CONFIG.moderate_support,
    "WEAK": SCORING_CONFIG.weak_support,
}

_STRENGTH_TO_CONTRADICTION = {
    "STRONG": SCORING_CONFIG.strong_contradiction,
    "MODERATE": SCORING_CONFIG.moderate_contradiction,
    "WEAK": SCORING_CONFIG.weak_contradiction,
}

_EFFORT_TO_PENALTY = {
    "high": SCORING_CONFIG.action_effort_penalty_high,
    "medium": SCORING_CONFIG.action_effort_penalty_medium,
    "low": SCORING_CONFIG.action_effort_penalty_low,
}


def support_weight(strength: str) -> float:
    """Return the positive-evidence weight for a given strength level."""
    return _STRENGTH_TO_SUPPORT.get(strength, SCORING_CONFIG.moderate_support)


def contradiction_weight(strength: str) -> float:
    """Return the contradiction penalty for a given strength level."""
    return _STRENGTH_TO_CONTRADICTION.get(
        strength, SCORING_CONFIG.moderate_contradiction
    )


def effort_penalty(effort_level: str) -> float:
    """Return the effort penalty for an action's effort level."""
    return _EFFORT_TO_PENALTY.get(
        effort_level, SCORING_CONFIG.action_effort_penalty_medium
    )


def clamp_score(score: float) -> float:
    """Clamp a score to the configured [min, max] range."""
    return max(SCORING_CONFIG.min_score, min(SCORING_CONFIG.max_score, score))
