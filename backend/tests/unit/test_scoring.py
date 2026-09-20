"""
Dispense Lens - Scoring Configuration & Math Unit Tests (Section 23)

Verifies:
1. Support weight mappings for STRONG, MODERATE, WEAK
2. Contradiction penalty mappings for STRONG, MODERATE, WEAK
3. Duplicate weight is zero (never inflates score)
4. Score clamping between min_score (0.0) and max_score (100.0)
5. Action effort penalties
"""

from __future__ import annotations

import pytest

from app.utils.scoring import (
    SCORING_CONFIG,
    clamp_score,
    contradiction_weight,
    effort_penalty,
    support_weight,
)


def test_scoring_config_defaults() -> None:
    """Verify default scoring configuration constants."""
    assert SCORING_CONFIG.strong_support == 20.0
    assert SCORING_CONFIG.moderate_support == 12.0
    assert SCORING_CONFIG.weak_support == 5.0

    assert SCORING_CONFIG.strong_contradiction == 18.0
    assert SCORING_CONFIG.moderate_contradiction == 10.0
    assert SCORING_CONFIG.weak_contradiction == 4.0

    assert SCORING_CONFIG.duplicate_weight == 0.0
    assert SCORING_CONFIG.base_score == 30.0
    assert SCORING_CONFIG.min_score == 0.0
    assert SCORING_CONFIG.max_score == 100.0


def test_support_weight_lookup() -> None:
    """Verify positive evidence weights by strength."""
    assert support_weight("STRONG") == 20.0
    assert support_weight("MODERATE") == 12.0
    assert support_weight("WEAK") == 5.0
    # Fallback to moderate
    assert support_weight("UNKNOWN_STRENGTH") == 12.0


def test_contradiction_weight_lookup() -> None:
    """Verify contradiction penalties by strength."""
    assert contradiction_weight("STRONG") == 18.0
    assert contradiction_weight("MODERATE") == 10.0
    assert contradiction_weight("WEAK") == 4.0
    assert contradiction_weight("UNKNOWN_STRENGTH") == 10.0


def test_effort_penalty_lookup() -> None:
    """Verify action effort penalties."""
    assert effort_penalty("high") == 5.0
    assert effort_penalty("medium") == 2.0
    assert effort_penalty("low") == 0.0
    assert effort_penalty("unknown") == 2.0


def test_clamp_score() -> None:
    """Verify score clamping boundaries."""
    assert clamp_score(50.0) == 50.0
    assert clamp_score(-15.0) == 0.0
    assert clamp_score(150.0) == 100.0
    assert clamp_score(0.0) == 0.0
    assert clamp_score(100.0) == 100.0
