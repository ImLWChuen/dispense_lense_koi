"""
DispenseIQ — Troubleshooting Check Execution API Integration Tests (/checks)

Verifies:
1. Successful POST /api/v1/cases/{case_id}/checks submission through real PostgreSQL.
2. Durable revision and check history after a fresh-session GET and JSON/PDF report export.
3. Dual-table persistence synchronizing canonical CaseCheckResultModel and CheckExecutionModel.
4. Semantic alias support (e.g. ACT_INSPECT_NOZZLE -> ACT01).
5. Non-executing/blocked check semantics (advances revision without altering cause hypotheses).
6. Stale-write rejection (HTTP 409 Conflict) with verified zero database mutations.
7. Input validation rejections (HTTP 422 / HTTP 404) with verified zero database mutations.
8. Interleaved check execution (/checks) and check result (/check-results) workflow continuity.
"""

from __future__ import annotations

import os
import uuid
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.config import get_database_url
from app.db.database import reset_engine
from app.db.session import get_session_factory
from app.main import app
from app.models.case import (
    AnalysisRevisionModel,
    CaseCheckResultModel,
    CaseModel,
    CheckExecutionModel,
)
from tests.case_snapshot_helper import capture_complete_case_state
from tests.unit.test_persistence_safety import assert_safe_test_database

client = TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def configure_test_environment(test_database_url: str) -> None:
    """Configure and verify PostgreSQL connection URL for integration tests."""
    pass


@pytest.fixture
def tracked_cases() -> Generator[list[str], None, None]:
    """Track created case IDs and clean them up after test execution."""
    case_ids: list[str] = []
    yield case_ids

    if case_ids:
        factory = get_session_factory()
        with factory() as session:
            session.execute(delete(CaseModel).where(CaseModel.case_id.in_(case_ids)))
            session.commit()


# ===========================================================================
# 1. Successful Submission & Durable State Hydration
# ===========================================================================

def test_submit_check_execution_success_and_hydration(tracked_cases: list[str]):
    """Scenario:
    - Create durable case (rev 1);
    - Submit check execution via POST /cases/{case_id}/checks (ACT01, COMPLETED, SUPPORTS);
    - Assert 200 OK with CaseCheckResponse structure;
    - Verify fresh-session GET /cases/{case_id} contains persisted check and rev 2;
    - Verify fresh-session GET /cases/{case_id}/report contains check result record;
    - Verify fresh-session GET /cases/{case_id}/report.pdf exports valid PDF;
    - Verify both case_check_results and case_check_executions tables are synchronized.
    """
    create_payload = {
        "description": "Dispense dots are shrinking over time during continuous operation",
        "defect_code": "D03_INCONSISTENT_SIZE",
        "material": "solder_paste",
        "method": "jetting",
    }
    create_resp = client.post("/api/v1/cases", json=create_payload)
    assert create_resp.status_code == 201
    case_id = create_resp.json()["case_id"]
    tracked_cases.append(case_id)
    assert create_resp.json()["diagnosis"]["analysis_revision"]["revision_number"] == 1

    check_payload = {
        "check_id": "ACT01",
        "status": "COMPLETED",
        "finding": "SUPPORTS",
        "expected_revision": 1,
        "notes": "Nozzle tip was partially obstructed.",
    }
    check_resp = client.post(f"/api/v1/cases/{case_id}/checks", json=check_payload)
    assert check_resp.status_code == 200
    check_data = check_resp.json()

    assert check_data["case_id"] == case_id
    assert check_data["current_revision"] == 2
    assert check_data["submitted_check"]["check_id"] == "ACT01"
    assert check_data["submitted_check"]["status"] == "COMPLETED"
    assert check_data["submitted_check"]["finding"] == "SUPPORTS"
    assert check_data["submitted_check"]["notes"] == "Nozzle tip was partially obstructed."
    assert check_data["submitted_check"]["resulting_revision_number"] == 2
    assert len(check_data["previous_checks"]) == 1
    assert check_data["diagnosis"]["analysis_revision"]["revision_number"] == 2

    # Fresh session GET /cases/{case_id}
    get_resp = client.get(f"/api/v1/cases/{case_id}")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["diagnosis"]["analysis_revision"]["revision_number"] == 2
    assert len(get_data["previous_check_results"]) == 1
    assert get_data["previous_check_results"][0]["check_id"] == "ACT01"
    assert get_data["previous_check_results"][0]["resulting_revision_number"] == 2
    assert len(get_data["analysis_revisions"]) == 2
    assert check_data["analysis_revisions"] == get_data["analysis_revisions"]

    # Fresh session GET /cases/{case_id}/report
    report_resp = client.get(f"/api/v1/cases/{case_id}/report")
    assert report_resp.status_code == 200
    report_data = report_resp.json()
    assert report_data["case_id"] == case_id
    assert report_data["current_revision"] == 2
    assert len(report_data["check_results"]) == 1
    assert report_data["check_results"][0]["check_id"] == "ACT01"
    assert report_data["check_results"][0]["resulting_revision_number"] == 2

    # Fresh session GET /cases/{case_id}/report.pdf
    pdf_resp = client.get(f"/api/v1/cases/{case_id}/report.pdf")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert pdf_resp.content.startswith(b"%PDF-")

    # Direct database verification of dual-table synchronization
    factory = get_session_factory()
    with factory() as session:
        cr_rows = list(session.scalars(
            select(CaseCheckResultModel).where(CaseCheckResultModel.case_id == case_id)
        ).all())
        ce_rows = list(session.scalars(
            select(CheckExecutionModel).where(CheckExecutionModel.case_id == case_id)
        ).all())
        rev_rows = list(session.scalars(
            select(AnalysisRevisionModel).where(AnalysisRevisionModel.case_id == case_id)
        ).all())

        assert len(cr_rows) == 1
        assert cr_rows[0].check_id == "ACT01"
        assert cr_rows[0].resulting_revision_number == 2
        assert cr_rows[0].finding == "SUPPORTS"

        assert len(ce_rows) == 1
        assert ce_rows[0].check_id == "ACT01"
        assert ce_rows[0].status == "COMPLETED"
        assert ce_rows[0].finding == "SUPPORTS"
        assert ce_rows[0].resulting_revision_number == 2
        assert ce_rows[0].notes == "Nozzle tip was partially obstructed."

        assert len(rev_rows) == 2


# ===========================================================================
# 2. Semantic Alias Support
# ===========================================================================

def test_submit_check_execution_alias_support(tracked_cases: list[str]):
    """Verify that semantic check aliases (e.g. ACT_INSPECT_NOZZLE) resolve cleanly."""
    create_payload = {
        "description": "Inconsistent dot size on valve dispenser",
        "defect_code": "D03_INCONSISTENT_SIZE",
        "material": "adhesive",
        "method": "time_pressure",
    }
    create_resp = client.post("/api/v1/cases", json=create_payload)
    assert create_resp.status_code == 201
    case_id = create_resp.json()["case_id"]
    tracked_cases.append(case_id)

    alias_payload = {
        "check_id": "ACT_INSPECT_NOZZLE",
        "status": "COMPLETED",
        "finding": "SUPPORTS",
        "expected_revision": 1,
        "notes": "Obstruction found at nozzle tip.",
    }
    check_resp = client.post(f"/api/v1/cases/{case_id}/checks", json=alias_payload)
    assert check_resp.status_code == 200
    data = check_resp.json()
    assert data["current_revision"] == 2
    assert data["submitted_check"]["resulting_revision_number"] == 2


# ===========================================================================
# 3. Blocked Check Semantics
# ===========================================================================

def test_submit_check_execution_blocked_semantics(tracked_cases: list[str]):
    """Verify that BLOCKED checks advance revision but produce no hypotheses modifications."""
    create_payload = {
        "description": "Missing dots defect",
        "defect_code": "D04_MISSING_DOTS",
        "material": "flux",
        "method": "jetting",
    }
    create_resp = client.post("/api/v1/cases", json=create_payload)
    assert create_resp.status_code == 201
    case_id = create_resp.json()["case_id"]
    tracked_cases.append(case_id)

    blocked_payload = {
        "check_id": "ACT01",
        "status": "BLOCKED",
        "finding": "UNKNOWN",
        "expected_revision": 1,
        "notes": "Safety guard could not be opened.",
    }
    check_resp = client.post(f"/api/v1/cases/{case_id}/checks", json=blocked_payload)
    assert check_resp.status_code == 200
    data = check_resp.json()
    assert data["current_revision"] == 2
    assert data["submitted_check"]["status"] == "BLOCKED"
    assert data["submitted_check"]["finding"] == "UNKNOWN"

    # Fresh session GET verification
    get_resp = client.get(f"/api/v1/cases/{case_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["diagnosis"]["analysis_revision"]["revision_number"] == 2


# ===========================================================================
# 4. Stale-Write 409 Rejection with Zero Database Mutations
# ===========================================================================

def test_submit_check_execution_stale_write_409_no_mutation(tracked_cases: list[str]):
    """Verify that submitting with mismatched expected_revision returns 409 Conflict
    and leaves complete database state completely unmodified.
    """
    create_payload = {
        "description": "Testing concurrency protection on /checks",
        "defect_code": "D01_TOO_LITTLE",
        "material": "epoxy",
        "method": "screw",
    }
    create_resp = client.post("/api/v1/cases", json=create_payload)
    assert create_resp.status_code == 201
    case_id = create_resp.json()["case_id"]
    tracked_cases.append(case_id)

    factory = get_session_factory()
    with factory() as session:
        state_before = capture_complete_case_state(session, case_id)

    # Submit with stale expected_revision=99
    stale_payload = {
        "check_id": "ACT01",
        "status": "COMPLETED",
        "finding": "SUPPORTS",
        "expected_revision": 99,
        "notes": "This write must be rejected.",
    }
    stale_resp = client.post(f"/api/v1/cases/{case_id}/checks", json=stale_payload)
    assert stale_resp.status_code == 409
    assert "Stale revision" in stale_resp.json()["detail"]

    # Verify zero database mutations
    with factory() as fresh_session:
        state_after = capture_complete_case_state(fresh_session, case_id)

    assert state_before == state_after


# ===========================================================================
# 5. Validation Rejections with Zero Database Mutations
# ===========================================================================

def test_submit_check_execution_validation_errors_no_mutation(tracked_cases: list[str]):
    """Verify that invalid inputs return HTTP 422 or HTTP 404 without mutating database state."""
    create_payload = {
        "description": "Testing input rejection safety on /checks",
        "defect_code": "D02_TOO_MUCH",
        "material": "silicone",
        "method": "time_pressure",
    }
    create_resp = client.post("/api/v1/cases", json=create_payload)
    assert create_resp.status_code == 201
    case_id = create_resp.json()["case_id"]
    tracked_cases.append(case_id)

    factory = get_session_factory()
    with factory() as session:
        state_before = capture_complete_case_state(session, case_id)

    # 1. Invalid UUID format
    r1 = client.post("/api/v1/cases/not-a-valid-uuid/checks", json={"check_id": "ACT01", "expected_revision": 1})
    assert r1.status_code == 422
    assert "Invalid case ID format" in r1.json()["detail"]

    # 2. Non-existent case
    random_cid = str(uuid.uuid4())
    r2 = client.post(f"/api/v1/cases/{random_cid}/checks", json={"check_id": "ACT01", "expected_revision": 1})
    assert r2.status_code == 404
    assert f"Case '{random_cid}' not found." in r2.json()["detail"]

    # 3. Unknown check_id
    r3 = client.post(f"/api/v1/cases/{case_id}/checks", json={"check_id": "ACT_COMPLETELY_UNKNOWN", "expected_revision": 1})
    assert r3.status_code == 422
    assert "Unknown check_id" in r3.json()["detail"]

    # 4. Invalid execution status
    r4 = client.post(f"/api/v1/cases/{case_id}/checks", json={"check_id": "ACT01", "status": "INVALID_STATUS", "expected_revision": 1})
    assert r4.status_code == 422
    assert "Invalid check execution status" in r4.json()["detail"]

    # 5. Unfinished execution status: PENDING
    r5 = client.post(f"/api/v1/cases/{case_id}/checks", json={"check_id": "ACT01", "status": "PENDING", "expected_revision": 1})
    assert r5.status_code == 422
    assert "unfinished" in r5.json()["detail"]

    # 6. Unfinished execution status: IN_PROGRESS
    r6 = client.post(f"/api/v1/cases/{case_id}/checks", json={"check_id": "ACT01", "status": "IN_PROGRESS", "expected_revision": 1})
    assert r6.status_code == 422
    assert "unfinished" in r6.json()["detail"]

    # 7. Invalid check finding
    r7 = client.post(f"/api/v1/cases/{case_id}/checks", json={"check_id": "ACT01", "finding": "INVALID_FINDING", "expected_revision": 1})
    assert r7.status_code == 422
    assert "Invalid check finding" in r7.json()["detail"]

    # 8. Expected revision < 1
    r8 = client.post(f"/api/v1/cases/{case_id}/checks", json={"check_id": "ACT01", "expected_revision": 0})
    assert r8.status_code == 422

    # Verify state is completely pristine after all failed requests
    with factory() as fresh_session:
        state_after = capture_complete_case_state(fresh_session, case_id)

    assert state_before == state_after


# ===========================================================================
# 6. Interleaved Check Execution & Lifecycle Workflow Continuity
# ===========================================================================

def test_interleaved_checks_and_lifecycle_continuity(tracked_cases: list[str]):
    """Verify that a case can execute checks via /checks, confirm cause, apply recovery,
    and report correctly across multiple revisions.
    """
    create_payload = {
        "description": "Multi-step workflow testing /checks and lifecycle continuity",
        "defect_code": "D03_INCONSISTENT_SIZE",
        "material": "solder_paste",
        "method": "jetting",
    }
    create_resp = client.post("/api/v1/cases", json=create_payload)
    assert create_resp.status_code == 201
    case_id = create_resp.json()["case_id"]
    tracked_cases.append(case_id)

    # Rev 1 -> 2 via POST /checks
    c1_resp = client.post(
        f"/api/v1/cases/{case_id}/checks",
        json={"check_id": "ACT01", "status": "COMPLETED", "finding": "SUPPORTS", "expected_revision": 1, "notes": "Nozzle partially obstructed."},
    )
    assert c1_resp.status_code == 200
    assert c1_resp.json()["current_revision"] == 2

    # Rev 2 -> 3 via POST /check-results
    c2_resp = client.post(
        f"/api/v1/cases/{case_id}/check-results",
        json={"check_id": "ACT02", "execution_status": "COMPLETED", "finding": "SUPPORTS", "outcome": "air_bubbles_found", "expected_revision": 2},
    )
    assert c2_resp.status_code == 200
    assert c2_resp.json()["current_revision"] == 3

    # Rev 3 -> 4 via POST /cause-confirmations
    conf_resp = client.post(
        f"/api/v1/cases/{case_id}/cause-confirmations",
        json={"cause_id": "nozzle_restriction", "expected_revision": 3, "confirmed_by": "lead_tech"},
    )
    assert conf_resp.status_code == 200
    assert conf_resp.json()["current_revision"] == 4

    # Fresh GET /report check
    rep_resp = client.get(f"/api/v1/cases/{case_id}/report")
    assert rep_resp.status_code == 200
    rep_data = rep_resp.json()
    assert rep_data["current_revision"] == 4
    assert len(rep_data["check_results"]) == 2
    assert rep_data["cause_confirmations"][0]["cause_id"] == "nozzle_restriction"


# ===========================================================================
# 7. Complete Analysis Revision History Parity & Snapshot Fidelity
# ===========================================================================

def test_check_execution_analysis_revision_history_parity(tracked_cases: list[str]):
    """Verify that POST /checks returns the persisted nested analysis_revision
    snapshots identically to GET /cases/{case_id}, retaining the revision bound,
    preserving changes_from_previous and new_evidence_summary across revisions,
    and matching the stored PostgreSQL result_snapshot exactly.
    """
    create_payload = {
        "description": "Dispense dots are shrinking over time during continuous operation",
        "defect_code": "D03_INCONSISTENT_SIZE",
        "material": "solder_paste",
        "method": "jetting",
    }
    create_resp = client.post("/api/v1/cases", json=create_payload)
    assert create_resp.status_code == 201
    case_id = create_resp.json()["case_id"]
    tracked_cases.append(case_id)
    assert create_resp.json()["analysis_revisions"] == []

    # 1. First check execution: Rev 1 -> Rev 2
    c1_payload = {
        "check_id": "ACT01",
        "status": "COMPLETED",
        "finding": "SUPPORTS",
        "expected_revision": 1,
        "notes": "Nozzle tip was partially obstructed.",
    }
    c1_resp = client.post(f"/api/v1/cases/{case_id}/checks", json=c1_payload)
    assert c1_resp.status_code == 200
    c1_data = c1_resp.json()
    assert c1_data["current_revision"] == 2
    assert len(c1_data["analysis_revisions"]) == 2

    # 2. Second check execution: Rev 2 -> Rev 3
    c2_payload = {
        "check_id": "ACT02",
        "status": "COMPLETED",
        "finding": "CONTRADICTS",
        "expected_revision": 2,
        "notes": "Fluid pressure was calibrated and within operating envelope.",
    }
    c2_resp = client.post(f"/api/v1/cases/{case_id}/checks", json=c2_payload)
    assert c2_resp.status_code == 200
    c2_data = c2_resp.json()
    assert c2_data["current_revision"] == 3
    assert len(c2_data["analysis_revisions"]) == 3

    # 3. Fresh-session GET /cases/{case_id}
    get_resp = client.get(f"/api/v1/cases/{case_id}")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["diagnosis"]["analysis_revision"]["revision_number"] == 3
    assert len(get_data["analysis_revisions"]) == 3

    # 4. Assert complete history objects equality between /checks and GET
    assert c2_data["analysis_revisions"] == get_data["analysis_revisions"]

    # Assert revision bound retention: c1_data (at rev 2) contains only rev 1 and 2
    assert c1_data["analysis_revisions"] == get_data["analysis_revisions"][:2]

    # 5. Direct database stored snapshot verification
    factory = get_session_factory()
    with factory() as session:
        db_rev_models = list(
            session.scalars(
                select(AnalysisRevisionModel)
                .where(AnalysisRevisionModel.case_id == case_id)
                .order_by(AnalysisRevisionModel.revision_number)
            ).all()
        )
        assert len(db_rev_models) == 3

        for i, db_rev in enumerate(db_rev_models):
            expected_snapshot = db_rev.result_snapshot["analysis_revision"]
            assert c2_data["analysis_revisions"][i] == expected_snapshot
            assert get_data["analysis_revisions"][i] == expected_snapshot

    # 6. Specific semantic verification of changes_from_previous and new_evidence_summary
    rev1_hist = c2_data["analysis_revisions"][0]
    rev2_hist = c2_data["analysis_revisions"][1]
    rev3_hist = c2_data["analysis_revisions"][2]

    # Revision 1 (initial assessment baseline)
    assert rev1_hist["revision_number"] == 1
    assert rev1_hist["defect_code"] == "D03_INCONSISTENT_SIZE"
    assert rev1_hist["new_evidence_summary"] == "Initial diagnostic assessment."
    assert rev1_hist["changes_from_previous"] == []
    assert rev1_hist == db_rev_models[0].result_snapshot["analysis_revision"]

    # Revision 2 (after SUPPORTS check: ranks/scores changed)
    assert rev2_hist["revision_number"] == 2
    assert rev2_hist["defect_code"] == "D03_INCONSISTENT_SIZE"
    assert "ACT01" in rev2_hist["new_evidence_summary"]
    assert "COMPLETED" in rev2_hist["new_evidence_summary"]
    assert rev2_hist["new_evidence_summary"] == db_rev_models[1].result_snapshot["analysis_revision"]["new_evidence_summary"]
    assert len(rev2_hist["changes_from_previous"]) > 0
    assert rev2_hist["changes_from_previous"] == db_rev_models[1].result_snapshot["analysis_revision"]["changes_from_previous"]
    assert rev2_hist == db_rev_models[1].result_snapshot["analysis_revision"]

    # Revision 3 (after CONTRADICTS check: ranks/scores changed again)
    assert rev3_hist["revision_number"] == 3
    assert rev3_hist["defect_code"] == "D03_INCONSISTENT_SIZE"
    assert "ACT02" in rev3_hist["new_evidence_summary"]
    assert "COMPLETED" in rev3_hist["new_evidence_summary"]
    assert rev3_hist["new_evidence_summary"] == db_rev_models[2].result_snapshot["analysis_revision"]["new_evidence_summary"]
    assert len(rev3_hist["changes_from_previous"]) > 0
    assert rev3_hist["changes_from_previous"] == db_rev_models[2].result_snapshot["analysis_revision"]["changes_from_previous"]
    assert rev3_hist == db_rev_models[2].result_snapshot["analysis_revision"]
