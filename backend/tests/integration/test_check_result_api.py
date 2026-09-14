"""
DispenseIQ — Technician Troubleshooting Check Result Submission API Integration Tests

Tests persistent technician troubleshooting check-result submission (POST /api/v1/cases/{case_id}/check-results)
against real PostgreSQL. Verifies atomicity, provenance preservation, optimistic concurrency via expected_revision,
clean 409 stale-revision handling, 404 missing case handling, 422 validation rejections, non-executing and
inconclusive check semantics, prior revision immutability, ACT03 non-directional mapping, cause confirmation
separation, and API regression safety.
"""

from __future__ import annotations

import copy
import os
import uuid
from typing import Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, select
from sqlalchemy.orm import Session

from app.api.cases import get_diagnosis_engine
from app.core.config import get_database_url
from app.db.database import get_engine, reset_engine
from app.db.repository import CaseRepository
from app.db.session import get_session_factory
from app.main import app
from app.models.case import (
    AnalysisRevisionModel,
    CaseCheckResultModel,
    CaseModel,
    ObservationModel,
)
from app.schemas.diagnosis import (
    CauseConclusion,
    CheckExecutionStatus,
    CheckFinding,
    EvidenceSource,
    IssueCondition,
    ObservationType,
)
from app.services.diagnosis.engine import DiagnosticEngine
from tests.unit.test_persistence_safety import assert_safe_test_database

client = TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def configure_test_environment() -> None:
    """Configure and verify PostgreSQL connection URL for integration tests."""
    if not os.environ.get("DATABASE_URL"):
        os.environ["DATABASE_URL"] = (
            "postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens"
        )
    url = get_database_url()
    assert_safe_test_database(url)
    reset_engine()


@pytest.fixture
def tracked_cases() -> Generator[list[str], None, None]:
    """Track created case IDs and clean them up after test execution."""
    case_ids: list[str] = []
    yield case_ids

    if case_ids:
        factory = get_session_factory()
        with factory() as session:
            # Cascades to case_observations, analysis_revisions, case_question_answers, and case_check_results
            session.execute(delete(CaseModel).where(CaseModel.case_id.in_(case_ids)))
            session.commit()


# ===========================================================================
# 1. OpenAPI & Route Registration Verification
# ===========================================================================

def test_check_result_endpoint_registered_in_openapi():
    """Verify that POST /api/v1/cases/{case_id}/check-results is present in OpenAPI specification."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema["paths"]

    assert "/api/v1/cases/{case_id}/check-results" in paths
    check_path = paths["/api/v1/cases/{case_id}/check-results"]
    assert "post" in check_path
    responses = check_path["post"]["responses"]
    assert "200" in responses
    assert "404" in responses
    assert "409" in responses
    assert "422" in responses
    assert "500" in responses


# ===========================================================================
# 2. Scenario 1: Valid Evidence-Producing Completed Check Creates Revision N+1
# ===========================================================================

def test_valid_evidence_producing_check_creates_revision_n_plus_1(tracked_cases: list[str]):
    """Scenario 1:
    - Create durable case;
    - Submit valid check result (ACT01:no_blockage);
    - Assert 200;
    - Assert revision advances from 1 to 2;
    - Verify submitted_check_result provenance is USER_CHECK_RESULT;
    - Reload durable state and verify check result + revision 2.
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

    check_payload = {
        "check_id": "ACT01",
        "execution_status": "COMPLETED",
        "finding": "CONTRADICTS",
        "outcome": "no_blockage",
        "finding_details": "No visible blockage under 50x microscope",
        "expected_revision": 1,
    }
    resp = client.post(f"/api/v1/cases/{case_id}/check-results", json=check_payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["case_id"] == case_id
    assert data["current_revision"] == 2
    assert data["diagnosis"]["analysis_revision"]["revision_number"] == 2

    # Check submitted check result record
    submitted = data["submitted_check_result"]
    assert submitted["check_id"] == "ACT01"
    assert submitted["execution_status"] == "COMPLETED"
    assert submitted["finding"] == "CONTRADICTS"
    assert submitted["outcome"] == "no_blockage"
    assert submitted["finding_details"] == "No visible blockage under 50x microscope"
    assert submitted["resulting_revision_number"] == 2
    assert submitted["source"].lower() == "user_check_result"

    # Check history
    assert len(data["previous_check_results"]) == 1
    assert data["previous_check_results"][0]["check_id"] == "ACT01"

    # Reload via GET and repository
    get_resp = client.get(f"/api/v1/cases/{case_id}")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["case_id"] == case_id

    factory = get_session_factory()
    with factory() as session:
        repo = CaseRepository(session)
        assert repo.list_case_revisions(case_id) == [1, 2]
        cr_records = repo.get_case_check_results(case_id)
        assert len(cr_records) == 1
        assert cr_records[0].check_id == "ACT01"
        loaded = repo.load_structured_case(case_id)
        assert loaded is not None
        assert loaded.analysis_revisions[-1].revision_number == 2
        assert len(loaded.previous_check_results) == 1
        assert loaded.previous_check_results[0].check_id == "ACT01"


# ===========================================================================
# 3. Scenario 2: ACT03:consistent_but_wrong_size Does Not Fabricate Directional Evidence
# ===========================================================================

def test_act03_consistent_but_wrong_size_does_not_fabricate_directional_deposit_size(tracked_cases: list[str]):
    """Scenario 2:
    - Submit ACT03 with outcome consistent_but_wrong_size;
    - Emits CHECK_RESULT observation;
    - Emits NO directional DEPOSIT_SIZE (neither undersized nor oversized).
    """
    create_payload = {
        "description": "Dispense dots are inconsistent",
        "defect_code": "D03_INCONSISTENT_SIZE",
    }
    create_resp = client.post("/api/v1/cases", json=create_payload)
    assert create_resp.status_code == 201
    case_id = create_resp.json()["case_id"]
    tracked_cases.append(case_id)

    check_payload = {
        "check_id": "ACT03",
        "execution_status": "COMPLETED",
        "finding": "SUPPORTS",
        "outcome": "consistent_but_wrong_size",
        "finding_details": "Shots are repeatable in mass but dot diameter is off target",
        "expected_revision": 1,
    }
    resp = client.post(f"/api/v1/cases/{case_id}/check-results", json=check_payload)
    assert resp.status_code == 200
    data = resp.json()

    # Verify observations
    obs_types_and_values = [(o["observation_type"], o["value"]) for o in data["observations"]]

    # 1. Structured CHECK_RESULT is present
    assert any(
        o_type == "check_result" and "ACT03:consistent_but_wrong_size" in o_val
        for o_type, o_val in obs_types_and_values
    )

    # 2. NO directional deposit_size is created
    assert not any(
        o_type == "deposit_size" and o_val in ("undersized", "oversized")
        for o_type, o_val in obs_types_and_values
    )


# ===========================================================================
# 4. Scenario 3: BLOCKED Check Persists History But Adds No Diagnostic Evidence
# ===========================================================================

def test_blocked_check_persists_history_without_diagnostic_evidence(tracked_cases: list[str]):
    """Scenario 3:
    - BLOCKED check persists history and creates Revision N+1;
    - Finding is normalized to UNKNOWN;
    - Zero new observations added.
    """
    create_payload = {
        "description": "Dispense dots are shrinking over time",
        "defect_code": "D03_INCONSISTENT_SIZE",
    }
    create_resp = client.post("/api/v1/cases", json=create_payload)
    assert create_resp.status_code == 201
    case_data = create_resp.json()
    case_id = case_data["case_id"]
    tracked_cases.append(case_id)
    initial_obs_count = len(case_data["observations"])

    check_payload = {
        "check_id": "ACT01",
        "execution_status": "BLOCKED",
        "finding": "UNKNOWN",
        "finding_details": "Cleaning station offline; cannot perform nozzle inspection",
        "expected_revision": 1,
    }
    resp = client.post(f"/api/v1/cases/{case_id}/check-results", json=check_payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["current_revision"] == 2
    assert data["submitted_check_result"]["execution_status"] == "BLOCKED"
    assert data["submitted_check_result"]["finding"] == "UNKNOWN"
    assert len(data["previous_check_results"]) == 1

    # Zero diagnostic observations added
    assert len(data["observations"]) == initial_obs_count


# ===========================================================================
# 5. Scenario 4: INCONCLUSIVE Check Persists History But Adds No Diagnostic Evidence
# ===========================================================================

def test_inconclusive_check_persists_history_without_diagnostic_evidence(tracked_cases: list[str]):
    """Scenario 4:
    - Completed check with INCONCLUSIVE finding persists history and creates Revision N+1;
    - Zero new observations added.
    """
    create_payload = {
        "description": "Dispense dots are shrinking over time",
        "defect_code": "D03_INCONSISTENT_SIZE",
    }
    create_resp = client.post("/api/v1/cases", json=create_payload)
    assert create_resp.status_code == 201
    case_data = create_resp.json()
    case_id = case_data["case_id"]
    tracked_cases.append(case_id)
    initial_obs_count = len(case_data["observations"])

    check_payload = {
        "check_id": "ACT01",
        "execution_status": "COMPLETED",
        "finding": "INCONCLUSIVE",
        "finding_details": "Microscope magnification insufficient to verify nozzle bore",
        "expected_revision": 1,
    }
    resp = client.post(f"/api/v1/cases/{case_id}/check-results", json=check_payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["current_revision"] == 2
    assert data["submitted_check_result"]["execution_status"] == "COMPLETED"
    assert data["submitted_check_result"]["finding"] == "INCONCLUSIVE"
    assert len(data["previous_check_results"]) == 1
    assert len(data["observations"]) == initial_obs_count


# ===========================================================================
# 6. Scenario 5: Invalid Check ID -> 422 With No Mutation
# ===========================================================================

def test_invalid_check_id_returns_422_with_no_mutation(tracked_cases: list[str]):
    """Scenario 5:
    - Non-existent check ID rejected with 422;
    - No check result record or revision persisted.
    """
    create_payload = {
        "description": "Dispense dots are shrinking over time",
        "defect_code": "D03_INCONSISTENT_SIZE",
    }
    create_resp = client.post("/api/v1/cases", json=create_payload)
    assert create_resp.status_code == 201
    case_id = create_resp.json()["case_id"]
    tracked_cases.append(case_id)

    check_payload = {
        "check_id": "ACT99_NON_EXISTENT",
        "execution_status": "COMPLETED",
        "finding": "SUPPORTS",
        "expected_revision": 1,
    }
    resp = client.post(f"/api/v1/cases/{case_id}/check-results", json=check_payload)
    assert resp.status_code == 422
    assert "Unknown check_id" in resp.json()["detail"]

    # Verify no mutation
    factory = get_session_factory()
    with factory() as session:
        repo = CaseRepository(session)
        assert repo.list_case_revisions(case_id) == [1]
        assert len(repo.get_case_check_results(case_id)) == 0


# ===========================================================================
# 7. Scenario 6: Invalid Outcome -> 422 With No Mutation
# ===========================================================================

def test_invalid_outcome_returns_422_with_no_mutation(tracked_cases: list[str]):
    """Scenario 6:
    - Unsupported outcome for a valid check rejected with 422;
    - No check result record or revision persisted.
    """
    create_payload = {
        "description": "Dispense dots are shrinking over time",
        "defect_code": "D03_INCONSISTENT_SIZE",
    }
    create_resp = client.post("/api/v1/cases", json=create_payload)
    assert create_resp.status_code == 201
    case_id = create_resp.json()["case_id"]
    tracked_cases.append(case_id)

    check_payload = {
        "check_id": "ACT01",
        "execution_status": "COMPLETED",
        "finding": "CONTRADICTS",
        "outcome": "laser_vaporized",
        "expected_revision": 1,
    }
    resp = client.post(f"/api/v1/cases/{case_id}/check-results", json=check_payload)
    assert resp.status_code == 422
    assert "Invalid outcome" in resp.json()["detail"]

    # Verify no mutation
    factory = get_session_factory()
    with factory() as session:
        repo = CaseRepository(session)
        assert repo.list_case_revisions(case_id) == [1]
        assert len(repo.get_case_check_results(case_id)) == 0


# ===========================================================================
# 8. Scenario 7: Missing Case -> 404
# ===========================================================================

def test_missing_case_returns_404():
    """Scenario 7:
    - Check submission to a non-existent case returns 404.
    """
    non_existent = str(uuid.uuid4())
    check_payload = {
        "check_id": "ACT01",
        "execution_status": "COMPLETED",
        "finding": "CONTRADICTS",
        "outcome": "no_blockage",
        "expected_revision": 1,
    }
    resp = client.post(f"/api/v1/cases/{non_existent}/check-results", json=check_payload)
    assert resp.status_code == 404
    assert f"Case '{non_existent}' not found." in resp.json()["detail"]


# ===========================================================================
# 9. Scenario 8: Stale Expected Revision -> 409 With No Mutation
# ===========================================================================

def test_stale_expected_revision_returns_409_with_no_mutation(tracked_cases: list[str]):
    """Scenario 8:
    - Submitting with expected_revision != current_revision returns 409;
    - No mutation occurs.
    """
    create_payload = {
        "description": "Dispense dots are shrinking over time",
        "defect_code": "D03_INCONSISTENT_SIZE",
    }
    create_resp = client.post("/api/v1/cases", json=create_payload)
    assert create_resp.status_code == 201
    case_id = create_resp.json()["case_id"]
    tracked_cases.append(case_id)

    # Current revision is 1; supply 2
    check_payload = {
        "check_id": "ACT01",
        "execution_status": "COMPLETED",
        "finding": "CONTRADICTS",
        "outcome": "no_blockage",
        "expected_revision": 2,
    }
    resp = client.post(f"/api/v1/cases/{case_id}/check-results", json=check_payload)
    assert resp.status_code == 409
    assert "Stale revision" in resp.json()["detail"]

    # Verify no mutation
    factory = get_session_factory()
    with factory() as session:
        repo = CaseRepository(session)
        assert repo.list_case_revisions(case_id) == [1]
        assert len(repo.get_case_check_results(case_id)) == 0


# ===========================================================================
# 10. Scenario 9: Replay After Success With Old Revision -> 409
# ===========================================================================

def test_replay_after_success_with_old_revision_returns_409(tracked_cases: list[str]):
    """Scenario 9:
    - First check submission succeeds (revision 1 -> 2);
    - Replaying the same request with expected_revision=1 returns 409;
    - Revision remains 2 and only 1 check result persisted.
    """
    create_payload = {
        "description": "Dispense dots are shrinking over time",
        "defect_code": "D03_INCONSISTENT_SIZE",
    }
    create_resp = client.post("/api/v1/cases", json=create_payload)
    assert create_resp.status_code == 201
    case_id = create_resp.json()["case_id"]
    tracked_cases.append(case_id)

    check_payload = {
        "check_id": "ACT01",
        "execution_status": "COMPLETED",
        "finding": "CONTRADICTS",
        "outcome": "no_blockage",
        "expected_revision": 1,
    }
    # 1. First submission succeeds
    resp1 = client.post(f"/api/v1/cases/{case_id}/check-results", json=check_payload)
    assert resp1.status_code == 200
    assert resp1.json()["current_revision"] == 2

    # 2. Replay returns 409
    resp2 = client.post(f"/api/v1/cases/{case_id}/check-results", json=check_payload)
    assert resp2.status_code == 409

    # 3. Verify exactly 1 check result persisted and revision is 2
    factory = get_session_factory()
    with factory() as session:
        repo = CaseRepository(session)
        assert repo.list_case_revisions(case_id) == [1, 2]
        assert len(repo.get_case_check_results(case_id)) == 1


# ===========================================================================
# 11. Scenario 10: Induced Persistence Failure -> Sanitized 500 & Atomic Rollback
# ===========================================================================

def test_induced_persistence_failure_returns_sanitized_500_and_rolls_back(tracked_cases: list[str]):
    """Scenario 10 (R2 post-write rollback proof):
    - Create an unrelated control case (Case A) to verify it remains untouched;
    - Create a target case (Case B);
    - Submit a valid, evidence-producing check result (ACT01, COMPLETED, SUPPORTS, blockage_found);
    - Allow the real append path to flush check-result, generated observations, and revision 2;
    - Intercept at the commit boundary using a test-only SQLAlchemy before_commit event;
    - Assert inside the transaction that the pending flushed check-result, observation, and revision exist;
    - Inject an unhandled failure (with sensitive paths) before commit;
    - Verify that the production transaction boundary rolls back naturally;
    - Assert the HTTP response is a sanitized 500 without leaking sensitive paths;
    - In a fresh independent session, verify all new rows are absent, Case B is at revision 1, and Case A is intact.
    """
    factory = get_session_factory()

    # 1. Create unrelated control case (Case A)
    control_resp = client.post(
        "/api/v1/cases",
        json={
            "description": "Control case for rollback isolation",
            "defect_code": "D03_INCONSISTENT_SIZE",
        },
    )
    assert control_resp.status_code == 201
    control_id = control_resp.json()["case_id"]
    tracked_cases.append(control_id)

    # 2. Create target case (Case B)
    target_resp = client.post(
        "/api/v1/cases",
        json={
            "description": "Target case for post-flush rollback test",
            "defect_code": "D03_INCONSISTENT_SIZE",
        },
    )
    assert target_resp.status_code == 201
    target_id = target_resp.json()["case_id"]
    tracked_cases.append(target_id)

    with factory() as session:
        repo = CaseRepository(session)
        target_initial_case = repo.load_structured_case(target_id)
        assert target_initial_case is not None
        initial_obs_count = len(target_initial_case.observations)
        control_initial_revs = repo.list_case_revisions(control_id)

    # 3. Prepare evidence-producing check result payload
    check_payload = {
        "check_id": "ACT01",
        "execution_status": "COMPLETED",
        "finding": "SUPPORTS",
        "outcome": "blockage_found",
        "finding_details": "Nozzle orifice blocked with particulate",
        "expected_revision": 1,
    }

    sensitive_path = "C:/private/database/secrets/db.sqlite"
    hook_called = False

    def fail_after_flush_before_commit(session: Session) -> None:
        nonlocal hook_called
        # Only intercept for target_id check-result transaction
        target_crs = session.scalars(
            select(CaseCheckResultModel).where(
                CaseCheckResultModel.case_id == target_id,
                CaseCheckResultModel.resulting_revision_number == 2,
            )
        ).all()
        if not target_crs:
            return

        hook_called = True

        # Assert flushed rows exist inside the pending transaction:
        # 1. Check-result record
        assert len(target_crs) == 1
        assert target_crs[0].check_id == "ACT01"
        assert target_crs[0].outcome == "blockage_found"

        # 2. Generated observations for revision 2 (ACT01:blockage_found and nozzle_condition=blocked)
        target_rev2_obs = session.scalars(
            select(ObservationModel).where(
                ObservationModel.case_id == target_id,
                ObservationModel.first_seen_revision == 2,
            )
        ).all()
        assert len(target_rev2_obs) >= 1

        # 3. New analysis revision 2
        target_rev2 = session.scalars(
            select(AnalysisRevisionModel).where(
                AnalysisRevisionModel.case_id == target_id,
                AnalysisRevisionModel.revision_number == 2,
            )
        ).all()
        assert len(target_rev2) == 1

        # Now inject failure after flush but before commit
        raise RuntimeError(f"Simulated disk write fault at {sensitive_path}")

    event.listen(Session, "before_commit", fail_after_flush_before_commit)
    try:
        resp = client.post(f"/api/v1/cases/{target_id}/check-results", json=check_payload)
    finally:
        event.remove(Session, "before_commit", fail_after_flush_before_commit)

    assert hook_called is True

    # 4. Assert response is sanitized 500
    assert resp.status_code == 500
    error_detail = resp.json()["detail"]
    assert "An unexpected error occurred while persisting the check result revision." in error_detail
    assert sensitive_path not in error_detail

    # 5. Open a fresh independent session and verify full rollback
    with factory() as session:
        repo = CaseRepository(session)

        # Verify no check result rows were committed for target_id
        assert len(repo.get_case_check_results(target_id)) == 0

        # Verify no revision 2 observations were committed for target_id
        current_obs = repo.get_case_observations(target_id)
        assert len(current_obs) == initial_obs_count
        assert not any(obs.first_seen_revision == 2 for obs in current_obs)

        # Verify target case remains at revision 1
        assert repo.list_case_revisions(target_id) == [1]

        # Verify structured case snapshot is intact
        loaded_target = repo.load_structured_case(target_id)
        assert loaded_target is not None
        assert loaded_target.analysis_revisions[-1].revision_number == 1
        assert len(loaded_target.previous_check_results) == 0

        # Verify control case (Case A) was completely untouched
        assert repo.list_case_revisions(control_id) == control_initial_revs
        assert len(repo.get_case_check_results(control_id)) == 0


# ===========================================================================
# 12. Scenario 11: Supporting Check Leaves Root Cause Unconfirmed
# ===========================================================================

def test_supporting_check_leaves_root_cause_unconfirmed(tracked_cases: list[str]):
    """Scenario 11:
    - Submitting a check that supports a cause (e.g. ACT02:air_bubbles_found) increases evidence;
    - But does NOT automatically confirm the cause;
    - Cause conclusions remain SUSPECTED;
    - confirmed_causes remains empty.
    """
    create_payload = {
        "description": "Dispense dots have inconsistent size and occasionally missing dots",
        "defect_code": "D03_INCONSISTENT_SIZE",
    }
    create_resp = client.post("/api/v1/cases", json=create_payload)
    assert create_resp.status_code == 201
    case_id = create_resp.json()["case_id"]
    tracked_cases.append(case_id)

    check_payload = {
        "check_id": "ACT02",
        "execution_status": "COMPLETED",
        "finding": "SUPPORTS",
        "outcome": "air_bubbles_found",
        "finding_details": "Micro-air bubbles visible in fluid syringe",
        "expected_revision": 1,
    }
    resp = client.post(f"/api/v1/cases/{case_id}/check-results", json=check_payload)
    assert resp.status_code == 200
    data = resp.json()

    # None of the ranked causes may be CONFIRMED
    ranked = data["diagnosis"]["ranked_causes"]
    for cause in ranked:
        assert cause["conclusion"] != "CONFIRMED", f"Cause {cause['cause_id']} was auto-confirmed!"
        assert cause["conclusion"] in ("SUSPECTED", "UNRESOLVED")

    # Confirmed causes list remains empty
    if "confirmed_causes" in data["diagnosis"]:
        assert len(data["diagnosis"]["confirmed_causes"]) == 0


# ===========================================================================
# 13. Scenario 12: Issue Remains Unresolved
# ===========================================================================

def test_issue_remains_unresolved_after_check_result(tracked_cases: list[str]):
    """Scenario 12:
    - Check completion does not transition issue_condition to RESOLVED;
    - Issue condition remains UNRESOLVED.
    """
    create_payload = {
        "description": "Dispense dots are shrinking over time",
        "defect_code": "D03_INCONSISTENT_SIZE",
    }
    create_resp = client.post("/api/v1/cases", json=create_payload)
    assert create_resp.status_code == 201
    case_id = create_resp.json()["case_id"]
    tracked_cases.append(case_id)

    check_payload = {
        "check_id": "ACT01",
        "execution_status": "COMPLETED",
        "finding": "CONTRADICTS",
        "outcome": "no_blockage",
        "expected_revision": 1,
    }
    resp = client.post(f"/api/v1/cases/{case_id}/check-results", json=check_payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["issue_condition"] == "UNRESOLVED"


# ===========================================================================
# 14. Scenario 13: Mixed Question-Answer and Check-Result History
# ===========================================================================

def test_mixed_question_answer_and_check_result_history(tracked_cases: list[str]):
    """Scenario 13:
    - Rev 1: Create case
    - Rev 2: Submit check result (ACT01)
    - Rev 3: Submit question answer (Q01)
    - Rev 4: Submit check result (ACT02)
    - Verify all answers and check results are tracked in order and revision advances monotonically.
    """
    create_payload = {
        "description": "Dispense dots are shrinking over time",
        "defect_code": "D03_INCONSISTENT_SIZE",
    }
    create_resp = client.post("/api/v1/cases", json=create_payload)
    assert create_resp.status_code == 201
    case_id = create_resp.json()["case_id"]
    tracked_cases.append(case_id)

    # 1. Rev 2: Check result
    check_payload_1 = {
        "check_id": "ACT01",
        "execution_status": "COMPLETED",
        "finding": "CONTRADICTS",
        "outcome": "no_blockage",
        "expected_revision": 1,
    }
    cr_resp1 = client.post(f"/api/v1/cases/{case_id}/check-results", json=check_payload_1)
    assert cr_resp1.status_code == 200
    assert cr_resp1.json()["current_revision"] == 2

    # 2. Rev 3: Question answer
    ans_payload_1 = {
        "question_id": "Q01",
        "answer": "after_prolonged_operation",
        "expected_revision": 2,
    }
    qa_resp1 = client.post(f"/api/v1/cases/{case_id}/answers", json=ans_payload_1)
    assert qa_resp1.status_code == 200
    qa_data = qa_resp1.json()
    assert qa_data["current_revision"] == 3
    assert len(qa_data["previous_check_results"]) == 1
    assert len(qa_data["previous_answers"]) == 1

    # 3. Rev 4: Check result
    check_payload_2 = {
        "check_id": "ACT02",
        "execution_status": "COMPLETED",
        "finding": "SUPPORTS",
        "outcome": "air_bubbles_found",
        "expected_revision": 3,
    }
    cr_resp2 = client.post(f"/api/v1/cases/{case_id}/check-results", json=check_payload_2)
    assert cr_resp2.status_code == 200
    cr_data = cr_resp2.json()
    assert cr_data["current_revision"] == 4
    assert len(cr_data["previous_check_results"]) == 2
    assert len(cr_data["previous_answers"]) == 1
    assert [c["check_id"] for c in cr_data["previous_check_results"]] == ["ACT01", "ACT02"]
    assert [a["question_id"] for a in cr_data["previous_answers"]] == ["Q01"]


# ===========================================================================
# 15. Scenario 14: Committed Response Matches Persisted State
# ===========================================================================

def test_committed_response_matches_persisted_state(tracked_cases: list[str]):
    """Scenario 14:
    - Fields in response of POST check-results strictly match GET /api/v1/cases/{case_id}.
    """
    create_payload = {
        "description": "Dispense dots are shrinking over time",
        "defect_code": "D03_INCONSISTENT_SIZE",
        "material": "solder_paste",
        "method": "jetting",
    }
    create_resp = client.post("/api/v1/cases", json=create_payload)
    assert create_resp.status_code == 201
    case_id = create_resp.json()["case_id"]
    tracked_cases.append(case_id)

    check_payload = {
        "check_id": "ACT01",
        "execution_status": "COMPLETED",
        "finding": "CONTRADICTS",
        "outcome": "no_blockage",
        "finding_details": "No blockage seen",
        "expected_revision": 1,
    }
    post_resp = client.post(f"/api/v1/cases/{case_id}/check-results", json=check_payload)
    assert post_resp.status_code == 200
    post_data = post_resp.json()

    get_resp = client.get(f"/api/v1/cases/{case_id}")
    assert get_resp.status_code == 200
    get_data = get_resp.json()

    assert post_data["case_id"] == get_data["case_id"]
    assert post_data["issue_condition"] == get_data["issue_condition"]
    assert len(post_data["observations"]) == len(get_data["observations"])

    factory = get_session_factory()
    with factory() as session:
        repo = CaseRepository(session)
        loaded = repo.load_structured_case(case_id)
        assert loaded is not None
        assert loaded.analysis_revisions[-1].revision_number == post_data["current_revision"]
        assert len(loaded.previous_check_results) == len(post_data["previous_check_results"])
        assert loaded.previous_check_results[0].check_id == post_data["submitted_check_result"]["check_id"]
        assert loaded.previous_check_results[0].outcome == post_data["submitted_check_result"]["outcome"]


# ===========================================================================
# 16. Additional Scenario: Non-Executing Statuses Normalize Finding to UNKNOWN
# ===========================================================================

@pytest.mark.parametrize(
    "status_val",
    ["FAILED", "UNKNOWN", "NOT_APPLICABLE", "SKIPPED"],
)
def test_non_executing_statuses_normalize_to_unknown_finding(tracked_cases: list[str], status_val: str):
    """Verify that non-executing statuses normalize finding to UNKNOWN and add 0 observations."""
    create_payload = {
        "description": "Dispense dots are shrinking over time",
        "defect_code": "D03_INCONSISTENT_SIZE",
    }
    create_resp = client.post("/api/v1/cases", json=create_payload)
    assert create_resp.status_code == 201
    case_data = create_resp.json()
    case_id = case_data["case_id"]
    tracked_cases.append(case_id)
    initial_obs_count = len(case_data["observations"])

    check_payload = {
        "check_id": "ACT01",
        "execution_status": status_val,
        "finding": "SUPPORTS",  # Non-executing must override this to UNKNOWN
        "finding_details": f"Check status: {status_val}",
        "expected_revision": 1,
    }
    resp = client.post(f"/api/v1/cases/{case_id}/check-results", json=check_payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["current_revision"] == 2
    assert data["submitted_check_result"]["execution_status"] == status_val
    assert data["submitted_check_result"]["finding"] == "UNKNOWN"
    assert len(data["observations"]) == initial_obs_count


# ===========================================================================
# 17. Additional Scenario: Invalid UUID Format Returns 422
# ===========================================================================

def test_invalid_uuid_returns_422():
    """Verify that invalid UUID in path returns 422 with no internal error."""
    check_payload = {
        "check_id": "ACT01",
        "execution_status": "COMPLETED",
        "finding": "CONTRADICTS",
        "outcome": "no_blockage",
        "expected_revision": 1,
    }
    resp = client.post("/api/v1/cases/not-a-valid-uuid/check-results", json=check_payload)
    assert resp.status_code == 422
    assert "Invalid case ID format" in resp.json()["detail"]


# ===========================================================================
# 18. R1 Regression: Unfinished Execution Statuses Rejected with 422
# ===========================================================================

@pytest.mark.parametrize("unfinished_status", ["PENDING", "IN_PROGRESS"])
def test_unfinished_execution_status_rejected_with_422_and_no_mutation(
    tracked_cases: list[str],
    unfinished_status: str,
):
    """R1 Requirement:
    - Submitting PENDING or IN_PROGRESS returns 422 Unprocessable Entity;
    - Uses an otherwise-valid, evidence-producing payload (ACT01, SUPPORTS, blockage_found);
    - Proves rejected before evidence generation or persistence;
    - Asserts no check history, observation, revision, or current_revision mutation occurs;
    - Prior snapshots remain intact.
    """
    create_payload = {
        "description": "Dispense dots are shrinking over time",
        "defect_code": "D03_INCONSISTENT_SIZE",
        "material": "solder_paste",
        "method": "jetting",
    }
    create_resp = client.post("/api/v1/cases", json=create_payload)
    assert create_resp.status_code == 201
    case_data = create_resp.json()
    case_id = case_data["case_id"]
    tracked_cases.append(case_id)
    initial_obs_count = len(case_data["observations"])

    # Adversarial payload that WOULD create observations if processed as COMPLETED
    check_payload = {
        "check_id": "ACT01",
        "execution_status": unfinished_status,
        "finding": "SUPPORTS",
        "outcome": "blockage_found",
        "finding_details": f"Check status is {unfinished_status}",
        "expected_revision": 1,
    }
    resp = client.post(f"/api/v1/cases/{case_id}/check-results", json=check_payload)
    assert resp.status_code == 422
    error_text = resp.text
    assert "unfinished execution status" in error_text or unfinished_status in error_text

    # Verify no database mutation
    factory = get_session_factory()
    with factory() as session:
        repo = CaseRepository(session)
        assert len(repo.get_case_check_results(case_id)) == 0
        assert repo.list_case_revisions(case_id) == [1]

        obs = repo.get_case_observations(case_id)
        assert len(obs) == initial_obs_count
        assert not any(o.first_seen_revision == 2 for o in obs)

        loaded = repo.load_structured_case(case_id)
        assert loaded is not None
        assert loaded.analysis_revisions[-1].revision_number == 1
        assert len(loaded.previous_check_results) == 0
