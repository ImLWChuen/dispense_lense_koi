"""
Dispense Lens - Integrated Region Inspection Acceptance Tests (DLK-M3-042)

End-to-end integration acceptance test suite exercising:
- Scenario A: Public multipart POST /api/v1/images/analyze with two distinct detected sites
  producing one deduplicated undersized observation. Preserves ordered affected IDs,
  distinct site snapshots, and applied limits. Creates a durable case, advances revision
  to Rev 2 via check submission, and verifies metadata survives losslessly through the later
  case, JSON report, and downloadable PDF report.
- Scenario B: Mixed detected/unassessed input. Verifies PARTIAL coverage with explicit counts,
  per-site statuses and warnings, top-level UNRELIABLE status, and zero emitted observations.
- Scenario C: Confirmed missing expected site with adequate synthetic fiducial context.
  Verifies MISSING differs from UNASSESSED, and emitted missing evidence is controlled
  by explicit limit parameters.
- Scenario D: Reference mode with current/reference coverage kept separate, including an
  unassessed reference that prevents score-bearing comparison while retaining conservative
  reference gating.
"""

from __future__ import annotations

import io
import json
import pytest
import pypdf
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import get_session_factory
from app.models.case import CaseModel
from tests.fixtures.synthetic_images import (
    create_blank_image,
    create_centered_dot_image,
    create_empty_image,
    create_multi_roi_image,
    encode_image,
)


@pytest.fixture
def client(test_database_url: str) -> TestClient:
    """FastAPI TestClient bound to the disposable test database."""
    return TestClient(app)


@pytest.fixture
def db_session(test_database_url: str):
    """Database session for test data cleanup against disposable test database."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def cleanup_cases(db_session: Session):
    """Tracks created case IDs and removes only those cases on teardown."""
    case_ids: list[str] = []
    yield case_ids
    if case_ids:
        for cid in case_ids:
            db_session.execute(delete(CaseModel).where(CaseModel.case_id == cid))
        db_session.commit()


def test_scenario_a_distinct_sites_deduplicated_observation_and_case_lifecycle(
    client: TestClient,
    cleanup_cases: list[str],
) -> None:
    """Scenario A: Two distinct detected sites produce one deduplicated undersized observation.

    Verifies:
    1. Public multipart POST /api/v1/images/analyze produces CALIBRATED status with
       exactly one observation having ordered affected_roi_ids, distinct per-site
       measurement snapshots, and applied limits.
    2. Durable case creation from the response persists the metadata into PostgreSQL.
    3. Case retrieval via GET /api/v1/cases/{id} round-trips the observation metadata losslessly.
    4. Submitting a follow-up check advances the case to Revision 2.
    5. Case retrieval at Revision 2 verifies observation metadata remains intact and immutable.
    6. Case JSON report at Revision 2 contains the image observation with unchanged metadata.
    7. PDF report download at Revision 2 succeeds, matches the revision, and contains both site IDs
       along with distinguishable measurements.
    """
    # 1. Multi-ROI image with two distinct deposits:
    # dot_1 at (100, 100) radius 10 (area ~314 px^2, coverage ~0.0157)
    # dot_2 at (300, 100) radius 15 (area ~706 px^2, coverage ~0.0353)
    img_bytes = create_multi_roi_image(
        width=400,
        height=200,
        deposits=[(100, 100, 10), (300, 100, 15)],
    )

    profile = {
        "mode": "PROCESS_LIMITS",
        "rois": [
            {"roi_id": "site_alpha", "x": 0.0, "y": 0.0, "width": 0.5, "height": 1.0},
            {"roi_id": "site_beta", "x": 0.5, "y": 0.0, "width": 0.5, "height": 1.0},
        ],
        "process_limits": {
            "min_coverage_ratio": 0.10,
        },
    }

    analyze_resp = client.post(
        "/api/v1/images/analyze",
        files={"file": ("acceptance_sample.png", img_bytes, "image/png")},
        data={"profile": json.dumps(profile)},
    )
    assert analyze_resp.status_code == 200
    analysis = analyze_resp.json()

    assert analysis["status"] == "CALIBRATED"
    assert len(analysis["observations"]) == 1
    obs = analysis["observations"][0]

    assert obs["source"] == "IMAGE"
    assert obs["observation_type"] == "deposit_size"
    assert obs["value"] == "undersized"

    meta = obs["metadata"]
    assert meta["region_evidence_scope"] == "individual_regions"
    assert meta["affected_roi_ids"] == ["site_alpha", "site_beta"]
    assert meta["applied_limits"] == {"min_coverage_ratio": 0.10}

    region_ev = meta["region_evidence"]
    assert len(region_ev) == 2
    assert region_ev[0]["roi_id"] == "site_alpha"
    assert region_ev[1]["roi_id"] == "site_beta"

    alpha_m = region_ev[0]["current_measurements"]
    beta_m = region_ev[1]["current_measurements"]
    assert alpha_m["inspection_status"] == "DETECTED"
    assert beta_m["inspection_status"] == "DETECTED"

    # Distinguishable measurements between the two sites
    assert alpha_m["coverage_ratio"] != beta_m["coverage_ratio"]
    assert alpha_m["deposit_area_px"] != beta_m["deposit_area_px"]
    alpha_cov = alpha_m["coverage_ratio"]
    beta_cov = beta_m["coverage_ratio"]

    # 2. Create durable case from the analysis observation
    case_payload = {
        "description": "[SYNTHETIC DEMO] Acceptance scenario A multi-site undersized dispense",
        "defect_code": "D01_TOO_LITTLE",
        "observations": [
            {
                "observation_type": obs["observation_type"],
                "value": obs["value"],
                "original_text": obs.get("original_text", "Undersized deposit detected"),
                "statement_type": obs.get("statement_type", "AI_INFERENCE"),
                "source": obs["source"],
                "confidence": obs.get("confidence", 0.9),
                "metadata": meta,
            }
        ],
    }

    create_resp = client.post("/api/v1/cases", json=case_payload)
    assert create_resp.status_code == 201
    case_data = create_resp.json()
    case_id = case_data["case_id"]
    cleanup_cases.append(case_id)

    assert case_data["diagnosis"]["analysis_revision"]["revision_number"] == 1
    assert len(case_data["observations"]) == 1
    created_obs = case_data["observations"][0]
    assert created_obs["metadata"]["affected_roi_ids"] == ["site_alpha", "site_beta"]
    assert created_obs["metadata"]["applied_limits"] == {"min_coverage_ratio": 0.10}

    # 3. Retrieve case via GET /api/v1/cases/{id} and verify database round-trip
    get_resp_1 = client.get(f"/api/v1/cases/{case_id}")
    assert get_resp_1.status_code == 200
    retrieved_case_1 = get_resp_1.json()
    ret_obs_1 = retrieved_case_1["observations"][0]
    assert ret_obs_1["metadata"]["affected_roi_ids"] == ["site_alpha", "site_beta"]
    assert len(ret_obs_1["metadata"]["region_evidence"]) == 2
    assert ret_obs_1["metadata"]["region_evidence"][0]["roi_id"] == "site_alpha"
    assert ret_obs_1["metadata"]["region_evidence"][1]["roi_id"] == "site_beta"

    # 4. Submit follow-up check to advance case to Revision 2
    check_payload = {
        "check_id": "ACT01",
        "execution_status": "COMPLETED",
        "finding": "SUPPORTS",
        "outcome": "blockage_found",
        "finding_details": "[SYNTHETIC DEMO] Verified partial nozzle restriction during acceptance rehearsal",
        "expected_revision": 1,
    }
    check_resp = client.post(f"/api/v1/cases/{case_id}/check-results", json=check_payload)
    assert check_resp.status_code == 200
    rev2_info = check_resp.json()
    assert rev2_info["current_revision"] == 2

    # 5. Retrieve case at Revision 2 and verify image observation metadata remains identical
    get_resp_2 = client.get(f"/api/v1/cases/{case_id}")
    assert get_resp_2.status_code == 200
    retrieved_case_2 = get_resp_2.json()
    assert retrieved_case_2["diagnosis"]["analysis_revision"]["revision_number"] == 2
    assert len(retrieved_case_2["analysis_revisions"]) == 2

    img_obs_rev2 = next(o for o in retrieved_case_2["observations"] if o["source"] == "IMAGE")
    assert img_obs_rev2["metadata"]["affected_roi_ids"] == ["site_alpha", "site_beta"]
    assert img_obs_rev2["metadata"]["applied_limits"] == {"min_coverage_ratio": 0.10}
    assert len(img_obs_rev2["metadata"]["region_evidence"]) == 2
    assert img_obs_rev2["metadata"]["region_evidence"][0]["current_measurements"]["coverage_ratio"] == alpha_cov
    assert img_obs_rev2["metadata"]["region_evidence"][1]["current_measurements"]["coverage_ratio"] == beta_cov

    # 6. Retrieve JSON report at Revision 2 and verify image observations
    report_resp = client.get(f"/api/v1/cases/{case_id}/report")
    assert report_resp.status_code == 200
    report_data = report_resp.json()
    assert report_data["current_revision"] == 2
    assert len(report_data["image_observations"]) == 1

    report_obs = report_data["image_observations"][0]
    assert report_obs["source"] == "IMAGE"
    assert report_obs["metadata"]["affected_roi_ids"] == ["site_alpha", "site_beta"]
    assert len(report_obs["metadata"]["region_evidence"]) == 2
    assert report_obs["metadata"]["region_evidence"][0]["roi_id"] == "site_alpha"
    assert report_obs["metadata"]["region_evidence"][1]["roi_id"] == "site_beta"

    # 7. Download PDF report at Revision 2 and parse with pypdf
    pdf_resp = client.get(f"/api/v1/cases/{case_id}/report.pdf")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["Content-Type"] == "application/pdf"
    assert f'filename="dispenselens-case-{case_id}-r2.pdf"' in pdf_resp.headers.get("Content-Disposition", "")

    reader = pypdf.PdfReader(io.BytesIO(pdf_resp.content))
    assert len(reader.pages) >= 1
    pdf_text = "\n".join(page.extract_text() or "" for page in reader.pages)

    # Verify structural section heading, site identifiers, and applied limits
    assert "8. Image Inspection Evidence" in pdf_text
    assert "site_alpha" in pdf_text
    assert "site_beta" in pdf_text
    assert "DETECTED" in pdf_text
    assert "min_coverage_ratio" in pdf_text
    assert "Report Revision: 2" in pdf_text or "Revision 2" in pdf_text
    assert "First-Seen Rev: 1" in pdf_text

    # Verify distinguishable measurements appear in the rendered PDF
    assert "Coverage:" in pdf_text
    assert f"{alpha_cov:.4f}"[:5] in pdf_text
    assert f"{beta_cov:.4f}"[:5] in pdf_text


def test_scenario_b_mixed_detected_and_unassessed_input(client: TestClient) -> None:
    """Scenario B: Mixed detected and unassessed input.

    Verifies:
    1. Input with one inspectable deposit and one flat uniform uninspectable region
       yields PARTIAL inspection coverage with exact counts:
       expected_roi_count=2, assessed_roi_count=1, unassessed_roi_ids=['site_unassessed'].
    2. Per-site statuses and warnings are preserved:
       site_detected is DETECTED; site_unassessed is UNASSESSED with explanatory warning.
    3. Top-level status is UNRELIABLE due to the unassessed region.
    4. Exactly zero diagnostic observations are emitted (conservative gate).
    """
    # 400x200 image: left half contains dot at (100, 100), right half is completely uniform white
    img_bytes = create_multi_roi_image(
        width=400,
        height=200,
        deposits=[(100, 100, 20)],
    )

    profile = {
        "mode": "PROCESS_LIMITS",
        "rois": [
            {"roi_id": "site_detected", "x": 0.0, "y": 0.0, "width": 0.5, "height": 1.0},
            {"roi_id": "site_unassessed", "x": 0.5, "y": 0.0, "width": 0.5, "height": 1.0},
        ],
        "process_limits": {
            "min_coverage_ratio": 0.10,
        },
    }

    response = client.post(
        "/api/v1/images/analyze",
        files={"file": ("mixed_sample.png", img_bytes, "image/png")},
        data={"profile": json.dumps(profile)},
    )
    assert response.status_code == 200
    data = response.json()

    # Top-level status must be UNRELIABLE
    assert data["status"] == "UNRELIABLE"

    # Conservative gate: zero observations emitted
    assert data["observations"] == []

    # Coverage aggregate must be PARTIAL with explicit counts
    agg = data["aggregate_measurements"]
    assert agg["inspection_coverage_status"] == "PARTIAL"
    assert agg["expected_roi_count"] == 2
    assert agg["assessed_roi_count"] == 1
    assert agg["unassessed_roi_ids"] == ["site_unassessed"]
    assert agg["missing_roi_ids"] == []

    # Per-site measurements and warnings
    rois = {m["roi_id"]: m for m in data["roi_measurements"]}
    assert rois["site_detected"]["inspection_status"] == "DETECTED"
    assert rois["site_unassessed"]["inspection_status"] == "UNASSESSED"
    assert len(rois["site_unassessed"]["inspection_warnings"]) > 0

    # Top-level warnings must cite the unassessed ROI
    assert any("site_unassessed" in w for w in data["warnings"])


def test_scenario_c_confirmed_missing_site_with_fiducial_context(client: TestClient) -> None:
    """Scenario C: Confirmed missing expected site with adequate synthetic fiducial context.

    Verifies:
    1. An empty target with surrounding fiducial markings yields MISSING (not UNASSESSED).
    2. Missing site is considered ASSESSED, yielding COMPLETE coverage (assessed_roi_count=1).
    3. Emitted missing evidence is strictly controlled by explicit limit parameters:
       - Supplying min_presence_ratio emits deposit_presence = missing.
       - Supplying only max_size_cv emits zero missing observations.
    """
    empty_img = create_empty_image(200)

    # 1. With explicit min_presence_ratio: emits deposit_presence = missing
    profile_with_presence = {
        "mode": "PROCESS_LIMITS",
        "rois": [
            {"roi_id": "roi_empty_target", "x": 0.25, "y": 0.25, "width": 0.5, "height": 0.5},
        ],
        "process_limits": {
            "min_presence_ratio": 0.05,
        },
    }

    resp1 = client.post(
        "/api/v1/images/analyze",
        files={"file": ("empty_fiducial.png", empty_img, "image/png")},
        data={"profile": json.dumps(profile_with_presence)},
    )
    assert resp1.status_code == 200
    data1 = resp1.json()

    assert data1["status"] == "CALIBRATED"
    assert data1["roi_measurements"][0]["inspection_status"] == "MISSING"

    # Coverage status is COMPLETE because MISSING is an assessed status
    agg1 = data1["aggregate_measurements"]
    assert agg1["inspection_coverage_status"] == "COMPLETE"
    assert agg1["expected_roi_count"] == 1
    assert agg1["assessed_roi_count"] == 1
    assert agg1["missing_roi_ids"] == ["roi_empty_target"]
    assert agg1["unassessed_roi_ids"] == []

    # Emitted observation verifies missing presence
    assert len(data1["observations"]) == 1
    obs1 = data1["observations"][0]
    assert obs1["observation_type"] == "deposit_presence"
    assert obs1["value"] == "missing"
    assert obs1["metadata"]["affected_roi_ids"] == ["roi_empty_target"]
    assert obs1["metadata"]["region_evidence"][0]["current_measurements"]["inspection_status"] == "MISSING"

    # 2. With only max_size_cv supplied: MISSING status preserved, but no missing observation emitted
    profile_without_presence = {
        "mode": "PROCESS_LIMITS",
        "rois": [
            {"roi_id": "roi_empty_target", "x": 0.25, "y": 0.25, "width": 0.5, "height": 0.5},
        ],
        "process_limits": {
            "max_size_cv": 0.20,
        },
    }

    resp2 = client.post(
        "/api/v1/images/analyze",
        files={"file": ("empty_fiducial.png", empty_img, "image/png")},
        data={"profile": json.dumps(profile_without_presence)},
    )
    assert resp2.status_code == 200
    data2 = resp2.json()

    assert data2["status"] == "CALIBRATED"
    assert data2["roi_measurements"][0]["inspection_status"] == "MISSING"
    # Unrequested dimension is NOT emitted
    assert not any(o["observation_type"] == "deposit_presence" for o in data2["observations"])


def test_scenario_d_reference_mode_separate_coverage_and_unassessed_reference(
    client: TestClient,
) -> None:
    """Scenario D: Reference mode with current and reference coverage kept separate.

    Verifies:
    1. Reliable current image paired with unassessed reference reports UNRELIABLE.
    2. Zero score-bearing observations are emitted.
    3. Current-image inspection coverage is COMPLETE (1/1 assessed).
    4. Reference-image inspection coverage is reported separately as NONE (0/1 assessed, unassessed_roi_ids=['ref_site_1']).
    5. No alignment assumption is made; reference evaluation failure safely gates the analysis.
    """
    curr_bytes = create_centered_dot_image(size=200, dot_radius=25)
    # Uniform gray reference without fiducials or contrast -> unassessed
    ref_bytes = encode_image(create_blank_image(200, 200, bg_color=128))

    profile = {
        "mode": "REFERENCE_IMAGE",
        "rois": [
            {"roi_id": "ref_site_1", "x": 0.1, "y": 0.1, "width": 0.8, "height": 0.8},
        ],
        "reference_limits": {
            "min_reference_ratio": 0.8,
            "max_reference_ratio": 1.2,
        },
    }

    response = client.post(
        "/api/v1/images/analyze",
        files={
            "file": ("current_dot.png", curr_bytes, "image/png"),
            "reference_file": ("unassessed_ref.png", ref_bytes, "image/png"),
        },
        data={"profile": json.dumps(profile)},
    )
    assert response.status_code == 200
    data = response.json()

    # Analysis status is UNRELIABLE due to reference unassessed failure
    assert data["status"] == "UNRELIABLE"
    assert data["observations"] == []
    assert any("Reference ROI 'ref_site_1' is unassessed" in w for w in data["warnings"])

    # Current aggregate coverage is COMPLETE
    agg = data["aggregate_measurements"]
    assert agg["expected_roi_count"] == 1
    assert agg["assessed_roi_count"] == 1
    assert agg["inspection_coverage_status"] == "COMPLETE"
    assert agg["unassessed_roi_ids"] == []

    # Reference aggregate coverage is reported separately
    ref_agg = data["reference_aggregate_measurements"]
    assert ref_agg is not None
    assert ref_agg["expected_roi_count"] == 1
    assert ref_agg["assessed_roi_count"] == 0
    assert ref_agg["inspection_coverage_status"] == "NONE"
    assert ref_agg["unassessed_roi_ids"] == ["ref_site_1"]
    assert ref_agg["missing_roi_ids"] == []
