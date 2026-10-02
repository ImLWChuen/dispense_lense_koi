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
    assert data["roi_measurements"][0]["inspection_status"] == "MISSING"
    assert data["roi_measurements"][0]["is_missing"] is True
    assert data["aggregate_measurements"]["missing_roi_ids"] == ["r1"]
    assert data["aggregate_measurements"]["unassessed_roi_ids"] == []


def test_image_analyze_uniform_uninspectable_image_end_to_end(client: TestClient) -> None:
    """Verifies that an uninspectable uniform image returns UNASSESSED status, no missing IDs, and no observations."""
    gray_img = encode_image(create_blank_image(200, 200, bg_color=128))
    profile = {
        "mode": "PROCESS_LIMITS",
        "rois": [{"roi_id": "r1", "x": 0.25, "y": 0.25, "width": 0.5, "height": 0.5}],
        "process_limits": {"min_presence_ratio": 0.05, "min_coverage_ratio": 0.10},
    }

    response = client.post(
        "/api/v1/images/analyze",
        files={"file": ("uninspectable.png", gray_img, "image/png")},
        data={"profile": json.dumps(profile)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "UNRELIABLE"
    assert data["observations"] == []
    # Must NOT be mislabeled as missing deposit
    assert data["aggregate_measurements"]["missing_roi_ids"] == []
    assert data["aggregate_measurements"]["unassessed_roi_ids"] == ["r1"]
    # Check region measurement
    m = data["roi_measurements"][0]
    assert m["roi_id"] == "r1"
    assert m["inspection_status"] == "UNASSESSED"
    assert m["is_missing"] is False
    assert len(m["inspection_warnings"]) > 0
    # Top-level warnings expose affected ROI ID and reason
    assert any("r1" in w and "unassessed" in w for w in data["warnings"])


def test_image_analyze_mixed_valid_and_unassessed_rois(client: TestClient) -> None:
    """A mixed image preserves valid ROI measurement, excludes unassessed from aggregates, and conservatively gates observations."""
    import cv2
    import numpy as np

    # 400x200 image: Left side has a dark circular deposit; right side is completely flat/uniform
    img = np.full((200, 400, 3), 255, dtype=np.uint8)
    cv2.circle(img, (100, 100), 25, (30, 30, 30), -1)
    mixed_img = encode_image(img)

    profile = {
        "mode": "PROCESS_LIMITS",
        "rois": [
            {"roi_id": "r_valid", "x": 0.125, "y": 0.25, "width": 0.25, "height": 0.5},
            {"roi_id": "r_unassessed", "x": 0.625, "y": 0.25, "width": 0.25, "height": 0.5},
        ],
        "process_limits": {"min_presence_ratio": 0.05, "min_coverage_ratio": 0.10},
    }

    response = client.post(
        "/api/v1/images/analyze",
        files={"file": ("mixed.png", mixed_img, "image/png")},
        data={"profile": json.dumps(profile)},
    )
    assert response.status_code == 200
    data = response.json()

    # 1. Conservative gating: any unassessed region yields UNRELIABLE and zero observations in calibrated mode
    assert data["status"] == "UNRELIABLE"
    assert data["observations"] == []
    assert any("r_unassessed" in w for w in data["warnings"])

    # 2. Region measurements preserve individual valid details
    meas_by_id = {m["roi_id"]: m for m in data["roi_measurements"]}
    assert "r_valid" in meas_by_id
    assert "r_unassessed" in meas_by_id

    m_valid = meas_by_id["r_valid"]
    assert m_valid["inspection_status"] == "DETECTED"
    assert m_valid["is_missing"] is False
    assert m_valid["coverage_ratio"] > 0.15
    assert m_valid["deposit_area_px"] > 0

    m_unassessed = meas_by_id["r_unassessed"]
    assert m_unassessed["inspection_status"] == "UNASSESSED"
    assert m_unassessed["is_missing"] is False
    assert len(m_unassessed["inspection_warnings"]) > 0

    # 3. Aggregate measurements exclude unassessed from coverage and size CV, and report PARTIAL coverage
    agg = data["aggregate_measurements"]
    assert agg["missing_roi_ids"] == []
    assert agg["unassessed_roi_ids"] == ["r_unassessed"]
    assert agg["mean_coverage"] == pytest.approx(m_valid["coverage_ratio"], rel=1e-3)
    assert agg["size_cv"] is None  # Only 1 valid deposit
    assert agg["expected_roi_count"] == 2
    assert agg["assessed_roi_count"] == 1
    assert agg["inspection_coverage_status"] == "PARTIAL"


def test_image_analyze_features_only_uniform_uninspectable_image_exposes_warnings(client: TestClient) -> None:
    """R1 regression: Real uniform FEATURES_ONLY image exposes top-level ROI ID and failure reason."""
    gray_img = encode_image(create_blank_image(200, 200, bg_color=128))
    profile = {
        "mode": "FEATURES_ONLY",
        "rois": [{"roi_id": "r1", "x": 0.25, "y": 0.25, "width": 0.5, "height": 0.5}],
    }

    response = client.post(
        "/api/v1/images/analyze",
        files={"file": ("uninspectable.png", gray_img, "image/png")},
        data={"profile": json.dumps(profile)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "UNCALIBRATED"
    assert data["observations"] == []
    assert data["aggregate_measurements"]["missing_roi_ids"] == []
    assert data["aggregate_measurements"]["unassessed_roi_ids"] == ["r1"]
    m = data["roi_measurements"][0]
    assert m["roi_id"] == "r1"
    assert m["inspection_status"] == "UNASSESSED"
    # Top-level warnings must contain the ROI ID and the actual failure reason
    assert any("r1" in w and "unassessed" in w and "Target and surroundings are both uniform" in w for w in data["warnings"])


def test_image_analyze_detected_deposit_returns_bounded_outline_normalized(client: TestClient) -> None:
    """Real synthetic off-center deposit emits valid bounded outer outline in normalized coords."""
    import cv2
    import numpy as np

    # 400x200 image with an off-center circular deposit at (300, 100), radius 25
    img = np.full((200, 400, 3), 255, dtype=np.uint8)
    cv2.circle(img, (300, 100), 25, (30, 30, 30), -1)
    img_bytes = encode_image(img)

    profile = {
        "mode": "PROCESS_LIMITS",
        "rois": [{"roi_id": "r_offcenter", "x": 0.625, "y": 0.25, "width": 0.25, "height": 0.5}],
        "process_limits": {"min_coverage_ratio": 0.10},
    }

    response = client.post(
        "/api/v1/images/analyze",
        files={"file": ("offcenter.png", img_bytes, "image/png")},
        data={"profile": json.dumps(profile)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "CALIBRATED"

    m = data["roi_measurements"][0]
    assert m["roi_id"] == "r_offcenter"
    assert m["inspection_status"] == "DETECTED"
    assert m["is_missing"] is False

    outline = m["deposit_outline_normalized"]
    assert outline is not None
    assert 3 <= len(outline) <= 128

    # All points are in [0, 1]
    for pt in outline:
        assert 0.0 <= pt["x"] <= 1.0
        assert 0.0 <= pt["y"] <= 1.0

    # Centroid of the outline should closely match the normalized center of the deposit (300/400=0.75, 100/200=0.5)
    mean_x = sum(p["x"] for p in outline) / len(outline)
    mean_y = sum(p["y"] for p in outline) / len(outline)
    assert mean_x == pytest.approx(0.75, abs=0.03)
    assert mean_y == pytest.approx(0.50, abs=0.03)


def test_image_analyze_missing_and_unassessed_regions_emit_null_outlines(client: TestClient) -> None:
    """MISSING and UNASSESSED regions strictly emit null deposit outlines."""
    # 1. Defensible empty target (MISSING)
    empty_img = create_empty_image(200)
    profile_missing = {
        "mode": "PROCESS_LIMITS",
        "rois": [{"roi_id": "r_empty", "x": 0.25, "y": 0.25, "width": 0.5, "height": 0.5}],
        "process_limits": {"min_presence_ratio": 0.05},
    }
    resp1 = client.post(
        "/api/v1/images/analyze",
        files={"file": ("empty.png", empty_img, "image/png")},
        data={"profile": json.dumps(profile_missing)},
    )
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["roi_measurements"][0]["inspection_status"] == "MISSING"
    assert data1["roi_measurements"][0]["deposit_outline_normalized"] is None

    # 2. Flat uniform uninspectable target (UNASSESSED)
    gray_img = encode_image(create_blank_image(200, 200, bg_color=128))
    profile_unassessed = {
        "mode": "FEATURES_ONLY",
        "rois": [{"roi_id": "r_gray", "x": 0.25, "y": 0.25, "width": 0.5, "height": 0.5}],
    }
    resp2 = client.post(
        "/api/v1/images/analyze",
        files={"file": ("gray.png", gray_img, "image/png")},
        data={"profile": json.dumps(profile_unassessed)},
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["roi_measurements"][0]["inspection_status"] == "UNASSESSED"
    assert data2["roi_measurements"][0]["deposit_outline_normalized"] is None


def test_image_analyze_detected_region_with_unavailable_outline_exposes_warning_without_downgrade(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DETECTED region with unavailable outline remains DETECTED and CALIBRATED with top-level warning."""
    import app.api.images as images_mod

    # Monkeypatch extract_deposit_outline to simulate an outline failure on a DETECTED region
    def mock_extract(*args, **kwargs):
        return None, "ROI 'r1' deposit outline unavailable (simulated test omission)."

    monkeypatch.setattr(images_mod, "extract_deposit_outline", mock_extract)

    img_bytes = create_centered_dot_image(size=200, dot_radius=25)
    profile = {
        "mode": "PROCESS_LIMITS",
        "rois": [{"roi_id": "r1", "x": 0.25, "y": 0.25, "width": 0.5, "height": 0.5}],
        "process_limits": {"min_coverage_ratio": 0.10},
    }

    response = client.post(
        "/api/v1/images/analyze",
        files={"file": ("dot.png", img_bytes, "image/png")},
        data={"profile": json.dumps(profile)},
    )
    assert response.status_code == 200
    data = response.json()
    # Gating and status remain CALIBRATED; not downgraded to UNRELIABLE
    assert data["status"] == "CALIBRATED"
    m = data["roi_measurements"][0]
    assert m["roi_id"] == "r1"
    assert m["inspection_status"] == "DETECTED"
    assert m["deposit_outline_normalized"] is None
    # Specific warning reaches top-level warnings
    assert any("deposit outline unavailable (simulated test omission)" in w for w in data["warnings"])


def test_image_analyze_detected_region_with_nonconsecutive_duplicate_vertices_warning(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R1 regression: Nonconsecutive duplicate vertices rejection keeps region DETECTED and CALIBRATED."""
    import app.api.images as images_mod

    def mock_extract(*args, **kwargs):
        roi_id = kwargs.get("roi_id") or (args[5] if len(args) > 5 else "r_dup")
        return None, f"ROI '{roi_id}' deposit outline unavailable (nonconsecutive duplicate vertices detected)."

    monkeypatch.setattr(images_mod, "extract_deposit_outline", mock_extract)

    img_bytes = create_centered_dot_image(size=200, dot_radius=25)
    profile = {
        "mode": "PROCESS_LIMITS",
        "rois": [{"roi_id": "r_dup", "x": 0.25, "y": 0.25, "width": 0.5, "height": 0.5}],
        "process_limits": {"min_coverage_ratio": 0.10},
    }

    response = client.post(
        "/api/v1/images/analyze",
        files={"file": ("dot.png", img_bytes, "image/png")},
        data={"profile": json.dumps(profile)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "CALIBRATED"
    m = data["roi_measurements"][0]
    assert m["roi_id"] == "r_dup"
    assert m["inspection_status"] == "DETECTED"
    assert m["deposit_outline_normalized"] is None
    assert any("nonconsecutive duplicate vertices detected" in w for w in m["inspection_warnings"])
    assert any("nonconsecutive duplicate vertices detected" in w for w in data["warnings"])


def test_image_analyze_multi_site_same_defect_preserves_all_affected_roi_ids(client: TestClient) -> None:
    """Real synthetic multi-site image with same defect on 2 ROIs emits 1 observation with both affected IDs."""
    from tests.fixtures.synthetic_images import create_multi_roi_image

    # 400x200 image with two small dots (radius 10) at (100, 100) and (300, 100)
    img_bytes = create_multi_roi_image(
        width=400,
        height=200,
        deposits=[(100, 100, 10), (300, 100, 10)],
    )

    profile = {
        "mode": "PROCESS_LIMITS",
        "rois": [
            {"roi_id": "site_left", "x": 0.0, "y": 0.0, "width": 0.5, "height": 1.0},
            {"roi_id": "site_right", "x": 0.5, "y": 0.0, "width": 0.5, "height": 1.0},
        ],
        "process_limits": {"min_coverage_ratio": 0.05},
    }

    response = client.post(
        "/api/v1/images/analyze",
        files={"file": ("multi_undersized.png", img_bytes, "image/png")},
        data={"profile": json.dumps(profile)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "CALIBRATED"

    # Must emit exactly 1 observation for deposit_size=undersized
    assert len(data["observations"]) == 1
    obs = data["observations"][0]
    assert obs["observation_type"] == "deposit_size"
    assert obs["value"] == "undersized"
    assert obs["metadata"]["affected_roi_ids"] == ["site_left", "site_right"]
    assert obs["metadata"]["roi_id"] == "site_left"


def test_image_analyze_multi_site_different_defects_isolates_affected_roi_ids(client: TestClient) -> None:
    """Real synthetic multi-site image with different defects on 2 ROIs isolates affected IDs per value."""
    from tests.fixtures.synthetic_images import create_multi_roi_image

    # 400x200 image: left dot small (radius 10), right dot large (radius 45)
    img_bytes = create_multi_roi_image(
        width=400,
        height=200,
        deposits=[(100, 100, 10), (300, 100, 45)],
    )

    profile = {
        "mode": "PROCESS_LIMITS",
        "rois": [
            {"roi_id": "site_small", "x": 0.0, "y": 0.0, "width": 0.5, "height": 1.0},
            {"roi_id": "site_large", "x": 0.5, "y": 0.0, "width": 0.5, "height": 1.0},
        ],
        "process_limits": {
            "min_coverage_ratio": 0.03,
            "max_coverage_ratio": 0.10,
        },
    }

    response = client.post(
        "/api/v1/images/analyze",
        files={"file": ("multi_different.png", img_bytes, "image/png")},
        data={"profile": json.dumps(profile)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "CALIBRATED"

    obs_by_val = {o["value"]: o for o in data["observations"]}
    assert "undersized" in obs_by_val
    assert "oversized" in obs_by_val
    assert obs_by_val["undersized"]["metadata"]["affected_roi_ids"] == ["site_small"]
    assert obs_by_val["oversized"]["metadata"]["affected_roi_ids"] == ["site_large"]


def test_image_analyze_inspection_coverage_complete_with_detected_and_missing(client: TestClient) -> None:
    """A multi-site image with detected and confirmed missing deposits yields COMPLETE inspection coverage."""
    import cv2
    import numpy as np

    # 400x200 image:
    # Left window [0.0..0.5]: target box [0.125, 0.25, 0.25, 0.5] has a dark circular deposit at (100, 100)
    # Right window [0.5..1.0]: target box [0.625, 0.25, 0.25, 0.5] is empty, with fiducials inside window margin
    img = np.full((200, 400, 3), 255, dtype=np.uint8)
    cv2.circle(img, (100, 100), 20, (30, 30, 30), -1)
    for pt in [(240, 40), (360, 40), (240, 160), (360, 160)]:
        cv2.circle(img, pt, 5, (60, 60, 60), -1)

    img_bytes = encode_image(img)
    profile = {
        "mode": "PROCESS_LIMITS",
        "rois": [
            {"roi_id": "r_detected", "x": 0.125, "y": 0.25, "width": 0.25, "height": 0.5},
            {"roi_id": "r_missing", "x": 0.625, "y": 0.25, "width": 0.25, "height": 0.5},
        ],
        "process_limits": {
            "min_presence_ratio": 0.05,
            "min_coverage_ratio": 0.10,
        },
    }

    response = client.post(
        "/api/v1/images/analyze",
        files={"file": ("complete_mixed.png", img_bytes, "image/png")},
        data={"profile": json.dumps(profile)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "CALIBRATED"

    meas_by_id = {m["roi_id"]: m for m in data["roi_measurements"]}
    assert meas_by_id["r_detected"]["inspection_status"] == "DETECTED"
    assert meas_by_id["r_missing"]["inspection_status"] == "MISSING"

    agg = data["aggregate_measurements"]
    assert agg["expected_roi_count"] == 2
    assert agg["assessed_roi_count"] == 2
    assert agg["inspection_coverage_status"] == "COMPLETE"
    assert agg["missing_roi_ids"] == ["r_missing"]
    assert agg["unassessed_roi_ids"] == []


def test_image_analyze_inspection_coverage_complete_all_detected(client: TestClient) -> None:
    """A multi-site image with all sites reliably detected yields COMPLETE inspection coverage."""
    from tests.fixtures.synthetic_images import create_multi_roi_image

    img_bytes = create_multi_roi_image(
        width=400,
        height=200,
        deposits=[(100, 100, 20), (300, 100, 20)],
    )
    profile = {
        "mode": "PROCESS_LIMITS",
        "rois": [
            {"roi_id": "r1", "x": 0.0, "y": 0.0, "width": 0.5, "height": 1.0},
            {"roi_id": "r2", "x": 0.5, "y": 0.0, "width": 0.5, "height": 1.0},
        ],
        "process_limits": {
            "min_coverage_ratio": 0.01,
        },
    }

    response = client.post(
        "/api/v1/images/analyze",
        files={"file": ("complete.png", img_bytes, "image/png")},
        data={"profile": json.dumps(profile)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "CALIBRATED"

    meas_by_id = {m["roi_id"]: m for m in data["roi_measurements"]}
    assert meas_by_id["r1"]["inspection_status"] == "DETECTED"
    assert meas_by_id["r2"]["inspection_status"] == "DETECTED"

    agg = data["aggregate_measurements"]
    assert agg["expected_roi_count"] == 2
    assert agg["assessed_roi_count"] == 2
    assert agg["inspection_coverage_status"] == "COMPLETE"
    assert agg["missing_roi_ids"] == []
    assert agg["unassessed_roi_ids"] == []


def test_image_analyze_inspection_coverage_none_all_unassessed(client: TestClient) -> None:
    """An all-unassessed image reports NONE coverage status and 0 assessed count with UNRELIABLE status."""
    gray_img = encode_image(create_blank_image(200, 200, bg_color=128))
    profile = {
        "mode": "PROCESS_LIMITS",
        "rois": [
            {"roi_id": "r1", "x": 0.1, "y": 0.1, "width": 0.35, "height": 0.8},
            {"roi_id": "r2", "x": 0.55, "y": 0.1, "width": 0.35, "height": 0.8},
        ],
        "process_limits": {
            "min_coverage_ratio": 0.10,
        },
    }

    response = client.post(
        "/api/v1/images/analyze",
        files={"file": ("all_unassessed.png", gray_img, "image/png")},
        data={"profile": json.dumps(profile)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "UNRELIABLE"
    assert data["observations"] == []

    agg = data["aggregate_measurements"]
    assert agg["expected_roi_count"] == 2
    assert agg["assessed_roi_count"] == 0
    assert agg["inspection_coverage_status"] == "NONE"
    assert set(agg["unassessed_roi_ids"]) == {"r1", "r2"}
    assert agg["missing_roi_ids"] == []


def test_image_analyze_reference_mode_exposes_reference_aggregate(client: TestClient) -> None:
    """REFERENCE_IMAGE mode exposes separate reference_aggregate_measurements alongside current aggregate."""
    from tests.fixtures.synthetic_images import create_multi_roi_image

    curr_bytes = create_multi_roi_image(
        width=400,
        height=200,
        deposits=[(100, 100, 20), (300, 100, 20)],
    )
    ref_bytes = create_multi_roi_image(
        width=400,
        height=200,
        deposits=[(100, 100, 30), (300, 100, 30)],
    )

    profile = {
        "mode": "REFERENCE_IMAGE",
        "rois": [
            {"roi_id": "r1", "x": 0.0, "y": 0.0, "width": 0.5, "height": 1.0},
            {"roi_id": "r2", "x": 0.5, "y": 0.0, "width": 0.5, "height": 1.0},
        ],
        "reference_limits": {
            "min_reference_ratio": 0.3,
            "max_reference_ratio": 1.5,
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

    # Current aggregate describes current image
    agg = data["aggregate_measurements"]
    assert agg["expected_roi_count"] == 2
    assert agg["assessed_roi_count"] == 2
    assert agg["inspection_coverage_status"] == "COMPLETE"
    assert agg["missing_roi_ids"] == []
    assert agg["unassessed_roi_ids"] == []
    assert agg["mean_coverage"] is not None

    # Reference aggregate describes reference image
    ref_agg = data["reference_aggregate_measurements"]
    assert ref_agg is not None
    assert ref_agg["expected_roi_count"] == 2
    assert ref_agg["assessed_roi_count"] == 2
    assert ref_agg["inspection_coverage_status"] == "COMPLETE"
    assert ref_agg["missing_roi_ids"] == []
    assert ref_agg["unassessed_roi_ids"] == []
    assert ref_agg["mean_coverage"] is not None

    # Distinct values verify aggregates are not swapped or merged (reference deposits are larger)
    assert ref_agg["mean_coverage"] > agg["mean_coverage"]


def test_image_analyze_non_reference_modes_return_null_reference_aggregate(client: TestClient) -> None:
    """Non-reference modes explicitly serialize reference_aggregate_measurements as null."""
    curr_bytes = create_centered_dot_image(size=200, dot_radius=25)

    # FEATURES_ONLY mode
    fo_profile = {
        "mode": "FEATURES_ONLY",
        "rois": [{"roi_id": "r1", "x": 0.1, "y": 0.1, "width": 0.8, "height": 0.8}],
    }
    fo_resp = client.post(
        "/api/v1/images/analyze",
        files={"file": ("curr.png", curr_bytes, "image/png")},
        data={"profile": json.dumps(fo_profile)},
    )
    assert fo_resp.status_code == 200
    fo_data = fo_resp.json()
    assert "reference_aggregate_measurements" in fo_data
    assert fo_data["reference_aggregate_measurements"] is None
    assert fo_data["aggregate_measurements"] is not None

    # PROCESS_LIMITS mode
    pl_profile = {
        "mode": "PROCESS_LIMITS",
        "rois": [{"roi_id": "r1", "x": 0.1, "y": 0.1, "width": 0.8, "height": 0.8}],
        "process_limits": {"min_coverage_ratio": 0.05},
    }
    pl_resp = client.post(
        "/api/v1/images/analyze",
        files={"file": ("curr.png", curr_bytes, "image/png")},
        data={"profile": json.dumps(pl_profile)},
    )
    assert pl_resp.status_code == 200
    pl_data = pl_resp.json()
    assert "reference_aggregate_measurements" in pl_data
    assert pl_data["reference_aggregate_measurements"] is None
    assert pl_data["aggregate_measurements"] is not None


def test_image_analyze_reference_mode_unassessed_reference_image(client: TestClient) -> None:
    """Reliable current image paired with unassessed reference reports UNRELIABLE with reference coverage failure."""
    curr_bytes = create_centered_dot_image(size=200, dot_radius=25)
    ref_bytes = encode_image(create_blank_image(200, 200, bg_color=128))

    profile = {
        "mode": "REFERENCE_IMAGE",
        "rois": [{"roi_id": "r1", "x": 0.1, "y": 0.1, "width": 0.8, "height": 0.8}],
        "reference_limits": {"min_reference_ratio": 0.8, "max_reference_ratio": 1.2},
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
    assert data["status"] == "UNRELIABLE"
    assert data["observations"] == []
    assert any("Reference ROI 'r1' is unassessed" in w for w in data["warnings"])

    # Current aggregate is COMPLETE
    agg = data["aggregate_measurements"]
    assert agg["expected_roi_count"] == 1
    assert agg["assessed_roi_count"] == 1
    assert agg["inspection_coverage_status"] == "COMPLETE"
    assert agg["unassessed_roi_ids"] == []

    # Reference aggregate exposes unassessed failure
    ref_agg = data["reference_aggregate_measurements"]
    assert ref_agg is not None
    assert ref_agg["expected_roi_count"] == 1
    assert ref_agg["assessed_roi_count"] == 0
    assert ref_agg["inspection_coverage_status"] == "NONE"
    assert ref_agg["unassessed_roi_ids"] == ["r1"]
    assert ref_agg["missing_roi_ids"] == []


def test_image_analyze_reference_mode_confirmed_missing_reference_deposit(client: TestClient) -> None:
    """Confirmed missing reference deposit reports COMPLETE reference coverage but forces UNRELIABLE status."""
    import cv2
    import numpy as np

    # Current image: 400x200 with 2 detected deposits
    curr_img = np.full((200, 400, 3), 255, dtype=np.uint8)
    cv2.circle(curr_img, (100, 100), 20, (30, 30, 30), -1)
    cv2.circle(curr_img, (300, 100), 20, (30, 30, 30), -1)
    curr_bytes = encode_image(curr_img)

    # Reference image: 400x200 with detected deposit at r1, confirmed missing at r2 (surrounding fiducials)
    ref_img = np.full((200, 400, 3), 255, dtype=np.uint8)
    cv2.circle(ref_img, (100, 100), 20, (30, 30, 30), -1)
    for pt in [(240, 40), (360, 40), (240, 160), (360, 160)]:
        cv2.circle(ref_img, pt, 5, (60, 60, 60), -1)
    ref_bytes = encode_image(ref_img)

    profile = {
        "mode": "REFERENCE_IMAGE",
        "rois": [
            {"roi_id": "r1", "x": 0.125, "y": 0.25, "width": 0.25, "height": 0.5},
            {"roi_id": "r2", "x": 0.625, "y": 0.25, "width": 0.25, "height": 0.5},
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
    assert data["status"] == "UNRELIABLE"
    assert data["observations"] == []
    assert any("Reference ROI 'r2' is missing; downgrading analysis." in w for w in data["warnings"])

    # Current aggregate
    agg = data["aggregate_measurements"]
    assert agg["expected_roi_count"] == 2
    assert agg["assessed_roi_count"] == 2
    assert agg["inspection_coverage_status"] == "COMPLETE"
    assert agg["missing_roi_ids"] == []
    assert agg["unassessed_roi_ids"] == []

    # Reference aggregate: assessed_roi_count is 2 (both DETECTED and MISSING are assessed), status is COMPLETE
    ref_agg = data["reference_aggregate_measurements"]
    assert ref_agg is not None
    assert ref_agg["expected_roi_count"] == 2
    assert ref_agg["assessed_roi_count"] == 2
    assert ref_agg["inspection_coverage_status"] == "COMPLETE"
    assert ref_agg["missing_roi_ids"] == ["r2"]
    assert ref_agg["unassessed_roi_ids"] == []


def test_image_analysis_response_legacy_payload_deserialization() -> None:
    """Historical ImageAnalysisResponse JSON without reference_aggregate_measurements deserializes as None."""
    from app.schemas.image import ImageAnalysisResponse

    legacy_payload = {
        "status": "UNCALIBRATED",
        "mode": "FEATURES_ONLY",
        "image_dimensions": {"width": 200, "height": 200},
        "roi_measurements": [],
        "aggregate_measurements": {
            "mean_coverage": None,
            "size_cv": None,
            "missing_roi_ids": [],
            "unassessed_roi_ids": [],
            "expected_roi_count": 0,
            "assessed_roi_count": 0,
            "inspection_coverage_status": "NONE",
            "warnings": [],
        },
        "observations": [],
        "warnings": [],
    }

    resp = ImageAnalysisResponse.model_validate(legacy_payload)
    assert resp.reference_aggregate_measurements is None

    dumped = resp.model_dump(mode="json")
    assert "reference_aggregate_measurements" in dumped
    assert dumped["reference_aggregate_measurements"] is None


def test_image_analyze_preserves_per_region_evidence_in_api_response(client: TestClient) -> None:
    """API response preserves region_evidence_scope, applied_limits, and per-region snapshots."""
    img_bytes = create_centered_dot_image(size=200, dot_radius=10)
    profile = {
        "mode": "PROCESS_LIMITS",
        "rois": [
            {"roi_id": "site_1", "x": 0.25, "y": 0.25, "width": 0.5, "height": 0.5}
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
    meta = obs["metadata"]

    assert meta["region_evidence_scope"] == "individual_regions"
    assert meta["applied_limits"] == {"min_coverage_ratio": 0.15}
    assert meta["affected_roi_ids"] == ["site_1"]

    evidence = meta["region_evidence"]
    assert len(evidence) == 1
    assert evidence[0]["roi_id"] == "site_1"
    assert evidence[0]["current_measurements"]["inspection_status"] == "DETECTED"
    assert evidence[0]["current_measurements"]["coverage_ratio"] < 0.15
    assert evidence[0]["reference_measurements"] is None
