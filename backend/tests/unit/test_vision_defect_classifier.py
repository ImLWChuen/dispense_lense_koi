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
    AggregateMeasurements,
    AnalysisStatus,
    ImageAnalysisMode,
    NormalizedROI,
    ProcessLimits,
    ReferenceLimits,
    RoiInspectionStatus,
    RoiMeasurement,
)
from app.services.vision.defect_classifier import classify_defects_from_measurements
from app.services.vision.measurement import (
    calculate_aggregate_measurements,
    calculate_roi_features,
)
from app.services.vision.preprocessing import decode_and_validate_image, normalize_roi_to_pixels
from app.services.vision.segmentation import segment_roi
from tests.fixtures.synthetic_images import (
    create_abnormal_shape_image,
    create_bubble_dot_image,
    create_centered_dot_image,
    create_empty_image,
    create_overflow_image,
    create_proportional_dot_image,
    create_tailing_dot_image,
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


def test_process_limits_d06_tailing_aspect_ratio() -> None:
    """Tailing deposit violates max_aspect_ratio and emits deposit_shape=tailing."""
    tailing_img = create_tailing_dot_image(size=200, head_radius=22, tail_length=45, direction="horizontal")
    roi = NormalizedROI(roi_id="roi_1", x=0.20, y=0.20, width=0.60, height=0.60)
    dims, feats, agg = _measure_single_roi(tailing_img, roi)

    assert feats[0].aspect_ratio > 1.35
    assert feats[0].is_tailing is True

    limits = ProcessLimits(max_aspect_ratio=1.30)
    status, obs, warnings = classify_defects_from_measurements(
        mode=ImageAnalysisMode.PROCESS_LIMITS,
        roi_measurements=feats,
        aggregate=agg,
        process_limits=limits,
    )
    assert status == AnalysisStatus.CALIBRATED
    assert len(obs) == 1
    assert obs[0].observation_type == "deposit_shape"
    assert obs[0].value == "tailing"
    assert obs[0].source == EvidenceSource.IMAGE
    assert obs[0].statement_type == StatementType.AI_INFERENCE
    assert "aspect_ratio" in obs[0].metadata


def test_process_limits_d06_abnormal_shape_circularity_solidity() -> None:
    """Non-circular/indented deposit violates min_circularity or min_solidity and emits deposit_shape=abnormal."""
    abnormal_img = create_abnormal_shape_image(size=200)
    roi = NormalizedROI(roi_id="roi_1", x=0.20, y=0.20, width=0.60, height=0.60)
    dims, feats, agg = _measure_single_roi(abnormal_img, roi)

    assert feats[0].circularity < 0.70
    assert feats[0].is_abnormal_shape is True

    limits = ProcessLimits(min_circularity=0.75, min_solidity=0.85)
    status, obs, warnings = classify_defects_from_measurements(
        mode=ImageAnalysisMode.PROCESS_LIMITS,
        roi_measurements=feats,
        aggregate=agg,
        process_limits=limits,
    )
    assert status == AnalysisStatus.CALIBRATED
    assert any(o.observation_type == "deposit_shape" and o.value == "abnormal" for o in obs)


def test_process_limits_d06_bubble_detection() -> None:
    """Deposit with internal air bubbles violates max_bubble_count and emits bubble_presence=visible_bubbles."""
    bubble_img = create_bubble_dot_image(size=200, dot_radius=35, bubble_count=1, bubble_radius=8)
    roi = NormalizedROI(roi_id="roi_1", x=0.20, y=0.20, width=0.60, height=0.60)
    dims, feats, agg = _measure_single_roi(bubble_img, roi)

    assert feats[0].bubble_count >= 1
    assert feats[0].has_bubbles is True

    limits = ProcessLimits(max_bubble_count=0)
    status, obs, warnings = classify_defects_from_measurements(
        mode=ImageAnalysisMode.PROCESS_LIMITS,
        roi_measurements=feats,
        aggregate=agg,
        process_limits=limits,
    )
    assert status == AnalysisStatus.CALIBRATED
    assert any(o.observation_type == "bubble_presence" and o.value == "visible_bubbles" for o in obs)


def test_omitted_shape_limits_never_emit_d06_observations() -> None:
    """Rule R4 applies to D06: omitting shape and bubble limits never emits D06 observations."""
    bubble_img = create_bubble_dot_image(size=200, dot_radius=35, bubble_count=1, bubble_radius=8)
    roi = NormalizedROI(roi_id="roi_1", x=0.20, y=0.20, width=0.60, height=0.60)
    dims, feats, agg = _measure_single_roi(bubble_img, roi)

    # Only supply min_coverage_ratio
    limits = ProcessLimits(min_coverage_ratio=0.05)
    status, obs, _ = classify_defects_from_measurements(
        mode=ImageAnalysisMode.PROCESS_LIMITS,
        roi_measurements=feats,
        aggregate=agg,
        process_limits=limits,
    )
    assert status == AnalysisStatus.CALIBRATED
    # Must NOT emit bubble or shape observations when those limit dimensions are omitted
    assert not any(o.observation_type == "bubble_presence" for o in obs)
    assert not any(o.observation_type == "deposit_shape" for o in obs)


def test_explicit_unassessed_overrides_high_numeric_quality_in_process_limits() -> None:
    """Explicit UNASSESSED overrides artificial high numeric quality (1.0) and forces UNRELIABLE in PROCESS_LIMITS."""
    from app.schemas.image import AggregateMeasurements, RoiInspectionStatus, RoiMeasurement

    feat_unassessed = RoiMeasurement(
        roi_id="roi_test",
        deposit_area_px=100.0,
        target_area_px=1000.0,
        coverage_ratio=0.10,
        overflow_ratio=0.0,
        equivalent_diameter_px=11.2,
        circularity=0.9,
        solidity=0.95,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=1.0,  # Misleadingly high quality
        is_missing=False,
        inspection_status=RoiInspectionStatus.UNASSESSED,
        inspection_warnings=["Contradictory segmentation candidate score."],
    )
    agg = AggregateMeasurements(
        mean_coverage=None,
        size_cv=None,
        missing_roi_ids=[],
        unassessed_roi_ids=["roi_test"],
        warnings=[],
    )

    limits = ProcessLimits(min_coverage_ratio=0.20)  # Would normally trigger D01 undersized
    status, obs, warnings = classify_defects_from_measurements(
        mode=ImageAnalysisMode.PROCESS_LIMITS,
        roi_measurements=[feat_unassessed],
        aggregate=agg,
        process_limits=limits,
    )
    assert status == AnalysisStatus.UNRELIABLE
    assert obs == []
    assert any("roi_test" in w and "unassessed" in w for w in warnings)


def test_explicit_unassessed_overrides_high_numeric_quality_in_reference_mode() -> None:
    """Explicit UNASSESSED in reference measurement overrides quality 1.0 and forces UNRELIABLE."""
    from app.schemas.image import AggregateMeasurements, RoiInspectionStatus, RoiMeasurement

    curr_feat = RoiMeasurement(
        roi_id="roi_1",
        deposit_area_px=500.0,
        target_area_px=1000.0,
        coverage_ratio=0.50,
        overflow_ratio=0.0,
        equivalent_diameter_px=25.2,
        circularity=0.9,
        solidity=0.95,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=1.0,
        is_missing=False,
        inspection_status=RoiInspectionStatus.DETECTED,
    )
    ref_feat_unassessed = RoiMeasurement(
        roi_id="roi_1",
        deposit_area_px=500.0,
        target_area_px=1000.0,
        coverage_ratio=0.50,
        overflow_ratio=0.0,
        equivalent_diameter_px=25.2,
        circularity=0.9,
        solidity=0.95,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=1.0,  # Misleadingly high quality
        is_missing=False,
        inspection_status=RoiInspectionStatus.UNASSESSED,
        inspection_warnings=["Reference window boundary clipped."],
    )

    curr_agg = AggregateMeasurements(
        mean_coverage=0.50,
        size_cv=None,
        missing_roi_ids=[],
        unassessed_roi_ids=[],
    )
    ref_agg = AggregateMeasurements(
        mean_coverage=None,
        size_cv=None,
        missing_roi_ids=[],
        unassessed_roi_ids=["roi_1"],
    )

    ref_limits = ReferenceLimits(tolerance_ratio=0.10)
    status, obs, warnings = classify_defects_from_measurements(
        mode=ImageAnalysisMode.REFERENCE_IMAGE,
        roi_measurements=[curr_feat],
        aggregate=curr_agg,
        reference_measurements=[ref_feat_unassessed],
        reference_aggregate=ref_agg,
        reference_limits=ref_limits,
    )
    assert status == AnalysisStatus.UNRELIABLE
    assert obs == []
    assert any("Reference ROI 'roi_1' is unassessed" in w for w in warnings)


def test_multiple_unassessed_reference_regions_collects_all_ids_and_reasons() -> None:
    """R1 regression: Multiple unassessed reference ROIs must all be named with their reasons."""
    curr_feat_1 = RoiMeasurement(
        roi_id="dot_1",
        deposit_area_px=500.0,
        target_area_px=1000.0,
        coverage_ratio=0.50,
        overflow_ratio=0.0,
        equivalent_diameter_px=25.2,
        circularity=0.9,
        solidity=0.95,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=1.0,
        is_missing=False,
        inspection_status=RoiInspectionStatus.DETECTED,
    )
    curr_feat_2 = RoiMeasurement(
        roi_id="dot_2",
        deposit_area_px=500.0,
        target_area_px=1000.0,
        coverage_ratio=0.50,
        overflow_ratio=0.0,
        equivalent_diameter_px=25.2,
        circularity=0.9,
        solidity=0.95,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=1.0,
        is_missing=False,
        inspection_status=RoiInspectionStatus.DETECTED,
    )
    ref_unassessed_1 = RoiMeasurement(
        roi_id="dot_1",
        deposit_area_px=500.0,
        target_area_px=1000.0,
        coverage_ratio=0.50,
        overflow_ratio=0.0,
        equivalent_diameter_px=25.2,
        circularity=0.9,
        solidity=0.95,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=1.0,
        is_missing=False,
        inspection_status=RoiInspectionStatus.UNASSESSED,
        inspection_warnings=["Clipping at window boundary."],
    )
    ref_unassessed_2 = RoiMeasurement(
        roi_id="dot_2",
        deposit_area_px=500.0,
        target_area_px=1000.0,
        coverage_ratio=0.50,
        overflow_ratio=0.0,
        equivalent_diameter_px=25.2,
        circularity=0.9,
        solidity=0.95,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=1.0,
        is_missing=False,
        inspection_status=RoiInspectionStatus.UNASSESSED,
        inspection_warnings=["Low contrast ambiguous segmentation."],
    )

    curr_agg = AggregateMeasurements(
        mean_coverage=0.50,
        size_cv=0.0,
        missing_roi_ids=[],
        unassessed_roi_ids=[],
    )
    ref_agg = AggregateMeasurements(
        mean_coverage=None,
        size_cv=None,
        missing_roi_ids=[],
        unassessed_roi_ids=["dot_1", "dot_2"],
    )

    ref_limits = ReferenceLimits(tolerance_ratio=0.10)
    status, obs, warnings = classify_defects_from_measurements(
        mode=ImageAnalysisMode.REFERENCE_IMAGE,
        roi_measurements=[curr_feat_1, curr_feat_2],
        aggregate=curr_agg,
        reference_measurements=[ref_unassessed_1, ref_unassessed_2],
        reference_aggregate=ref_agg,
        reference_limits=ref_limits,
    )
    assert status == AnalysisStatus.UNRELIABLE
    assert obs == []
    assert any("dot_1" in w and "Clipping at window boundary" in w for w in warnings)
    assert any("dot_2" in w and "Low contrast ambiguous segmentation" in w for w in warnings)


def test_simultaneous_current_and_reference_failures_collects_both_explanations() -> None:
    """R1 regression: Simultaneous current and reference failures must retain both sets of explanations."""
    curr_unassessed = RoiMeasurement(
        roi_id="dot_a",
        deposit_area_px=0.0,
        target_area_px=1000.0,
        coverage_ratio=0.0,
        overflow_ratio=0.0,
        equivalent_diameter_px=0.0,
        circularity=0.0,
        solidity=0.0,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=0.0,
        is_missing=False,
        inspection_status=RoiInspectionStatus.UNASSESSED,
        inspection_warnings=["Zero deposit area without confirmed absence."],
    )
    ref_unassessed = RoiMeasurement(
        roi_id="dot_b",
        deposit_area_px=500.0,
        target_area_px=1000.0,
        coverage_ratio=0.50,
        overflow_ratio=0.0,
        equivalent_diameter_px=25.2,
        circularity=0.9,
        solidity=0.95,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=1.0,
        is_missing=False,
        inspection_status=RoiInspectionStatus.UNASSESSED,
        inspection_warnings=["Reference window boundary clipped."],
    )

    curr_agg = AggregateMeasurements(
        mean_coverage=None,
        size_cv=None,
        missing_roi_ids=[],
        unassessed_roi_ids=["dot_a"],
    )
    ref_agg = AggregateMeasurements(
        mean_coverage=None,
        size_cv=None,
        missing_roi_ids=[],
        unassessed_roi_ids=["dot_b"],
    )

    ref_limits = ReferenceLimits(tolerance_ratio=0.10)
    status, obs, warnings = classify_defects_from_measurements(
        mode=ImageAnalysisMode.REFERENCE_IMAGE,
        roi_measurements=[curr_unassessed],
        aggregate=curr_agg,
        reference_measurements=[ref_unassessed],
        reference_aggregate=ref_agg,
        reference_limits=ref_limits,
    )
    assert status == AnalysisStatus.UNRELIABLE
    assert obs == []
    # Both current and reference failure explanations must be collected into warnings
    assert any("dot_a" in w and "Zero deposit area without confirmed absence" in w for w in warnings)
    assert any("dot_b" in w and "Reference window boundary clipped" in w for w in warnings)


def test_empty_current_measurements_with_populated_unassessed_ids() -> None:
    """R1 regression: Empty current measurements with unassessed IDs generates missing-measurement warnings and preserves status."""
    aggregate = AggregateMeasurements(
        mean_coverage=None,
        size_cv=None,
        missing_roi_ids=[],
        unassessed_roi_ids=["roi_a", "roi_b"],
    )

    # FEATURES_ONLY: preserves UNCALIBRATED with empty observations and expected warnings
    status_fo, obs_fo, warnings_fo = classify_defects_from_measurements(
        mode=ImageAnalysisMode.FEATURES_ONLY,
        roi_measurements=[],
        aggregate=aggregate,
    )
    assert status_fo == AnalysisStatus.UNCALIBRATED
    assert obs_fo == []
    assert any("ROI 'roi_a' is unassessed (missing measurement data)." in w for w in warnings_fo)
    assert any("ROI 'roi_b' is unassessed (missing measurement data)." in w for w in warnings_fo)

    # PROCESS_LIMITS: preserves UNRELIABLE with empty observations and expected warnings
    limits = ProcessLimits(min_coverage_ratio=0.10)
    status_pl, obs_pl, warnings_pl = classify_defects_from_measurements(
        mode=ImageAnalysisMode.PROCESS_LIMITS,
        roi_measurements=[],
        aggregate=aggregate,
        process_limits=limits,
    )
    assert status_pl == AnalysisStatus.UNRELIABLE
    assert obs_pl == []
    assert any("ROI 'roi_a' is unassessed (missing measurement data)." in w for w in warnings_pl)
    assert any("ROI 'roi_b' is unassessed (missing measurement data)." in w for w in warnings_pl)


def test_empty_reference_measurements_with_populated_unassessed_ids() -> None:
    """R1 regression: Empty/None reference measurements with unassessed IDs generates missing-measurement warnings."""
    curr_feat = RoiMeasurement(
        roi_id="dot_1",
        deposit_area_px=500.0,
        target_area_px=1000.0,
        coverage_ratio=0.50,
        overflow_ratio=0.0,
        equivalent_diameter_px=25.2,
        circularity=0.9,
        solidity=0.95,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=1.0,
        is_missing=False,
        inspection_status=RoiInspectionStatus.DETECTED,
    )
    curr_agg = AggregateMeasurements(
        mean_coverage=0.50,
        size_cv=None,
        missing_roi_ids=[],
        unassessed_roi_ids=[],
    )
    ref_agg = AggregateMeasurements(
        mean_coverage=None,
        size_cv=None,
        missing_roi_ids=[],
        unassessed_roi_ids=["ref_roi_1", "ref_roi_2"],
    )
    ref_limits = ReferenceLimits(tolerance_ratio=0.10)

    # Empty list [] for reference_measurements
    status_empty, obs_empty, warnings_empty = classify_defects_from_measurements(
        mode=ImageAnalysisMode.REFERENCE_IMAGE,
        roi_measurements=[curr_feat],
        aggregate=curr_agg,
        reference_measurements=[],
        reference_aggregate=ref_agg,
        reference_limits=ref_limits,
    )
    assert status_empty == AnalysisStatus.UNRELIABLE
    assert obs_empty == []
    assert any("Reference ROI 'ref_roi_1' is unassessed (missing measurement data); downgrading analysis." in w for w in warnings_empty)
    assert any("Reference ROI 'ref_roi_2' is unassessed (missing measurement data); downgrading analysis." in w for w in warnings_empty)

    # None for reference_measurements
    status_none, obs_none, warnings_none = classify_defects_from_measurements(
        mode=ImageAnalysisMode.REFERENCE_IMAGE,
        roi_measurements=[curr_feat],
        aggregate=curr_agg,
        reference_measurements=None,
        reference_aggregate=ref_agg,
        reference_limits=ref_limits,
    )
    assert status_none == AnalysisStatus.UNRELIABLE
    assert obs_none == []
    assert any("Reference ROI 'ref_roi_1' is unassessed (missing measurement data); downgrading analysis." in w for w in warnings_none)
    assert any("Reference ROI 'ref_roi_2' is unassessed (missing measurement data); downgrading analysis." in w for w in warnings_none)


def test_two_rois_same_defect_preserves_every_affected_roi_id_in_metadata() -> None:
    """Two ROIs with the same defect emit one observation with both ROI IDs in affected_roi_ids."""
    from app.schemas.image import AggregateMeasurements, RoiInspectionStatus, RoiMeasurement

    m1 = RoiMeasurement(
        roi_id="site_1",
        deposit_area_px=100.0,
        target_area_px=1000.0,
        coverage_ratio=0.05,
        overflow_ratio=0.0,
        equivalent_diameter_px=11.2,
        circularity=0.9,
        solidity=0.95,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=1.0,
        is_missing=False,
        inspection_status=RoiInspectionStatus.DETECTED,
    )
    m2 = RoiMeasurement(
        roi_id="site_2",
        deposit_area_px=120.0,
        target_area_px=1000.0,
        coverage_ratio=0.06,
        overflow_ratio=0.0,
        equivalent_diameter_px=12.3,
        circularity=0.9,
        solidity=0.95,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=1.0,
        is_missing=False,
        inspection_status=RoiInspectionStatus.DETECTED,
    )
    agg = AggregateMeasurements(
        mean_coverage=0.055,
        size_cv=0.10,
        missing_roi_ids=[],
        unassessed_roi_ids=[],
    )
    limits = ProcessLimits(min_coverage_ratio=0.10)

    status, obs, _ = classify_defects_from_measurements(
        mode=ImageAnalysisMode.PROCESS_LIMITS,
        roi_measurements=[m1, m2],
        aggregate=agg,
        process_limits=limits,
    )

    assert status == AnalysisStatus.CALIBRATED
    assert len(obs) == 1
    assert obs[0].observation_type == "deposit_size"
    assert obs[0].value == "undersized"
    assert "affected_roi_ids" in obs[0].metadata
    assert obs[0].metadata["affected_roi_ids"] == ["site_1", "site_2"]
    assert obs[0].metadata["roi_id"] == "site_1"


def test_different_defect_values_have_independent_affected_roi_ids() -> None:
    """Distinct defect values (undersized vs oversized) retain independent affected_roi_ids."""
    m_under = RoiMeasurement(
        roi_id="site_under",
        deposit_area_px=50.0,
        target_area_px=1000.0,
        coverage_ratio=0.05,
        overflow_ratio=0.0,
        equivalent_diameter_px=8.0,
        circularity=0.9,
        solidity=0.95,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=1.0,
        is_missing=False,
        inspection_status=RoiInspectionStatus.DETECTED,
    )
    m_over = RoiMeasurement(
        roi_id="site_over",
        deposit_area_px=600.0,
        target_area_px=1000.0,
        coverage_ratio=0.60,
        overflow_ratio=0.0,
        equivalent_diameter_px=27.6,
        circularity=0.9,
        solidity=0.95,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=1.0,
        is_missing=False,
        inspection_status=RoiInspectionStatus.DETECTED,
    )
    agg = AggregateMeasurements(
        mean_coverage=0.325,
        size_cv=0.0,
        missing_roi_ids=[],
        unassessed_roi_ids=[],
    )
    limits = ProcessLimits(min_coverage_ratio=0.10, max_coverage_ratio=0.50)

    status, obs, _ = classify_defects_from_measurements(
        mode=ImageAnalysisMode.PROCESS_LIMITS,
        roi_measurements=[m_under, m_over],
        aggregate=agg,
        process_limits=limits,
    )

    assert status == AnalysisStatus.CALIBRATED
    assert len(obs) == 2
    obs_by_val = {o.value: o for o in obs}
    assert "undersized" in obs_by_val
    assert "oversized" in obs_by_val
    assert obs_by_val["undersized"].metadata["affected_roi_ids"] == ["site_under"]
    assert obs_by_val["oversized"].metadata["affected_roi_ids"] == ["site_over"]


def test_single_roi_violating_multiple_independent_dimensions() -> None:
    """One ROI violating multiple dimensions appears once in each distinct observation list."""
    m_multi = RoiMeasurement(
        roi_id="site_1",
        deposit_area_px=50.0,
        target_area_px=1000.0,
        coverage_ratio=0.05,
        overflow_ratio=0.0,
        equivalent_diameter_px=8.0,
        circularity=0.9,
        solidity=0.95,
        aspect_ratio=2.5,  # Tailing violation
        hole_void_ratio=0.0,
        segmentation_quality=1.0,
        is_missing=False,
        inspection_status=RoiInspectionStatus.DETECTED,
    )
    agg = AggregateMeasurements(
        mean_coverage=0.05,
        size_cv=None,
        missing_roi_ids=[],
        unassessed_roi_ids=[],
    )
    limits = ProcessLimits(min_coverage_ratio=0.10, max_aspect_ratio=1.30)

    status, obs, _ = classify_defects_from_measurements(
        mode=ImageAnalysisMode.PROCESS_LIMITS,
        roi_measurements=[m_multi],
        aggregate=agg,
        process_limits=limits,
    )

    assert status == AnalysisStatus.CALIBRATED
    assert len(obs) == 2
    types = {o.observation_type: o for o in obs}
    assert "deposit_size" in types
    assert "deposit_shape" in types
    assert types["deposit_size"].metadata["affected_roi_ids"] == ["site_1"]
    assert types["deposit_shape"].metadata["affected_roi_ids"] == ["site_1"]


def test_per_rule_limit_gating_excludes_nonviolating_sites() -> None:
    """Nonviolating ROIs are strictly excluded from affected_roi_ids."""
    m1_violating = RoiMeasurement(
        roi_id="r1",
        deposit_area_px=40.0,
        target_area_px=1000.0,
        coverage_ratio=0.04,
        overflow_ratio=0.0,
        equivalent_diameter_px=7.1,
        circularity=0.9,
        solidity=0.95,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=1.0,
        is_missing=False,
        inspection_status=RoiInspectionStatus.DETECTED,
    )
    m2_ok = RoiMeasurement(
        roi_id="r2",
        deposit_area_px=200.0,
        target_area_px=1000.0,
        coverage_ratio=0.20,
        overflow_ratio=0.0,
        equivalent_diameter_px=16.0,
        circularity=0.9,
        solidity=0.95,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=1.0,
        is_missing=False,
        inspection_status=RoiInspectionStatus.DETECTED,
    )
    m3_violating = RoiMeasurement(
        roi_id="r3",
        deposit_area_px=50.0,
        target_area_px=1000.0,
        coverage_ratio=0.05,
        overflow_ratio=0.0,
        equivalent_diameter_px=8.0,
        circularity=0.9,
        solidity=0.95,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=1.0,
        is_missing=False,
        inspection_status=RoiInspectionStatus.DETECTED,
    )
    agg = AggregateMeasurements(
        mean_coverage=0.096,
        size_cv=0.1,
        missing_roi_ids=[],
        unassessed_roi_ids=[],
    )
    limits = ProcessLimits(min_coverage_ratio=0.10)

    status, obs, _ = classify_defects_from_measurements(
        mode=ImageAnalysisMode.PROCESS_LIMITS,
        roi_measurements=[m1_violating, m2_ok, m3_violating],
        aggregate=agg,
        process_limits=limits,
    )

    assert status == AnalysisStatus.CALIBRATED
    assert len(obs) == 1
    assert obs[0].metadata["affected_roi_ids"] == ["r1", "r3"]
    assert "r2" not in obs[0].metadata["affected_roi_ids"]


def test_missing_deposit_skips_further_checks_and_isolates_affected_id() -> None:
    """Missing deposit is isolated to deposit_presence=missing and skipped from size checks."""
    m_missing = RoiMeasurement(
        roi_id="r_miss",
        deposit_area_px=0.0,
        target_area_px=1000.0,
        coverage_ratio=0.005,
        overflow_ratio=0.0,
        equivalent_diameter_px=0.0,
        circularity=0.0,
        solidity=0.0,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=1.0,
        is_missing=True,
        inspection_status=RoiInspectionStatus.MISSING,
    )
    m_under = RoiMeasurement(
        roi_id="r_under",
        deposit_area_px=50.0,
        target_area_px=1000.0,
        coverage_ratio=0.05,
        overflow_ratio=0.0,
        equivalent_diameter_px=8.0,
        circularity=0.9,
        solidity=0.95,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=1.0,
        is_missing=False,
        inspection_status=RoiInspectionStatus.DETECTED,
    )
    agg = AggregateMeasurements(
        mean_coverage=0.05,
        size_cv=None,
        missing_roi_ids=["r_miss"],
        unassessed_roi_ids=[],
    )
    limits = ProcessLimits(min_presence_ratio=0.01, min_coverage_ratio=0.10)

    status, obs, _ = classify_defects_from_measurements(
        mode=ImageAnalysisMode.PROCESS_LIMITS,
        roi_measurements=[m_missing, m_under],
        aggregate=agg,
        process_limits=limits,
    )

    assert status == AnalysisStatus.CALIBRATED
    assert len(obs) == 2
    types = {o.observation_type: o for o in obs}
    assert types["deposit_presence"].value == "missing"
    assert types["deposit_presence"].metadata["affected_roi_ids"] == ["r_miss"]
    assert types["deposit_size"].value == "undersized"
    assert types["deposit_size"].metadata["affected_roi_ids"] == ["r_under"]


def test_d03_inconsistent_size_metadata_records_comparison_participants() -> None:
    """D03 inconsistent size lists eligible detected positive-area comparison participants in affected_roi_ids."""
    m1 = RoiMeasurement(
        roi_id="r1",
        deposit_area_px=100.0,
        target_area_px=1000.0,
        coverage_ratio=0.10,
        overflow_ratio=0.0,
        equivalent_diameter_px=11.2,
        circularity=0.9,
        solidity=0.95,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=1.0,
        is_missing=False,
        inspection_status=RoiInspectionStatus.DETECTED,
    )
    m2 = RoiMeasurement(
        roi_id="r2",
        deposit_area_px=400.0,
        target_area_px=1000.0,
        coverage_ratio=0.40,
        overflow_ratio=0.0,
        equivalent_diameter_px=22.5,
        circularity=0.9,
        solidity=0.95,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=1.0,
        is_missing=False,
        inspection_status=RoiInspectionStatus.DETECTED,
    )
    m_missing = RoiMeasurement(
        roi_id="r_miss",
        deposit_area_px=0.0,
        target_area_px=1000.0,
        coverage_ratio=0.0,
        overflow_ratio=0.0,
        equivalent_diameter_px=0.0,
        circularity=0.0,
        solidity=0.0,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=1.0,
        is_missing=True,
        inspection_status=RoiInspectionStatus.MISSING,
    )
    agg = AggregateMeasurements(
        mean_coverage=0.25,
        size_cv=0.85,
        missing_roi_ids=["r_miss"],
        unassessed_roi_ids=[],
    )
    limits = ProcessLimits(max_size_cv=0.20)

    status, obs, _ = classify_defects_from_measurements(
        mode=ImageAnalysisMode.PROCESS_LIMITS,
        roi_measurements=[m1, m2, m_missing],
        aggregate=agg,
        process_limits=limits,
    )

    assert status == AnalysisStatus.CALIBRATED
    d03_obs = next((o for o in obs if o.value == "inconsistent"), None)
    assert d03_obs is not None
    assert d03_obs.metadata["affected_roi_ids"] == ["r1", "r2"]
    assert d03_obs.metadata["size_cv"] == 0.85
    assert d03_obs.metadata["max_size_cv"] == 0.20


def test_reference_image_mode_multiple_affected_sites_and_unmatched_exclusion() -> None:
    """REFERENCE_IMAGE mode preserves affected_roi_ids for violating sites and excludes unmatched or near-zero sites."""
    curr1 = RoiMeasurement(
        roi_id="r1",
        deposit_area_px=200.0,
        target_area_px=1000.0,
        coverage_ratio=0.20,
        overflow_ratio=0.0,
        equivalent_diameter_px=16.0,
        circularity=0.9,
        solidity=0.95,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=1.0,
        is_missing=False,
        inspection_status=RoiInspectionStatus.DETECTED,
    )
    curr2 = RoiMeasurement(
        roi_id="r2",
        deposit_area_px=250.0,
        target_area_px=1000.0,
        coverage_ratio=0.25,
        overflow_ratio=0.0,
        equivalent_diameter_px=17.8,
        circularity=0.9,
        solidity=0.95,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=1.0,
        is_missing=False,
        inspection_status=RoiInspectionStatus.DETECTED,
    )
    curr3_ok = RoiMeasurement(
        roi_id="r3",
        deposit_area_px=500.0,
        target_area_px=1000.0,
        coverage_ratio=0.50,
        overflow_ratio=0.0,
        equivalent_diameter_px=25.2,
        circularity=0.9,
        solidity=0.95,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=1.0,
        is_missing=False,
        inspection_status=RoiInspectionStatus.DETECTED,
    )
    curr4_unmatched = RoiMeasurement(
        roi_id="r4",
        deposit_area_px=100.0,
        target_area_px=1000.0,
        coverage_ratio=0.10,
        overflow_ratio=0.0,
        equivalent_diameter_px=11.2,
        circularity=0.9,
        solidity=0.95,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=1.0,
        is_missing=False,
        inspection_status=RoiInspectionStatus.DETECTED,
    )

    # Reference has r1, r2, r3 (coverage 0.50 each), no r4
    ref1 = RoiMeasurement(
        roi_id="r1",
        deposit_area_px=500.0,
        target_area_px=1000.0,
        coverage_ratio=0.50,
        overflow_ratio=0.0,
        equivalent_diameter_px=25.2,
        circularity=0.9,
        solidity=0.95,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=1.0,
        is_missing=False,
        inspection_status=RoiInspectionStatus.DETECTED,
    )
    ref2 = RoiMeasurement(
        roi_id="r2",
        deposit_area_px=500.0,
        target_area_px=1000.0,
        coverage_ratio=0.50,
        overflow_ratio=0.0,
        equivalent_diameter_px=25.2,
        circularity=0.9,
        solidity=0.95,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=1.0,
        is_missing=False,
        inspection_status=RoiInspectionStatus.DETECTED,
    )
    ref3 = RoiMeasurement(
        roi_id="r3",
        deposit_area_px=500.0,
        target_area_px=1000.0,
        coverage_ratio=0.50,
        overflow_ratio=0.0,
        equivalent_diameter_px=25.2,
        circularity=0.9,
        solidity=0.95,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=1.0,
        is_missing=False,
        inspection_status=RoiInspectionStatus.DETECTED,
    )

    curr_agg = AggregateMeasurements(mean_coverage=0.26, size_cv=0.1, missing_roi_ids=[], unassessed_roi_ids=[])
    ref_agg = AggregateMeasurements(mean_coverage=0.50, size_cv=0.0, missing_roi_ids=[], unassessed_roi_ids=[])
    ref_limits = ReferenceLimits(min_reference_ratio=0.80)  # r1=0.40, r2=0.50 (both < 0.80), r3=1.0 (ok)

    status, obs, warnings = classify_defects_from_measurements(
        mode=ImageAnalysisMode.REFERENCE_IMAGE,
        roi_measurements=[curr1, curr2, curr3_ok, curr4_unmatched],
        aggregate=curr_agg,
        reference_measurements=[ref1, ref2, ref3],
        reference_aggregate=ref_agg,
        reference_limits=ref_limits,
    )

    assert status == AnalysisStatus.CALIBRATED
    assert len(obs) == 1
    assert obs[0].value == "undersized"
    assert obs[0].metadata["affected_roi_ids"] == ["r1", "r2"]
    assert "r3" not in obs[0].metadata["affected_roi_ids"]
    assert "r4" not in obs[0].metadata["affected_roi_ids"]
    assert any("No matching reference measurement for ROI 'r4'" in w for w in warnings)


def test_reference_image_mode_multiple_shape_rules_deduplicate_same_roi() -> None:
    """REFERENCE_IMAGE does not duplicate the same ROI ID if it violates both circularity and solidity."""
    curr1 = RoiMeasurement(
        roi_id="r1",
        deposit_area_px=500.0,
        target_area_px=1000.0,
        coverage_ratio=0.50,
        overflow_ratio=0.0,
        equivalent_diameter_px=25.2,
        circularity=0.50,  # Circularity ratio = 0.50/0.90 = 0.55 < 0.80
        solidity=0.60,     # Solidity ratio = 0.60/0.95 = 0.63 < 0.80
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=1.0,
        is_missing=False,
        inspection_status=RoiInspectionStatus.DETECTED,
    )
    ref1 = RoiMeasurement(
        roi_id="r1",
        deposit_area_px=500.0,
        target_area_px=1000.0,
        coverage_ratio=0.50,
        overflow_ratio=0.0,
        equivalent_diameter_px=25.2,
        circularity=0.90,
        solidity=0.95,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=1.0,
        is_missing=False,
        inspection_status=RoiInspectionStatus.DETECTED,
    )
    curr_agg = AggregateMeasurements(mean_coverage=0.50, size_cv=None, missing_roi_ids=[], unassessed_roi_ids=[])
    ref_agg = AggregateMeasurements(mean_coverage=0.50, size_cv=None, missing_roi_ids=[], unassessed_roi_ids=[])
    ref_limits = ReferenceLimits(min_circularity_ratio=0.80, min_solidity_ratio=0.80)

    status, obs, _ = classify_defects_from_measurements(
        mode=ImageAnalysisMode.REFERENCE_IMAGE,
        roi_measurements=[curr1],
        aggregate=curr_agg,
        reference_measurements=[ref1],
        reference_aggregate=ref_agg,
        reference_limits=ref_limits,
    )

    assert status == AnalysisStatus.CALIBRATED
    assert len(obs) == 1
    assert obs[0].value == "abnormal"
    assert obs[0].metadata["affected_roi_ids"] == ["r1"]


# ---------------------------------------------------------------------------
# DLK-M3-039: Per-region evidence snapshots tests
# ---------------------------------------------------------------------------


def test_process_limits_mode_preserves_per_region_evidence_snapshots() -> None:
    """Distinct measurements on multiple sites sharing an observation preserve ordered snapshots and limits."""
    m1 = RoiMeasurement(
        roi_id="site_1",
        deposit_area_px=250.0,
        target_area_px=1000.0,
        coverage_ratio=0.25,
        overflow_ratio=0.0,
        equivalent_diameter_px=17.8,
        calibrated_diameter_mm=1.2,
        circularity=0.88,
        solidity=0.92,
        convexity=0.95,
        aspect_ratio=1.05,
        hole_void_ratio=0.0,
        bubble_count=0,
        has_bubbles=False,
        segmentation_quality=0.95,
        is_missing=False,
        inspection_status=RoiInspectionStatus.DETECTED,
    )
    m2 = RoiMeasurement(
        roi_id="site_2",
        deposit_area_px=350.0,
        target_area_px=1000.0,
        coverage_ratio=0.35,
        overflow_ratio=0.0,
        equivalent_diameter_px=21.1,
        calibrated_diameter_mm=1.5,
        circularity=0.82,
        solidity=0.89,
        convexity=0.91,
        aspect_ratio=1.10,
        hole_void_ratio=0.0,
        bubble_count=0,
        has_bubbles=False,
        segmentation_quality=0.90,
        is_missing=False,
        inspection_status=RoiInspectionStatus.DETECTED,
    )
    agg = AggregateMeasurements(mean_coverage=0.30, size_cv=0.10, missing_roi_ids=[], unassessed_roi_ids=[])
    limits = ProcessLimits(min_coverage_ratio=0.50)

    status, obs, _ = classify_defects_from_measurements(
        mode=ImageAnalysisMode.PROCESS_LIMITS,
        roi_measurements=[m1, m2],
        aggregate=agg,
        process_limits=limits,
    )

    assert status == AnalysisStatus.CALIBRATED
    assert len(obs) == 1
    assert obs[0].value == "undersized"
    assert obs[0].metadata["affected_roi_ids"] == ["site_1", "site_2"]

    # Scope and applied limits
    assert obs[0].metadata["region_evidence_scope"] == "individual_regions"
    assert obs[0].metadata["applied_limits"] == {"min_coverage_ratio": 0.50}

    # Region evidence
    evidence = obs[0].metadata["region_evidence"]
    assert len(evidence) == 2

    # site_1 snapshot
    assert evidence[0]["roi_id"] == "site_1"
    assert evidence[0]["current_measurements"]["coverage_ratio"] == 0.25
    assert evidence[0]["current_measurements"]["deposit_area_px"] == 250.0
    assert evidence[0]["current_measurements"]["calibrated_diameter_mm"] == 1.2
    assert evidence[0]["current_measurements"]["inspection_status"] == "DETECTED"
    assert evidence[0]["reference_measurements"] is None

    # site_2 snapshot
    assert evidence[1]["roi_id"] == "site_2"
    assert evidence[1]["current_measurements"]["coverage_ratio"] == 0.35
    assert evidence[1]["current_measurements"]["deposit_area_px"] == 350.0
    assert evidence[1]["current_measurements"]["calibrated_diameter_mm"] == 1.5
    assert evidence[1]["current_measurements"]["inspection_status"] == "DETECTED"
    assert evidence[1]["reference_measurements"] is None

    # Legacy metadata preserved (from first site)
    assert obs[0].metadata["roi_id"] == "site_1"
    assert obs[0].metadata["coverage_ratio"] == 0.25


def test_reference_mode_preserves_current_and_reference_snapshots_and_limits() -> None:
    """Reference mode preserves matching reference snapshots and resolved effective limits."""
    curr1 = RoiMeasurement(
        roi_id="site_a",
        deposit_area_px=400.0,
        target_area_px=1000.0,
        coverage_ratio=0.40,
        overflow_ratio=0.0,
        equivalent_diameter_px=22.5,
        calibrated_diameter_mm=None,
        circularity=0.85,
        solidity=0.90,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=0.95,
        is_missing=False,
        inspection_status=RoiInspectionStatus.DETECTED,
    )
    ref1 = RoiMeasurement(
        roi_id="site_a",
        deposit_area_px=800.0,
        target_area_px=1000.0,
        coverage_ratio=0.80,
        overflow_ratio=0.0,
        equivalent_diameter_px=31.9,
        calibrated_diameter_mm=None,
        circularity=0.90,
        solidity=0.95,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=0.98,
        is_missing=False,
        inspection_status=RoiInspectionStatus.DETECTED,
    )
    curr_agg = AggregateMeasurements(mean_coverage=0.40, size_cv=None, missing_roi_ids=[], unassessed_roi_ids=[])
    ref_agg = AggregateMeasurements(mean_coverage=0.80, size_cv=None, missing_roi_ids=[], unassessed_roi_ids=[])
    # tolerance_ratio=0.2 resolves min_reference_ratio=0.8, max_reference_ratio=1.2
    ref_limits = ReferenceLimits(tolerance_ratio=0.2)

    status, obs, _ = classify_defects_from_measurements(
        mode=ImageAnalysisMode.REFERENCE_IMAGE,
        roi_measurements=[curr1],
        aggregate=curr_agg,
        reference_measurements=[ref1],
        reference_aggregate=ref_agg,
        reference_limits=ref_limits,
    )

    assert status == AnalysisStatus.CALIBRATED
    assert len(obs) == 1
    assert obs[0].value == "undersized"
    assert obs[0].metadata["region_evidence_scope"] == "individual_regions"

    # Effective resolved limits
    applied = obs[0].metadata["applied_limits"]
    assert applied["tolerance_ratio"] == 0.2
    assert applied["min_reference_ratio"] == 0.8
    assert applied["max_reference_ratio"] == 1.2

    # Evidence snapshots
    evidence = obs[0].metadata["region_evidence"]
    assert len(evidence) == 1
    item = evidence[0]
    assert item["roi_id"] == "site_a"
    assert item["current_measurements"]["coverage_ratio"] == 0.40
    assert item["reference_measurements"]["coverage_ratio"] == 0.80

    # Consumer can reconstruct ratio: 0.40 / 0.80 = 0.50 < 0.80 (min_reference_ratio)
    computed_ratio = item["current_measurements"]["coverage_ratio"] / item["reference_measurements"]["coverage_ratio"]
    assert pytest.approx(computed_ratio, 1e-4) == 0.50
    assert computed_ratio < applied["min_reference_ratio"]


def test_d03_inconsistent_size_comparison_group_snapshots() -> None:
    """D03 inconsistent size uses comparison_group scope, includes eligible participants without pass/fail labels."""
    m1 = RoiMeasurement(
        roi_id="site_1",
        deposit_area_px=200.0,
        target_area_px=1000.0,
        coverage_ratio=0.20,
        overflow_ratio=0.0,
        equivalent_diameter_px=16.0,
        circularity=0.85,
        solidity=0.90,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=0.90,
        is_missing=False,
        inspection_status=RoiInspectionStatus.DETECTED,
    )
    m2 = RoiMeasurement(
        roi_id="site_2",
        deposit_area_px=800.0,
        target_area_px=1000.0,
        coverage_ratio=0.80,
        overflow_ratio=0.0,
        equivalent_diameter_px=31.9,
        circularity=0.85,
        solidity=0.90,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=0.90,
        is_missing=False,
        inspection_status=RoiInspectionStatus.DETECTED,
    )
    m3 = RoiMeasurement(
        roi_id="site_3",
        deposit_area_px=0.0,
        target_area_px=1000.0,
        coverage_ratio=0.0,
        overflow_ratio=0.0,
        equivalent_diameter_px=0.0,
        circularity=0.0,
        solidity=0.0,
        aspect_ratio=0.0,
        hole_void_ratio=0.0,
        segmentation_quality=0.90,
        is_missing=True,
        inspection_status=RoiInspectionStatus.MISSING,
    )
    agg = AggregateMeasurements(mean_coverage=0.50, size_cv=0.45, missing_roi_ids=["site_3"], unassessed_roi_ids=[])
    limits = ProcessLimits(max_size_cv=0.20, min_presence_ratio=0.50)

    status, obs, _ = classify_defects_from_measurements(
        mode=ImageAnalysisMode.PROCESS_LIMITS,
        roi_measurements=[m1, m2, m3],
        aggregate=agg,
        process_limits=limits,
    )

    assert status == AnalysisStatus.CALIBRATED
    d03_obs = [o for o in obs if o.value == "inconsistent"]
    assert len(d03_obs) == 1
    d03 = d03_obs[0]

    assert d03.metadata["region_evidence_scope"] == "comparison_group"
    assert d03.metadata["size_cv"] == 0.45
    assert d03.metadata["max_size_cv"] == 0.20
    assert d03.metadata["affected_roi_ids"] == ["site_1", "site_2"]

    evidence = d03.metadata["region_evidence"]
    assert len(evidence) == 2
    assert evidence[0]["roi_id"] == "site_1"
    assert evidence[1]["roi_id"] == "site_2"

    # Confirm no individual outlier or pass/fail labels
    for item in evidence:
        curr = item["current_measurements"]
        assert "is_outlier" not in curr
        assert "passed" not in curr
        assert "failed" not in curr
        assert "verdict" not in curr


def test_multiple_conditions_on_same_roi_do_not_duplicate_evidence() -> None:
    """Multiple rules contributing to one observation type/value on the same ROI do not duplicate its snapshot."""
    curr = RoiMeasurement(
        roi_id="site_x",
        deposit_area_px=500.0,
        target_area_px=1000.0,
        coverage_ratio=0.50,
        overflow_ratio=0.0,
        equivalent_diameter_px=25.2,
        circularity=0.50,  # Circularity ratio = 0.50/0.90 = 0.55 < 0.80
        solidity=0.60,     # Solidity ratio = 0.60/0.95 = 0.63 < 0.80
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=1.0,
        is_missing=False,
        inspection_status=RoiInspectionStatus.DETECTED,
    )
    ref = RoiMeasurement(
        roi_id="site_x",
        deposit_area_px=500.0,
        target_area_px=1000.0,
        coverage_ratio=0.50,
        overflow_ratio=0.0,
        equivalent_diameter_px=25.2,
        circularity=0.90,
        solidity=0.95,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=1.0,
        is_missing=False,
        inspection_status=RoiInspectionStatus.DETECTED,
    )
    curr_agg = AggregateMeasurements(mean_coverage=0.50, size_cv=None, missing_roi_ids=[], unassessed_roi_ids=[])
    ref_agg = AggregateMeasurements(mean_coverage=0.50, size_cv=None, missing_roi_ids=[], unassessed_roi_ids=[])
    ref_limits = ReferenceLimits(min_circularity_ratio=0.80, min_solidity_ratio=0.80)

    status, obs, _ = classify_defects_from_measurements(
        mode=ImageAnalysisMode.REFERENCE_IMAGE,
        roi_measurements=[curr],
        aggregate=curr_agg,
        reference_measurements=[ref],
        reference_aggregate=ref_agg,
        reference_limits=ref_limits,
    )

    assert status == AnalysisStatus.CALIBRATED
    assert len(obs) == 1
    assert obs[0].value == "abnormal"
    evidence = obs[0].metadata["region_evidence"]
    assert len(evidence) == 1
    assert evidence[0]["roi_id"] == "site_x"


def test_separate_observations_contain_only_own_affected_sites() -> None:
    """Separate observations (e.g. undersized vs bubbles) isolate their respective affected ROI snapshots."""
    m_undersized = RoiMeasurement(
        roi_id="site_small",
        deposit_area_px=200.0,
        target_area_px=1000.0,
        coverage_ratio=0.20,
        overflow_ratio=0.0,
        equivalent_diameter_px=16.0,
        circularity=0.90,
        solidity=0.95,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        bubble_count=0,
        has_bubbles=False,
        segmentation_quality=0.95,
        is_missing=False,
        inspection_status=RoiInspectionStatus.DETECTED,
    )
    m_bubble = RoiMeasurement(
        roi_id="site_bubble",
        deposit_area_px=600.0,
        target_area_px=1000.0,
        coverage_ratio=0.60,
        overflow_ratio=0.0,
        equivalent_diameter_px=27.6,
        circularity=0.90,
        solidity=0.95,
        aspect_ratio=1.0,
        hole_void_ratio=0.05,
        bubble_count=3,
        has_bubbles=True,
        segmentation_quality=0.95,
        is_missing=False,
        inspection_status=RoiInspectionStatus.DETECTED,
    )
    agg = AggregateMeasurements(mean_coverage=0.40, size_cv=None, missing_roi_ids=[], unassessed_roi_ids=[])
    limits = ProcessLimits(min_coverage_ratio=0.50, max_bubble_count=0)

    status, obs, _ = classify_defects_from_measurements(
        mode=ImageAnalysisMode.PROCESS_LIMITS,
        roi_measurements=[m_undersized, m_bubble],
        aggregate=agg,
        process_limits=limits,
    )

    assert status == AnalysisStatus.CALIBRATED
    obs_by_val = {o.value: o for o in obs}
    assert "undersized" in obs_by_val
    assert "visible_bubbles" in obs_by_val

    # Undersized has only site_small
    under_ev = obs_by_val["undersized"].metadata["region_evidence"]
    assert len(under_ev) == 1
    assert under_ev[0]["roi_id"] == "site_small"

    # Visible bubbles has only site_bubble
    bubble_ev = obs_by_val["visible_bubbles"].metadata["region_evidence"]
    assert len(bubble_ev) == 1
    assert bubble_ev[0]["roi_id"] == "site_bubble"


def test_snapshots_are_detached_and_immutable() -> None:
    """Modifying input RoiMeasurement after classification does not mutate recorded snapshot values."""
    m = RoiMeasurement(
        roi_id="site_mut",
        deposit_area_px=200.0,
        target_area_px=1000.0,
        coverage_ratio=0.20,
        overflow_ratio=0.0,
        equivalent_diameter_px=16.0,
        calibrated_diameter_mm=1.0,
        circularity=0.90,
        solidity=0.95,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        bubble_count=0,
        has_bubbles=False,
        segmentation_quality=0.95,
        is_missing=False,
        inspection_status=RoiInspectionStatus.DETECTED,
    )
    agg = AggregateMeasurements(mean_coverage=0.20, size_cv=None, missing_roi_ids=[], unassessed_roi_ids=[])
    limits = ProcessLimits(min_coverage_ratio=0.50)

    status, obs, _ = classify_defects_from_measurements(
        mode=ImageAnalysisMode.PROCESS_LIMITS,
        roi_measurements=[m],
        aggregate=agg,
        process_limits=limits,
    )

    assert status == AnalysisStatus.CALIBRATED
    snapshot = obs[0].metadata["region_evidence"][0]["current_measurements"]
    assert snapshot["coverage_ratio"] == 0.20

    # Mutate the input object
    m.coverage_ratio = 0.99
    m.deposit_area_px = 9999.0
    m.inspection_status = RoiInspectionStatus.UNASSESSED

    # Snapshot must remain completely unchanged
    assert snapshot["coverage_ratio"] == 0.20
    assert snapshot["deposit_area_px"] == 200.0
    assert snapshot["inspection_status"] == "DETECTED"

    # Verify exact 15 allowed scalar fields
    expected_fields = {
        "inspection_status",
        "deposit_area_px",
        "target_area_px",
        "coverage_ratio",
        "overflow_ratio",
        "equivalent_diameter_px",
        "calibrated_diameter_mm",
        "circularity",
        "solidity",
        "convexity",
        "aspect_ratio",
        "hole_void_ratio",
        "bubble_count",
        "has_bubbles",
        "segmentation_quality",
    }
    assert set(snapshot.keys()) == expected_fields
