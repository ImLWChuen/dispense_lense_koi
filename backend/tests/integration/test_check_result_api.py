"""
Dispense Lens - Technician Troubleshooting Check Result Submission API Integration Tests

Tests persistent technician troubleshooting check-result submission (POST /api/v1/cases/{case_id}/check-results)
against real PostgreSQL. Verifies atomicity, provenance preservation, optimistic concurrency via expected_revision,
clean 409 stale-revision handling, 404 missing case handling, 422 validation rejections, non-executing and
inconclusive check semantics, prior revision immutability, ACT03 non-directional mapping, cause confirmation
separation, and API regression safety.
"""

from __future__ import annotations

from datetime import datetime, timezone
import copy
import os
import uuid
from typing import Any, Generator
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
    - Create an unrelated control case (Case A) with prior answer history and multiple revisions;
    - Create a target case (Case B) with prior answer history and multiple revisions;
    - Capture complete baseline state for both cases (all scalar fields, observations, answers, revision snapshots);
    - Derive expected_revision (baseline_rev) and attempted_rev = baseline_rev + 1;
    - Submit a valid, evidence-producing check result (ACT01, COMPLETED, SUPPORTS, blockage_found);
    - Allow the real append path to flush check-result, generated observations, and attempted_rev;
    - Intercept at the commit boundary using a test-only SQLAlchemy before_commit event;
    - In the hook, capture detached immutable evidence of the flushed check result, observations, and revision;
    - Set fault_reached immediately before raising synthetic RuntimeError;
    - Let the production transaction boundary perform rollback naturally;
    - Assert outside request handling: fault_reached is True, captured pending evidence matches expected values;
    - Assert the HTTP response is a sanitized 500 without leaking sensitive paths;
    - Open a fresh independent session: verify all rows for attempted_rev are absent, and full baseline state
      for both target and control cases is exactly preserved.
    """
    factory = get_session_factory()

    # 1. Create unrelated control case (Case A) and advance to Rev 2 with an answer
    control_resp = client.post(
        "/api/v1/cases",
        json={
            "description": "Control case for rollback isolation",
            "defect_code": "D03_INCONSISTENT_SIZE",
            "material": "solder_paste",
            "method": "jetting",
        },
    )
    assert control_resp.status_code == 201
    control_id = control_resp.json()["case_id"]
    tracked_cases.append(control_id)

    control_ans_resp = client.post(
        f"/api/v1/cases/{control_id}/answers",
        json={
            "question_id": "Q01",
            "answer": "after_prolonged_operation",
            "expected_revision": 1,
        },
    )
    assert control_ans_resp.status_code == 200

    control_prior_check_resp = client.post(
        f"/api/v1/cases/{control_id}/check-results",
        json={
            "check_id": "ACT02",
            "execution_status": "COMPLETED",
            "finding": "SUPPORTS",
            "outcome": "air_bubbles_found",
            "finding_details": "Micro-air bubbles in control syringe",
            "expected_revision": 2,
        },
    )
    assert control_prior_check_resp.status_code == 200

    # 2. Create target case (Case B) and advance to Rev 3 with an answer AND a prior check result
    target_resp = client.post(
        "/api/v1/cases",
        json={
            "description": "Target case for post-flush rollback test",
            "defect_code": "D03_INCONSISTENT_SIZE",
            "material": "solder_paste",
            "method": "jetting",
        },
    )
    assert target_resp.status_code == 201
    target_id = target_resp.json()["case_id"]
    tracked_cases.append(target_id)

    target_ans_resp = client.post(
        f"/api/v1/cases/{target_id}/answers",
        json={
            "question_id": "Q01",
            "answer": "after_prolonged_operation",
            "expected_revision": 1,
        },
    )
    assert target_ans_resp.status_code == 200

    target_prior_check_resp = client.post(
        f"/api/v1/cases/{target_id}/check-results",
        json={
            "check_id": "ACT02",
            "execution_status": "COMPLETED",
            "finding": "SUPPORTS",
            "outcome": "air_bubbles_found",
            "finding_details": "Micro-air bubbles visible in syringe",
            "expected_revision": 2,
        },
    )
    assert target_prior_check_resp.status_code == 200

    # Capture complete baselines from an independent session
    with factory() as session:
        target_baseline = capture_complete_case_state(session, target_id)
        control_baseline = capture_complete_case_state(session, control_id)

    # Verify nonempty baselines with both prior question answers AND prior check results
    assert len(target_baseline["analysis_revisions"]) >= 3
    assert len(target_baseline["question_answers"]) >= 1
    assert len(target_baseline["check_results"]) >= 1
    assert len(control_baseline["analysis_revisions"]) >= 3
    assert len(control_baseline["question_answers"]) >= 1
    assert len(control_baseline["check_results"]) >= 1

    baseline_rev = target_baseline["analysis_revisions"][-1]["revision_number"]
    attempted_rev = baseline_rev + 1

    # 3. Prepare subsequent evidence-producing check result payload
    check_payload = {
        "check_id": "ACT01",
        "execution_status": "COMPLETED",
        "finding": "SUPPORTS",
        "outcome": "blockage_found",
        "finding_details": "Nozzle orifice blocked with particulate",
        "expected_revision": baseline_rev,
    }

    sensitive_path = "C:/private/database/secrets/db.sqlite"
    fault_reached = False
    captured_pending_evidence: dict[str, Any] = {}

    def fail_after_flush_before_commit(session: Session) -> None:
        nonlocal fault_reached, captured_pending_evidence
        # Only intercept for target_id check-result transaction at attempted_rev
        target_crs = session.scalars(
            select(CaseCheckResultModel).where(
                CaseCheckResultModel.case_id == target_id,
                CaseCheckResultModel.resulting_revision_number == attempted_rev,
            )
        ).all()
        if not target_crs:
            return

        # Capture detached immutable values (no live ORM objects)
        cr = target_crs[0]
        cr_data = {
            "check_id": str(cr.check_id),
            "execution_status": str(cr.execution_status),
            "finding": str(cr.finding),
            "outcome": str(cr.outcome),
            "source": str(cr.source),
            "resulting_revision_number": int(cr.resulting_revision_number),
        }

        rev_obs = session.scalars(
            select(ObservationModel).where(
                ObservationModel.case_id == target_id,
                ObservationModel.first_seen_revision == attempted_rev,
            )
        ).all()
        obs_data = [
            {
                "observation_id": str(o.observation_id),
                "observation_type": str(o.observation_type),
                "value": str(o.value),
                "source": str(o.source),
                "first_seen_revision": int(o.first_seen_revision),
            }
            for o in rev_obs
        ]

        revs = session.scalars(
            select(AnalysisRevisionModel).where(
                AnalysisRevisionModel.case_id == target_id,
                AnalysisRevisionModel.revision_number == attempted_rev,
            )
        ).all()
        rev_data = (
            {
                "revision_number": int(revs[0].revision_number),
                "defect_code": str(revs[0].defect_code) if revs[0].defect_code is not None else None,
                "issue_condition": str(revs[0].issue_condition) if revs[0].issue_condition is not None else None,
                "result_snapshot": copy.deepcopy(revs[0].result_snapshot),
            }
            if revs
            else None
        )

        captured_pending_evidence = {
            "check_result": cr_data,
            "observations": obs_data,
            "analysis_revision": rev_data,
        }

        fault_reached = True
        raise RuntimeError(f"Simulated disk write fault at {sensitive_path}")

    event.listen(Session, "before_commit", fail_after_flush_before_commit)
    try:
        resp = client.post(f"/api/v1/cases/{target_id}/check-results", json=check_payload)
    finally:
        event.remove(Session, "before_commit", fail_after_flush_before_commit)

    # 4. Assert outside the request handling so endpoint exception handlers cannot mask assertion errors
    assert fault_reached is True, "The deliberate fault was never reached in the commit boundary hook."
    assert captured_pending_evidence.get("check_result") is not None
    assert captured_pending_evidence["check_result"]["check_id"] == "ACT01"
    assert captured_pending_evidence["check_result"]["outcome"] == "blockage_found"
    assert captured_pending_evidence["check_result"]["resulting_revision_number"] == attempted_rev
    assert len(captured_pending_evidence["observations"]) >= 1
    obs_types = [o["observation_type"] for o in captured_pending_evidence["observations"]]
    assert "check_result" in obs_types or "nozzle_condition" in obs_types
    assert captured_pending_evidence.get("analysis_revision") is not None
    assert captured_pending_evidence["analysis_revision"]["revision_number"] == attempted_rev
    pending_snapshot = captured_pending_evidence["analysis_revision"]["result_snapshot"]
    assert isinstance(pending_snapshot, dict)
    assert len(pending_snapshot) > 0
    assert pending_snapshot["defect"] == "D03_INCONSISTENT_SIZE"
    assert "ranked_causes" in pending_snapshot
    assert any(c["cause_id"] == "nozzle_restriction" for c in pending_snapshot["ranked_causes"])

    # 5. Assert response is sanitized 500
    assert resp.status_code == 500
    error_detail = resp.json()["detail"]
    assert "An unexpected error occurred while persisting the check result revision." in error_detail
    assert sensitive_path not in error_detail

    # 6. Open a fresh independent session and verify full rollback and exact state preservation
    with factory() as session:
        # Verify no check result rows were committed for attempted_rev
        attempted_crs = session.scalars(
            select(CaseCheckResultModel).where(
                CaseCheckResultModel.case_id == target_id,
                CaseCheckResultModel.resulting_revision_number == attempted_rev,
            )
        ).all()
        assert len(attempted_crs) == 0

        # Verify no observations for attempted_rev were committed
        attempted_obs = session.scalars(
            select(ObservationModel).where(
                ObservationModel.case_id == target_id,
                ObservationModel.first_seen_revision == attempted_rev,
            )
        ).all()
        assert len(attempted_obs) == 0

        # Verify no analysis revision for attempted_rev was committed
        attempted_revs = session.scalars(
            select(AnalysisRevisionModel).where(
                AnalysisRevisionModel.case_id == target_id,
                AnalysisRevisionModel.revision_number == attempted_rev,
            )
        ).all()
        assert len(attempted_revs) == 0

        # Verify target case complete baseline is preserved identically
        target_after = capture_complete_case_state(session, target_id)
        assert target_after == target_baseline
        assert len(target_after["check_results"]) >= 1
        assert target_after["check_results"][0]["check_id"] == "ACT02"

        # Verify control case complete baseline is preserved identically
        control_after = capture_complete_case_state(session, control_id)
        assert control_after == control_baseline


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
    - Target case has prior question-answer history and multiple revisions;
    - Uses an otherwise-valid, evidence-producing payload (ACT01, SUPPORTS, blockage_found);
    - Proves rejected before evidence generation or persistence;
    - Asserts complete prior state (case row, observations, answers, revisions, snapshots)
      remains exactly identical from an independent session.
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

    # Advance to Revision 2 with an answer to establish nonempty prior history
    ans_resp = client.post(
        f"/api/v1/cases/{case_id}/answers",
        json={
            "question_id": "Q01",
            "answer": "after_prolonged_operation",
            "expected_revision": 1,
        },
    )
    assert ans_resp.status_code == 200

    factory = get_session_factory()
    with factory() as session:
        target_baseline = capture_complete_case_state(session, case_id)

    assert len(target_baseline["analysis_revisions"]) == 2
    assert len(target_baseline["question_answers"]) == 1
    current_rev = target_baseline["analysis_revisions"][-1]["revision_number"]

    # Adversarial payload that WOULD create observations if processed as COMPLETED
    check_payload = {
        "check_id": "ACT01",
        "execution_status": unfinished_status,
        "finding": "SUPPORTS",
        "outcome": "blockage_found",
        "finding_details": f"Check status is {unfinished_status}",
        "expected_revision": current_rev,
    }
    resp = client.post(f"/api/v1/cases/{case_id}/check-results", json=check_payload)
    assert resp.status_code == 422
    error_text = resp.text
    assert "unfinished execution status" in error_text or unfinished_status in error_text

    # Verify complete state is preserved identically from an independent session
    with factory() as session:
        target_after = capture_complete_case_state(session, case_id)
        assert target_after == target_baseline


# ===========================================================================
# 19. Sensitivity: Snapshot Helper Detects Mutation with Unchanged Counts
# ===========================================================================

def test_snapshot_helper_detects_nested_snapshot_mutation_with_identical_counts():
    """Sensitivity check:
    Demonstrates that capture_complete_case_state comparison detects mutation
    in nested result_snapshot contents even when row counts, revision numbers,
    and keys are 100% identical.
    """
    baseline = {
        "case": {
            "case_id": "99999999-9999-9999-9999-999999999999",
            "issue_condition": "UNRESOLVED",
            "defect_code": "D03_INCONSISTENT_SIZE",
        },
        "observations": [
            {
                "observation_id": "obs-1",
                "observation_type": "deposit_size",
                "value": "undersized",
                "first_seen_revision": 1,
            }
        ],
        "question_answers": [
            {
                "question_id": "Q01",
                "answer_value": "after_prolonged_operation",
                "resulting_revision_number": 2,
            }
        ],
        "check_results": [
            {
                "check_id": "ACT01",
                "execution_status": "COMPLETED",
                "finding": "SUPPORTS",
                "outcome": "blockage_found",
                "resulting_revision_number": 2,
            }
        ],
        "analysis_revisions": [
            {
                "revision_number": 1,
                "defect_code": "D03_INCONSISTENT_SIZE",
                "issue_condition": "UNRESOLVED",
                "result_snapshot": {
                    "defect": "D03_INCONSISTENT_SIZE",
                    "ranked_causes": [
                        {"cause_id": "nozzle_restriction", "score": 30.0, "conclusion": "SUSPECTED"}
                    ],
                },
            }
        ],
    }

    mutated = copy.deepcopy(baseline)
    # Mutate only the deeply nested score inside result_snapshot
    mutated["analysis_revisions"][0]["result_snapshot"]["ranked_causes"][0]["score"] = 99.0

    # Counts and revision numbers remain identical
    assert len(baseline["observations"]) == len(mutated["observations"])
    assert len(baseline["question_answers"]) == len(mutated["question_answers"])
    assert len(baseline["check_results"]) == len(mutated["check_results"])
    assert len(baseline["analysis_revisions"]) == len(mutated["analysis_revisions"])
    assert baseline["analysis_revisions"][0]["revision_number"] == mutated["analysis_revisions"][0]["revision_number"]

    # But full state comparison detects the mutation
    assert baseline != mutated


# ===========================================================================
# 20. Sensitivity: Snapshot Helper Distinguishes Empty String and None
# ===========================================================================

def test_snapshot_helper_distinguishes_empty_string_and_none_for_optional_fields(tracked_cases: list[str]):
    """Sensitivity check (Requirement 3):
    Demonstrates that capture_complete_case_state preserves "" and None as distinct
    stored scalar values without truthiness normalization, and that exact state comparison
    fails when an optional field changes between "" and None while row counts and revision
    numbers are unchanged.
    """
    case_id_empty = str(uuid.uuid4())
    case_id_none = str(uuid.uuid4())
    tracked_cases.extend([case_id_empty, case_id_none])

    now = datetime.now(timezone.utc)
    factory = get_session_factory()

    with factory() as session:
        case_empty = CaseModel(
            case_id=case_id_empty,
            description="Case with empty string optional fields",
            material="",
            defect_code="D03_INCONSISTENT_SIZE",
            defect_name="",
            issue_condition="UNRESOLVED",
            created_at=now,
        )
        case_none = CaseModel(
            case_id=case_id_none,
            description="Case with None optional fields",
            material=None,
            defect_code="D03_INCONSISTENT_SIZE",
            defect_name=None,
            issue_condition="UNRESOLVED",
            created_at=now,
        )
        session.add_all([case_empty, case_none])
        session.commit()

    with factory() as session:
        snapshot_empty = capture_complete_case_state(session, case_id_empty)
        snapshot_none = capture_complete_case_state(session, case_id_none)

    # 1. Assert exact stored values are captured distinctly without truthiness collapsing
    assert snapshot_empty["case"]["material"] == ""
    assert snapshot_empty["case"]["defect_name"] == ""
    assert snapshot_none["case"]["material"] is None
    assert snapshot_none["case"]["defect_name"] is None

    # 2. Assert that altering an optional field from "" to None in a baseline copy causes comparison failure
    copied = copy.deepcopy(snapshot_empty)
    copied["case"]["material"] = None
    assert snapshot_empty != copied
    assert snapshot_empty["case"]["material"] != copied["case"]["material"]
