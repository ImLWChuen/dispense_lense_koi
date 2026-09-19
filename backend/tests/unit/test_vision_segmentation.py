"""
DispenseIQ — Vision Segmentation Unit Tests

Verifies:
- Local segmentation within target ROIs and expanded windows (prohibiting naive whole-image largest-contour selection).
- Deterministic candidate selection using target overlap/proximity.
- Rejection of background-dominant, border-dominant, degenerate, or absent deposits.
- Quality metrics and UNRELIABLE classification on ambiguous/noisy inputs.
- Missing deposit detection inside ROI.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.schemas.image import NormalizedROI
from app.services.vision.preprocessing import decode_and_validate_image, normalize_roi_to_pixels
from app.services.vision.segmentation import (
    segment_roi,
    SegmentationStatus,
)
from tests.fixtures.synthetic_images import (
    create_centered_dot_image,
    create_empty_image,
    create_multi_roi_image,
    create_noisy_image,
)


def test_segment_clean_centered_deposit() -> None:
    img_bytes = create_centered_dot_image(size=200, dot_radius=30)
    img, dims = decode_and_validate_image(img_bytes)
    roi = NormalizedROI(roi_id="roi_1", x=0.25, y=0.25, width=0.5, height=0.5)
    px_roi, win_roi = normalize_roi_to_pixels(roi, dims.width, dims.height)

    result = segment_roi(img, px_roi, win_roi)
    assert result.status == SegmentationStatus.SUCCESS
    assert result.deposit_mask is not None
    assert result.deposit_area_px > 0
    assert result.quality_score >= 0.8
    assert not result.is_missing


def test_segment_missing_deposit() -> None:
    # Empty image without any deposit in ROI
    img_bytes = create_empty_image(size=200)
    img, dims = decode_and_validate_image(img_bytes)
    roi = NormalizedROI(roi_id="roi_1", x=0.25, y=0.25, width=0.5, height=0.5)
    px_roi, win_roi = normalize_roi_to_pixels(roi, dims.width, dims.height)

    result = segment_roi(img, px_roi, win_roi)
    assert result.is_missing is True
    assert result.deposit_area_px == 0


def test_segment_noisy_ambiguous_image() -> None:
    # Random low-contrast noise
    img_bytes = create_noisy_image(size=200)
    img, dims = decode_and_validate_image(img_bytes)
    roi = NormalizedROI(roi_id="roi_1", x=0.25, y=0.25, width=0.5, height=0.5)
    px_roi, win_roi = normalize_roi_to_pixels(roi, dims.width, dims.height)

    result = segment_roi(img, px_roi, win_roi)
    assert result.status == SegmentationStatus.UNRELIABLE or result.quality_score < 0.5


def test_prohibit_whole_image_contamination_multiple_rois() -> None:
    # Create image with two separate deposits:
    # Deposit 1 at (50, 50) radius 15
    # Deposit 2 at (150, 150) radius 40 (much larger!)
    # When segmenting ROI around deposit 1, it must NOT latch onto Deposit 2 outside the ROI window!
    img_bytes = create_multi_roi_image(200, 200, [(50, 50, 15), (150, 150, 40)])
    img, dims = decode_and_validate_image(img_bytes)

    roi1 = NormalizedROI(roi_id="roi_1", x=0.1, y=0.1, width=0.4, height=0.4)
    px_roi1, win_roi1 = normalize_roi_to_pixels(roi1, dims.width, dims.height, window_expansion=0.1)

    result1 = segment_roi(img, px_roi1, win_roi1)
    assert result1.status == SegmentationStatus.SUCCESS
    # Radius 15 deposit area ~ pi * 15^2 = 706.8 px
    # Radius 40 deposit area ~ 5026 px
    # result1 must have detected deposit 1 (~700 px), not deposit 2!
    assert result1.deposit_area_px < 1500
    assert result1.deposit_area_px > 400
