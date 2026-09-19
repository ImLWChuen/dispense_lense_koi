"""
DispenseIQ — Vision Preprocessing Service

Handles image payload verification, decode, dimensional validation,
and normalized-to-pixel coordinate projection.
"""

from __future__ import annotations

import cv2
import numpy as np

from app.schemas.image import ImageDimensions, NormalizedROI, PixelROI

MAX_IMAGE_DIMENSION = 4096
MAX_TOTAL_PIXELS = 16_000_000


def validate_image_dimensions(
    width: int,
    height: int,
    max_dim: int = MAX_IMAGE_DIMENSION,
    max_pixels: int = MAX_TOTAL_PIXELS,
) -> None:
    """Validate that decoded image dimensions do not exceed safe resource bounds."""
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid image dimensions: {width}x{height}.")

    if width > max_dim:
        raise ValueError(f"Image width ({width}px) exceeds maximum allowed ({max_dim}px).")
    if height > max_dim:
        raise ValueError(f"Image height ({height}px) exceeds maximum allowed ({max_dim}px).")

    total_pixels = width * height
    if total_pixels > max_pixels:
        raise ValueError(f"Total image pixels ({total_pixels}) exceeds maximum allowed ({max_pixels}).")


def decode_and_validate_image(image_bytes: bytes) -> tuple[np.ndarray, ImageDimensions]:
    """Verify magic bytes, decode image buffer into BGR numpy array, and enforce dimensional limits."""
    if not image_bytes:
        raise ValueError("Empty image buffer.")

    # Validate magic bytes for JPEG or PNG
    is_png = image_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    is_jpeg = image_bytes.startswith(b"\xff\xd8\xff")
    if not (is_png or is_jpeg):
        raise ValueError("Invalid image format: only PNG and JPEG images are supported.")

    np_arr = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if image is None:
        raise ValueError("Cannot decode image data; file may be corrupt or truncated.")

    height, width = image.shape[:2]
    channels = image.shape[2] if len(image.shape) > 2 else 1

    validate_image_dimensions(width, height)

    return image, ImageDimensions(width=width, height=height, channels=channels)


def normalize_roi_to_pixels(
    roi: NormalizedROI,
    img_width: int,
    img_height: int,
    window_expansion: float = 0.2,
) -> tuple[PixelROI, PixelROI]:
    """Convert a NormalizedROI to an exact target PixelROI and a bounded expanded analysis window."""
    # Exact target ROI in pixel coordinates
    tx = int(round(roi.x * img_width))
    ty = int(round(roi.y * img_height))
    tw = max(1, int(round(roi.width * img_width)))
    th = max(1, int(round(roi.height * img_height)))

    # Ensure target stays within image boundary
    tx = max(0, min(tx, img_width - 1))
    ty = max(0, min(ty, img_height - 1))
    tw = min(tw, img_width - tx)
    th = min(th, img_height - ty)

    target_roi = PixelROI(
        roi_id=roi.roi_id,
        x=tx,
        y=ty,
        width=tw,
        height=th,
    )

    # Expanded analysis window
    exp_x = int(round(tw * window_expansion))
    exp_y = int(round(th * window_expansion))

    wx = max(0, tx - exp_x)
    wy = max(0, ty - exp_y)
    wx2 = min(img_width, tx + tw + exp_x)
    wy2 = min(img_height, ty + th + exp_y)
    ww = max(1, wx2 - wx)
    wh = max(1, wy2 - wy)

    window_roi = PixelROI(
        roi_id=f"{roi.roi_id}_window",
        x=wx,
        y=wy,
        width=ww,
        height=wh,
    )

    return target_roi, window_roi
