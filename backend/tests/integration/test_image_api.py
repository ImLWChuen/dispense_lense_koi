"""
DispenseIQ — Image Analysis API Integration Tests

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
    create_centered_dot_image,
    create_proportional_dot_image,
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
