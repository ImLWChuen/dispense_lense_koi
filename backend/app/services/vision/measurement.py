"""
Dispense Lens - Vision Measurement Service

Calculates resolution-independent geometric features and aggregate metrics
from segmented dispensing deposit regions.
"""

from __future__ import annotations

import math
import cv2
import numpy as np

from app.schemas.image import AggregateMeasurements, PixelROI, RoiMeasurement
from app.services.vision.segmentation import SegmentationResult


def calculate_roi_features(
    seg_result: SegmentationResult,
    target_roi: PixelROI,
    roi_id: str,
    mm_per_pixel: float | None = None,
) -> RoiMeasurement:
    """Calculate normalized resolution-independent geometric features for a single segmented ROI."""
    target_area = float(target_roi.width * target_roi.height)
    if target_area <= 0:
        target_area = 1.0

    deposit_area = float(seg_result.deposit_area_px)
    inside_area = float(seg_result.deposit_inside_target_px)
    outside_area = float(seg_result.deposit_outside_target_px)

    coverage_ratio = inside_area / target_area

    if deposit_area > 0:
        overflow_ratio = outside_area / deposit_area
        equivalent_diameter_px = 2.0 * math.sqrt(deposit_area / math.pi)
    else:
        overflow_ratio = 0.0
        equivalent_diameter_px = 0.0

    calibrated_diameter_mm: float | None = None
    if mm_per_pixel is not None and mm_per_pixel > 0:
        calibrated_diameter_mm = equivalent_diameter_px * mm_per_pixel

    circularity = 0.0
    solidity = 0.0
    convexity = 1.0
    aspect_ratio = 1.0
    hole_void_ratio = 0.0
    bubble_count = seg_result.bubble_count
    has_bubbles = seg_result.has_bubbles
    bubble_details = list(seg_result.bubble_details)
    is_tailing = False
    is_abnormal_shape = False

    if seg_result.deposit_contour is not None and deposit_area > 0:
        cnt = seg_result.deposit_contour
        perimeter = float(cv2.arcLength(cnt, True))
        if perimeter > 0:
            # 4 * pi * area / perimeter^2
            raw_circ = (4.0 * math.pi * deposit_area) / (perimeter * perimeter)
            circularity = max(0.0, min(1.0, raw_circ))

        hull = cv2.convexHull(cnt)
        hull_area = float(cv2.contourArea(hull))
        if hull_area > 0:
            solidity = max(0.0, min(1.0, deposit_area / hull_area))

        if perimeter > 0:
            hull_perimeter = float(cv2.arcLength(hull, True))
            convexity = max(0.0, min(1.0, hull_perimeter / perimeter))

        # Bounding box aspect ratio (w / h)
        _, _, bw, bh = cv2.boundingRect(cnt)
        if bh > 0:
            aspect_ratio = float(bw) / float(bh)

        if deposit_area > 0:
            hole_void_ratio = max(0.0, min(1.0, seg_result.inner_holes_area_px / deposit_area))

        # Programmatic shape abnormality checks
        elongation = max(aspect_ratio, 1.0 / aspect_ratio) if aspect_ratio > 0 else 1.0
        if (elongation >= 1.35 and (solidity < 0.94 or circularity < 0.82)) or elongation >= 1.55:
            is_tailing = True

        if circularity < 0.78 or solidity < 0.88 or convexity < 0.88 or is_tailing:
            is_abnormal_shape = True

    return RoiMeasurement(
        roi_id=roi_id,
        deposit_area_px=deposit_area,
        target_area_px=target_area,
        coverage_ratio=coverage_ratio,
        overflow_ratio=overflow_ratio,
        equivalent_diameter_px=equivalent_diameter_px,
        calibrated_diameter_mm=calibrated_diameter_mm,
        circularity=circularity,
        solidity=solidity,
        convexity=convexity,
        aspect_ratio=aspect_ratio,
        hole_void_ratio=hole_void_ratio,
        bubble_count=bubble_count,
        has_bubbles=has_bubbles,
        is_abnormal_shape=is_abnormal_shape,
        is_tailing=is_tailing,
        bubble_details=bubble_details,
        segmentation_quality=seg_result.quality_score,
        is_missing=seg_result.is_missing,
    )


def calculate_aggregate_measurements(
    roi_measurements: list[RoiMeasurement],
    all_roi_ids: list[str],
) -> AggregateMeasurements:
    """Compute aggregate statistics across multiple ROI measurements."""
    missing_ids = [m.roi_id for m in roi_measurements if m.is_missing or m.deposit_area_px == 0]
    # Identify any ROIs in all_roi_ids that have no measurement
    measured_ids = {m.roi_id for m in roi_measurements}
    for rid in all_roi_ids:
        if rid not in measured_ids and rid not in missing_ids:
            missing_ids.append(rid)

    valid_coverages = [m.coverage_ratio for m in roi_measurements if not m.is_missing and m.deposit_area_px > 0]

    mean_cov: float | None = None
    size_cv: float | None = None
    warnings: list[str] = []

    if valid_coverages:
        mean_cov = float(np.mean(valid_coverages))
        if len(valid_coverages) >= 2:
            std_cov = float(np.std(valid_coverages, ddof=1))
            if mean_cov > 1e-6:
                size_cv = std_cov / mean_cov
            else:
                size_cv = 0.0

    if missing_ids:
        warnings.append(f"Missing deposits detected in {len(missing_ids)} ROI(s): {', '.join(missing_ids)}.")

    return AggregateMeasurements(
        mean_coverage=mean_cov,
        size_cv=size_cv,
        missing_roi_ids=missing_ids,
        warnings=warnings,
    )
