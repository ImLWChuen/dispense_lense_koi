"""
Dispense Lens - Vision Overlay Service

Provides bounded full-image normalized contour geometry for display overlays
of reliably detected dispensing deposits.
"""

from __future__ import annotations

import math
import cv2
import numpy as np

from app.schemas.image import NormalizedPoint, PixelROI, RoiInspectionStatus
from app.services.vision.segmentation import SegmentationResult


def extract_deposit_outline(
    seg_result: SegmentationResult | None,
    inspection_status: RoiInspectionStatus,
    window_roi: PixelROI,
    image_width: int,
    image_height: int,
    roi_id: str,
) -> tuple[list[NormalizedPoint] | None, str | None]:
    """Extract a bounded, normalized outer polygon outline for a reliably detected deposit.

    Args:
        seg_result: Segmentation output containing the detected candidate contour.
        inspection_status: Explicit per-region inspection status (DETECTED, MISSING, UNASSESSED).
        window_roi: Expanded analysis window bounding box in pixel coordinates.
        image_width: Decoded full image width in pixels.
        image_height: Decoded full image height in pixels.
        roi_id: Identifier of the region being evaluated.

    Returns:
        tuple (outline, warning):
        - If region is MISSING or UNASSESSED: (None, None).
        - If region is DETECTED and contour is valid: (list[NormalizedPoint], None).
        - If region is DETECTED but geometry is unavailable: (None, warning_message).
    """
    # 1. Geometry is published strictly for DETECTED regions
    if inspection_status != RoiInspectionStatus.DETECTED:
        return None, None

    if seg_result is None or seg_result.deposit_contour is None:
        return None, f"ROI '{roi_id}' deposit outline unavailable (no contour detected)."

    cnt = seg_result.deposit_contour
    if cnt.size == 0:
        return None, f"ROI '{roi_id}' deposit outline unavailable (no contour detected)."

    pts = cnt.reshape(-1, 2)
    if len(pts) < 3:
        return None, f"ROI '{roi_id}' deposit outline unavailable (fewer than 3 contour points)."

    if image_width <= 0 or image_height <= 0:
        return None, f"ROI '{roi_id}' deposit outline unavailable (invalid image dimensions)."

    perimeter = float(cv2.arcLength(cnt, closed=True))
    if perimeter <= 0:
        return None, f"ROI '{roi_id}' deposit outline unavailable (zero perimeter contour)."

    # 2. Deterministic bounded approximation: cap at 128 points
    approx = cnt
    if len(pts) > 128:
        low = 0.0
        high = float(perimeter)
        best: np.ndarray | None = None

        # Binary search for optimal epsilon
        for _ in range(35):
            mid = (low + high) / 2.0
            cand = cv2.approxPolyDP(cnt, mid, closed=True)
            k = len(cand)
            if k > 128:
                low = mid
            elif k < 3:
                high = mid
            else:
                best = cand
                high = mid

        # Fallback stepped scan if binary search missed a discrete step
        if best is None:
            eps = max(0.1, 0.0005 * perimeter)
            while eps < perimeter:
                cand = cv2.approxPolyDP(cnt, eps, closed=True)
                k = len(cand)
                if 3 <= k <= 128:
                    best = cand
                    break
                elif k < 3:
                    break
                eps *= 1.15

        if best is None:
            return None, f"ROI '{roi_id}' deposit outline unavailable (contour could not be simplified to 3-128 points)."
        approx = best

    # 3. Coordinate conversion: window-local -> full-image pixel -> normalized [0, 1]
    approx_pts = approx.reshape(-1, 2)
    norm_points: list[NormalizedPoint] = []
    tol = 1e-4

    for pt in approx_pts:
        x_local = float(pt[0])
        y_local = float(pt[1])
        x_global = window_roi.x + x_local
        y_global = window_roi.y + y_local

        x_norm = x_global / float(image_width)
        y_norm = y_global / float(image_height)

        # Reject substantially out-of-bounds geometry without silent fake clamping
        if x_norm < -tol or x_norm > 1.0 + tol or y_norm < -tol or y_norm > 1.0 + tol:
            return None, f"ROI '{roi_id}' deposit outline unavailable (contour points out of image bounds)."

        x_clamped = max(0.0, min(1.0, x_norm))
        y_clamped = max(0.0, min(1.0, y_norm))

        if not (math.isfinite(x_clamped) and math.isfinite(y_clamped)):
            return None, f"ROI '{roi_id}' deposit outline unavailable (non-finite coordinate detected)."

        # Deduplicate consecutive identical points
        pt_key = (round(x_clamped, 6), round(y_clamped, 6))
        if norm_points:
            prev_key = (round(norm_points[-1].x, 6), round(norm_points[-1].y, 6))
            if pt_key == prev_key:
                continue

        norm_points.append(NormalizedPoint(x=x_clamped, y=y_clamped))

    # Remove redundant closing point if identical to the first point
    if len(norm_points) > 1:
        first_key = (round(norm_points[0].x, 6), round(norm_points[0].y, 6))
        last_key = (round(norm_points[-1].x, 6), round(norm_points[-1].y, 6))
        if first_key == last_key:
            norm_points.pop()

    # 4. Final polygon validity checks
    distinct_keys = {(round(p.x, 6), round(p.y, 6)) for p in norm_points}
    if len(norm_points) < 3 or len(distinct_keys) < 3:
        return None, f"ROI '{roi_id}' deposit outline unavailable (fewer than 3 distinct points)."

    if len(distinct_keys) < len(norm_points):
        return None, f"ROI '{roi_id}' deposit outline unavailable (nonconsecutive duplicate vertices detected)."

    if len(norm_points) > 128:
        return None, f"ROI '{roi_id}' deposit outline unavailable (polygon exceeds 128 points)."

    return norm_points, None
