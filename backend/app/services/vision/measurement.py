"""
DispenseIQ — OpenCV Visual Measurement & Defect Analysis Service

Analyzes dispensing deposit images to extract quantitative physical features
and convert them into normalized diagnostic observations for the evidence engine:
1. Deposit Presence (missing vs present)
2. Deposit Size (undersized vs normal vs oversized)
3. Deposit Shape & Circularity (normal vs abnormal vs tailing vs satellite dots)
4. Spreading Behaviour (normal vs excessive spread)
5. Bubbles / Internal Voids (visible bubbles / crater shapes)
"""

from __future__ import annotations

import logging
from typing import Any

import cv2
import numpy as np

from app.schemas.diagnosis import (
    EvidenceSource,
    Observation,
    ObservationType,
    StatementType,
)

logger = logging.getLogger(__name__)

# Calibrated area boundaries (in pixels) for standard magnification
TARGET_AREA_MIN = 1200.0
TARGET_AREA_MAX = 4500.0
MIN_DETECTABLE_AREA = 60.0

# Shape and geometry thresholds
MIN_CIRCULARITY_NORMAL = 0.70
MAX_ASPECT_RATIO_NORMAL = 1.45
SOLIDITY_BUBBLE_THRESHOLD = 0.88


def analyze_image_observations(image_bytes: bytes) -> list[dict[str, Any]]:
    """Process an image and extract all relevant diagnostic observations.

    Args:
        image_bytes: Raw binary bytes of the image (PNG, JPG, etc.)

    Returns:
        List of observation dictionaries ready for ingestion by the diagnostic engine,
        each containing observation_type, value, source, confidence, and quantitative details.
    """
    np_arr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if image is None:
        raise ValueError("Failed to decode image: invalid or corrupt image data.")

    # 1. Grayscale & Noise reduction
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # 2. Otsu thresholding (detect both dark-on-bright and bright-on-dark)
    # We test both polarities and pick the one with better foreground separation
    _, thresh_inv = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    _, thresh_normal = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Count foreground pixels; a typical deposit occupies < 60% of frame
    h, w = gray.shape
    total_pixels = h * w
    inv_fg = cv2.countNonZero(thresh_inv)
    thresh = thresh_inv if inv_fg <= total_pixels * 0.7 else thresh_normal

    # Morphological opening to remove small sensor specks
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

    # 3. Contour detection with full hierarchy (tree mode enables detecting internal voids/bubbles)
    contours, hierarchy = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    observations: list[dict[str, Any]] = []

    # -----------------------------------------------------------------------
    # Case A: No deposit detected (Missing Dots defect)
    # -----------------------------------------------------------------------
    if not contours:
        det = {"area_px": 0.0, "reason": "No material contour detected in image"}
        return [
            {
                "observation_type": "deposit_presence",
                "value": "missing",
                "source": "IMAGE",
                "confidence": 0.95,
                "details": det,
                "metadata": det,
            }
        ]

    # Find the largest contour (primary deposit)
    largest_idx = int(np.argmax([cv2.contourArea(c) for c in contours]))
    largest_contour = contours[largest_idx]
    area = float(cv2.contourArea(largest_contour))

    if area < MIN_DETECTABLE_AREA:
        det = {"area_px": area, "reason": "Foreground area below minimum detectable deposit size"}
        return [
            {
                "observation_type": "deposit_presence",
                "value": "missing",
                "source": "IMAGE",
                "confidence": 0.90,
                "details": det,
                "metadata": det,
            }
        ]

    perimeter = float(cv2.arcLength(largest_contour, True))
    x, y, bw, bh = cv2.boundingRect(largest_contour)
    aspect_ratio = float(max(bw, bh) / max(min(bw, bh), 1))

    # Circularity: 4 * pi * area / perimeter^2 (1.0 = perfect circle)
    circularity = float(4.0 * np.pi * area / (perimeter * perimeter)) if perimeter > 0 else 0.0

    # Convex hull and solidity (area / convex_hull_area)
    hull = cv2.convexHull(largest_contour)
    hull_area = float(cv2.contourArea(hull))
    solidity = float(area / hull_area) if hull_area > 0 else 1.0

    # -----------------------------------------------------------------------
    # 1. Deposit Size Observation
    # -----------------------------------------------------------------------
    if area < TARGET_AREA_MIN:
        size_val = "undersized"
        size_conf = min(0.99, 0.75 + (TARGET_AREA_MIN - area) / TARGET_AREA_MIN * 0.24)
    elif area > TARGET_AREA_MAX:
        size_val = "oversized"
        size_conf = min(0.99, 0.75 + (area - TARGET_AREA_MAX) / TARGET_AREA_MAX * 0.24)
    else:
        size_val = "normal"
        size_conf = 0.85

    size_det = {
        "area_px": round(area, 1),
        "target_min": TARGET_AREA_MIN,
        "target_max": TARGET_AREA_MAX,
    }
    observations.append({
        "observation_type": "deposit_size",
        "value": size_val,
        "source": "IMAGE",
        "confidence": round(size_conf, 2),
        "details": size_det,
        "metadata": size_det,
    })

    # -----------------------------------------------------------------------
    # 2. Bubble Presence & Internal Voids
    # -----------------------------------------------------------------------
    # Check hierarchy for internal holes inside the largest contour
    # hierarchy format: [Next, Previous, First_Child, Parent]
    has_internal_hole = False
    if hierarchy is not None and len(hierarchy[0]) > largest_idx:
        first_child_idx = hierarchy[0][largest_idx][2]
        if first_child_idx != -1:
            child_area = cv2.contourArea(contours[first_child_idx])
            if child_area >= 12.0:  # significant void
                has_internal_hole = True

    # Low solidity or internal hole indicates bubble / crater
    if has_internal_hole or solidity < SOLIDITY_BUBBLE_THRESHOLD:
        bubble_det = {"solidity": round(solidity, 3), "internal_void_detected": has_internal_hole}
        observations.append({
            "observation_type": "bubble_presence",
            "value": "visible_bubbles",
            "source": "IMAGE",
            "confidence": 0.92,
            "details": bubble_det,
            "metadata": bubble_det,
        })
        crater_det = {"solidity": round(solidity, 3)}
        observations.append({
            "observation_type": "visual_appearance",
            "value": "crater_shape",
            "source": "IMAGE",
            "confidence": 0.88,
            "details": crater_det,
            "metadata": crater_det,
        })

    # -----------------------------------------------------------------------
    # 3. Shape, Tailing & Spreading Behaviour
    # -----------------------------------------------------------------------
    if circularity < MIN_CIRCULARITY_NORMAL:
        if aspect_ratio > MAX_ASPECT_RATIO_NORMAL:
            # Elongated tear-drop / line shape indicates tailing / stringing
            tailing_det = {"circularity": round(circularity, 3), "aspect_ratio": round(aspect_ratio, 2)}
            observations.append({
                "observation_type": "deposit_shape",
                "value": "tailing",
                "source": "IMAGE",
                "confidence": 0.88,
                "details": tailing_det,
                "metadata": tailing_det,
            })
        elif area > TARGET_AREA_MAX:
            # Large flat spread
            spread_det = {"circularity": round(circularity, 3), "area_px": round(area, 1)}
            observations.append({
                "observation_type": "spreading_behaviour",
                "value": "excessive_spread",
                "source": "IMAGE",
                "confidence": 0.90,
                "details": spread_det,
                "metadata": spread_det,
            })
        else:
            abnormal_det = {"circularity": round(circularity, 3)}
            observations.append({
                "observation_type": "deposit_shape",
                "value": "abnormal",
                "source": "IMAGE",
                "confidence": 0.82,
                "details": abnormal_det,
                "metadata": abnormal_det,
            })

    # -----------------------------------------------------------------------
    # 4. Satellite Droplets Detection
    # -----------------------------------------------------------------------
    # If other distinct contours exist outside the main deposit with medium size
    satellite_count = 0
    for idx, c in enumerate(contours):
        if idx == largest_idx:
            continue
        c_area = cv2.contourArea(c)
        if 25.0 <= c_area <= (area * 0.25):
            satellite_count += 1

    if satellite_count >= 1:
        sat_det = {"satellite_droplet_count": satellite_count}
        observations.append({
            "observation_type": "deposit_shape",
            "value": "satellite_dots",
            "source": "IMAGE",
            "confidence": 0.85,
            "details": sat_det,
            "metadata": sat_det,
        })

    return observations


def analyze_deposit(image_bytes: bytes) -> dict[str, Any]:
    """Compatibility wrapper preserving the original measurement interface."""
    observations = analyze_image_observations(image_bytes)
    for obs in observations:
        if obs["observation_type"] == "deposit_size":
            return {
                "observation_type": obs["observation_type"],
                "value": obs["value"],
                "area": obs.get("details", {}).get("area_px", 0.0),
                "confidence": obs.get("confidence", 0.85),
                "source": "IMAGE",
                "all_observations": observations,
            }
    return {
        "observation_type": "deposit_size",
        "value": "normal",
        "area": 0.0,
        "confidence": 0.85,
        "source": "IMAGE",
        "all_observations": observations,
    }


def to_domain_observations(raw_observations: list[dict[str, Any]]) -> list[Observation]:
    """Convert raw image analysis output dicts into strongly-typed domain Observations."""
    domain_obs: list[Observation] = []
    for item in raw_observations:
        raw_type = item.get("observation_type", "")
        raw_val = item.get("value", "")

        matched_type = None
        for ot in ObservationType:
            if ot.value == raw_type or ot.name.lower() == raw_type.lower():
                matched_type = ot
                break

        if not matched_type:
            matched_type = ObservationType.OTHER

        metadata = item.get("metadata") or item.get("details") or {}
        domain_obs.append(
            Observation(
                observation_type=matched_type,
                value=str(raw_val).lower(),
                source=EvidenceSource.IMAGE,
                confidence=float(item.get("confidence", 0.85)),
                original_text=f"Camera image inspection: {raw_type}={raw_val}",
                statement_type=StatementType.AI_INFERENCE,
                metadata=metadata,
            )
        )
    return domain_obs
