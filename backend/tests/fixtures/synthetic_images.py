"""
Dispense Lens - Synthetic Image Fixtures for Vision Testing

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
    radius = round(size * normalized_radius)
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
    bg_color: int = 245,
    fmt: str = ".png",
) -> bytes:
    """Create a defensible missing-deposit image with established substrate/fiducial context but no deposit in target."""
    img = create_blank_image(size, size, bg_color)
    # Draw fiducial markings in the window margins outside the target ROI [0.25, 0.75].
    # This establishes background context (proving the camera is focused on an inspection substrate),
    # while the target ROI itself is empty bare substrate.
    fiducial_color = (60, 60, 60)
    p1 = int(size * 0.20)
    p2 = int(size * 0.80)
    r = max(3, int(size * 0.025))
    cv2.circle(img, (p1, p1), r, fiducial_color, -1)
    cv2.circle(img, (p2, p1), r, fiducial_color, -1)
    cv2.circle(img, (p1, p2), r, fiducial_color, -1)
    cv2.circle(img, (p2, p2), r, fiducial_color, -1)
    return encode_image(img, fmt)


def create_tailing_dot_image(
    size: int = 200,
    head_radius: int = 25,
    tail_length: int = 40,
    tail_width: int = 12,
    direction: str = "horizontal",
    bg_color: int = 255,
    dot_color: int = 30,
    fmt: str = ".png",
) -> bytes:
    """Create a deposit with an asymmetric tailing string / comet effect."""
    img = create_blank_image(size, size, bg_color)
    cx, cy = size // 2, size // 2
    color = (dot_color, dot_color, dot_color)

    # Main dot head
    cv2.circle(img, (cx, cy), head_radius, color, -1)

    # Tailing extension
    if direction == "horizontal":
        pts = np.array([
            [cx, cy - tail_width // 2],
            [cx + tail_length, cy],
            [cx, cy + tail_width // 2],
        ], dtype=np.int32)
    else:  # vertical
        pts = np.array([
            [cx - tail_width // 2, cy],
            [cx, cy + tail_length],
            [cx + tail_width // 2, cy],
        ], dtype=np.int32)

    cv2.fillPoly(img, [pts], color)
    return encode_image(img, fmt)


def create_abnormal_shape_image(
    size: int = 200,
    bg_color: int = 255,
    dot_color: int = 30,
    fmt: str = ".png",
) -> bytes:
    """Create an irregularly shaped deposit with low circularity and concavities."""
    img = create_blank_image(size, size, bg_color)
    cx, cy = size // 2, size // 2
    color = (dot_color, dot_color, dot_color)

    # Polygon with indented lobes (star/clover-like)
    points = []
    num_points = 12
    for i in range(num_points):
        angle = i * (2.0 * np.pi / num_points)
        r = 30 if i % 2 == 0 else 12  # Sharp concavity
        px = int(cx + r * np.cos(angle))
        py = int(cy + r * np.sin(angle))
        points.append([px, py])

    pts = np.array(points, dtype=np.int32)
    cv2.fillPoly(img, [pts], color)
    return encode_image(img, fmt)


def create_bubble_dot_image(
    size: int = 200,
    dot_radius: int = 35,
    bubble_count: int = 1,
    bubble_radius: int = 8,
    bg_color: int = 255,
    dot_color: int = 30,
    bubble_color: int = 240,
    fmt: str = ".png",
) -> bytes:
    """Create a deposit containing circular internal voids / air bubbles."""
    img = create_blank_image(size, size, bg_color)
    cx, cy = size // 2, size // 2
    dot_c = (dot_color, dot_color, dot_color)
    bubble_c = (bubble_color, bubble_color, bubble_color)

    # Draw solid adhesive deposit
    cv2.circle(img, (cx, cy), dot_radius, dot_c, -1)

    # Draw internal air bubbles inside the adhesive dot
    if bubble_count == 1:
        cv2.circle(img, (cx + 5, cy - 5), bubble_radius, bubble_c, -1)
    else:
        # Multiple bubbles arranged inside
        offsets = [(cx - 10, cy - 8), (cx + 12, cy + 8), (cx - 5, cy + 12)]
        for i in range(min(bubble_count, len(offsets))):
            bx, by = offsets[i]
            cv2.circle(img, (bx, by), bubble_radius, bubble_c, -1)

    return encode_image(img, fmt)

