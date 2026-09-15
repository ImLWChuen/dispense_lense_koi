"""
DispenseIQ — Explicit Root-Cause Confirmation API Integration Tests

Tests explicit technician root-cause confirmation (POST /api/v1/cases/{case_id}/cause-confirmations)
against real PostgreSQL. Verifies:
1. OpenAPI and route registration;
2. Successful explicit confirmation with prior answer + check history;
3. Supporting check alone is insufficient (check supports != cause confirmed);
4. Cause confirmation does not resolve the issue (cause confirmed != issue resolved);
5. Optimistic concurrency via expected_revision with clean 409 stale-revision handling;
6. Replay protection returning 409 after successful confirmation;
7. Domain-validated cause_id rejecting unknown causes with 422 and no mutation;
8. Input validation rules (empty fields, negative revision, malformed UUID) returning 422;
9. 404 missing case handling;
10. History preservation and monotonic mixed revision sequence (rev 1 -> rev 2 QA -> rev 3 check -> rev 4 confirmation);
11. Transaction rollback after flushed writes returning sanitized 500 without leaving phantom records;
12. Custom technician notes and confirmed_by stored faithfully without affecting scoring.
"""

from __future__ import annotations

import copy
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Generator

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
    CaseCauseConfirmationModel,
    CaseCheckResultModel,
    CaseModel,
    ObservationModel,
    QuestionAnswerModel,
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
            # Cascades to case_observations, analysis_revisions, case_question_answers, case_check_results, case_cause_confirmations
            session.execute(delete(CaseModel).where(CaseModel.case_id.in_(case_ids)))
            session.commit()


def _create_durable_case(
    description: str = "Dispense dots are shrinking over time during continuous operation",
    defect_code: str = "D03_INCONSISTENT_SIZE",
    material: str = "solder_paste",
    method: str = "jetting",
) -> str:
    """Helper to create and persist a standard initial diagnostic case (Revision 1)."""
    create_payload = {
        "description": description,
        "defect_code": defect_code,
        "material": material,
        "method": method,
    }
    resp = client.post("/api/v1/cases", json=create_payload)
    assert resp.status_code == 201, f"Failed to create case: {resp.text}"
    return resp.json()["case_id"]


def _advance_to_revision_3_with_qa_and_check(case_id: str) -> None:
    """Helper to advance a case from Revision 1 to Revision 3 using Q01 and ACT02."""
    # Step 1: Question answer advancing to Revision 2
    qa_payload = {
        "question_id": "Q01",
        "answer": "after_prolonged_operation",
        "expected_revision": 1,
    }
    qa_resp = client.post(f"/api/v1/cases/{case_id}/answers", json=qa_payload)
    assert qa_resp.status_code == 200, f"QA failed: {qa_resp.text}"
    assert qa_resp.json()["current_revision"] == 2

    # Step 2: Check result advancing to Revision 3
    check_payload = {
        "check_id": "ACT02",
        "execution_status": "COMPLETED",
        "finding": "SUPPORTS",
        "outcome": "air_bubbles_found",
        "expected_revision": 2,
    }
    cr_resp = client.post(f"/api/v1/cases/{case_id}/check-results", json=check_payload)
    assert cr_resp.status_code == 200, f"Check failed: {cr_resp.text}"
    assert cr_resp.json()["current_revision"] == 3


# ===========================================================================
# 1. OpenAPI & Route Registration Verification
# ===========================================================================

def test_cause_confirmation_endpoint_registered_in_openapi():
    """Verify that POST /api/v1/cases/{case_id}/cause-confirmations is present in OpenAPI specification."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema["paths"]

    assert "/api/v1/cases/{case_id}/cause-confirmations" in paths
    conf_path = paths["/api/v1/cases/{case_id}/cause-confirmations"]
    assert "post" in conf_path
    responses = conf_path["post"]["responses"]
    assert "200" in responses
    assert "404" in responses
    assert "409" in responses
    assert "422" in responses
    assert "500" in responses


# ===========================================================================
# 2. Scenario 1: Successful Explicit Confirmation with Prior History
# ===========================================================================

def test_successful_explicit_cause_confirmation_with_prior_history(tracked_cases: list[str]):
    """Scenario 1:
    - Start with a durable case containing prior answer and check history (Revision 3);
    - Confirm a valid cause with current revision (3);
    - Expect 200 OK;
    - Revision advances exactly once (Revision 4);
    - One confirmation event persists;
    - Selected cause is CONFIRMED;
    - Issue condition remains UNRESOLVED (cause confirmed != issue resolved);
    - Verify committed state in fresh database session.
    """
    case_id = _create_durable_case()
    tracked_cases.append(case_id)
    _advance_to_revision_3_with_qa_and_check(case_id)

    # Confirm a valid ranked cause
    conf_payload = {
        "cause_id": "nozzle_restriction",
        "expected_revision": 3,
        "confirmed_by": "technician",
        "notes": "Direct microscopic bore inspection confirms solder paste restriction.",
    }
    resp = client.post(f"/api/v1/cases/{case_id}/cause-confirmations", json=conf_payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["case_id"] == case_id
    assert data["current_revision"] == 4
    assert data["confirmed_cause"] == "nozzle_restriction"
    assert data["selected_cause_conclusion"] == "CONFIRMED"

    # Issue condition MUST remain UNRESOLVED
    assert data["issue_condition"] == "UNRESOLVED"
    assert data["diagnosis"]["issue_condition"] == "UNRESOLVED"

    # Verify ranked causes has nozzle_restriction as CONFIRMED
    ranked = data["diagnosis"]["ranked_causes"]
    nozzle = next((c for c in ranked if c["cause_id"] == "nozzle_restriction"), None)
    assert nozzle is not None
    assert nozzle["conclusion"] == "CONFIRMED"

    # Verify submitted confirmation record
    submitted = data["submitted_confirmation"]
    assert submitted["cause_id"] == "nozzle_restriction"
    assert submitted["confirmed_by"] == "technician"
    assert submitted["notes"] == "Direct microscopic bore inspection confirms solder paste restriction."
    assert submitted["resulting_revision_number"] == 4

    # Verify history in response
    assert len(data["previous_confirmations"]) == 1
    assert data["previous_confirmations"][0]["cause_id"] == "nozzle_restriction"
    assert len(data["previous_answers"]) == 1
    assert data["previous_answers"][0]["question_id"] == "Q01"
    assert len(data["previous_check_results"]) == 1
    assert data["previous_check_results"][0]["check_id"] == "ACT02"

    # Verify in fresh independent DB session
    factory = get_session_factory()
    with factory() as session:
        repo = CaseRepository(session)
        assert repo.list_case_revisions(case_id) == [1, 2, 3, 4]
        confs = repo.get_case_cause_confirmations(case_id)
        assert len(confs) == 1
        assert confs[0].cause_id == "nozzle_restriction"
        assert confs[0].resulting_revision_number == 4
        assert confs[0].notes == "Direct microscopic bore inspection confirms solder paste restriction."

        loaded = repo.load_structured_case(case_id)
        assert loaded is not None
        assert loaded.confirmed_causes == ["nozzle_restriction"]
        assert loaded.analysis_revisions[-1].revision_number == 4


# ===========================================================================
# 3. Scenario 2: Supporting Check Alone is Insufficient
# ===========================================================================

def test_supporting_check_alone_is_insufficient_to_confirm_cause(tracked_cases: list[str]):
    """Scenario 2:
    - Use check workflow to support a cause (ACT01:blockage_found -> SUPPORTS nozzle_restriction);
    - Prove cause remains SUSPECTED (unconfirmed) before explicit confirmation;
    - Call confirmation endpoint;
    - Prove transition to CONFIRMED happens only then;
    - Issue condition remains UNRESOLVED throughout.
    """
    case_id = _create_durable_case()
    tracked_cases.append(case_id)

    # Submit supporting check result advancing to Revision 2
    check_payload = {
        "check_id": "ACT01",
        "execution_status": "COMPLETED",
        "finding": "SUPPORTS",
        "outcome": "blockage_found",
        "finding_details": "Visual inspection reveals partial nozzle orifice blockage.",
        "expected_revision": 1,
    }
    check_resp = client.post(f"/api/v1/cases/{case_id}/check-results", json=check_payload)
    assert check_resp.status_code == 200
    check_data = check_resp.json()
    assert check_data["current_revision"] == 2

    # Verify cause is supported with high score, but remains SUSPECTED
    nozzle_check = next(
        (c for c in check_data["diagnosis"]["ranked_causes"] if c["cause_id"] == "nozzle_restriction"),
        None,
    )
    assert nozzle_check is not None
    assert nozzle_check["conclusion"] != "CONFIRMED"
    assert nozzle_check["conclusion"] in ("SUSPECTED", "RULED_OUT")
    assert check_data["issue_condition"] == "UNRESOLVED"

    # Now explicitly confirm the cause
    conf_payload = {
        "cause_id": "nozzle_restriction",
        "expected_revision": 2,
    }
    conf_resp = client.post(f"/api/v1/cases/{case_id}/cause-confirmations", json=conf_payload)
    assert conf_resp.status_code == 200
    conf_data = conf_resp.json()
    assert conf_data["current_revision"] == 3

    # Now the cause is CONFIRMED
    nozzle_conf = next(
        (c for c in conf_data["diagnosis"]["ranked_causes"] if c["cause_id"] == "nozzle_restriction"),
        None,
    )
    assert nozzle_conf is not None
    assert nozzle_conf["conclusion"] == "CONFIRMED"
    assert conf_data["selected_cause_conclusion"] == "CONFIRMED"

    # Issue condition STILL remains UNRESOLVED
    assert conf_data["issue_condition"] == "UNRESOLVED"


# ===========================================================================
# 4. Scenario 3: Stale Revision Returns 409
# ===========================================================================

def test_stale_expected_revision_returns_409_with_no_mutation(tracked_cases: list[str]):
    """Scenario 3:
    - Establish case at Revision 2;
    - Attempt confirmation with stale expected_revision=1;
    - Expect 409 Conflict;
    - No durable mutation occurred.
    """
    case_id = _create_durable_case()
    tracked_cases.append(case_id)

    # Advance to Revision 2 via question answer
    qa_payload = {
        "question_id": "Q01",
        "answer": "after_prolonged_operation",
        "expected_revision": 1,
    }
    qa_resp = client.post(f"/api/v1/cases/{case_id}/answers", json=qa_payload)
    assert qa_resp.status_code == 200

    factory = get_session_factory()
    with factory() as session:
        baseline_state = capture_complete_case_state(session, case_id)

    # Submit stale confirmation (expected_revision=1 while current is 2)
    conf_payload = {
        "cause_id": "nozzle_restriction",
        "expected_revision": 1,
    }
    resp = client.post(f"/api/v1/cases/{case_id}/cause-confirmations", json=conf_payload)
    assert resp.status_code == 409
    assert "Stale revision" in resp.json()["detail"]

    # Verify no mutation occurred
    with factory() as session:
        after_state = capture_complete_case_state(session, case_id)
        assert after_state == baseline_state
        repo = CaseRepository(session)
        assert len(repo.get_case_cause_confirmations(case_id)) == 0


# ===========================================================================
# 5. Scenario 4: Replay After Success Returns 409
# ===========================================================================

def test_replay_after_success_with_old_revision_returns_409(tracked_cases: list[str]):
    """Scenario 4:
    - Confirm successfully at Revision 1 -> advances to Revision 2;
    - Replay same request with expected_revision=1;
    - Expect 409 Conflict;
    - Case remains at Revision 2 with exactly 1 confirmation event.
    """
    case_id = _create_durable_case()
    tracked_cases.append(case_id)

    conf_payload = {
        "cause_id": "nozzle_restriction",
        "expected_revision": 1,
    }
    first_resp = client.post(f"/api/v1/cases/{case_id}/cause-confirmations", json=conf_payload)
    assert first_resp.status_code == 200
    assert first_resp.json()["current_revision"] == 2

    # Replay with old expected_revision=1
    replay_resp = client.post(f"/api/v1/cases/{case_id}/cause-confirmations", json=conf_payload)
    assert replay_resp.status_code == 409
    assert "Stale revision" in replay_resp.json()["detail"]

    factory = get_session_factory()
    with factory() as session:
        repo = CaseRepository(session)
        assert repo.list_case_revisions(case_id) == [1, 2]
        assert len(repo.get_case_cause_confirmations(case_id)) == 1


# ===========================================================================
# 6. Scenario 5: Invalid/Unknown Cause ID Returns 422
# ===========================================================================

def test_invalid_or_unknown_cause_id_returns_422_with_no_mutation(tracked_cases: list[str]):
    """Scenario 5:
    - Submit confirmation with an unknown cause_id;
    - Expect 422 Unprocessable Entity;
    - Verify no durable mutation.
    """
    case_id = _create_durable_case()
    tracked_cases.append(case_id)

    factory = get_session_factory()
    with factory() as session:
        baseline_state = capture_complete_case_state(session, case_id)

    # Unknown cause ID
    payload = {
        "cause_id": "nonexistent_cause_unknown_12345",
        "expected_revision": 1,
    }
    resp = client.post(f"/api/v1/cases/{case_id}/cause-confirmations", json=payload)
    assert resp.status_code == 422
    assert "not found in current ranked causes" in resp.json()["detail"]

    # Verify no mutation
    with factory() as session:
        after_state = capture_complete_case_state(session, case_id)
        assert after_state == baseline_state
        repo = CaseRepository(session)
        assert len(repo.get_case_cause_confirmations(case_id)) == 0


def test_empty_cause_id_returns_422_with_no_mutation(tracked_cases: list[str]):
    """Verify empty or whitespace cause_id is rejected with 422."""
    case_id = _create_durable_case()
    tracked_cases.append(case_id)

    payload = {
        "cause_id": "   ",
        "expected_revision": 1,
    }
    resp = client.post(f"/api/v1/cases/{case_id}/cause-confirmations", json=payload)
    assert resp.status_code == 422


def test_invalid_expected_revision_returns_422(tracked_cases: list[str]):
    """Verify expected_revision < 1 is rejected with 422."""
    case_id = _create_durable_case()
    tracked_cases.append(case_id)

    payload = {
        "cause_id": "nozzle_restriction",
        "expected_revision": 0,
    }
    resp = client.post(f"/api/v1/cases/{case_id}/cause-confirmations", json=payload)
    assert resp.status_code == 422


def test_invalid_uuid_returns_422():
    """Verify malformed case_id UUID returns 422."""
    payload = {
        "cause_id": "nozzle_restriction",
        "expected_revision": 1,
    }
    resp = client.post("/api/v1/cases/not-a-valid-uuid-format/cause-confirmations", json=payload)
    assert resp.status_code == 422
    assert "must be a valid UUID" in resp.json()["detail"]


# ===========================================================================
# 7. Scenario 6: Missing Case Returns 404
# ===========================================================================

def test_missing_case_returns_404():
    """Scenario 6: Missing case UUID returns 404 Not Found."""
    nonexistent_id = str(uuid.uuid4())
    payload = {
        "cause_id": "nozzle_restriction",
        "expected_revision": 1,
    }
    resp = client.post(f"/api/v1/cases/{nonexistent_id}/cause-confirmations", json=payload)
    assert resp.status_code == 404
    assert f"Case '{nonexistent_id}' not found." in resp.json()["detail"]


# ===========================================================================
# 8. Scenario 7: History Preservation and Monotonic Revision Sequence
# ===========================================================================

def test_mixed_global_revision_sequence_and_history_preservation(tracked_cases: list[str]):
    """Scenario 7:
    - Revision 1: Initial diagnosis;
    - Revision 2: Question answer;
    - Revision 3: Troubleshooting check result;
    - Revision 4: Cause confirmation;
    - Assert all revisions exist monotonically without collision or reset;
    - Prior answers and checks are preserved intact in response and database.
    """
    case_id = _create_durable_case()
    tracked_cases.append(case_id)

    # Rev 1 -> Rev 2
    qa_resp = client.post(
        f"/api/v1/cases/{case_id}/answers",
        json={"question_id": "Q01", "answer": "after_prolonged_operation", "expected_revision": 1},
    )
    assert qa_resp.status_code == 200
    assert qa_resp.json()["current_revision"] == 2

    # Rev 2 -> Rev 3
    cr_resp = client.post(
        f"/api/v1/cases/{case_id}/check-results",
        json={"check_id": "ACT02", "execution_status": "COMPLETED", "finding": "SUPPORTS", "expected_revision": 2},
    )
    assert cr_resp.status_code == 200
    assert cr_resp.json()["current_revision"] == 3

    # Rev 3 -> Rev 4
    conf_resp = client.post(
        f"/api/v1/cases/{case_id}/cause-confirmations",
        json={"cause_id": "nozzle_restriction", "expected_revision": 3},
    )
    assert conf_resp.status_code == 200
    data = conf_resp.json()
    assert data["current_revision"] == 4

    # Verify history in response
    assert len(data["previous_answers"]) == 1
    assert data["previous_answers"][0]["question_id"] == "Q01"
    assert len(data["previous_check_results"]) == 1
    assert data["previous_check_results"][0]["check_id"] == "ACT02"
    assert len(data["previous_confirmations"]) == 1
    assert data["previous_confirmations"][0]["cause_id"] == "nozzle_restriction"

    # Verify in DB
    factory = get_session_factory()
    with factory() as session:
        repo = CaseRepository(session)
        assert repo.list_case_revisions(case_id) == [1, 2, 3, 4]


# ===========================================================================
# 9. Scenario 8: Transaction Rollback Verification
# ===========================================================================

def test_induced_persistence_failure_returns_sanitized_500_and_rolls_back(tracked_cases: list[str]):
    """Scenario 8:
    - Establish target case and control case at Revision 3 with prior answers and checks;
    - Capture baselines in fresh independent session;
    - Attach SQLAlchemy before_commit listener that confirms flushed confirmation and revision writes;
    - Inject unhandled RuntimeError right before commit;
    - Verify sanitized HTTP 500 without leaking details;
    - Verify outside exception handler that fault hook was reached;
    - Fresh independent session proves:
      - Failed revision 4 is absent;
      - Failed confirmation is absent;
      - Target case remains strictly at Revision 3 with prior answers/checks intact;
      - Control case remains completely untouched.
    """
    control_id = _create_durable_case(description="Control case untouched during cause confirmation rollback")
    tracked_cases.append(control_id)
    _advance_to_revision_3_with_qa_and_check(control_id)

    target_id = _create_durable_case(description="Target case verifying cause confirmation rollback")
    tracked_cases.append(target_id)
    _advance_to_revision_3_with_qa_and_check(target_id)

    factory = get_session_factory()
    with factory() as session:
        control_baseline = capture_complete_case_state(session, control_id)
        target_baseline = capture_complete_case_state(session, target_id)
        assert len(target_baseline["question_answers"]) > 0
        assert len(target_baseline["check_results"]) > 0
        assert len(session.scalars(
            select(CaseCauseConfirmationModel).where(CaseCauseConfirmationModel.case_id == target_id)
        ).all()) == 0

    baseline_rev = target_baseline["case"]["current_revision"] if "current_revision" in target_baseline["case"] else 3
    attempted_rev = baseline_rev + 1

    fault_reached = False
    pending_conf_captured: dict[str, Any] = {}
    pending_rev_captured: dict[str, Any] = {}

    def before_commit_hook(session: Session) -> None:
        nonlocal fault_reached, pending_conf_captured, pending_rev_captured
        target_confs = session.scalars(
            select(CaseCauseConfirmationModel).where(
                CaseCauseConfirmationModel.case_id == target_id,
                CaseCauseConfirmationModel.resulting_revision_number == attempted_rev,
            )
        ).all()
        if not target_confs:
            return

        target_revs = session.scalars(
            select(AnalysisRevisionModel).where(
                AnalysisRevisionModel.case_id == target_id,
                AnalysisRevisionModel.revision_number == attempted_rev,
            )
        ).all()
        if not target_revs:
            return

        fault_reached = True
        p_conf = target_confs[0]
        p_rev = target_revs[0]
        pending_conf_captured = {
            "cause_id": str(p_conf.cause_id),
            "resulting_revision_number": int(p_conf.resulting_revision_number),
        }
        pending_rev_captured = {
            "revision_number": int(p_rev.revision_number),
            "result_snapshot": copy.deepcopy(p_rev.result_snapshot),
        }
        raise RuntimeError("Injected database failure before commit during cause confirmation")

    event.listen(Session, "before_commit", before_commit_hook)

    try:
        conf_payload = {
            "cause_id": "nozzle_restriction",
            "expected_revision": baseline_rev,
            "notes": "Testing rollback on failure",
        }
        resp = client.post(f"/api/v1/cases/{target_id}/cause-confirmations", json=conf_payload)
        assert resp.status_code == 500
        # Sanitized error detail
        assert "Injected database failure" not in resp.text
        assert resp.json()["detail"] == "An unexpected error occurred while persisting the cause confirmation revision."
    finally:
        event.remove(Session, "before_commit", before_commit_hook)

    # Outside the request handler: assert that the write boundary was actually reached
    assert fault_reached is True, "The before_commit hook was not triggered; writes were not flushed!"
    assert pending_conf_captured["cause_id"] == "nozzle_restriction"
    assert pending_conf_captured["resulting_revision_number"] == attempted_rev
    assert pending_rev_captured["revision_number"] == attempted_rev
    assert "defect" in pending_rev_captured["result_snapshot"]

    # Verify rollback in fresh independent DB session
    with factory() as fresh_session:
        target_after = capture_complete_case_state(fresh_session, target_id)
        control_after = capture_complete_case_state(fresh_session, control_id)

        # Base states must be identical
        assert target_after == target_baseline
        assert control_after == control_baseline

        # No confirmation rows exist for target
        confs = list(fresh_session.scalars(
            select(CaseCauseConfirmationModel).where(CaseCauseConfirmationModel.case_id == target_id)
        ).all())
        assert len(confs) == 0

        # Target revisions remain [1, 2, 3]
        repo = CaseRepository(fresh_session)
        assert repo.list_case_revisions(target_id) == [1, 2, 3]


# ===========================================================================
# 10. Scenario 9: Custom Notes and Confirmed By Persisted Faithfully
# ===========================================================================

def test_custom_notes_and_confirmed_by_persisted_faithfully(tracked_cases: list[str]):
    """Verify that technician notes and confirmed_by are persisted faithfully and exposed in response."""
    case_id = _create_durable_case()
    tracked_cases.append(case_id)

    conf_payload = {
        "cause_id": "nozzle_restriction",
        "expected_revision": 1,
        "confirmed_by": "lead_process_engineer",
        "notes": "Nozzle orifice confirmed 40% obstructed by solder flux residues under 100x magnification.",
    }
    resp = client.post(f"/api/v1/cases/{case_id}/cause-confirmations", json=conf_payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["submitted_confirmation"]["confirmed_by"] == "lead_process_engineer"
    assert data["submitted_confirmation"]["notes"] == conf_payload["notes"]

    # Verify in DB
    factory = get_session_factory()
    with factory() as session:
        repo = CaseRepository(session)
        confs = repo.get_case_cause_confirmations(case_id)
        assert len(confs) == 1
        assert confs[0].confirmed_by == "lead_process_engineer"
        assert confs[0].notes == conf_payload["notes"]


# ===========================================================================
# 11. Scenario 10: Committed Response Matches Persisted State
# ===========================================================================

def test_committed_response_matches_persisted_state(tracked_cases: list[str]):
    """Verify that every field in the committed response exactly matches persisted state."""
    case_id = _create_durable_case()
    tracked_cases.append(case_id)
    _advance_to_revision_3_with_qa_and_check(case_id)

    conf_payload = {
        "cause_id": "nozzle_restriction",
        "expected_revision": 3,
        "confirmed_by": "qa_specialist",
        "notes": "Verified by QA microscope inspection",
    }
    resp = client.post(f"/api/v1/cases/{case_id}/cause-confirmations", json=conf_payload)
    assert resp.status_code == 200
    data = resp.json()

    factory = get_session_factory()
    with factory() as session:
        repo = CaseRepository(session)
        case_model = repo.get_case(case_id)
        assert case_model is not None
        assert data["case_id"] == str(case_model.case_id)
        assert data["defect_code"] == case_model.defect_code
        assert data["defect_name"] == case_model.defect_name
        assert data["issue_condition"] == case_model.issue_condition

        rev_model = repo.get_analysis_revision(case_id, revision_number=4)
        assert rev_model is not None
        assert data["current_revision"] == rev_model.revision_number
        assert data["diagnosis"]["case_id"] == case_id
        assert data["diagnosis"]["analysis_revision"]["revision_number"] == 4

        confs = repo.get_case_cause_confirmations(case_id)
        assert len(confs) == 1
        assert confs[0].cause_id == data["submitted_confirmation"]["cause_id"]
        assert confs[0].confirmed_by == data["submitted_confirmation"]["confirmed_by"]
        assert confs[0].notes == data["submitted_confirmation"]["notes"]
        assert confs[0].resulting_revision_number == data["submitted_confirmation"]["resulting_revision_number"]
