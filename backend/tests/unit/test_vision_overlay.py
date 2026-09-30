"""
Dispense Lens - Vision Overlay Service Unit Tests

Verifies:
- Geometry is extracted only for DETECTED regions; MISSING and UNASSESSED return null.
- UNASSESSED regions containing candidate contours still return null outline with no false warning.
- Analysis window offset is correctly applied: (window_roi.x + x_local) / width.
- Resolution scaling preserves normalized coordinate alignment.
- Bounded approximation caps complex contours to 3-128 points without slicing or bounding box substitution.
- Degenerate, out-of-bounds, or missing contours on DETECTED regions return null with specific warnings.
- Schema defaults deposit_outline_normalized to None on legacy serialized payloads.
- NormalizedPoint rejects non-finite or out-of-range coordinates.
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from app.schemas.image import (
    NormalizedPoint,
    PixelROI,
    RoiInspectionStatus,
    RoiMeasurement,
)
from app.services.vision.overlay import extract_deposit_outline
from app.services.vision.segmentation import SegmentationResult, SegmentationStatus


def test_extract_deposit_outline_missing_and_unassessed_return_null() -> None:
    """MISSING and UNASSESSED regions emit null outlines, even with candidate contour."""
    cnt = np.array([[[10, 10]], [[30, 10]], [[30, 30]], [[10, 30]]], dtype=np.int32)
    win_roi = PixelROI(roi_id="r1", x=50, y=50, width=100, height=100)

    # 1. MISSING status
    seg_missing = SegmentationResult(
        status=SegmentationStatus.MISSING,
        deposit_contour=None,
        is_missing=True,
    )
    outline, warn = extract_deposit_outline(
        seg_result=seg_missing,
        inspection_status=RoiInspectionStatus.MISSING,
        window_roi=win_roi,
        image_width=200,
        image_height=200,
        roi_id="r1",
    )
    assert outline is None
    assert warn is None

    # 2. UNASSESSED status WITH candidate contour
    seg_unassessed = SegmentationResult(
        status=SegmentationStatus.UNRELIABLE,
        deposit_contour=cnt,
        is_missing=False,
        quality_score=0.2,
    )
    outline_unassessed, warn_unassessed = extract_deposit_outline(
        seg_result=seg_unassessed,
        inspection_status=RoiInspectionStatus.UNASSESSED,
        window_roi=win_roi,
        image_width=200,
        image_height=200,
        roi_id="r1",
    )
    assert outline_unassessed is None
    assert warn_unassessed is None


def test_extract_deposit_outline_detected_valid_nonzero_window_offset() -> None:
    """Nonzero window offset correctly translates window-local coordinates to full image."""
    # Window starts at (100, 50) in a 400x200 image
    win_roi = PixelROI(roi_id="r_off", x=100, y=50, width=100, height=100)

    # Local contour inside window: square from (10, 10) to (50, 50)
    cnt = np.array([[[10, 10]], [[50, 10]], [[50, 50]], [[10, 50]]], dtype=np.int32)
    seg = SegmentationResult(
        status=SegmentationStatus.SUCCESS,
        deposit_contour=cnt,
        deposit_area_px=1600.0,
        quality_score=1.0,
    )

    outline, warn = extract_deposit_outline(
        seg_result=seg,
        inspection_status=RoiInspectionStatus.DETECTED,
        window_roi=win_roi,
        image_width=400,
        image_height=200,
        roi_id="r_off",
    )

    assert warn is None
    assert outline is not None
    assert len(outline) == 4

    # Expected full-image pixel coordinates:
    # (100+10, 50+10) = (110, 60) -> norm: (110/400, 60/200) = (0.275, 0.3)
    # (100+50, 50+10) = (150, 60) -> norm: (150/400, 60/200) = (0.375, 0.3)
    # (100+50, 50+50) = (150, 100) -> norm: (150/400, 100/200) = (0.375, 0.5)
    # (100+10, 50+50) = (110, 100) -> norm: (110/400, 100/200) = (0.275, 0.5)
    expected = [(0.275, 0.3), (0.375, 0.3), (0.375, 0.5), (0.275, 0.5)]
    for pt, exp in zip(outline, expected):
        assert pt.x == pytest.approx(exp[0], abs=1e-5)
        assert pt.y == pytest.approx(exp[1], abs=1e-5)


def test_extract_deposit_outline_resolution_scaling_alignment() -> None:
    """Geometry aligns in normalized space after changing source image resolution."""
    # Scale 1: 200x200 image, window at (100, 50), size 100x100
    win1 = PixelROI(roi_id="r_scale", x=100, y=50, width=100, height=100)
    cnt1 = np.array([[[20, 20]], [[60, 20]], [[60, 60]], [[20, 60]]], dtype=np.int32)
    seg1 = SegmentationResult(status=SegmentationStatus.SUCCESS, deposit_contour=cnt1, deposit_area_px=1600.0)

    outline1, _ = extract_deposit_outline(
        seg_result=seg1,
        inspection_status=RoiInspectionStatus.DETECTED,
        window_roi=win1,
        image_width=200,
        image_height=200,
        roi_id="r_scale",
    )

    # Scale 2: 400x400 image (2x resolution), window at (200, 100), size 200x200
    win2 = PixelROI(roi_id="r_scale", x=200, y=100, width=200, height=200)
    cnt2 = (cnt1 * 2).astype(np.int32)
    seg2 = SegmentationResult(status=SegmentationStatus.SUCCESS, deposit_contour=cnt2, deposit_area_px=6400.0)

    outline2, _ = extract_deposit_outline(
        seg_result=seg2,
        inspection_status=RoiInspectionStatus.DETECTED,
        window_roi=win2,
        image_width=400,
        image_height=400,
        roi_id="r_scale",
    )

    assert outline1 is not None
    assert outline2 is not None
    assert len(outline1) == len(outline2)

    for p1, p2 in zip(outline1, outline2):
        assert p1.x == pytest.approx(p2.x, abs=1e-5)
        assert p1.y == pytest.approx(p2.y, abs=1e-5)


def test_extract_deposit_outline_complex_contour_capped_at_128_points() -> None:
    """Complex contour with >128 points is deterministically approximated to <= 128 points."""
    # Generate circle with 250 points
    angles = np.linspace(0, 2 * np.pi, 250, endpoint=False)
    cx, cy, r = 100.0, 100.0, 40.0
    pts = np.stack([cx + r * np.cos(angles), cy + r * np.sin(angles)], axis=1).astype(np.int32)
    cnt = pts.reshape(-1, 1, 2)

    win = PixelROI(roi_id="r_complex", x=0, y=0, width=200, height=200)
    seg = SegmentationResult(status=SegmentationStatus.SUCCESS, deposit_contour=cnt, deposit_area_px=math.pi * r * r)

    outline, warn = extract_deposit_outline(
        seg_result=seg,
        inspection_status=RoiInspectionStatus.DETECTED,
        window_roi=win,
        image_width=200,
        image_height=200,
        roi_id="r_complex",
    )

    assert warn is None
    assert outline is not None
    assert 3 <= len(outline) <= 128
    # Ensure all coordinates are valid finite numbers in [0, 1]
    for p in outline:
        assert 0.0 <= p.x <= 1.0
        assert 0.0 <= p.y <= 1.0


def test_extract_deposit_outline_detected_unavailable_geometry_warnings() -> None:
    """DETECTED region with unavailable geometry returns None with specific warning."""
    win = PixelROI(roi_id="r_bad", x=10, y=10, width=100, height=100)

    # 1. None contour
    seg_none = SegmentationResult(status=SegmentationStatus.SUCCESS, deposit_contour=None, deposit_area_px=100.0)
    outline, warn = extract_deposit_outline(seg_none, RoiInspectionStatus.DETECTED, win, 200, 200, "r_bad")
    assert outline is None
    assert warn is not None
    assert "no contour detected" in warn

    # 2. Fewer than 3 points
    cnt_2pts = np.array([[[10, 10]], [[20, 20]]], dtype=np.int32)
    seg_2pts = SegmentationResult(status=SegmentationStatus.SUCCESS, deposit_contour=cnt_2pts, deposit_area_px=10.0)
    outline, warn = extract_deposit_outline(seg_2pts, RoiInspectionStatus.DETECTED, win, 200, 200, "r_bad")
    assert outline is None
    assert warn is not None
    assert "fewer than 3" in warn

    # 3. Substantially out of bounds points (e.g. window placed at edge with out-of-bounds local coords)
    cnt_oob = np.array([[[-50, 10]], [[10, 10]], [[10, 50]]], dtype=np.int32)
    seg_oob = SegmentationResult(status=SegmentationStatus.SUCCESS, deposit_contour=cnt_oob, deposit_area_px=100.0)
    win_edge = PixelROI(roi_id="r_bad", x=0, y=0, width=100, height=100)
    outline, warn = extract_deposit_outline(seg_oob, RoiInspectionStatus.DETECTED, win_edge, 200, 200, "r_bad")
    assert outline is None
    assert warn is not None
    assert "out of image bounds" in warn


def test_roi_measurement_defaults_null_deposit_outline_normalized() -> None:
    """Legacy serialized ROI measurement deserializes with deposit_outline_normalized = None."""
    legacy_data = {
        "roi_id": "r1",
        "deposit_area_px": 500.0,
        "target_area_px": 1000.0,
        "coverage_ratio": 0.5,
        "overflow_ratio": 0.0,
        "equivalent_diameter_px": 25.2,
        "circularity": 0.9,
        "solidity": 0.95,
        "aspect_ratio": 1.0,
        "hole_void_ratio": 0.0,
        "segmentation_quality": 1.0,
        "is_missing": False,
        "inspection_status": "DETECTED",
    }
    m = RoiMeasurement.model_validate(legacy_data)
    assert m.deposit_outline_normalized is None


def test_normalized_point_validates_bounds_and_finite() -> None:
    """NormalizedPoint enforces [0.0, 1.0] and finite values."""
    p = NormalizedPoint(x=0.5, y=0.5)
    assert p.x == 0.5
    assert p.y == 0.5

    with pytest.raises(ValueError):
        NormalizedPoint(x=-0.01, y=0.5)

    with pytest.raises(ValueError):
        NormalizedPoint(x=0.5, y=1.01)

    with pytest.raises(ValueError):
        NormalizedPoint(x=float("nan"), y=0.5)

    with pytest.raises(ValueError):
        NormalizedPoint(x=0.5, y=float("inf"))
