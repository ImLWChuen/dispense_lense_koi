"""
DispenseIQ — Image-Driven Durable Case Workflow Integration Tests

Verifies end-to-end against disposable PostgreSQL:
1. Running image analysis producing calibrated observations with metadata.
2. Creating a durable case with image observations and persisting to PostgreSQL.
3. Loading the durable case via GET /cases/{id} and verifying lossless observation
   metadata and provenance round-trip.
4. Submitting a follow-up check result to produce Revision 2, verifying the image
   observation metadata remains immutable and preserved across revisions.
5. Verifying case report output reflects image evidence with provenance.
6. Verifying legacy observations without metadata safely deserialize as empty dict {}.
"""

from __future__ import annotations

import json
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import get_session_factory
from app.models.case import CaseModel
from app.schemas.image import (
    AnalysisProfile,
    ImageAnalysisMode,
    NormalizedROI,
    ProcessLimits,
)
from app.api.images import _sync_analyze_image
from tests.fixtures.synthetic_images import create_centered_dot_image


@pytest.fixture
def client(test_database_url: str) -> TestClient:
    return TestClient(app)


@pytest.fixture
def db_session(test_database_url: str):
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def cleanup_cases(db_session: Session):
    case_ids: list[str] = []
    yield case_ids
    if case_ids:
        for cid in case_ids:
            db_session.execute(delete(CaseModel).where(CaseModel.case_id == cid))
        db_session.commit()


def test_image_driven_case_end_to_end_lifecycle(client: TestClient, cleanup_cases: list[str]):
    """Full lifecycle: image analysis -> create case -> get case -> submit check -> verify report."""
    # 1. Analyze image to generate calibrated observation
    img_bytes = create_centered_dot_image(size=200, dot_radius=10)
    profile = AnalysisProfile(
        mode=ImageAnalysisMode.PROCESS_LIMITS,
        rois=[NormalizedROI(roi_id="r1", x=0.25, y=0.25, width=0.5, height=0.5)],
        process_limits=ProcessLimits(min_coverage_ratio=0.15),
    )
    analysis_res = _sync_analyze_image(file_bytes=img_bytes, profile=profile)
    assert len(analysis_res.observations) == 1
    image_obs = analysis_res.observations[0]
    obs_src = getattr(image_obs.source, "value", str(image_obs.source))
    obs_type = getattr(image_obs.observation_type, "value", str(image_obs.observation_type))
    stmt_type = getattr(image_obs.statement_type, "value", str(image_obs.statement_type))
    assert obs_src == "IMAGE"
    assert "coverage_ratio" in image_obs.metadata

    # 2. Create durable case with the image observation
    case_payload = {
        "description": "Dispense dot size issue identified on line 3",
        "defect_code": "D01_TOO_LITTLE",
        "observations": [
            {
                "observation_type": obs_type,
                "value": image_obs.value,
                "original_text": image_obs.original_text,
                "statement_type": stmt_type,
                "source": obs_src,
                "metadata": image_obs.metadata,
            }
        ],
    }

    create_resp = client.post("/api/v1/cases", json=case_payload)
    assert create_resp.status_code == 201
    case_data = create_resp.json()
    case_id = case_data["case_id"]
    cleanup_cases.append(case_id)

    # Verify initial response contains observation with metadata
    assert len(case_data["observations"]) == 1
    obs_resp = case_data["observations"][0]
    assert obs_resp["source"] == "IMAGE"
    assert obs_resp["statement_type"] == "AI_INFERENCE"
    assert "coverage_ratio" in obs_resp["metadata"]
    assert obs_resp["metadata"]["coverage_ratio"] == image_obs.metadata["coverage_ratio"]
    assert case_data["diagnosis"]["analysis_revision"]["revision_number"] == 1

    # 3. Retrieve case via GET /cases/{id} and verify database round-trip
    get_resp = client.get(f"/api/v1/cases/{case_id}")
    assert get_resp.status_code == 200
    retrieved_case = get_resp.json()
    assert len(retrieved_case["observations"]) == 1
    retrieved_obs = retrieved_case["observations"][0]
    assert retrieved_obs["source"] == "IMAGE"
    assert retrieved_obs["metadata"]["coverage_ratio"] == image_obs.metadata["coverage_ratio"]
    assert retrieved_obs["metadata"]["equivalent_diameter_px"] == image_obs.metadata["equivalent_diameter_px"]

    # 4. Submit check execution -> advances to Revision 2, preserves image metadata
    check_payload = {
        "check_id": "ACT01",
        "execution_status": "COMPLETED",
        "finding": "SUPPORTS",
        "outcome": "blockage_found",
        "finding_details": "Observed partial material blockage at tip",
        "expected_revision": 1,
    }
    check_resp = client.post(f"/api/v1/cases/{case_id}/check-results", json=check_payload)
    assert check_resp.status_code == 200
    rev2_data = check_resp.json()
    assert rev2_data["current_revision"] == 2

    # Verify image observation metadata remains intact in Revision 2
    get_resp_rev2 = client.get(f"/api/v1/cases/{case_id}")
    assert get_resp_rev2.status_code == 200
    case_rev2 = get_resp_rev2.json()
    # At least 2 observations now (image + check outcome)
    assert len(case_rev2["observations"]) >= 2
    img_obs_rev2 = next(o for o in case_rev2["observations"] if o["source"] == "IMAGE")
    assert img_obs_rev2["metadata"]["coverage_ratio"] == image_obs.metadata["coverage_ratio"]

    # 5. Verify case report output includes the image observation provenance
    report_resp = client.get(f"/api/v1/cases/{case_id}/report")
    assert report_resp.status_code == 200
    report_data = report_resp.json()
    assert report_data["case_id"] == case_id
    top_cause = report_data["current_diagnosis"]["ranked_causes"][0]
    all_ev = top_cause["supporting_evidence"] + top_cause["neutral_evidence"] + top_cause["contradicting_evidence"]
    assert any(e["source"] == "IMAGE" for e in all_ev)


def test_legacy_observation_metadata_compatibility(client: TestClient, cleanup_cases: list[str]):
    """Verify cases with legacy observations (no metadata field) return {} without crashing."""
    case_payload = {
        "description": "Legacy case without image metadata",
        "defect_code": "D01_TOO_LITTLE",
        "observations": [
            {
                "observation_type": "deposit_size",
                "value": "undersized",
                "source": "USER",
                "statement_type": "USER_OBSERVATION",
                # No metadata provided
            }
        ],
    }
    resp = client.post("/api/v1/cases", json=case_payload)
    assert resp.status_code == 201
    case_data = resp.json()
    case_id = case_data["case_id"]
    cleanup_cases.append(case_id)

    obs = case_data["observations"][0]
    assert obs["metadata"] == {}

    # GET /cases/{id} also returns {}
    get_resp = client.get(f"/api/v1/cases/{case_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["observations"][0]["metadata"] == {}
