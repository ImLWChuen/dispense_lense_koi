"""
DispenseIQ — Synthetic Image Fixtures for Vision Testing

Generates deterministic synthetic image buffers for testing resolution-independence,
ROI segmentation, calibrated defect classification, and failure handling.
"""

from __future__ import annotations

import cv2
import numpy as np


def encode_image(img: np.ndarray, fmt: str = ".png") -> bytes:
    """Encode OpenCV image numpy array to bytes."""
    success, buffer = cv2.imencode(fmt, img)
    if not success:
        raise ValueError(f"Failed to encode image to {fmt}")
    return buffer.tobytes()


def create_blank_image(
    width: int,
    height: int,
    bg_color: int = 255,
) -> np.ndarray:
    """Create a blank single-channel or grayscale-like image."""
    return np.full((height, width, 3), bg_color, dtype=np.uint8)


def create_centered_dot_image(
    size: int,
    dot_radius: int,
    bg_color: int = 255,
    dot_color: int = 30,
    fmt: str = ".png",
) -> bytes:
    """Create a square image with a centered dark circular deposit on light background."""
    img = create_blank_image(size, size, bg_color)
    center = (size // 2, size // 2)
    cv2.circle(img, center, dot_radius, (dot_color, dot_color, dot_color), -1)
    return encode_image(img, fmt)


def create_proportional_dot_image(
    size: int,
    normalized_radius: float,
    bg_color: int = 255,
    dot_color: int = 30,
    fmt: str = ".png",
) -> bytes:
    """Create an image where dot radius is proportional to image size (e.g. size * normalized_radius)."""
    radius = int(round(size * normalized_radius))
    return create_centered_dot_image(size, radius, bg_color, dot_color, fmt)


def create_overflow_image(
    size: int,
    center_roi_norm: tuple[float, float, float, float] = (0.25, 0.25, 0.5, 0.5),
    fmt: str = ".png",
) -> bytes:
    """Create an image where the deposit spills significantly outside the target ROI."""
    img = create_blank_image(size, size, 255)
    # Target ROI is in the middle (size*0.25 to size*0.75)
    # Place an elongated deposit or tail that extends past x=0.75
    center = (int(size * 0.5), int(size * 0.5))
    # Draw large ellipse that extends well beyond width*0.75
    cv2.ellipse(img, center, (int(size * 0.35), int(size * 0.15)), 0, 0, 360, (30, 30, 30), -1)
    return encode_image(img, fmt)


def create_multi_roi_image(
    width: int,
    height: int,
    deposits: list[tuple[int, int, int]],  # list of (cx, cy, radius)
    fmt: str = ".png",
) -> bytes:
    """Create an image containing multiple dots at specified coordinates."""
    img = create_blank_image(width, height, 255)
    for cx, cy, r in deposits:
        cv2.circle(img, (cx, cy), r, (30, 30, 30), -1)
    return encode_image(img, fmt)


def create_noisy_image(
    size: int,
    fmt: str = ".png",
) -> bytes:
    """Create an ambiguous / noisy image without clear deposit contrast."""
    # Low contrast random noise
    noise = np.random.randint(120, 140, (size, size, 3), dtype=np.uint8)
    return encode_image(noise, fmt)


def create_empty_image(
    size: int,
    fmt: str = ".png",
) -> bytes:
    """Create an image with no deposit (pure background)."""
    img = create_blank_image(size, size, 255)
    return encode_image(img, fmt)
