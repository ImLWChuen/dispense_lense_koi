"""
DispenseIQ — Vision Segmentation Service

Performs localized, ROI-bounded segmentation of dispensing deposits.
Enforces candidate selection using target overlap/proximity and rejects
degenerate, border-dominant, background-dominant, or ambiguous contours.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import cv2
import numpy as np

from app.schemas.image import PixelROI


class SegmentationStatus(str, Enum):
    SUCCESS = "SUCCESS"
    MISSING = "MISSING"
    UNRELIABLE = "UNRELIABLE"


@dataclass
class SegmentationResult:
    status: SegmentationStatus
    deposit_mask: np.ndarray | None = None
    deposit_contour: np.ndarray | None = None
    deposit_area_px: float = 0.0
    deposit_inside_target_px: float = 0.0
    deposit_outside_target_px: float = 0.0
    target_area_px: float = 0.0
    quality_score: float = 1.0
    is_missing: bool = False
    inner_holes_area_px: float = 0.0
    warnings: list[str] = field(default_factory=list)


def segment_roi(
    image: np.ndarray,
    target_roi: PixelROI,
    window_roi: PixelROI,
) -> SegmentationResult:
    """Segment the deposit inside target_roi using the bounded window_roi image patch."""
    target_area = float(target_roi.width * target_roi.height)

    # Extract analysis window sub-image
    sub_img = image[
        window_roi.y : window_roi.y + window_roi.height,
        window_roi.x : window_roi.x + window_roi.width,
    ]
    if sub_img.size == 0:
        return SegmentationResult(
            status=SegmentationStatus.UNRELIABLE,
            target_area_px=target_area,
            quality_score=0.0,
            warnings=["Analysis window has zero size."],
        )

    gray = cv2.cvtColor(sub_img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    # Relative target coordinates inside the window sub-image
    tx_rel = max(0, target_roi.x - window_roi.x)
    ty_rel = max(0, target_roi.y - window_roi.y)
    tw = min(target_roi.width, w - tx_rel)
    th = min(target_roi.height, h - ty_rel)

    target_mask = np.zeros((h, w), dtype=np.uint8)
    target_mask[ty_rel : ty_rel + th, tx_rel : tx_rel + tw] = 255

    # Check contrast within target region
    target_crop = gray[ty_rel : ty_rel + th, tx_rel : tx_rel + tw]
    if target_crop.size == 0:
        return SegmentationResult(
            status=SegmentationStatus.UNRELIABLE,
            target_area_px=target_area,
            quality_score=0.0,
            warnings=["Target ROI crop is empty."],
        )

    std_val = float(np.std(target_crop))
    mean_val = float(np.mean(target_crop))

    # Extremely low contrast check
    if std_val < 3.0:
        # Uniform light background or uniform dark with no feature
        return SegmentationResult(
            status=SegmentationStatus.SUCCESS,
            deposit_area_px=0.0,
            deposit_inside_target_px=0.0,
            deposit_outside_target_px=0.0,
            target_area_px=target_area,
            quality_score=1.0,
            is_missing=True,
            warnings=["No deposit detected; region is uniform background."],
        )

    # Blurring to reduce high-frequency raster noise
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Determine polarity (deposit darker than background vs lighter)
    # Compare target center to window borders
    border_pixels = np.concatenate([
        blurred[0, :], blurred[-1, :], blurred[:, 0], blurred[:, -1]
    ])
    border_mean = float(np.mean(border_pixels))
    target_mean = float(np.mean(blurred[ty_rel : ty_rel + th, tx_rel : tx_rel + tw]))

    if target_mean < border_mean:
        # Dark deposit on light background
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    else:
        # Light deposit on dark background
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Find contours with hierarchy to detect inner holes
    contours, hierarchy = cv2.findContours(thresh, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return SegmentationResult(
            status=SegmentationStatus.SUCCESS,
            deposit_area_px=0.0,
            deposit_inside_target_px=0.0,
            deposit_outside_target_px=0.0,
            target_area_px=target_area,
            quality_score=1.0,
            is_missing=True,
            warnings=["No contours found in analysis window."],
        )

    target_center = np.array([tx_rel + tw / 2.0, ty_rel + th / 2.0])

    candidates = []
    for idx, cnt in enumerate(contours):
        # Only consider external contours (hierarchy[0][idx][3] == -1 in RETR_CCOMP)
        if hierarchy is not None and hierarchy[0][idx][3] != -1:
            continue

        area = float(cv2.contourArea(cnt))
        if area < 8.0:
            continue  # Tiny speckle noise

        # Draw contour mask
        c_mask = np.zeros((h, w), dtype=np.uint8)
        cv2.drawContours(c_mask, [cnt], -1, 255, -1)

        # Calculate overlap with target ROI
        overlap_mask = cv2.bitwise_and(c_mask, target_mask)
        overlap_area = float(np.count_nonzero(overlap_mask))

        # Check centroid of contour
        m = cv2.moments(cnt)
        if m["m00"] > 0:
            cx = m["m10"] / m["m00"]
            cy = m["m01"] / m["m00"]
        else:
            cx, cy = target_center[0], target_center[1]

        dist_to_center = float(np.linalg.norm(np.array([cx, cy]) - target_center))

        # Reject candidate if it has zero overlap with target and is far away
        if overlap_area == 0 and dist_to_center > max(tw, th):
            continue

        # Score candidate: prioritize higher overlap with target ROI and proximity to target center
        cand_score = overlap_area - (dist_to_center * 0.5)
        candidates.append((cand_score, idx, cnt, c_mask, area, overlap_area))

    if not candidates:
        return SegmentationResult(
            status=SegmentationStatus.SUCCESS,
            deposit_area_px=0.0,
            deposit_inside_target_px=0.0,
            deposit_outside_target_px=0.0,
            target_area_px=target_area,
            quality_score=1.0,
            is_missing=True,
            warnings=["No candidate contours overlapped the target ROI."],
        )

    # Sort candidates by score descending
    candidates.sort(key=lambda x: x[0], reverse=True)
    best_score, best_idx, best_cnt, best_mask, total_area, inside_area = candidates[0]

    # Calculate inner holes area if hierarchy exists
    inner_holes_area = 0.0
    if hierarchy is not None:
        child_idx = hierarchy[0][best_idx][2]
        while child_idx != -1:
            inner_holes_area += float(cv2.contourArea(contours[child_idx]))
            child_idx = hierarchy[0][child_idx][0]

    outside_area = max(0.0, total_area - inside_area)

    # Assess segmentation quality
    # 1. Background-dominant check: if mask takes up > 90% of entire window
    if total_area > 0.90 * (w * h):
        return SegmentationResult(
            status=SegmentationStatus.UNRELIABLE,
            deposit_area_px=total_area,
            target_area_px=target_area,
            quality_score=0.2,
            warnings=["Segmentation mask is background-dominant (covers > 90% of window)."],
        )

    # 2. Quality score based on contrast and edge clarity
    contrast_ratio = min(1.0, std_val / 50.0)
    # Check boundary touch: touches border?
    touches_border = (
        np.any(best_mask[0, :])
        or np.any(best_mask[-1, :])
        or np.any(best_mask[:, 0])
        or np.any(best_mask[:, -1])
    )
    border_penalty = 0.2 if touches_border else 0.0
    quality = max(0.1, min(1.0, contrast_ratio * (1.0 - border_penalty)))

    if std_val < 8.0:
        # Ambiguous contrast
        return SegmentationResult(
            status=SegmentationStatus.UNRELIABLE,
            deposit_mask=best_mask,
            deposit_contour=best_cnt,
            deposit_area_px=total_area,
            deposit_inside_target_px=inside_area,
            deposit_outside_target_px=outside_area,
            target_area_px=target_area,
            inner_holes_area_px=inner_holes_area,
            quality_score=quality,
            warnings=["Low contrast ambiguous segmentation."],
        )

    return SegmentationResult(
        status=SegmentationStatus.SUCCESS,
        deposit_mask=best_mask,
        deposit_contour=best_cnt,
        deposit_area_px=total_area,
        deposit_inside_target_px=inside_area,
        deposit_outside_target_px=outside_area,
        target_area_px=target_area,
        inner_holes_area_px=inner_holes_area,
        quality_score=quality,
        is_missing=False,
    )
