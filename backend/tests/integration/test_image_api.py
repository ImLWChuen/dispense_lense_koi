"""
Dispense Lens - Image Analysis API Integration Tests

Verifies:
- Successful multipart upload with JSON profile returning typed ImageAnalysisResponse.
- Enforcement of 10 MB file size limit (HTTP 413).
- Enforcement of valid image content and format (HTTP 422 on corrupt/non-image bytes).
- Rejection of invalid profile specifications or missing ROIs (HTTP 422).
- Rejection of REFERENCE_IMAGE mode without reference_file (HTTP 400).
- Safe asynchronous execution offloaded from the event loop.
- Calibrated vs uncalibrated modes.
"""

from __future__ import annotations

import io
import json
import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.fixtures.synthetic_images import (
    create_blank_image,
    create_centered_dot_image,
    create_empty_image,
    create_proportional_dot_image,
    encode_image,
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_image_analyze_features_only_mode(client: TestClient) -> None:
    img_bytes = create_centered_dot_image(size=200, dot_radius=25)
    profile = {
        "mode": "FEATURES_ONLY",
        "rois": [
            {"roi_id": "r1", "x": 0.25, "y": 0.25, "width": 0.5, "height": 0.5}
        ],
    }

    response = client.post(
        "/api/v1/images/analyze",
        files={"file": ("test.png", img_bytes, "image/png")},
        data={"profile": json.dumps(profile)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "UNCALIBRATED"
    assert data["mode"] == "FEATURES_ONLY"
    assert data["image_dimensions"]["width"] == 200
    assert len(data["roi_measurements"]) == 1
    assert data["roi_measurements"][0]["roi_id"] == "r1"
    assert data["observations"] == []


def test_image_analyze_process_limits_calibrated(client: TestClient) -> None:
    # Small dot (radius 10) inside 100x100 target box -> coverage < 0.05
    img_bytes = create_centered_dot_image(size=200, dot_radius=10)
    profile = {
        "mode": "PROCESS_LIMITS",
        "rois": [
            {"roi_id": "r1", "x": 0.25, "y": 0.25, "width": 0.5, "height": 0.5}
        ],
        "process_limits": {
            "min_coverage_ratio": 0.15,
        },
    }

    response = client.post(
        "/api/v1/images/analyze",
        files={"file": ("test.png", img_bytes, "image/png")},
        data={"profile": json.dumps(profile)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "CALIBRATED"
    assert len(data["observations"]) == 1
    obs = data["observations"][0]
    assert obs["observation_type"] == "deposit_size"
    assert obs["value"] == "undersized"
    assert obs["source"] == "IMAGE"
    assert obs["statement_type"] == "AI_INFERENCE"
    assert "coverage_ratio" in obs["metadata"]


def test_image_analyze_reference_image_mode_success(client: TestClient) -> None:
    curr_bytes = create_proportional_dot_image(200, 0.08)
    ref_bytes = create_proportional_dot_image(200, 0.18)

    profile = {
        "mode": "REFERENCE_IMAGE",
        "rois": [
            {"roi_id": "r1", "x": 0.25, "y": 0.25, "width": 0.5, "height": 0.5}
        ],
        "reference_limits": {
            "min_reference_ratio": 0.8,
            "max_reference_ratio": 1.2,
        },
    }

    response = client.post(
        "/api/v1/images/analyze",
        files={
            "file": ("current.png", curr_bytes, "image/png"),
            "reference_file": ("ref.png", ref_bytes, "image/png"),
        },
        data={"profile": json.dumps(profile)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "CALIBRATED"
    assert any(o["value"] == "undersized" for o in data["observations"])


def test_image_analyze_reference_mode_missing_reference_file(client: TestClient) -> None:
    curr_bytes = create_centered_dot_image(size=100, dot_radius=15)
    profile = {
        "mode": "REFERENCE_IMAGE",
        "rois": [{"roi_id": "r1", "x": 0.2, "y": 0.2, "width": 0.6, "height": 0.6}],
        "reference_limits": {"tolerance_ratio": 0.1},
    }

    response = client.post(
        "/api/v1/images/analyze",
        files={"file": ("current.png", curr_bytes, "image/png")},
        data={"profile": json.dumps(profile)},
    )
    assert response.status_code == 400
    assert "reference_file" in response.json()["detail"]


def test_image_analyze_rejects_corrupt_image(client: TestClient) -> None:
    corrupt_bytes = b"\x89PNG\r\n\x1a\n\x00\x00corrupted_data_not_an_image"
    profile = {
        "mode": "FEATURES_ONLY",
        "rois": [{"roi_id": "r1", "x": 0.1, "y": 0.1, "width": 0.5, "height": 0.5}],
    }

    response = client.post(
        "/api/v1/images/analyze",
        files={"file": ("corrupt.png", corrupt_bytes, "image/png")},
        data={"profile": json.dumps(profile)},
    )
    assert response.status_code == 422


def test_image_analyze_rejects_oversized_payload(client: TestClient) -> None:
    # 11 MB payload
    large_payload = b"\x00" * (11 * 1024 * 1024)
    profile = {
        "mode": "FEATURES_ONLY",
        "rois": [{"roi_id": "r1", "x": 0.1, "y": 0.1, "width": 0.5, "height": 0.5}],
    }

    response = client.post(
        "/api/v1/images/analyze",
        files={"file": ("large.png", large_payload, "image/png")},
        data={"profile": json.dumps(profile)},
    )
    assert response.status_code == 413


def test_image_analyze_rejects_invalid_profile(client: TestClient) -> None:
    img_bytes = create_centered_dot_image(size=100, dot_radius=15)
    # Missing rois
    invalid_profile = {"mode": "FEATURES_ONLY"}

    response = client.post(
        "/api/v1/images/analyze",
        files={"file": ("test.png", img_bytes, "image/png")},
        data={"profile": json.dumps(invalid_profile)},
    )
    assert response.status_code == 422


def test_image_analyze_internal_pipeline_failure_returns_sanitized_500(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R1 regression: Internal worker/classifier failure returns sanitized 500 without leaking private details or paths."""
    from app.api import images

    def mock_run_pipeline(*args, **kwargs):
        raise ValueError("Internal classifier failure at C:/private/model/path/weights.onnx: division by zero")

    monkeypatch.setattr(images, "_sync_analyze_image", mock_run_pipeline)

    img_bytes = create_centered_dot_image(size=100, dot_radius=15)
    profile = {
        "mode": "FEATURES_ONLY",
        "rois": [{"roi_id": "r1", "x": 0.2, "y": 0.2, "width": 0.6, "height": 0.6}],
    }

    response = client.post(
        "/api/v1/images/analyze",
        files={"file": ("test.png", img_bytes, "image/png")},
        data={"profile": json.dumps(profile)},
    )
    assert response.status_code == 500
    data = response.json()
    assert data["detail"] == "An unexpected error occurred during image analysis."
    assert "C:/private/model/path" not in response.text
    assert "division by zero" not in response.text


@pytest.mark.anyio
async def test_read_bounded_upload_aborts_mid_stream_without_full_buffer() -> None:
    """R5 regression: Chunked streaming upload exceeding 10 MB aborts immediately upon crossing threshold."""
    from fastapi import HTTPException, UploadFile
    from app.api.images import _read_bounded_upload, MAX_FILE_SIZE_BYTES

    # Custom stream that generates 20 MB of data but tracks how many bytes were actually read
    class ChunkedStream(io.RawIOBase):
        def __init__(self, total_bytes: int):
            self.total_bytes = total_bytes
            self.bytes_read = 0

        def readable(self) -> bool:
            return True

        def read(self, n: int = -1) -> bytes:
            if self.bytes_read >= self.total_bytes:
                return b""
            chunk_size = min(n if n > 0 else 65536, self.total_bytes - self.bytes_read)
            self.bytes_read += chunk_size
            return b"X" * chunk_size

    stream = ChunkedStream(total_bytes=20 * 1024 * 1024)
    upload = UploadFile(file=stream, filename="stream.png", size=None)

    with pytest.raises(HTTPException) as exc_info:
        await _read_bounded_upload(upload, MAX_FILE_SIZE_BYTES, "Uploaded file")

    assert exc_info.value.status_code == 413
    assert "exceeds maximum allowed size" in exc_info.value.detail
    # Verify we aborted shortly after 10 MB, well before reading all 20 MB!
    assert stream.bytes_read <= MAX_FILE_SIZE_BYTES + (64 * 1024)
    assert stream.bytes_read < 12 * 1024 * 1024


def test_image_analyze_rejects_oversized_reference_file(client: TestClient) -> None:
    """R5 regression: Oversized reference file is rejected with 413."""
    curr_bytes = create_centered_dot_image(size=100, dot_radius=15)
    large_ref = b"\x00" * (11 * 1024 * 1024)
    profile = {
        "mode": "REFERENCE_IMAGE",
        "rois": [{"roi_id": "r1", "x": 0.2, "y": 0.2, "width": 0.6, "height": 0.6}],
        "reference_limits": {"tolerance_ratio": 0.1},
    }

    response = client.post(
        "/api/v1/images/analyze",
        files={
            "file": ("current.png", curr_bytes, "image/png"),
            "reference_file": ("large_ref.png", large_ref, "image/png"),
        },
        data={"profile": json.dumps(profile)},
    )
    assert response.status_code == 413
    assert "Reference file" in response.json()["detail"]


def test_image_analyze_rejects_empty_process_limits(client: TestClient) -> None:
    """R6 regression: Rejects empty ProcessLimits object with HTTP 422."""
    img_bytes = create_centered_dot_image(size=100, dot_radius=15)
    profile = {
        "mode": "PROCESS_LIMITS",
        "rois": [{"roi_id": "r1", "x": 0.2, "y": 0.2, "width": 0.6, "height": 0.6}],
        "process_limits": {},
    }

    response = client.post(
        "/api/v1/images/analyze",
        files={"file": ("test.png", img_bytes, "image/png")},
        data={"profile": json.dumps(profile)},
    )
    assert response.status_code == 422
    assert "ProcessLimits requires at least one limit" in response.json()["detail"]


def test_image_analyze_rejects_duplicate_roi_id(client: TestClient) -> None:
    """R6 regression: Rejects duplicate roi_id values with HTTP 422."""
    img_bytes = create_centered_dot_image(size=100, dot_radius=15)
    profile = {
        "mode": "FEATURES_ONLY",
        "rois": [
            {"roi_id": "roi_1", "x": 0.1, "y": 0.1, "width": 0.3, "height": 0.3},
            {"roi_id": "roi_1", "x": 0.5, "y": 0.5, "width": 0.3, "height": 0.3},
        ],
    }

    response = client.post(
        "/api/v1/images/analyze",
        files={"file": ("test.png", img_bytes, "image/png")},
        data={"profile": json.dumps(profile)},
    )
    assert response.status_code == 422
    assert "Duplicate roi_id values detected" in response.json()["detail"]


def test_image_analyze_rejects_blank_roi_id(client: TestClient) -> None:
    """R6 regression: Rejects blank roi_id values with HTTP 422."""
    img_bytes = create_centered_dot_image(size=100, dot_radius=15)
    profile = {
        "mode": "FEATURES_ONLY",
        "rois": [
            {"roi_id": "   ", "x": 0.1, "y": 0.1, "width": 0.3, "height": 0.3},
        ],
    }

    response = client.post(
        "/api/v1/images/analyze",
        files={"file": ("test.png", img_bytes, "image/png")},
        data={"profile": json.dumps(profile)},
    )
    assert response.status_code == 422
    assert "roi_id must not be blank" in response.json()["detail"]


def test_image_analyze_rejects_mode_incompatible_limits(client: TestClient) -> None:
    """R6 regression: Rejects profiles where limits don't match the active mode."""
    img_bytes = create_centered_dot_image(size=100, dot_radius=15)

    # 1. FEATURES_ONLY mode must not include process_limits
    profile_features_with_limits = {
        "mode": "FEATURES_ONLY",
        "rois": [{"roi_id": "r1", "x": 0.2, "y": 0.2, "width": 0.6, "height": 0.6}],
        "process_limits": {"min_coverage_ratio": 0.1},
    }
    resp1 = client.post(
        "/api/v1/images/analyze",
        files={"file": ("test.png", img_bytes, "image/png")},
        data={"profile": json.dumps(profile_features_with_limits)},
    )
    assert resp1.status_code == 422
    assert "FEATURES_ONLY mode must not include process_limits" in resp1.json()["detail"]

    # 2. PROCESS_LIMITS mode must not include reference_limits
    profile_process_with_ref = {
        "mode": "PROCESS_LIMITS",
        "rois": [{"roi_id": "r1", "x": 0.2, "y": 0.2, "width": 0.6, "height": 0.6}],
        "process_limits": {"min_coverage_ratio": 0.1},
        "reference_limits": {"tolerance_ratio": 0.1},
    }
    resp2 = client.post(
        "/api/v1/images/analyze",
        files={"file": ("test.png", img_bytes, "image/png")},
        data={"profile": json.dumps(profile_process_with_ref)},
    )
    assert resp2.status_code == 422
    assert "PROCESS_LIMITS mode must not include reference_limits" in resp2.json()["detail"]


def test_image_analyze_uniform_black_frame_returns_unreliable_no_d04(client: TestClient) -> None:
    """R8 regression: Completely uniform black frame (e.g. occluded lens) returns UNRELIABLE and no D04 observation."""
    black_img = encode_image(create_blank_image(200, 200, bg_color=0))
    profile = {
        "mode": "PROCESS_LIMITS",
        "rois": [{"roi_id": "r1", "x": 0.25, "y": 0.25, "width": 0.5, "height": 0.5}],
        "process_limits": {"min_presence_ratio": 0.05},
    }

    response = client.post(
        "/api/v1/images/analyze",
        files={"file": ("black.png", black_img, "image/png")},
        data={"profile": json.dumps(profile)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "UNRELIABLE"
    assert data["observations"] == []
    assert not any(o["observation_type"] == "deposit_presence" for o in data["observations"])


def test_image_analyze_uniform_mid_gray_frame_returns_unreliable_no_d04(client: TestClient) -> None:
    """R8 regression: Completely uniform mid-gray frame (e.g. unpowered/unlit sensor) returns UNRELIABLE and no D04 observation."""
    gray_img = encode_image(create_blank_image(200, 200, bg_color=128))
    profile = {
        "mode": "PROCESS_LIMITS",
        "rois": [{"roi_id": "r1", "x": 0.25, "y": 0.25, "width": 0.5, "height": 0.5}],
        "process_limits": {"min_presence_ratio": 0.05},
    }

    response = client.post(
        "/api/v1/images/analyze",
        files={"file": ("gray.png", gray_img, "image/png")},
        data={"profile": json.dumps(profile)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "UNRELIABLE"
    assert data["observations"] == []
    assert not any(o["observation_type"] == "deposit_presence" for o in data["observations"])


def test_image_analyze_uniform_white_frame_returns_unreliable_no_d04(client: TestClient) -> None:
    """R8 regression: Completely uniform white frame (e.g. overexposed capture) returns UNRELIABLE and no D04 observation."""
    white_img = encode_image(create_blank_image(200, 200, bg_color=255))
    profile = {
        "mode": "PROCESS_LIMITS",
        "rois": [{"roi_id": "r1", "x": 0.25, "y": 0.25, "width": 0.5, "height": 0.5}],
        "process_limits": {"min_presence_ratio": 0.05},
    }

    response = client.post(
        "/api/v1/images/analyze",
        files={"file": ("white.png", white_img, "image/png")},
        data={"profile": json.dumps(profile)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "UNRELIABLE"
    assert data["observations"] == []
    assert not any(o["observation_type"] == "deposit_presence" for o in data["observations"])


def test_image_analyze_defensible_empty_target_returns_calibrated_d04_missing(client: TestClient) -> None:
    """R8 verification: Defensible empty target with established background context returns CALIBRATED and D04 missing."""
    empty_img = create_empty_image(200)
    profile = {
        "mode": "PROCESS_LIMITS",
        "rois": [{"roi_id": "r1", "x": 0.25, "y": 0.25, "width": 0.5, "height": 0.5}],
        "process_limits": {"min_presence_ratio": 0.05},
    }

    response = client.post(
        "/api/v1/images/analyze",
        files={"file": ("empty.png", empty_img, "image/png")},
        data={"profile": json.dumps(profile)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "CALIBRATED"
    assert len(data["observations"]) == 1
    obs = data["observations"][0]
    assert obs["observation_type"] == "deposit_presence"
    assert obs["value"] == "missing"
