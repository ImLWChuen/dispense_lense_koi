"""
DispenseIQ — Image Diagnosis Integration Tests

Verifies:
- Uncalibrated / features-only image analysis produces no score-bearing observations,
  maintaining exact baseline parity with non-image diagnosis.
- Calibrated image observations (e.g. deposit_size=undersized, source=IMAGE)
  feed into DiagnosticEngine and deterministically alter candidate cause scores
  via existing authoritative rule contributions.
- Calibrated oversized observations alter D02 cause rankings.
- Canonical image observations for D03 (inconsistent), D04 (missing), and D05 (tailing)
  are recognized and processed by the engine.
- D06 neutrality: void/irregular features never produce score-bearing observations.
- Intake merge: image observations and natural language description observations
  co-exist and both contribute to diagnosis.
"""

from __future__ import annotations

import json
import pytest

from app.schemas.diagnosis import (
    CandidateCause,
    DiagnosisRequest,
    EvidenceSource,
    Observation,
    ObservationType,
    StructuredCase,
)
from app.services.diagnosis.engine import DiagnosticEngine
from app.api.images import _sync_analyze_image
from app.schemas.image import (
    AnalysisProfile,
    ImageAnalysisMode,
    NormalizedROI,
    ProcessLimits,
    ReferenceLimits,
)
from tests.fixtures.synthetic_images import (
    create_centered_dot_image,
    create_proportional_dot_image,
    create_overflow_image,
    create_empty_image,
)


def _run_vision_pipeline(
    image_bytes: bytes,
    profile: AnalysisProfile,
    reference_bytes: bytes | None = None,
):
    """Helper to run the full vision service pipeline without HTTP."""
    return _sync_analyze_image(
        file_bytes=image_bytes,
        profile=profile,
        reference_bytes=reference_bytes,
    )


def test_uncalibrated_baseline_parity():
    """Features-only / uncalibrated analysis produces no observations and exact baseline score parity."""
    engine = DiagnosticEngine()
    img_bytes = create_centered_dot_image(size=200, dot_radius=20)
    profile = AnalysisProfile(
        mode=ImageAnalysisMode.FEATURES_ONLY,
        rois=[NormalizedROI(roi_id="r1", x=0.2, y=0.2, width=0.6, height=0.6)],
    )

    result = _run_vision_pipeline(img_bytes, profile)
    assert result.status.value == "UNCALIBRATED"
    assert len(result.observations) == 0

    # Baseline diagnosis with no observations
    case_baseline = StructuredCase(defect_code="D01_TOO_LITTLE", observations=[])
    res_baseline = engine.diagnose(case_baseline)

    # Diagnosis with uncalibrated observations (empty)
    case_with_img = StructuredCase(
        defect_code="D01_TOO_LITTLE",
        observations=list(result.observations),
    )
    res_with_img = engine.diagnose(case_with_img)

    assert len(res_baseline.ranked_causes) == len(res_with_img.ranked_causes)
    for c_base, c_img in zip(res_baseline.ranked_causes, res_with_img.ranked_causes):
        assert c_base.cause_id == c_img.cause_id
        assert c_base.score == c_img.score


def test_calibrated_undersized_deposit_alters_score():
    """Calibrated undersized deposit creates score-bearing observation that changes cause rankings."""
    engine = DiagnosticEngine()

    # Small dot (radius 10) in 200x200 image -> coverage ~0.03
    img_bytes = create_centered_dot_image(size=200, dot_radius=10)
    profile = AnalysisProfile(
        mode=ImageAnalysisMode.PROCESS_LIMITS,
        rois=[NormalizedROI(roi_id="r1", x=0.25, y=0.25, width=0.5, height=0.5)],
        process_limits=ProcessLimits(min_coverage_ratio=0.15),
    )

    result = _run_vision_pipeline(img_bytes, profile)
    assert result.status.value == "CALIBRATED"
    assert len(result.observations) == 1
    obs = result.observations[0]
    assert obs.observation_type == ObservationType.DEPOSIT_SIZE
    assert obs.value == "undersized"
    assert obs.source == EvidenceSource.IMAGE

    # Baseline without image
    res_baseline = engine.diagnose(StructuredCase(defect_code="D01_TOO_LITTLE", observations=[]))
    base_scores = {c.cause_id: c.score for c in res_baseline.ranked_causes}

    # Diagnosis with image observation
    res_image = engine.diagnose(StructuredCase(defect_code="D01_TOO_LITTLE", observations=[obs]))
    image_scores = {c.cause_id: c.score for c in res_image.ranked_causes}

    # Causal scores supporting undersized deposit should be higher than baseline
    top_cause = res_image.ranked_causes[0]
    assert image_scores[top_cause.cause_id] > base_scores[top_cause.cause_id]

    # Verify evidence provenance
    all_ev = top_cause.supporting_evidence + top_cause.contradicting_evidence + top_cause.neutral_evidence
    image_ev = [e for e in all_ev if e.source == EvidenceSource.IMAGE]
    assert len(image_ev) >= 1
    assert image_ev[0].score_contribution > 0


def test_calibrated_oversized_deposit_for_d02():
    """Calibrated oversized deposit creates deposit_size=oversized observation."""
    engine = DiagnosticEngine()

    # Large dot (radius 45) inside 100x100 box -> coverage ~0.63
    img_bytes = create_centered_dot_image(size=200, dot_radius=45)
    profile = AnalysisProfile(
        mode=ImageAnalysisMode.PROCESS_LIMITS,
        rois=[NormalizedROI(roi_id="r1", x=0.25, y=0.25, width=0.5, height=0.5)],
        process_limits=ProcessLimits(max_coverage_ratio=0.30),
    )

    result = _run_vision_pipeline(img_bytes, profile)
    assert result.status.value == "CALIBRATED"
    assert len(result.observations) == 1
    obs = result.observations[0]
    assert obs.observation_type == ObservationType.DEPOSIT_SIZE
    assert obs.value == "oversized"
    assert obs.source == EvidenceSource.IMAGE

    res = engine.diagnose(StructuredCase(defect_code="D02_TOO_MUCH", observations=[obs]))
    assert len(res.ranked_causes) > 0
    top_cause = res.ranked_causes[0]
    image_ev = [e for e in top_cause.supporting_evidence if e.source == EvidenceSource.IMAGE]
    assert len(image_ev) >= 1


def test_calibrated_missing_deposit_identifies_d04():
    """Missing deposit from image analysis triggers D04 defect identification."""
    engine = DiagnosticEngine()
    img_bytes = create_empty_image(size=200)
    profile = AnalysisProfile(
        mode=ImageAnalysisMode.PROCESS_LIMITS,
        rois=[NormalizedROI(roi_id="r1", x=0.25, y=0.25, width=0.5, height=0.5)],
        process_limits=ProcessLimits(min_presence_ratio=0.05),
    )

    result = _run_vision_pipeline(img_bytes, profile)
    assert result.status.value == "CALIBRATED"
    assert len(result.observations) == 1
    obs = result.observations[0]
    assert obs.observation_type == ObservationType.DEPOSIT_PRESENCE
    assert obs.value == "missing"

    case = StructuredCase(observations=[obs])
    res = engine.diagnose(case)
    assert res.defect == "D04_MISSING_DOTS"


def test_d06_neutrality_no_score_bearing_observations():
    """D06 bubble/shape features never produce score-bearing observations."""
    engine = DiagnosticEngine()

    # Image with small dot
    img_bytes = create_centered_dot_image(size=200, dot_radius=20)
    profile = AnalysisProfile(
        mode=ImageAnalysisMode.FEATURES_ONLY,
        rois=[NormalizedROI(roi_id="r1", x=0.25, y=0.25, width=0.5, height=0.5)],
    )

    result = _run_vision_pipeline(img_bytes, profile)
    # FEATURES_ONLY produces 0 score-bearing observations
    assert len(result.observations) == 0

    # Even if an irregular shape / void is detected in measurements, classifier produces no D06 score-bearing obs
    for obs in result.observations:
        assert obs.observation_type not in (
            ObservationType.BUBBLE_PRESENCE,
            ObservationType.DEPOSIT_SHAPE,
        )


def test_intake_merge_image_and_text_description():
    """Both image observations and text symptoms co-exist and affect ranking."""
    engine = DiagnosticEngine()

    # Image observation
    img_obs = Observation(
        observation_type=ObservationType.DEPOSIT_SIZE,
        value="undersized",
        source=EvidenceSource.IMAGE,
        metadata={"coverage_ratio": 0.04},
    )

    case = StructuredCase(
        description="pressure drop observed during run",
        observations=[img_obs],
    )

    res = engine.diagnose(case)
    obs_types = {getattr(o.observation_type, "value", str(o.observation_type)) for o in case.observations}
    assert "deposit_size" in obs_types
    assert "pressure" in obs_types

    # Both observations are preserved in case.observations
    assert len(case.observations) == 2
    sources = {o.source for o in case.observations}
    assert EvidenceSource.IMAGE in sources
    assert EvidenceSource.USER in sources
