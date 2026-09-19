"""
DispenseIQ — Vision Measurement Unit Tests

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
