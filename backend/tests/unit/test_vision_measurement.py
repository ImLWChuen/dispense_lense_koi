"""
Dispense Lens - Vision Measurement Unit Tests

Verifies:
- Resolution-independent coverage calculation:
  Proportional deposits across 100x100, 200x200, and 400x400 yield near-identical coverage ratios.
- Correct calculations of equivalent diameter, circularity, solidity, aspect ratio, hole/void ratio, and overflow ratio.
- Calculation of physical diameter only when mm_per_pixel is provided.
- Aggregate size_cv across multiple ROIs with safe zero-mean handling.
"""

from __future__ import annotations

import math
import pytest

from app.schemas.image import NormalizedROI
from app.services.vision.preprocessing import decode_and_validate_image, normalize_roi_to_pixels
from app.services.vision.segmentation import segment_roi
from app.services.vision.measurement import (
    calculate_aggregate_measurements,
    calculate_roi_features,
)
from tests.fixtures.synthetic_images import (
    create_centered_dot_image,
    create_overflow_image,
    create_proportional_dot_image,
)


def test_resolution_independence_100_200_400() -> None:
    """Proportional circular dots scaled across 100x100, 200x200, and 400x400

    must yield near-identical coverage ratios within 0.02 tolerance due to discrete pixel grid sampling.
    """
    roi = NormalizedROI(roi_id="roi_main", x=0.25, y=0.25, width=0.5, height=0.5)
    # Dot radius is 0.18 of image size (so diameter 0.36 inside target width 0.5)
    norm_radius = 0.18

    coverages = []
    circularities = []

    for size in [100, 200, 400]:
        img_bytes = create_proportional_dot_image(size=size, normalized_radius=norm_radius)
        img, dims = decode_and_validate_image(img_bytes)
        px_roi, win_roi = normalize_roi_to_pixels(roi, dims.width, dims.height, window_expansion=0.1)
        seg_result = segment_roi(img, px_roi, win_roi)

        features = calculate_roi_features(
            seg_result=seg_result,
            target_roi=px_roi,
            roi_id=roi.roi_id,
            mm_per_pixel=None,
        )
        coverages.append(features.coverage_ratio)
        circularities.append(features.circularity)

    # All three coverages should be within small discrete-grid tolerance (0.02) of each other
    assert abs(coverages[0] - coverages[1]) < 0.02
    assert abs(coverages[1] - coverages[2]) < 0.02
    assert abs(coverages[0] - coverages[2]) < 0.02

    # Circularity of a circle should be close to 1.0 (e.g. > 0.85 on discrete raster grids)
    for c in circularities:
        assert c > 0.85


def test_physical_calibration_diameter() -> None:
    """Equivalent diameter is calculated in pixels, and converted to mm if mm_per_pixel is provided."""
    # 200x200 image, radius 25 -> diameter 50 px
    img_bytes = create_centered_dot_image(size=200, dot_radius=25)
    img, dims = decode_and_validate_image(img_bytes)
    roi = NormalizedROI(roi_id="roi_1", x=0.2, y=0.2, width=0.6, height=0.6)
    px_roi, win_roi = normalize_roi_to_pixels(roi, dims.width, dims.height)
    seg_result = segment_roi(img, px_roi, win_roi)

    # Without calibration
    f_uncalibrated = calculate_roi_features(seg_result, px_roi, "roi_1", mm_per_pixel=None)
    assert f_uncalibrated.calibrated_diameter_mm is None
    assert abs(f_uncalibrated.equivalent_diameter_px - 50.0) < 3.0

    # With calibration: 0.05 mm / pixel -> 50 px * 0.05 = 2.5 mm
    f_calibrated = calculate_roi_features(seg_result, px_roi, "roi_1", mm_per_pixel=0.05)
    assert f_calibrated.calibrated_diameter_mm is not None
    assert abs(f_calibrated.calibrated_diameter_mm - 2.5) < 0.2


def test_overflow_ratio_measurement() -> None:
    """Deposit extending beyond target ROI boundary has positive overflow ratio."""
    roi = NormalizedROI(roi_id="roi_1", x=0.25, y=0.25, width=0.5, height=0.5)
    img_bytes = create_overflow_image(size=200, center_roi_norm=(0.25, 0.25, 0.5, 0.5))
    img, dims = decode_and_validate_image(img_bytes)
    px_roi, win_roi = normalize_roi_to_pixels(roi, dims.width, dims.height, window_expansion=0.4)
    seg_result = segment_roi(img, px_roi, win_roi)

    features = calculate_roi_features(seg_result, px_roi, "roi_1")
    assert features.overflow_ratio > 0.05


def test_aggregate_measurements_size_cv() -> None:
    """Aggregate measurements calculate mean_coverage and size_cv safely."""
    # When >= 2 valid measurements
    img_bytes = create_centered_dot_image(size=200, dot_radius=20)
    img, dims = decode_and_validate_image(img_bytes)
    roi1 = NormalizedROI(roi_id="roi_1", x=0.25, y=0.25, width=0.5, height=0.5)
    px_roi1, win_roi1 = normalize_roi_to_pixels(roi1, dims.width, dims.height)
    seg1 = segment_roi(img, px_roi1, win_roi1)
    f1 = calculate_roi_features(seg1, px_roi1, "roi_1")

    # Second feature with different coverage
    f2 = f1.model_copy(update={"roi_id": "roi_2", "coverage_ratio": f1.coverage_ratio * 0.8})

    agg = calculate_aggregate_measurements([f1, f2], all_roi_ids=["roi_1", "roi_2"])
    assert agg.mean_coverage is not None
    assert agg.size_cv is not None
    assert agg.size_cv > 0
    assert len(agg.missing_roi_ids) == 0


def test_regression_unreliable_zero_area_not_mislabeled_as_missing() -> None:
    """An unreliable segmentation with zero area must NOT be placed into missing_roi_ids."""
    from app.services.vision.segmentation import SegmentationResult, SegmentationStatus

    unreliable_seg = SegmentationResult(
        status=SegmentationStatus.UNRELIABLE,
        deposit_area_px=0.0,
        deposit_inside_target_px=0.0,
        deposit_outside_target_px=0.0,
        target_area_px=100.0,
        quality_score=0.0,
        is_missing=False,
        warnings=["Analysis window has zero size."],
    )
    from app.schemas.image import PixelROI
    target = PixelROI(roi_id="roi_bad", x=10, y=10, width=50, height=50)
    feat = calculate_roi_features(unreliable_seg, target, "roi_bad")

    agg = calculate_aggregate_measurements([feat], all_roi_ids=["roi_bad"])
    # Under bug: 'roi_bad' is put in missing_roi_ids because deposit_area_px == 0
    # Required: must NOT be in missing_roi_ids, must be in unassessed_roi_ids
    assert "roi_bad" not in agg.missing_roi_ids, "Unreliable zero-area ROI must not be in missing_roi_ids"
    assert hasattr(agg, "unassessed_roi_ids")
    assert "roi_bad" in agg.unassessed_roi_ids


def test_regression_omitted_roi_not_mislabeled_as_missing() -> None:
    """An expected ROI without a measurement must NOT be placed into missing_roi_ids."""
    img_bytes = create_centered_dot_image(size=200, dot_radius=20)
    img, dims = decode_and_validate_image(img_bytes)
    roi1 = NormalizedROI(roi_id="roi_1", x=0.25, y=0.25, width=0.5, height=0.5)
    px_roi1, win_roi1 = normalize_roi_to_pixels(roi1, dims.width, dims.height)
    seg1 = segment_roi(img, px_roi1, win_roi1)
    f1 = calculate_roi_features(seg1, px_roi1, "roi_1")

    # Only roi_1 is measured, but all_roi_ids expects both roi_1 and roi_omitted
    agg = calculate_aggregate_measurements([f1], all_roi_ids=["roi_1", "roi_omitted"])
    # Under bug: 'roi_omitted' is put in missing_roi_ids
    # Required: must NOT be in missing_roi_ids, must be in unassessed_roi_ids
    assert "roi_omitted" not in agg.missing_roi_ids, "Omitted ROI must not be placed in missing_roi_ids"
    assert hasattr(agg, "unassessed_roi_ids")
    assert "roi_omitted" in agg.unassessed_roi_ids


def test_aggregate_boundaries_all_unassessed_and_fewer_than_two_deposits() -> None:
    """Verifies aggregate boundary conditions across unassessed, missing, and valid deposits."""
    from app.schemas.image import RoiInspectionStatus, RoiMeasurement

    m_detected_1 = RoiMeasurement(
        roi_id="det_1",
        deposit_area_px=500.0,
        target_area_px=1000.0,
        coverage_ratio=0.50,
        overflow_ratio=0.0,
        equivalent_diameter_px=25.2,
        circularity=0.9,
        solidity=0.95,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=0.9,
        is_missing=False,
        inspection_status=RoiInspectionStatus.DETECTED,
    )
    m_detected_2 = m_detected_1.model_copy(
        update={"roi_id": "det_2", "deposit_area_px": 600.0, "coverage_ratio": 0.60}
    )
    m_unassessed = RoiMeasurement(
        roi_id="unassessed_1",
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
        inspection_warnings=["Low contrast ambiguous segmentation."],
    )
    m_missing = RoiMeasurement(
        roi_id="missing_1",
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

    # 1. All-unassessed -> mean_coverage is None, size_cv is None
    agg_unassessed = calculate_aggregate_measurements(
        [m_unassessed], all_roi_ids=["unassessed_1"]
    )
    assert agg_unassessed.mean_coverage is None
    assert agg_unassessed.size_cv is None
    assert agg_unassessed.unassessed_roi_ids == ["unassessed_1"]
    assert agg_unassessed.missing_roi_ids == []

    # 2. Missing + Unassessed (0 eligible) -> mean_coverage is None, size_cv is None, disjoint lists
    agg_mixed_zero = calculate_aggregate_measurements(
        [m_missing, m_unassessed], all_roi_ids=["missing_1", "unassessed_1"]
    )
    assert agg_mixed_zero.mean_coverage is None
    assert agg_mixed_zero.size_cv is None
    assert agg_mixed_zero.missing_roi_ids == ["missing_1"]
    assert agg_mixed_zero.unassessed_roi_ids == ["unassessed_1"]
    assert set(agg_mixed_zero.missing_roi_ids).isdisjoint(set(agg_mixed_zero.unassessed_roi_ids))

    # 3. Exactly 1 valid deposit + 1 unassessed -> mean_coverage is float, size_cv is None
    agg_one = calculate_aggregate_measurements(
        [m_detected_1, m_unassessed], all_roi_ids=["det_1", "unassessed_1"]
    )
    assert agg_one.mean_coverage == 0.50
    assert agg_one.size_cv is None
    assert agg_one.unassessed_roi_ids == ["unassessed_1"]
    assert agg_one.missing_roi_ids == []

    # 4. >=2 valid deposits + 1 unassessed -> valid mean_coverage, valid size_cv > 0 (excluding unassessed)
    agg_two = calculate_aggregate_measurements(
        [m_detected_1, m_detected_2, m_unassessed],
        all_roi_ids=["det_1", "det_2", "unassessed_1"],
    )
    assert agg_two.mean_coverage == pytest.approx(0.55, rel=1e-3)
    assert agg_two.size_cv is not None
    assert agg_two.size_cv > 0.0
    assert agg_two.unassessed_roi_ids == ["unassessed_1"]


def test_legacy_serialized_measurement_defaults() -> None:
    """Verifies that legacy serialized payloads missing new fields parse safely to defaults."""
    from app.schemas.image import AggregateMeasurements, RoiInspectionStatus, RoiMeasurement

    legacy_roi_data = {
        "roi_id": "legacy_roi",
        "deposit_area_px": 250.0,
        "target_area_px": 500.0,
        "coverage_ratio": 0.5,
        "overflow_ratio": 0.0,
        "equivalent_diameter_px": 17.8,
        "circularity": 0.88,
        "solidity": 0.92,
        "aspect_ratio": 1.05,
        "hole_void_ratio": 0.0,
        "bubble_count": 0,
        "has_bubbles": False,
        "is_abnormal_shape": False,
        "is_tailing": False,
        "bubble_details": [],
        "segmentation_quality": 0.85,
        "is_missing": False,
    }
    m = RoiMeasurement.model_validate(legacy_roi_data)
    assert m.inspection_status == RoiInspectionStatus.UNASSESSED
    assert m.inspection_warnings == []

    legacy_agg_data = {
        "mean_coverage": 0.5,
        "size_cv": 0.05,
        "missing_roi_ids": ["legacy_missing"],
        "warnings": ["Legacy warning"],
    }
    agg = AggregateMeasurements.model_validate(legacy_agg_data)
    assert agg.unassessed_roi_ids == []
    assert agg.missing_roi_ids == ["legacy_missing"]
    assert agg.expected_roi_count is None
    assert agg.assessed_roi_count is None
    assert agg.inspection_coverage_status is None


def _make_measurement(
    roi_id: str,
    status: RoiInspectionStatus,
    coverage: float = 0.5,
    area: float = 500.0,
) -> RoiMeasurement:
    """Helper to construct minimal RoiMeasurement instances for coverage tests."""
    from app.schemas.image import RoiInspectionStatus, RoiMeasurement

    is_missing = status == RoiInspectionStatus.MISSING
    return RoiMeasurement(
        roi_id=roi_id,
        deposit_area_px=0.0 if is_missing or status == RoiInspectionStatus.UNASSESSED else area,
        target_area_px=1000.0,
        coverage_ratio=0.0 if is_missing or status == RoiInspectionStatus.UNASSESSED else coverage,
        overflow_ratio=0.0,
        equivalent_diameter_px=0.0 if is_missing or status == RoiInspectionStatus.UNASSESSED else 25.0,
        circularity=0.0 if is_missing or status == RoiInspectionStatus.UNASSESSED else 0.9,
        solidity=0.0 if is_missing or status == RoiInspectionStatus.UNASSESSED else 0.95,
        aspect_ratio=1.0,
        hole_void_ratio=0.0,
        segmentation_quality=0.9 if is_missing or status == RoiInspectionStatus.DETECTED else 0.1,
        is_missing=is_missing,
        inspection_status=status,
    )


def test_inspection_coverage_complete_detected_and_missing() -> None:
    """A complete inspection includes all expected sites as DETECTED or confirmed MISSING."""
    from app.schemas.image import InspectionCoverageStatus, RoiInspectionStatus

    m1 = _make_measurement("r1", RoiInspectionStatus.DETECTED)
    m2 = _make_measurement("r2", RoiInspectionStatus.MISSING)

    agg = calculate_aggregate_measurements([m1, m2], all_roi_ids=["r1", "r2"])
    assert agg.expected_roi_count == 2
    assert agg.assessed_roi_count == 2
    assert agg.inspection_coverage_status == InspectionCoverageStatus.COMPLETE
    assert agg.missing_roi_ids == ["r2"]
    assert agg.unassessed_roi_ids == []


def test_inspection_coverage_partial_detected_and_unassessed() -> None:
    """Mixed detected and unassessed expected sites report exact counts and PARTIAL."""
    from app.schemas.image import InspectionCoverageStatus, RoiInspectionStatus

    m1 = _make_measurement("r1", RoiInspectionStatus.DETECTED)
    m2 = _make_measurement("r2", RoiInspectionStatus.UNASSESSED)

    agg = calculate_aggregate_measurements([m1, m2], all_roi_ids=["r1", "r2"])
    assert agg.expected_roi_count == 2
    assert agg.assessed_roi_count == 1
    assert agg.inspection_coverage_status == InspectionCoverageStatus.PARTIAL
    assert agg.unassessed_roi_ids == ["r2"]
    assert agg.missing_roi_ids == []


def test_inspection_coverage_none_all_unassessed() -> None:
    """When no expected site is assessed, coverage status is NONE with 0 assessed count."""
    from app.schemas.image import InspectionCoverageStatus, RoiInspectionStatus

    m1 = _make_measurement("r1", RoiInspectionStatus.UNASSESSED)
    m2 = _make_measurement("r2", RoiInspectionStatus.UNASSESSED)

    agg = calculate_aggregate_measurements([m1, m2], all_roi_ids=["r1", "r2"])
    assert agg.expected_roi_count == 2
    assert agg.assessed_roi_count == 0
    assert agg.inspection_coverage_status == InspectionCoverageStatus.NONE
    assert set(agg.unassessed_roi_ids) == {"r1", "r2"}


def test_inspection_coverage_omitted_expected_measurement() -> None:
    """Omitted expected measurements are treated as unassessed, yielding PARTIAL coverage."""
    from app.schemas.image import InspectionCoverageStatus, RoiInspectionStatus

    m1 = _make_measurement("r1", RoiInspectionStatus.DETECTED)

    agg = calculate_aggregate_measurements([m1], all_roi_ids=["r1", "r2", "r3"])
    assert agg.expected_roi_count == 3
    assert agg.assessed_roi_count == 1
    assert agg.inspection_coverage_status == InspectionCoverageStatus.PARTIAL
    assert agg.unassessed_roi_ids == ["r2", "r3"]
    assert agg.missing_roi_ids == []


def test_inspection_coverage_duplicate_expected_ids() -> None:
    """Duplicate expected IDs in all_roi_ids do not inflate expected or assessed counts."""
    from app.schemas.image import InspectionCoverageStatus, RoiInspectionStatus

    m1 = _make_measurement("r1", RoiInspectionStatus.DETECTED)
    m2 = _make_measurement("r2", RoiInspectionStatus.DETECTED)

    agg = calculate_aggregate_measurements([m1, m2], all_roi_ids=["r1", "r1", "r2", "r2"])
    assert agg.expected_roi_count == 2
    assert agg.assessed_roi_count == 2
    assert agg.inspection_coverage_status == InspectionCoverageStatus.COMPLETE


def test_inspection_coverage_unexpected_measurement_ids() -> None:
    """Measurements with ROI IDs not in expected all_roi_ids are ignored for coverage counts."""
    from app.schemas.image import InspectionCoverageStatus, RoiInspectionStatus

    m1 = _make_measurement("r1", RoiInspectionStatus.DETECTED)
    m_extra = _make_measurement("r_extra", RoiInspectionStatus.DETECTED)
    m_unassessed_extra = _make_measurement("r_unassessed_extra", RoiInspectionStatus.UNASSESSED)

    agg = calculate_aggregate_measurements(
        [m1, m_extra, m_unassessed_extra],
        all_roi_ids=["r1"],
    )
    assert agg.expected_roi_count == 1
    assert agg.assessed_roi_count == 1
    assert agg.inspection_coverage_status == InspectionCoverageStatus.COMPLETE


def test_inspection_coverage_empty_expected_list_internal_edge_case() -> None:
    """An empty expected ROI list reports 0/0 and NONE, never COMPLETE."""
    from app.schemas.image import InspectionCoverageStatus

    agg = calculate_aggregate_measurements([], all_roi_ids=[])
    assert agg.expected_roi_count == 0
    assert agg.assessed_roi_count == 0
    assert agg.inspection_coverage_status == InspectionCoverageStatus.NONE


def test_image_analysis_response_deserialization_legacy_and_reference_aggregate() -> None:
    """ImageAnalysisResponse defaults reference_aggregate_measurements to None on legacy payloads."""
    from app.schemas.image import (
        ImageAnalysisResponse,
        InspectionCoverageStatus,
    )

    legacy_payload = {
        "status": "CALIBRATED",
        "mode": "PROCESS_LIMITS",
        "image_dimensions": {"width": 100, "height": 100},
        "roi_measurements": [],
        "aggregate_measurements": {
            "mean_coverage": 0.25,
            "size_cv": None,
            "missing_roi_ids": [],
            "unassessed_roi_ids": [],
            "expected_roi_count": 1,
            "assessed_roi_count": 1,
            "inspection_coverage_status": "COMPLETE",
            "warnings": [],
        },
        "observations": [],
        "warnings": [],
    }

    resp = ImageAnalysisResponse.model_validate(legacy_payload)
    assert resp.reference_aggregate_measurements is None

    # Providing explicit reference_aggregate_measurements
    ref_payload = dict(legacy_payload)
    ref_payload["mode"] = "REFERENCE_IMAGE"
    ref_payload["reference_aggregate_measurements"] = {
        "mean_coverage": 0.30,
        "size_cv": None,
        "missing_roi_ids": [],
        "unassessed_roi_ids": [],
        "expected_roi_count": 1,
        "assessed_roi_count": 1,
        "inspection_coverage_status": "COMPLETE",
        "warnings": [],
    }
    resp_with_ref = ImageAnalysisResponse.model_validate(ref_payload)
    assert resp_with_ref.reference_aggregate_measurements is not None
    assert resp_with_ref.reference_aggregate_measurements.mean_coverage == 0.30
    assert resp_with_ref.reference_aggregate_measurements.inspection_coverage_status == InspectionCoverageStatus.COMPLETE
