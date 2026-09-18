"""
DispenseIQ — Defect Classifier / Identifier Unit Tests (Section 23)

Verifies deterministic mapping from structured observations to the six mandatory defects:
- D01_TOO_LITTLE
- D02_TOO_MUCH
- D03_INCONSISTENT_SIZE
- D04_MISSING_DOTS
- D05_SPREADING
- D06_BUBBLES_ABNORMAL_SHAPE
"""

from __future__ import annotations

import pytest

from app.schemas.diagnosis import Observation, ObservationType
from app.services.diagnosis.defect_identifier import identify_defect


def test_identify_d01_too_little() -> None:
    """Undersized dots without inconsistent runtime pattern map to D01_TOO_LITTLE."""
    obs = [
        Observation(observation_type=ObservationType.DEPOSIT_SIZE, value="undersized"),
        Observation(observation_type=ObservationType.FREQUENCY_PATTERN, value="consistent"),
    ]
    match = identify_defect(obs)
    assert match is not None
    assert match.code == "D01_TOO_LITTLE"
    assert match.confidence >= 0.8
    assert len(match.matching_observations) > 0


def test_identify_d02_too_much() -> None:
    """Oversized dots map to D02_TOO_MUCH."""
    obs = [
        Observation(observation_type=ObservationType.DEPOSIT_SIZE, value="oversized"),
    ]
    match = identify_defect(obs)
    assert match is not None
    assert match.code == "D02_TOO_MUCH"
    assert match.confidence >= 0.8


def test_identify_d03_inconsistent_size() -> None:
    """Inconsistent dots or undersized with prolonged operation map to D03_INCONSISTENT_SIZE."""
    obs = [
        Observation(observation_type=ObservationType.DEPOSIT_SIZE, value="inconsistent"),
    ]
    match = identify_defect(obs)
    assert match is not None
    assert match.code == "D03_INCONSISTENT_SIZE"

    # Also undersized + prolonged operation
    obs2 = [
        Observation(observation_type=ObservationType.DEPOSIT_SIZE, value="undersized"),
        Observation(observation_type=ObservationType.RUNTIME_PATTERN, value="after_prolonged_operation"),
    ]
    match2 = identify_defect(obs2)
    assert match2 is not None
    assert match2.code == "D03_INCONSISTENT_SIZE"


def test_identify_d04_missing_dots() -> None:
    """Missing deposit presence maps to D04_MISSING_DOTS."""
    obs = [
        Observation(observation_type=ObservationType.DEPOSIT_PRESENCE, value="missing"),
    ]
    match = identify_defect(obs)
    assert match is not None
    assert match.code == "D04_MISSING_DOTS"


def test_identify_d05_spreading() -> None:
    """Excessive spread maps to D05_SPREADING."""
    obs = [
        Observation(observation_type=ObservationType.SPREADING_BEHAVIOUR, value="excessive_spread"),
    ]
    match = identify_defect(obs)
    assert match is not None
    assert match.code == "D05_SPREADING"


def test_identify_d06_bubbles_abnormal_shape() -> None:
    """Visible bubbles or abnormal shape map to D06_BUBBLES_ABNORMAL_SHAPE."""
    obs_bubbles = [
        Observation(observation_type=ObservationType.BUBBLE_PRESENCE, value="visible_bubbles"),
    ]
    match_bubbles = identify_defect(obs_bubbles)
    assert match_bubbles is not None
    assert match_bubbles.code == "D06_BUBBLES_ABNORMAL_SHAPE"

    obs_shape = [
        Observation(observation_type=ObservationType.DEPOSIT_SHAPE, value="abnormal"),
    ]
    match_shape = identify_defect(obs_shape)
    assert match_shape is not None
    assert match_shape.code == "D06_BUBBLES_ABNORMAL_SHAPE"


def test_identify_unmatched_observations() -> None:
    """Unrelated observations return None or low-confidence fallback."""
    obs = [
        Observation(observation_type=ObservationType.OTHER, value="unrelated_info"),
    ]
    match = identify_defect(obs)
    assert match is None
