"""
DispenseIQ — Defect Identifier

Deterministic defect identification from structured observations.
Maps extracted observations to one of six mandatory defect types.

This is a traceable, rule-based mapper — NOT a neural classifier.
Every identification includes a human-readable reason.
"""

from __future__ import annotations

from app.knowledge import get_defect_by_code, load_defects
from app.schemas.diagnosis import (
    DefectCode,
    Observation,
    ObservationType,
)


# ---------------------------------------------------------------------------
# Defect-identification result
# ---------------------------------------------------------------------------

class DefectMatch:
    """Result of defect identification."""

    def __init__(
        self,
        code: str,
        name: str,
        confidence: float,
        reason: str,
        matching_observations: list[Observation],
    ):
        self.code = code
        self.name = name
        self.confidence = confidence
        self.reason = reason
        self.matching_observations = matching_observations

    def __repr__(self) -> str:
        return f"DefectMatch(code={self.code!r}, confidence={self.confidence})"


# ---------------------------------------------------------------------------
# Helper predicates
# ---------------------------------------------------------------------------

def _has_observation(
    observations: list[Observation],
    obs_type: str,
    values: set[str],
) -> list[Observation]:
    """Return observations matching the given type and value set."""
    return [
        o for o in observations
        if o.observation_type == obs_type and o.value in values
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def identify_defect(observations: list[Observation]) -> DefectMatch | None:
    """Identify the most likely defect from structured observations.

    Uses a priority-ordered rule chain. The first strong match wins.
    If multiple defects are plausible, the one with the most
    supporting observations is chosen.

    Args:
        observations: List of structured observations from symptom extraction.

    Returns:
        A DefectMatch with the identified defect, or None if no defect
        could be determined.
    """
    if not observations:
        return None

    # Collect all matching candidates with scores
    candidates: list[DefectMatch] = []

    # --- D04: Missing Dots ---
    missing_obs = _has_observation(observations, "deposit_presence", {"missing", "absent", "no_deposit"})
    fewer_obs = _has_observation(observations, "deposit_count", {"fewer_than_expected"})
    if missing_obs or fewer_obs:
        matched = missing_obs + fewer_obs
        candidates.append(DefectMatch(
            code=DefectCode.D04_MISSING_DOTS.value,
            name="Missing Dots",
            confidence=0.9 if missing_obs else 0.7,
            reason="Deposits are missing or absent at dispensing locations.",
            matching_observations=matched,
        ))

    # --- D06: Bubbles / Abnormal Shape ---
    bubble_obs = _has_observation(observations, "bubble_presence", {"visible_bubbles", "air_entrapment"})
    abnormal_shape = _has_observation(observations, "deposit_shape", {"abnormal", "irregular", "tailing", "satellite_dots"})
    crater_obs = _has_observation(observations, "visual_appearance", {"crater_shape", "void_inside"})
    if bubble_obs or (abnormal_shape and not _has_observation(observations, "spreading_behaviour", {"excessive_spread", "flat_spread", "bleeding"})):
        matched = bubble_obs + abnormal_shape + crater_obs
        confidence = 0.9 if bubble_obs else 0.7
        candidates.append(DefectMatch(
            code=DefectCode.D06_BUBBLES_ABNORMAL_SHAPE.value,
            name="Bubbles / Abnormal Shape",
            confidence=confidence,
            reason="Deposits contain bubbles, voids, or exhibit abnormal shape.",
            matching_observations=matched,
        ))

    # --- D05: Spreading ---
    spread_obs = _has_observation(observations, "spreading_behaviour", {"excessive_spread", "flat_spread", "bleeding"})
    flat_obs = _has_observation(observations, "deposit_shape", {"flat", "irregular_spread"})
    bleed_obs = _has_observation(observations, "visual_appearance", {"thin_flat", "bleeding_edges"})
    if spread_obs:
        matched = spread_obs + flat_obs + bleed_obs
        candidates.append(DefectMatch(
            code=DefectCode.D05_SPREADING.value,
            name="Spreading",
            confidence=0.85,
            reason="Dispensed material spreads excessively on the substrate.",
            matching_observations=matched,
        ))

    # --- D03: Inconsistent Size ---
    inconsistent_obs = _has_observation(observations, "deposit_size", {"inconsistent", "variable", "varying", "uneven"})
    intermittent_obs = _has_observation(observations, "frequency_pattern", {"intermittent"})
    location_varies = _has_observation(observations, "location_pattern", {"varies_across_points"})
    runtime_drift = _has_observation(observations, "runtime_pattern", {"after_prolonged_operation", "worsens_over_time"})

    if inconsistent_obs:
        matched = inconsistent_obs + intermittent_obs + location_varies
        candidates.append(DefectMatch(
            code=DefectCode.D03_INCONSISTENT_SIZE.value,
            name="Inconsistent Dispensing Size",
            confidence=0.85,
            reason="Deposit size varies across dispensing shots.",
            matching_observations=matched,
        ))

    # --- D01: Too Little Material ---
    too_little_obs = _has_observation(
        observations, "deposit_size",
        {"undersized", "small", "insufficient", "too_little", "below_target"},
    )
    # Only classify as too-little if NOT already classified as inconsistent/runtime drift
    if too_little_obs and not inconsistent_obs and not runtime_drift:
        candidates.append(DefectMatch(
            code=DefectCode.D01_TOO_LITTLE.value,
            name="Too Little Material",
            confidence=0.8,
            reason="Dispensed volume is consistently less than the target.",
            matching_observations=too_little_obs,
        ))

    # --- D02: Too Much Material ---
    too_much_obs = _has_observation(
        observations, "deposit_size",
        {"oversized", "large", "excessive", "too_much", "above_target"},
    )
    if too_much_obs and not inconsistent_obs and not runtime_drift and not spread_obs:
        candidates.append(DefectMatch(
            code=DefectCode.D02_TOO_MUCH.value,
            name="Too Much Material",
            confidence=0.8,
            reason="Dispensed volume is consistently more than the target.",
            matching_observations=too_much_obs,
        ))

    # --- Handle runtime drift (size change over run time) ---
    if not inconsistent_obs and runtime_drift and (too_little_obs or too_much_obs):
        size_obs = too_little_obs + too_much_obs
        candidates.append(DefectMatch(
            code=DefectCode.D03_INCONSISTENT_SIZE.value,
            name="Inconsistent Dispensing Size",
            confidence=0.85,
            reason="Deposit size changes over operating time, indicating process drift / inconsistency.",
            matching_observations=size_obs + runtime_drift,
        ))

    # --- Handle intermittent + size change without explicit "inconsistent" ---
    if not inconsistent_obs and not runtime_drift and intermittent_obs and (too_little_obs or too_much_obs):
        size_obs = too_little_obs + too_much_obs
        candidates.append(DefectMatch(
            code=DefectCode.D03_INCONSISTENT_SIZE.value,
            name="Inconsistent Dispensing Size",
            confidence=0.7,
            reason="Size defect appears intermittently, suggesting inconsistency.",
            matching_observations=size_obs + intermittent_obs,
        ))

    if not candidates:
        return None

    # Return the highest-confidence candidate
    candidates.sort(key=lambda c: (c.confidence, len(c.matching_observations)), reverse=True)
    return candidates[0]
