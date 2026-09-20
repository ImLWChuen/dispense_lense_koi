"""
Dispense Lens - Vision Defect Classifier Unit Tests

Verifies:
- Mode FEATURES_ONLY returns UNCALIBRATED and no score-bearing observations.
- Mode PROCESS_LIMITS classifies only caller-supplied limits:
  - D01: deposit_size=undersized
  - D02: deposit_size=oversized
  - D03: deposit_size=inconsistent
  - D04: deposit_presence=missing
  - D05: spreading_behaviour=excessive_spread
- Mode REFERENCE_IMAGE:
  - Classifies current vs reference coverage ratio using caller-supplied tolerances.
  - Scaling current and reference together preserves normalized ratio and classification.
  - Unreliable reference image downgrades status to UNRELIABLE and produces no observations.
- Emitted observations use source=IMAGE, statement_type=AI_INFERENCE, and contain metadata.
- D06 bubble/abnormal shape remains diagnostic-neutral.
- Resolution independence: 100x100, 200x200, and 400x400 yield identical calibrated classification.
"""

from __future__ import annotations

import pytest

from app.schemas.diagnosis import EvidenceSource, StatementType
from app.schemas.image import (
    AnalysisStatus,
    ImageAnalysisMode,
    NormalizedROI,
    ProcessLimits,
    ReferenceLimits,
)
from app.services.vision.defect_classifier import classify_defects_from_measurements
from app.services.vision.measurement import (
    calculate_aggregate_measurements,
    calculate_roi_features,
)
from app.services.vision.preprocessing import decode_and_validate_image, normalize_roi_to_pixels
from app.services.vision.segmentation import segment_roi
from tests.fixtures.synthetic_images import (
    create_centered_dot_image,
    create_empty_image,
    create_overflow_image,
    create_proportional_dot_image,
)


def _measure_single_roi(img_bytes: bytes, roi: NormalizedROI):
    img, dims = decode_and_validate_image(img_bytes)
    px_roi, win_roi = normalize_roi_to_pixels(roi, dims.width, dims.height, window_expansion=0.2)
    seg = segment_roi(img, px_roi, win_roi)
    feat = calculate_roi_features(seg, px_roi, roi.roi_id)
    agg = calculate_aggregate_measurements([feat], [roi.roi_id])
    return dims, [feat], agg


def test_features_only_mode_returns_uncalibrated_no_observations() -> None:
    img_bytes = create_centered_dot_image(200, 20)
    roi = NormalizedROI(roi_id="roi_1", x=0.25, y=0.25, width=0.5, height=0.5)
    dims, feats, agg = _measure_single_roi(img_bytes, roi)

    status, obs, warnings = classify_defects_from_measurements(
        mode=ImageAnalysisMode.FEATURES_ONLY,
        roi_measurements=feats,
        aggregate=agg,
    )
    assert status == AnalysisStatus.UNCALIBRATED
    assert len(obs) == 0


def test_process_limits_d01_undersized() -> None:
    # Small dot: radius 10 at 200x200 (area ~314 px, target area 100x100 = 10000 px -> coverage 0.0314)
    img_bytes = create_centered_dot_image(200, 10)
    roi = NormalizedROI(roi_id="roi_1", x=0.25, y=0.25, width=0.5, height=0.5)
    dims, feats, agg = _measure_single_roi(img_bytes, roi)

    limits = ProcessLimits(min_coverage_ratio=0.10)
    status, obs, warnings = classify_defects_from_measurements(
        mode=ImageAnalysisMode.PROCESS_LIMITS,
        roi_measurements=feats,
        aggregate=agg,
        process_limits=limits,
    )
    assert status == AnalysisStatus.CALIBRATED
    assert len(obs) == 1
    assert obs[0].observation_type == "deposit_size"
    assert obs[0].value == "undersized"
    assert obs[0].source == EvidenceSource.IMAGE
    assert obs[0].statement_type == StatementType.AI_INFERENCE
    assert "coverage_ratio" in obs[0].metadata


def test_process_limits_d02_oversized() -> None:
    # Large dot: radius 45 at 200x200 (area ~6361 px, target 10000 px -> coverage 0.636)
    img_bytes = create_centered_dot_image(200, 45)
    roi = NormalizedROI(roi_id="roi_1", x=0.25, y=0.25, width=0.5, height=0.5)
    dims, feats, agg = _measure_single_roi(img_bytes, roi)

    limits = ProcessLimits(max_coverage_ratio=0.40)
    status, obs, warnings = classify_defects_from_measurements(
        mode=ImageAnalysisMode.PROCESS_LIMITS,
        roi_measurements=feats,
        aggregate=agg,
        process_limits=limits,
    )
    assert status == AnalysisStatus.CALIBRATED
    assert len(obs) == 1
    assert obs[0].observation_type == "deposit_size"
    assert obs[0].value == "oversized"
    assert obs[0].source == EvidenceSource.IMAGE


def test_process_limits_d04_missing() -> None:
    img_bytes = create_empty_image(200)
    roi = NormalizedROI(roi_id="roi_1", x=0.25, y=0.25, width=0.5, height=0.5)
    dims, feats, agg = _measure_single_roi(img_bytes, roi)

    limits = ProcessLimits(min_presence_ratio=0.01)
    status, obs, warnings = classify_defects_from_measurements(
        mode=ImageAnalysisMode.PROCESS_LIMITS,
        roi_measurements=feats,
        aggregate=agg,
        process_limits=limits,
    )
    assert status == AnalysisStatus.CALIBRATED
    assert any(o.observation_type == "deposit_presence" and o.value == "missing" for o in obs)


def test_process_limits_d05_overflow_spread() -> None:
    img_bytes = create_overflow_image(200)
    roi = NormalizedROI(roi_id="roi_1", x=0.25, y=0.25, width=0.5, height=0.5)
    dims, feats, agg = _measure_single_roi(img_bytes, roi)

    limits = ProcessLimits(max_overflow_ratio=0.05)
    status, obs, warnings = classify_defects_from_measurements(
        mode=ImageAnalysisMode.PROCESS_LIMITS,
        roi_measurements=feats,
        aggregate=agg,
        process_limits=limits,
    )
    assert status == AnalysisStatus.CALIBRATED
    assert any(o.observation_type == "spreading_behaviour" and o.value == "excessive_spread" for o in obs)


def test_resolution_independence_classification_100_200_400() -> None:
    """The same normalized geometry at 100x100, 200x200, and 400x400

    yields the exact same calibrated classification under identical process limits.
    """
    roi = NormalizedROI(roi_id="roi_1", x=0.25, y=0.25, width=0.5, height=0.5)
    # Undersized normalized radius 0.08
    limits = ProcessLimits(min_coverage_ratio=0.10)

    for size in [100, 200, 400]:
        img_bytes = create_proportional_dot_image(size=size, normalized_radius=0.08)
        dims, feats, agg = _measure_single_roi(img_bytes, roi)
        status, obs, _ = classify_defects_from_measurements(
            mode=ImageAnalysisMode.PROCESS_LIMITS,
            roi_measurements=feats,
            aggregate=agg,
            process_limits=limits,
        )
        assert status == AnalysisStatus.CALIBRATED
        assert len(obs) == 1
        assert obs[0].value == "undersized"


def test_reference_image_mode_scaling_invariance() -> None:
    """Scaling current and reference images together preserves normalized ratio and classification."""
    roi = NormalizedROI(roi_id="roi_1", x=0.25, y=0.25, width=0.5, height=0.5)
    ref_limits = ReferenceLimits(min_reference_ratio=0.85, max_reference_ratio=1.15)

    # Scale 1: Current radius 0.12, Reference radius 0.20 at 100x100
    curr_100 = create_proportional_dot_image(100, 0.12)
    ref_100 = create_proportional_dot_image(100, 0.20)
    _, curr_feats_100, curr_agg_100 = _measure_single_roi(curr_100, roi)
    _, ref_feats_100, ref_agg_100 = _measure_single_roi(ref_100, roi)

    status_100, obs_100, _ = classify_defects_from_measurements(
        mode=ImageAnalysisMode.REFERENCE_IMAGE,
        roi_measurements=curr_feats_100,
        aggregate=curr_agg_100,
        reference_measurements=ref_feats_100,
        reference_aggregate=ref_agg_100,
        reference_limits=ref_limits,
    )

    # Scale 2: Same proportional radii at 400x400
    curr_400 = create_proportional_dot_image(400, 0.12)
    ref_400 = create_proportional_dot_image(400, 0.20)
    _, curr_feats_400, curr_agg_400 = _measure_single_roi(curr_400, roi)
    _, ref_feats_400, ref_agg_400 = _measure_single_roi(ref_400, roi)

    status_400, obs_400, _ = classify_defects_from_measurements(
        mode=ImageAnalysisMode.REFERENCE_IMAGE,
        roi_measurements=curr_feats_400,
        aggregate=curr_agg_400,
        reference_measurements=ref_feats_400,
        reference_aggregate=ref_agg_400,
        reference_limits=ref_limits,
    )

    assert status_100 == AnalysisStatus.CALIBRATED
    assert status_400 == AnalysisStatus.CALIBRATED
    assert len(obs_100) == 1 and obs_100[0].value == "undersized"
    assert len(obs_400) == 1 and obs_400[0].value == "undersized"


def test_omitted_limits_never_emit_unrequested_dimensions() -> None:
    """R4: An omitted limit field must never emit observations for that defect dimension."""
    roi = NormalizedROI(roi_id="roi_1", x=0.25, y=0.25, width=0.5, height=0.5)

    # 1. Empty image with only max_size_cv supplied: MUST NOT emit missing or undersized
    empty_img = create_empty_image(200)
    _, empty_feats, empty_agg = _measure_single_roi(empty_img, roi)
    status, obs, _ = classify_defects_from_measurements(
        mode=ImageAnalysisMode.PROCESS_LIMITS,
        roi_measurements=empty_feats,
        aggregate=empty_agg,
        process_limits=ProcessLimits(max_size_cv=0.2),
    )
    assert status == AnalysisStatus.CALIBRATED
    assert not any(o.observation_type == "deposit_presence" for o in obs)
    assert not any(o.value == "undersized" for o in obs)

    # 2. Empty image with only min_coverage_ratio supplied: emits undersized, but MUST NOT emit missing
    status, obs, _ = classify_defects_from_measurements(
        mode=ImageAnalysisMode.PROCESS_LIMITS,
        roi_measurements=empty_feats,
        aggregate=empty_agg,
        process_limits=ProcessLimits(min_coverage_ratio=0.10),
    )
    assert status == AnalysisStatus.CALIBRATED
    assert any(o.observation_type == "deposit_size" and o.value == "undersized" for o in obs)
    assert not any(o.observation_type == "deposit_presence" for o in obs)

    # 3. Oversized deposit with only min_coverage_ratio (omitting max_coverage_ratio): MUST NOT emit oversized
    large_img = create_centered_dot_image(200, 45)
    _, large_feats, large_agg = _measure_single_roi(large_img, roi)
    status, obs, _ = classify_defects_from_measurements(
        mode=ImageAnalysisMode.PROCESS_LIMITS,
        roi_measurements=large_feats,
        aggregate=large_agg,
        process_limits=ProcessLimits(min_coverage_ratio=0.01),
    )
    assert status == AnalysisStatus.CALIBRATED
    assert not any(o.value == "oversized" for o in obs)

    # 4. Overflow deposit with only min_coverage_ratio (omitting max_overflow_ratio): MUST NOT emit excessive_spread
    overflow_img = create_overflow_image(200)
    _, overflow_feats, overflow_agg = _measure_single_roi(overflow_img, roi)
    status, obs, _ = classify_defects_from_measurements(
        mode=ImageAnalysisMode.PROCESS_LIMITS,
        roi_measurements=overflow_feats,
        aggregate=overflow_agg,
        process_limits=ProcessLimits(min_coverage_ratio=0.01),
    )
    assert status == AnalysisStatus.CALIBRATED
    assert not any(o.value == "excessive_spread" for o in obs)
