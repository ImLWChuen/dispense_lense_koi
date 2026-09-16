"""
DispenseIQ — Resolved-Issue Recurrence Reporting Integration Tests

Tests DLK-M3-021:
1. OpenAPI routes and schemas for recurrence reporting (200, 404, 409, 422, 500);
2. Resolved -> recurrence success (Rev 6 -> Rev 7, issue_condition=RECURRED);
3. Recurrence on resolved case with no confirmed cause (unconfirmed causes stay unconfirmed);
4. Invalid source-state matrix (UNRESOLVED, RECOVERY_PENDING_VERIFICATION, RECURRED return 422 with zero mutation);
5. Stale expected_revision and replay protection return 409 with zero mutation;
6. Missing case (404) and input validation (empty details, invalid UUID, > 64 chars -> 422, 64 chars -> 200);
7. Injected internal ValueError with sensitive marker returns sanitized 500 with zero mutation;
8. Post-write rollback on injected database failure before commit preserves full target baseline and control case;
9. Monotonic mixed revision sequence across all 7 revisions (R1..R7).
"""

from __future__ import annotations

import copy
import os
import uuid
from typing import Any, Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, select
from sqlalchemy.orm import Session

from app.api.cases import get_diagnosis_engine
from app.core.config import get_database_url
from app.db.database import reset_engine
from app.db.session import get_session_factory
from app.main import app
from app.models.case import (
    AnalysisRevisionModel,
    CaseCauseConfirmationModel,
    CaseCheckResultModel,
    CaseLifecycleEventModel,
    CaseModel,
    ObservationModel,
    QuestionAnswerModel,
)
from app.schemas.diagnosis import (
    CauseConclusion,
    CheckExecutionStatus,
    CheckFinding,
    IssueCondition,
)
from app.services.diagnosis.engine import StateManager
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

    factory = get_session_factory()
    with factory() as session:
        for cid in case_ids:
            try:
                session.execute(
                    delete(CaseLifecycleEventModel).where(CaseLifecycleEventModel.case_id == cid)
                )
                session.execute(
                    delete(CaseCauseConfirmationModel).where(CaseCauseConfirmationModel.case_id == cid)
                )
                session.execute(
                    delete(CaseCheckResultModel).where(CaseCheckResultModel.case_id == cid)
                )
                session.execute(
                    delete(QuestionAnswerModel).where(QuestionAnswerModel.case_id == cid)
                )
                session.execute(
                    delete(AnalysisRevisionModel).where(AnalysisRevisionModel.case_id == cid)
                )
                session.execute(
                    delete(ObservationModel).where(ObservationModel.case_id == cid)
                )
                session.execute(delete(CaseModel).where(CaseModel.case_id == cid))
                session.commit()
            except Exception:
                session.rollback()


def _create_initial_case(tracked_ids: list[str], defect_code: str = "D03_INCONSISTENT_SIZE") -> dict[str, Any]:
    payload = {
        "description": "Dispense dots are shrinking over time during continuous operation",
        "material": "solder_paste",
        "method": "jetting",
        "defect_code": defect_code,
        "observations": [
            {
                "observation_type": "deposit_size",
                "value": "inconsistent",
                "statement_type": "USER_OBSERVATION",
                "source": "USER",
            },
            {
                "observation_type": "runtime_pattern",
                "value": "after_prolonged_operation",
                "statement_type": "USER_OBSERVATION",
                "source": "USER",
            },
        ],
    }
    response = client.post("/api/v1/cases", json=payload)
    assert response.status_code == 201, f"Failed to create case: {response.text}"
    data = response.json()
    tracked_ids.append(data["case_id"])
    return data


def _advance_case_to_rev6_resolved(tracked_ids: list[str]) -> tuple[dict[str, Any], int]:
    """Advance case to Revision 6 (RESOLVED) with confirmed cause."""
    case_data = _create_initial_case(tracked_ids)
    case_id = case_data["case_id"]

    # Rev 2: Answer
    ans_resp = client.post(
        f"/api/v1/cases/{case_id}/answers",
        json={
            "question_id": "Q01",
            "answer": "after_prolonged_operation",
            "expected_revision": 1,
        },
    )
    assert ans_resp.status_code == 200

    # Rev 3: Check
    chk_resp = client.post(
        f"/api/v1/cases/{case_id}/check-results",
        json={
            "check_id": "ACT02",
            "execution_status": "COMPLETED",
            "finding": "SUPPORTS",
            "outcome": "air_bubbles_found",
            "expected_revision": 2,
        },
    )
    assert chk_resp.status_code == 200

    # Rev 4: Cause Confirmation
    conf_resp = client.post(
        f"/api/v1/cases/{case_id}/cause-confirmations",
        json={
            "cause_id": "nozzle_restriction",
            "expected_revision": 3,
            "confirmed_by": "lead_tech",
            "notes": "Verified restriction via microscopic inspection",
        },
    )
    assert conf_resp.status_code == 200

    # Rev 5: Recovery Action
    act_resp = client.post(
        f"/api/v1/cases/{case_id}/recovery-actions",
        json={
            "expected_revision": 4,
            "recovery_details": "Replaced fluid syringe and cleaned nozzle",
            "performed_by": "technician",
        },
    )
    assert act_resp.status_code == 200

    # Rev 6: Recovery Verification (passed -> RESOLVED)
    ver_resp = client.post(
        f"/api/v1/cases/{case_id}/recovery-verifications",
        json={
            "expected_revision": 5,
            "verification_passed": True,
            "verification_details": "100 test shots verified within nominal dot tolerance",
            "verified_by": "qa_engineer",
        },
    )
    assert ver_resp.status_code == 200
    data = ver_resp.json()
    assert data["current_revision"] == 6
    assert data["issue_condition"] == "RESOLVED"
    return data, 6


def test_recurrence_route_registered_in_openapi():
    """Verify POST /api/v1/cases/{case_id}/recurrences is registered in OpenAPI."""
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    paths = schema.get("paths", {})
    route = "/api/v1/cases/{case_id}/recurrences"
    assert route in paths, f"Route {route} not found in OpenAPI paths: {list(paths.keys())}"
    post_op = paths[route].get("post", {})
    responses = post_op.get("responses", {})
    assert "200" in responses
    assert "404" in responses
    assert "409" in responses
    assert "422" in responses
    assert "500" in responses


def test_resolved_to_recurrence_success(tracked_cases: list[str]):
    """Scenario 1: Resolved -> recurrence success (Rev 6 -> Rev 7)."""
    case_data, rev = _advance_case_to_rev6_resolved(tracked_cases)
    case_id = case_data["case_id"]

    resp = client.post(
        f"/api/v1/cases/{case_id}/recurrences",
        json={
            "expected_revision": 6,
            "recurrence_details": "Defect symptoms recurred after 2 hours of production run",
            "reported_by": "technician_dan",
        },
    )
    assert resp.status_code == 200, f"Failed: {resp.text}"
    data = resp.json()

    # Verify response structure
    assert data["case_id"] == case_id
    assert data["current_revision"] == 7
    assert data["issue_condition"] == "RECURRED"
    assert data["confirmed_cause"] == "nozzle_restriction"

    # Verify submitted recurrence record
    submitted = data["submitted_recurrence"]
    assert submitted["event_type"] == "RECURRENCE"
    assert submitted["actor"] == "technician_dan"
    assert submitted["details"] == "Defect symptoms recurred after 2 hours of production run"
    assert submitted["prior_issue_condition"] == "RESOLVED"
    assert submitted["resulting_issue_condition"] == "RECURRED"
    assert submitted["resulting_revision_number"] == 7
    assert submitted["verification_passed"] is None

    # Verify submitted_event alias matches submitted_recurrence
    assert data["submitted_event"] == submitted

    # Verify cumulative history
    assert len(data["lifecycle_events"]) == 3
    assert data["lifecycle_events"][-1]["event_type"] == "RECURRENCE"
    assert len(data["previous_confirmations"]) == 1
    assert len(data["previous_check_results"]) == 1
    assert len(data["previous_answers"]) == 1

    # Verify in fresh database session
    factory = get_session_factory()
    with factory() as session:
        db_case = session.scalar(select(CaseModel).where(CaseModel.case_id == case_id))
        assert db_case is not None
        assert db_case.issue_condition == "RECURRED"

        revs = session.scalars(
            select(AnalysisRevisionModel)
            .where(AnalysisRevisionModel.case_id == case_id)
            .order_by(AnalysisRevisionModel.revision_number.asc())
        ).all()
        assert len(revs) == 7
        assert [r.revision_number for r in revs] == [1, 2, 3, 4, 5, 6, 7]
        assert revs[-1].issue_condition == "RECURRED"

        events = session.scalars(
            select(CaseLifecycleEventModel)
            .where(CaseLifecycleEventModel.case_id == case_id)
            .order_by(CaseLifecycleEventModel.resulting_revision_number.asc())
        ).all()
        assert len(events) == 3
        assert events[0].event_type == "RECOVERY_ACTION"
        assert events[1].event_type == "RECOVERY_VERIFICATION"
        assert events[2].event_type == "RECURRENCE"
        assert events[2].resulting_revision_number == 7


def test_recurrence_on_resolved_case_without_confirmed_cause(tracked_cases: list[str]):
    """Scenario 2: Recurrence on a resolved case with no confirmed cause; no cause becomes confirmed."""
    # Create case and advance directly without cause confirmation
    case_data = _create_initial_case(tracked_cases)
    case_id = case_data["case_id"]

    # Rev 2: QA
    ans_resp = client.post(
        f"/api/v1/cases/{case_id}/answers",
        json={
            "question_id": "Q01",
            "answer": "after_prolonged_operation",
            "expected_revision": 1,
        },
    )
    assert ans_resp.status_code == 200

    # Rev 3: Check
    chk_resp = client.post(
        f"/api/v1/cases/{case_id}/check-results",
        json={
            "check_id": "ACT02",
            "execution_status": "COMPLETED",
            "finding": "SUPPORTS",
            "outcome": "air_bubbles_found",
            "expected_revision": 2,
        },
    )
    assert chk_resp.status_code == 200

    # Rev 4: Recovery Action (skip confirmation!)
    act_resp = client.post(
        f"/api/v1/cases/{case_id}/recovery-actions",
        json={
            "expected_revision": 3,
            "recovery_details": "Syringe purge and reload without confirmed root cause",
            "performed_by": "technician",
        },
    )
    assert act_resp.status_code == 200

    # Rev 5: Recovery Verification passed -> RESOLVED
    ver_resp = client.post(
        f"/api/v1/cases/{case_id}/recovery-verifications",
        json={
            "expected_revision": 4,
            "verification_passed": True,
            "verification_details": "Test shots nominal",
            "verified_by": "qa_engineer",
        },
    )
    assert ver_resp.status_code == 200
    assert ver_resp.json()["confirmed_cause"] is None
    assert ver_resp.json()["issue_condition"] == "RESOLVED"

    # Rev 6: Recurrence submission
    rec_resp = client.post(
        f"/api/v1/cases/{case_id}/recurrences",
        json={
            "expected_revision": 5,
            "recurrence_details": "Problem returned after 1 hour",
            "reported_by": "technician",
        },
    )
    assert rec_resp.status_code == 200
    rec_data = rec_resp.json()

    assert rec_data["current_revision"] == 6
    assert rec_data["issue_condition"] == "RECURRED"
    assert rec_data["confirmed_cause"] is None
    assert len(rec_data["previous_confirmations"]) == 0

    # None of the ranked causes should be CONFIRMED
    for c in rec_data["diagnosis"]["ranked_causes"]:
        assert c["conclusion"] != CauseConclusion.CONFIRMED.value


def test_invalid_source_state_matrix(tracked_cases: list[str]):
    """Scenario 3: Invalid source-state matrix for UNRESOLVED, RECOVERY_PENDING_VERIFICATION, RECURRED."""
    # 1. From UNRESOLVED (Rev 1 initial case)
    c1 = _create_initial_case(tracked_cases)
    cid1 = c1["case_id"]

    factory = get_session_factory()
    with factory() as session:
        base1 = capture_complete_case_state(session, cid1)

    r1 = client.post(
        f"/api/v1/cases/{cid1}/recurrences",
        json={
            "expected_revision": 1,
            "recurrence_details": "Premature recurrence report",
        },
    )
    assert r1.status_code == 422
    assert "Illegal issue condition transition" in r1.json()["detail"]
    assert "UNRESOLVED" in r1.json()["detail"]

    # Zero mutation check
    with factory() as session:
        after1 = capture_complete_case_state(session, cid1)
        assert after1 == base1

    # 2. From RECOVERY_PENDING_VERIFICATION
    c2 = _create_initial_case(tracked_cases)
    cid2 = c2["case_id"]
    act_resp = client.post(
        f"/api/v1/cases/{cid2}/recovery-actions",
        json={
            "expected_revision": 1,
            "recovery_details": "Syringe purge",
        },
    )
    assert act_resp.status_code == 200
    assert act_resp.json()["issue_condition"] == "RECOVERY_PENDING_VERIFICATION"

    with factory() as session:
        base2 = capture_complete_case_state(session, cid2)

    r2 = client.post(
        f"/api/v1/cases/{cid2}/recurrences",
        json={
            "expected_revision": 2,
            "recurrence_details": "Recurrence attempted while pending verification",
        },
    )
    assert r2.status_code == 422
    assert "Illegal issue condition transition" in r2.json()["detail"]
    assert "RECOVERY_PENDING_VERIFICATION" in r2.json()["detail"]

    with factory() as session:
        after2 = capture_complete_case_state(session, cid2)
        assert after2 == base2

    # 3. From RECURRED (already recurred)
    c3, rev3 = _advance_case_to_rev6_resolved(tracked_cases)
    cid3 = c3["case_id"]
    r3_ok = client.post(
        f"/api/v1/cases/{cid3}/recurrences",
        json={
            "expected_revision": 6,
            "recurrence_details": "First recurrence",
        },
    )
    assert r3_ok.status_code == 200
    assert r3_ok.json()["issue_condition"] == "RECURRED"
    assert r3_ok.json()["current_revision"] == 7

    with factory() as session:
        base3 = capture_complete_case_state(session, cid3)

    r3 = client.post(
        f"/api/v1/cases/{cid3}/recurrences",
        json={
            "expected_revision": 7,
            "recurrence_details": "Second recurrence attempted while already recurred",
        },
    )
    assert r3.status_code == 422
    assert "Illegal issue condition transition" in r3.json()["detail"]
    assert "RECURRED" in r3.json()["detail"]

    with factory() as session:
        after3 = capture_complete_case_state(session, cid3)
        assert after3 == base3


def test_stale_and_replay_revision_conflict(tracked_cases: list[str]):
    """Scenario 4: Stale revision & replay conflict (409)."""
    case_data, rev = _advance_case_to_rev6_resolved(tracked_cases)
    case_id = case_data["case_id"]

    factory = get_session_factory()
    with factory() as session:
        baseline = capture_complete_case_state(session, case_id)

    # 1. Stale revision (expected_revision = 5 instead of 6)
    stale_resp = client.post(
        f"/api/v1/cases/{case_id}/recurrences",
        json={
            "expected_revision": 5,
            "recurrence_details": "Recurrence with stale revision",
        },
    )
    assert stale_resp.status_code == 409
    assert "Stale revision" in stale_resp.json()["detail"]

    with factory() as session:
        after_stale = capture_complete_case_state(session, case_id)
        assert after_stale == baseline

    # 2. Valid recurrence (expected_revision = 6) -> 200
    valid_resp = client.post(
        f"/api/v1/cases/{case_id}/recurrences",
        json={
            "expected_revision": 6,
            "recurrence_details": "Valid recurrence",
        },
    )
    assert valid_resp.status_code == 200
    assert valid_resp.json()["current_revision"] == 7

    with factory() as session:
        baseline_rev7 = capture_complete_case_state(session, case_id)

    # 3. Replay with consumed revision (expected_revision = 6) -> 409
    replay_resp = client.post(
        f"/api/v1/cases/{case_id}/recurrences",
        json={
            "expected_revision": 6,
            "recurrence_details": "Replayed recurrence",
        },
    )
    assert replay_resp.status_code == 409
    assert "Stale revision" in replay_resp.json()["detail"]

    with factory() as session:
        after_replay = capture_complete_case_state(session, case_id)
        assert after_replay == baseline_rev7


def test_missing_case_and_validation_errors(tracked_cases: list[str]):
    """Scenario 5: Missing case (404) and validation errors (422/200)."""
    # 1. Missing case -> 404
    missing_id = str(uuid.uuid4())
    r404 = client.post(
        f"/api/v1/cases/{missing_id}/recurrences",
        json={
            "expected_revision": 1,
            "recurrence_details": "Valid details",
        },
    )
    assert r404.status_code == 404

    # 2. Invalid UUID format -> 422
    r_uuid = client.post(
        "/api/v1/cases/not-a-valid-uuid/recurrences",
        json={
            "expected_revision": 1,
            "recurrence_details": "Valid details",
        },
    )
    assert r_uuid.status_code == 422
    assert "must be a valid UUID" in r_uuid.json()["detail"]

    # 3. Validation errors on existing case
    case_data, _ = _advance_case_to_rev6_resolved(tracked_cases)
    case_id = case_data["case_id"]

    # Empty details -> 422
    r_empty = client.post(
        f"/api/v1/cases/{case_id}/recurrences",
        json={
            "expected_revision": 6,
            "recurrence_details": "   ",
        },
    )
    assert r_empty.status_code == 422

    # expected_revision < 1 -> 422
    r_rev0 = client.post(
        f"/api/v1/cases/{case_id}/recurrences",
        json={
            "expected_revision": 0,
            "recurrence_details": "Valid details",
        },
    )
    assert r_rev0.status_code == 422

    # reported_by > 64 chars -> 422
    r_long = client.post(
        f"/api/v1/cases/{case_id}/recurrences",
        json={
            "expected_revision": 6,
            "recurrence_details": "Valid details",
            "reported_by": "x" * 65,
        },
    )
    assert r_long.status_code == 422

    # Extra forbidden field -> 422
    r_extra = client.post(
        f"/api/v1/cases/{case_id}/recurrences",
        json={
            "expected_revision": 6,
            "recurrence_details": "Valid details",
            "unauthorized_field": "injected",
        },
    )
    assert r_extra.status_code == 422

    # reported_by exactly 64 chars -> 200
    r_64 = client.post(
        f"/api/v1/cases/{case_id}/recurrences",
        json={
            "expected_revision": 6,
            "recurrence_details": "Valid details",
            "reported_by": "x" * 64,
        },
    )
    assert r_64.status_code == 200
    assert r_64.json()["submitted_recurrence"]["actor"] == "x" * 64


def test_injected_internal_value_error_returns_sanitized_500(
    tracked_cases: list[str], monkeypatch: pytest.MonkeyPatch
):
    """Scenario 6: Injected internal ValueError with synthetic sensitive marker returns sanitized 500."""
    case_data, _ = _advance_case_to_rev6_resolved(tracked_cases)
    case_id = case_data["case_id"]

    factory = get_session_factory()
    with factory() as session:
        baseline = capture_complete_case_state(session, case_id)

    sensitive_marker = "SYNTHETIC_SENSITIVE_LEAK_SECRET_KEY_12345"

    def faulty_transition(*args: Any, **kwargs: Any) -> tuple[IssueCondition, str]:
        raise ValueError(f"Simulated internal engine failure with {sensitive_marker}")

    monkeypatch.setattr(StateManager, "transition_issue_condition", faulty_transition)

    resp = client.post(
        f"/api/v1/cases/{case_id}/recurrences",
        json={
            "expected_revision": 6,
            "recurrence_details": "Testing sanitized error",
        },
    )
    assert resp.status_code == 500
    body = resp.json()
    assert sensitive_marker not in resp.text
    assert body["detail"] == "An unexpected error occurred while submitting the issue recurrence."

    # Verify zero mutation in fresh session
    with factory() as fresh_session:
        after = capture_complete_case_state(fresh_session, case_id)
        assert after == baseline

        events = fresh_session.scalars(
            select(CaseLifecycleEventModel)
            .where(
                CaseLifecycleEventModel.case_id == case_id,
                CaseLifecycleEventModel.resulting_revision_number == 7,
            )
        ).all()
        assert len(list(events)) == 0


def test_post_write_rollback_preserves_target_and_control(tracked_cases: list[str]):
    """Scenario 7: Post-write rollback on injected database failure before commit.

    Verifies:
    - Attempted recurrence lifecycle event is absent
    - Attempted revision is absent
    - Issue condition remains RESOLVED
    - Prior question/check/confirmation/lifecycle history unchanged
    - Unrelated control case unchanged
    """
    # 1. Setup control case
    ctrl_data, _ = _advance_case_to_rev6_resolved(tracked_cases)
    control_id = ctrl_data["case_id"]

    # 2. Setup target case
    tgt_data, _ = _advance_case_to_rev6_resolved(tracked_cases)
    target_id = tgt_data["case_id"]

    factory = get_session_factory()
    with factory() as session:
        control_baseline = capture_complete_case_state(session, control_id)
        target_baseline = capture_complete_case_state(session, target_id)

    assert target_baseline["case"]["issue_condition"] == "RESOLVED"
    assert len(target_baseline["analysis_revisions"]) == 6
    assert len(target_baseline["lifecycle_events"]) == 2
    attempted_rev = 7

    # 3. Intercept Session before_commit to simulate failure after flush
    fault_triggered = False

    def fail_after_flush_before_commit(session: Session) -> None:
        nonlocal fault_triggered
        events = session.scalars(
            select(CaseLifecycleEventModel).where(
                CaseLifecycleEventModel.case_id == target_id,
                CaseLifecycleEventModel.resulting_revision_number == attempted_rev,
            )
        ).all()
        if not events:
            return

        fault_triggered = True
        raise RuntimeError("Simulated database failure during recurrence commit")

    event.listen(Session, "before_commit", fail_after_flush_before_commit)
    try:
        resp = client.post(
            f"/api/v1/cases/{target_id}/recurrences",
            json={
                "expected_revision": 6,
                "recurrence_details": "Rollback test recurrence",
            },
        )
        assert resp.status_code == 500
        assert resp.json()["detail"] == "An unexpected error occurred while persisting the issue recurrence revision."
    finally:
        event.remove(Session, "before_commit", fail_after_flush_before_commit)

    assert fault_triggered is True

    # 4. Verify in fresh session that target and control cases are identical to baselines
    with factory() as fresh_session:
        target_after = capture_complete_case_state(fresh_session, target_id)
        control_after = capture_complete_case_state(fresh_session, control_id)

        assert target_after == target_baseline
        assert control_after == control_baseline

        events = list(
            fresh_session.scalars(
                select(CaseLifecycleEventModel).where(CaseLifecycleEventModel.case_id == target_id)
            ).all()
        )
        assert len(events) == 2
        assert all(e.event_type != "RECURRENCE" for e in events)

        revs = list(
            fresh_session.scalars(
                select(AnalysisRevisionModel).where(AnalysisRevisionModel.case_id == target_id)
            ).all()
        )
        assert len(revs) == 6
        assert all(r.revision_number != 7 for r in revs)
        assert target_after["case"]["issue_condition"] == "RESOLVED"


def test_mixed_revision_sequence_across_all_seven_revisions(tracked_cases: list[str]):
    """Scenario 8: Mixed revision sequence:
    R1 initial -> R2 answer -> R3 check -> R4 confirmation -> R5 recovery action -> R6 verification -> R7 recurrence.
    """
    # R1: Initial case
    case_data = _create_initial_case(tracked_cases)
    case_id = case_data["case_id"]
    assert case_data["initial_diagnosis"]["analysis_revision"]["revision_number"] == 1
    assert case_data["issue_condition"] == "UNRESOLVED"

    # R2: Question Answer
    ans_resp = client.post(
        f"/api/v1/cases/{case_id}/answers",
        json={
            "question_id": "Q01",
            "answer": "after_prolonged_operation",
            "expected_revision": 1,
        },
    )
    assert ans_resp.status_code == 200
    assert ans_resp.json()["current_revision"] == 2
    assert ans_resp.json()["issue_condition"] == "UNRESOLVED"

    # R3: Check Result
    chk_resp = client.post(
        f"/api/v1/cases/{case_id}/check-results",
        json={
            "check_id": "ACT02",
            "execution_status": "COMPLETED",
            "finding": "SUPPORTS",
            "outcome": "air_bubbles_found",
            "expected_revision": 2,
        },
    )
    assert chk_resp.status_code == 200
    assert chk_resp.json()["current_revision"] == 3
    assert chk_resp.json()["issue_condition"] == "UNRESOLVED"

    # R4: Cause Confirmation
    conf_resp = client.post(
        f"/api/v1/cases/{case_id}/cause-confirmations",
        json={
            "cause_id": "nozzle_restriction",
            "expected_revision": 3,
            "confirmed_by": "lead_technician",
            "notes": "Microscope inspection confirmed restricted orifice",
        },
    )
    assert conf_resp.status_code == 200
    assert conf_resp.json()["current_revision"] == 4
    assert conf_resp.json()["confirmed_cause"] == "nozzle_restriction"
    assert conf_resp.json()["issue_condition"] == "UNRESOLVED"

    # R5: Recovery Action
    act_resp = client.post(
        f"/api/v1/cases/{case_id}/recovery-actions",
        json={
            "expected_revision": 4,
            "recovery_details": "Nozzle ultrasonic cleaning and syringe purge",
            "performed_by": "technician_bob",
        },
    )
    assert act_resp.status_code == 200
    assert act_resp.json()["current_revision"] == 5
    assert act_resp.json()["issue_condition"] == "RECOVERY_PENDING_VERIFICATION"
    assert act_resp.json()["confirmed_cause"] == "nozzle_restriction"

    # R6: Recovery Verification
    ver_resp = client.post(
        f"/api/v1/cases/{case_id}/recovery-verifications",
        json={
            "expected_revision": 5,
            "verification_passed": True,
            "verification_details": "50 consecutive test shots verified within +/- 2% diameter",
            "verified_by": "qa_engineer_alice",
        },
    )
    assert ver_resp.status_code == 200
    assert ver_resp.json()["current_revision"] == 6
    assert ver_resp.json()["issue_condition"] == "RESOLVED"
    assert ver_resp.json()["confirmed_cause"] == "nozzle_restriction"

    # R7: Recurrence Reporting
    rec_resp = client.post(
        f"/api/v1/cases/{case_id}/recurrences",
        json={
            "expected_revision": 6,
            "recurrence_details": "Dot size variation observed again during shift 2 run",
            "reported_by": "operator_charlie",
        },
    )
    assert rec_resp.status_code == 200
    final_data = rec_resp.json()
    assert final_data["current_revision"] == 7
    assert final_data["issue_condition"] == "RECURRED"
    assert final_data["confirmed_cause"] == "nozzle_restriction"

    # Verify cumulative historical records
    assert len(final_data["previous_answers"]) == 1
    assert final_data["previous_answers"][0]["question_id"] == "Q01"
    assert final_data["previous_answers"][0]["resulting_revision_number"] == 2

    assert len(final_data["previous_check_results"]) == 1
    assert final_data["previous_check_results"][0]["check_id"] == "ACT02"
    assert final_data["previous_check_results"][0]["resulting_revision_number"] == 3

    assert len(final_data["previous_confirmations"]) == 1
    assert final_data["previous_confirmations"][0]["cause_id"] == "nozzle_restriction"
    assert final_data["previous_confirmations"][0]["resulting_revision_number"] == 4

    assert len(final_data["lifecycle_events"]) == 3
    assert final_data["lifecycle_events"][0]["event_type"] == "RECOVERY_ACTION"
    assert final_data["lifecycle_events"][0]["resulting_revision_number"] == 5
    assert final_data["lifecycle_events"][1]["event_type"] == "RECOVERY_VERIFICATION"
    assert final_data["lifecycle_events"][1]["resulting_revision_number"] == 6
    assert final_data["lifecycle_events"][2]["event_type"] == "RECURRENCE"
    assert final_data["lifecycle_events"][2]["resulting_revision_number"] == 7

    # Verify GET endpoint returns updated state
    get_resp = client.get(f"/api/v1/cases/{case_id}")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["issue_condition"] == "RECURRED"

    # Verify structured case reconstruction from repository
    from app.db.repository import CaseRepository
    repo = CaseRepository()
    sc = repo.load_structured_case(case_id)
    assert sc is not None
    assert len(sc.analysis_revisions) == 7
    assert [r.revision_number for r in sc.analysis_revisions] == [1, 2, 3, 4, 5, 6, 7]
    assert sc.issue_condition == IssueCondition.RECURRED
    assert sc.confirmed_causes == ["nozzle_restriction"]
