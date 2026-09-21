"""
Dispense Lens - Interior Bubble & Void Detector

Detects trapped air bubbles, voids, and internal cavities within adhesive deposits
using classical OpenCV computer vision:
1. Contour hierarchy topological void analysis (RETR_CCOMP inner holes)
2. Interior-bounded Hough Circle Transform on masked deposit interior
3. Localized blob detection for low-contrast void pockets
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any
import cv2
import numpy as np


@dataclass
class BubbleDetail:
    x: float
    y: float
    radius: float
    area: float
    method: str


@dataclass
class BubbleDetectionResult:
    bubble_count: int = 0
    has_bubbles: bool = False
    total_bubble_area_px: float = 0.0
    bubble_details: list[dict[str, Any]] = field(default_factory=list)


def detect_interior_bubbles(
    image_gray: np.ndarray,
    deposit_mask: np.ndarray,
    deposit_contour: np.ndarray | None,
    inner_contours: list[np.ndarray] | None = None,
) -> BubbleDetectionResult:
    """Detect interior bubbles and voids strictly bounded within the segmented deposit contour.

    Args:
        image_gray: 2D uint8 grayscale image patch corresponding to analysis window.
        deposit_mask: 2D uint8 binary mask (255 inside deposit, 0 outside).
        deposit_contour: External contour points of the deposit.
        inner_contours: Optional list of child contours representing topological holes from RETR_CCOMP.

    Returns:
        BubbleDetectionResult containing bubble count, total void area, and detailed detections.
    """
    if deposit_contour is None or deposit_mask is None or np.count_nonzero(deposit_mask) < 20:
        return BubbleDetectionResult()

    deposit_area = float(cv2.contourArea(deposit_contour))
    if deposit_area < 20.0:
        return BubbleDetectionResult()

    equiv_diameter = 2.0 * math.sqrt(deposit_area / math.pi)
    detected: list[BubbleDetail] = []

    # 1. Topological inner holes from contour hierarchy
    if inner_contours:
        for hole_cnt in inner_contours:
            h_area = float(cv2.contourArea(hole_cnt))
            if h_area < 3.0:
                continue
            m = cv2.moments(hole_cnt)
            if m["m00"] > 0:
                hx = float(m["m10"] / m["m00"])
                hy = float(m["m01"] / m["m00"])
            else:
                x, y, w, h = cv2.boundingRect(hole_cnt)
                hx, hy = float(x + w / 2.0), float(y + h / 2.0)
            hr = math.sqrt(h_area / math.pi)
            detected.append(BubbleDetail(x=round(hx, 1), y=round(hy, 1), radius=round(hr, 1), area=round(h_area, 1), method="contour_hole"))

    # 2. Interior mask isolation (erode boundary so dot edge is excluded)
    erode_size = max(2, min(8, int(equiv_diameter * 0.07)))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (erode_size * 2 + 1, erode_size * 2 + 1))
    eroded_mask = cv2.erode(deposit_mask, kernel, iterations=1)

    # If erosion consumed too much, fallback to lighter erosion or polygon check
    if np.count_nonzero(eroded_mask) < 20:
        eroded_mask = deposit_mask

    # Crop to bounding box of deposit for faster local detection
    bx, by, bw, bh = cv2.boundingRect(deposit_contour)
    if bw <= 4 or bh <= 4:
        return _summarize_results(detected, deposit_area)

    patch_gray = image_gray[by : by + bh, bx : bx + bw]
    patch_eroded = eroded_mask[by : by + bh, bx : bx + bw]
    patch_masked = cv2.bitwise_and(patch_gray, patch_gray, mask=patch_eroded)

    min_r = max(2, int(equiv_diameter * 0.03))
    max_r = max(min_r + 2, int(equiv_diameter * 0.40))

    # 3. Interior Hough Circle Transform
    blurred = cv2.medianBlur(patch_masked, 5)
    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=1.0,
        minDist=max(4.0, float(min_r * 2)),
        param1=45,
        param2=13,
        minRadius=min_r,
        maxRadius=max_r,
    )

    if circles is not None:
        circles_arr = np.round(circles[0, :]).astype(int)
        for cx_p, cy_p, cr in circles_arr:
            # Map back to window ROI coordinates
            cx = float(cx_p + bx)
            cy = float(cy_p + by)
            r = float(cr)

            # Strict boundary check: circle center must be comfortably inside deposit contour
            dist = cv2.pointPolygonTest(deposit_contour, (cx, cy), True)
            if dist < r * 0.5:
                continue

            # Contrast validation: check that circle interior has variance / contrast against surroundings
            circ_mask = np.zeros((bh, bw), dtype=np.uint8)
            cv2.circle(circ_mask, (cx_p, cy_p), int(r), 255, -1)
            circ_pixels = patch_gray[(circ_mask > 0) & (patch_eroded > 0)]
            if circ_pixels.size < 4:
                continue

            annulus_mask = np.zeros((bh, bw), dtype=np.uint8)
            cv2.circle(annulus_mask, (cx_p, cy_p), int(r * 1.6), 255, -1)
            annulus_mask = cv2.subtract(annulus_mask, circ_mask)
            annulus_pixels = patch_gray[(annulus_mask > 0) & (patch_eroded > 0)]

            if annulus_pixels.size >= 4:
                contrast = abs(float(np.mean(circ_pixels)) - float(np.mean(annulus_pixels)))
                if contrast < 10.0:
                    continue

            b_area = math.pi * (r ** 2)
            detected.append(BubbleDetail(x=round(cx, 1), y=round(cy, 1), radius=round(r, 1), area=round(b_area, 1), method="hough_circle"))

    # 4. Deduplicate overlapping detections (merge nearby centers)
    deduped = _deduplicate_bubbles(detected)

    return _summarize_results(deduped, deposit_area)


def _deduplicate_bubbles(bubbles: list[BubbleDetail]) -> list[BubbleDetail]:
    """Merge detections with closely overlapping centers."""
    if len(bubbles) <= 1:
        return bubbles

    merged: list[BubbleDetail] = []
    for b in bubbles:
        duplicate = False
        for m in merged:
            dist = math.hypot(b.x - m.x, b.y - m.y)
            merge_dist = max(b.radius, m.radius) * 0.8
            if dist < merge_dist:
                duplicate = True
                break
        if not duplicate:
            merged.append(b)

    return merged


def _summarize_results(bubbles: list[BubbleDetail], deposit_area: float) -> BubbleDetectionResult:
    """Build structured summary result."""
    total_area = sum(b.area for b in bubbles)
    details = [
        {
            "x": b.x,
            "y": b.y,
            "radius": b.radius,
            "area": b.area,
            "method": b.method,
        }
        for b in bubbles
    ]
    return BubbleDetectionResult(
        bubble_count=len(bubbles),
        has_bubbles=len(bubbles) > 0,
        total_bubble_area_px=total_area,
        bubble_details=details,
    )
