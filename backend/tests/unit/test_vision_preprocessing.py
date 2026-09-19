"""
DispenseIQ — Vision Preprocessing Unit Tests

Verifies:
- Decoding and validation of JPEG/PNG image bytes (magic bytes and OpenCV decode).
- Rejection of invalid, corrupted, or unsupported formats.
- Enforcement of dimensional bounds (<= 4096 px width/height, <= 16,000,000 total pixels).
- Normalized ROI coordinate validation [0, 1] and bounds checks.
- Conversion of normalized ROI to target pixel masks and bounded analysis windows.
"""

from __future__ import annotations

import pytest
import numpy as np

from app.schemas.image import NormalizedROI
from app.services.vision.preprocessing import (
    decode_and_validate_image,
    normalize_roi_to_pixels,
    validate_image_dimensions,
)
from tests.fixtures.synthetic_images import (
    create_blank_image,
    create_centered_dot_image,
    encode_image,
)


def test_decode_valid_png() -> None:
    png_bytes = create_centered_dot_image(size=100, dot_radius=20, fmt=".png")
    img, dims = decode_and_validate_image(png_bytes)
    assert img is not None
    assert dims.width == 100
    assert dims.height == 100
    assert dims.channels == 3


def test_decode_valid_jpeg() -> None:
    jpg_bytes = create_centered_dot_image(size=120, dot_radius=25, fmt=".jpg")
    img, dims = decode_and_validate_image(jpg_bytes)
    assert img is not None
    assert dims.width == 120
    assert dims.height == 120


def test_reject_non_image_bytes() -> None:
    with pytest.raises(ValueError, match="Invalid image format|Cannot decode"):
        decode_and_validate_image(b"not an image file at all")


def test_reject_corrupted_image() -> None:
    # PNG header followed by garbage
    garbage = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\xff" * 50
    with pytest.raises(ValueError):
        decode_and_validate_image(garbage)


def test_dimension_bounds_enforcement() -> None:
    # Allowed: 4096 x 4096 is <= 16,000,000 pixels
    validate_image_dimensions(4096, 3900)

    # Exceeds max width/height > 4096
    with pytest.raises(ValueError, match="exceeds maximum allowed"):
        validate_image_dimensions(4097, 100)

    with pytest.raises(ValueError, match="exceeds maximum allowed"):
        validate_image_dimensions(100, 4097)

    # Exceeds total decoded pixels > 16,000,000 (e.g. 4096 x 4000 = 16,384,000)
    with pytest.raises(ValueError, match="exceeds maximum"):
        validate_image_dimensions(4096, 4000)


def test_normalized_roi_validation() -> None:
    # Valid ROI
    roi = NormalizedROI(roi_id="roi_1", x=0.2, y=0.2, width=0.5, height=0.5)
    assert roi.roi_id == "roi_1"

    # Out of bounds coordinates (x + width > 1.0)
    with pytest.raises(ValueError):
        NormalizedROI(roi_id="roi_bad", x=0.6, y=0.2, width=0.5, height=0.5)

    # Negative coordinates
    with pytest.raises(ValueError):
        NormalizedROI(roi_id="roi_neg", x=-0.1, y=0.2, width=0.5, height=0.5)

    # Zero or negative dimension
    with pytest.raises(ValueError):
        NormalizedROI(roi_id="roi_zero", x=0.2, y=0.2, width=0.0, height=0.5)


def test_roi_conversion_to_pixels() -> None:
    roi = NormalizedROI(roi_id="roi_1", x=0.25, y=0.25, width=0.5, height=0.5)
    # Image 200 x 200
    px_roi, win_roi = normalize_roi_to_pixels(roi, img_width=200, img_height=200, window_expansion=0.2)
    assert px_roi.x == 50
    assert px_roi.y == 50
    assert px_roi.width == 100
    assert px_roi.height == 100

    # Expanded window should be clamped inside image [0, 200]
    assert win_roi.x < px_roi.x
    assert win_roi.y < px_roi.y
    assert win_roi.x + win_roi.width > px_roi.x + px_roi.width
    assert win_roi.x >= 0
    assert win_roi.y >= 0
    assert win_roi.x + win_roi.width <= 200
    assert win_roi.y + win_roi.height <= 200
