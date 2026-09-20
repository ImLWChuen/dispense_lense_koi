"""
Dispense Lens - Vision Segmentation Service

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

    target_crop = gray[ty_rel : ty_rel + th, tx_rel : tx_rel + tw]
    if target_crop.size == 0:
        return SegmentationResult(
            status=SegmentationStatus.UNRELIABLE,
            target_area_px=target_area,
            quality_score=0.0,
            warnings=["Target ROI crop is empty."],
        )

    target_std = float(np.std(target_crop))
    target_mean = float(np.mean(target_crop))

    # Calculate statistics for the surrounding window region (outside target ROI)
    surrounding_mask = (target_mask == 0)
    surrounding_pixels = gray[surrounding_mask]
    if surrounding_pixels.size > 0:
        surrounding_mean = float(np.mean(surrounding_pixels))
        surrounding_std = float(np.std(surrounding_pixels))
    else:
        surrounding_mean = target_mean
        surrounding_std = 0.0

    contrast_to_surroundings = abs(target_mean - surrounding_mean)

    # Check for uniform target crop vs surrounding contrast
    if target_std < 2.5:
        if contrast_to_surroundings > 20.0:
            # Target is uniformly filled with contrasting material (e.g. solid deposit filling ROI).
            # Do NOT treat as missing; proceed to thresholding and segmentation.
            pass
        elif surrounding_std < 2.5:
            # Both target and surroundings are uniform: no background or reference basis exists to distinguish
            # empty target from occluded lens, camera failure, overexposure, or flooded material.
            return SegmentationResult(
                status=SegmentationStatus.UNRELIABLE,
                target_area_px=target_area,
                quality_score=0.0,
                is_missing=False,
                warnings=["Target and surroundings are both uniform; cannot establish background or missing deposit without reference."],
            )
        elif surrounding_std >= 5.0 and contrast_to_surroundings < 15.0:
            # Background basis is established by surrounding fiducials/substrate features,
            # and target ROI matches substrate with no deposit present -> genuine missing deposit.
            return SegmentationResult(
                status=SegmentationStatus.SUCCESS,
                deposit_area_px=0.0,
                deposit_inside_target_px=0.0,
                deposit_outside_target_px=0.0,
                target_area_px=target_area,
                quality_score=1.0,
                is_missing=True,
                warnings=["No deposit detected inside target ROI; established background indicates missing deposit."],
            )
        else:
            # Target is flat but surrounding window is ambiguous; polarity cannot be distinguished.
            return SegmentationResult(
                status=SegmentationStatus.UNRELIABLE,
                target_area_px=target_area,
                quality_score=0.0,
                is_missing=False,
                warnings=["Low target contrast against ambiguous background; polarity/background cannot be distinguished."],
            )

    # Blurring to reduce high-frequency raster noise
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Determine polarity (deposit darker than background vs lighter)
    # Compare target center to window borders
    border_pixels = np.concatenate([
        blurred[0, :], blurred[-1, :], blurred[:, 0], blurred[:, -1]
    ])
    border_mean = float(np.mean(border_pixels))
    blurred_target_mean = float(np.mean(blurred[ty_rel : ty_rel + th, tx_rel : tx_rel + tw]))

    if blurred_target_mean < border_mean:
        # Dark deposit on light background
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    else:
        # Light deposit on dark background
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Find contours with hierarchy to detect inner holes
    contours, hierarchy = cv2.findContours(thresh, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return SegmentationResult(
            status=SegmentationStatus.UNRELIABLE,
            deposit_area_px=0.0,
            deposit_inside_target_px=0.0,
            deposit_outside_target_px=0.0,
            target_area_px=target_area,
            quality_score=0.0,
            is_missing=False,
            warnings=["No contours found in analysis window."],
        )

    target_center = np.array([tx_rel + tw / 2.0, ty_rel + th / 2.0])

    candidates = []
    for idx, cnt in enumerate(contours):
        # Only consider external contours (hierarchy[0][idx][3] == -1 in RETR_CCOMP)
        if hierarchy is not None and hierarchy[0][idx][3] != -1:
            continue

        # Draw contour mask to count exact binary pixels
        c_mask = np.zeros((h, w), dtype=np.uint8)
        cv2.drawContours(c_mask, [cnt], -1, 255, -1)

        c_total_pixels = float(np.count_nonzero(c_mask))
        if c_total_pixels < 8.0:
            continue  # Tiny speckle noise

        # Calculate exact pixel overlap with target ROI
        overlap_mask = cv2.bitwise_and(c_mask, target_mask)
        c_inside_pixels = float(np.count_nonzero(overlap_mask))

        # Check centroid of contour
        m = cv2.moments(cnt)
        if m["m00"] > 0:
            cx = m["m10"] / m["m00"]
            cy = m["m01"] / m["m00"]
        else:
            cx, cy = target_center[0], target_center[1]

        dist_to_center = float(np.linalg.norm(np.array([cx, cy]) - target_center))

        # Reject candidate if it has zero overlap with target and is far away
        if c_inside_pixels == 0 and dist_to_center > max(tw, th):
            continue

        # Score candidate: prioritize higher overlap with target ROI and proximity to target center
        cand_score = c_inside_pixels - (dist_to_center * 0.5)
        candidates.append((cand_score, idx, cnt, c_mask, c_total_pixels, c_inside_pixels))

    if not candidates:
        return SegmentationResult(
            status=SegmentationStatus.UNRELIABLE,
            deposit_area_px=0.0,
            deposit_inside_target_px=0.0,
            deposit_outside_target_px=0.0,
            target_area_px=target_area,
            quality_score=0.0,
            is_missing=False,
            warnings=["No candidate contours overlapped the target ROI in analysis window."],
        )

    # Sort candidates by score descending
    candidates.sort(key=lambda x: x[0], reverse=True)

    # Check for indistinguishably ambiguous candidates (near-tied scores among viable candidates)
    if len(candidates) >= 2:
        top1_score = candidates[0][0]
        top2_score = candidates[1][0]
        top1_inside = candidates[0][5]
        top2_inside = candidates[1][5]
        if (top1_inside > 0 and top2_inside > 0) or (candidates[1][4] > 0.25 * candidates[0][4]):
            diff = abs(top1_score - top2_score)
            max_s = max(abs(top1_score), 1.0)
            if diff / max_s < 0.15:
                return SegmentationResult(
                    status=SegmentationStatus.UNRELIABLE,
                    target_area_px=target_area,
                    quality_score=0.3,
                    warnings=["Indistinguishably ambiguous segmentation candidates detected."],
                )

    best_score, best_idx, best_cnt, best_mask, total_deposit_pixels, inside_pixels = candidates[0]

    # Consistent binary mask arithmetic: total = inside + outside exactly
    outside_pixels = max(0.0, total_deposit_pixels - inside_pixels)

    # Calculate inner holes area if hierarchy exists
    inner_holes_area = 0.0
    if hierarchy is not None:
        child_idx = hierarchy[0][best_idx][2]
        while child_idx != -1:
            inner_holes_area += float(cv2.contourArea(contours[child_idx]))
            child_idx = hierarchy[0][child_idx][0]

    # Assess segmentation quality & reject border-dominant / clipped candidates
    # 1. Background-dominant check: if mask takes up > 90% of entire window
    if total_deposit_pixels > 0.90 * (w * h):
        return SegmentationResult(
            status=SegmentationStatus.UNRELIABLE,
            deposit_area_px=total_deposit_pixels,
            deposit_inside_target_px=inside_pixels,
            deposit_outside_target_px=outside_pixels,
            target_area_px=target_area,
            quality_score=0.2,
            warnings=["Segmentation mask is background-dominant (covers > 90% of window)."],
        )

    # 2. Border-dominant / clipped candidate check
    border_pixels_count = int(
        np.count_nonzero(best_mask[0, :])
        + np.count_nonzero(best_mask[-1, :])
        + np.count_nonzero(best_mask[:, 0])
        + np.count_nonzero(best_mask[:, -1])
    )
    perimeter = float(cv2.arcLength(best_cnt, True))
    border_ratio = border_pixels_count / max(1.0, perimeter)

    if border_ratio > 0.20 or (border_pixels_count >= 30 and border_ratio > 0.15):
        return SegmentationResult(
            status=SegmentationStatus.UNRELIABLE,
            deposit_mask=best_mask,
            deposit_contour=best_cnt,
            deposit_area_px=total_deposit_pixels,
            deposit_inside_target_px=inside_pixels,
            deposit_outside_target_px=outside_pixels,
            target_area_px=target_area,
            quality_score=0.3,
            warnings=["Candidate is clipped by window boundary or border-dominant."],
        )

    deposit_pixels = gray[best_mask > 0]
    background_pixels = gray[best_mask == 0]
    if deposit_pixels.size > 0 and background_pixels.size > 0:
        deposit_contrast = abs(float(np.mean(deposit_pixels)) - float(np.mean(background_pixels)))
    else:
        deposit_contrast = target_std

    contrast_ratio = min(1.0, deposit_contrast / 50.0)
    border_penalty = 0.15 if border_pixels_count > 0 else 0.0
    quality = max(0.1, min(1.0, contrast_ratio * (1.0 - border_penalty)))

    if deposit_contrast < 15.0:
        return SegmentationResult(
            status=SegmentationStatus.UNRELIABLE,
            deposit_mask=best_mask,
            deposit_contour=best_cnt,
            deposit_area_px=total_deposit_pixels,
            deposit_inside_target_px=inside_pixels,
            deposit_outside_target_px=outside_pixels,
            target_area_px=target_area,
            inner_holes_area_px=inner_holes_area,
            quality_score=quality,
            warnings=["Low contrast ambiguous segmentation."],
        )

    return SegmentationResult(
        status=SegmentationStatus.SUCCESS,
        deposit_mask=best_mask,
        deposit_contour=best_cnt,
        deposit_area_px=total_deposit_pixels,
        deposit_inside_target_px=inside_pixels,
        deposit_outside_target_px=outside_pixels,
        target_area_px=target_area,
        inner_holes_area_px=inner_holes_area,
        quality_score=quality,
        is_missing=False,
    )
