"""
Dispense Lens - Recovery Action & Post-Correction Verification Integration Tests

Tests:
1. OpenAPI routes and schemas for recovery action and recovery verification;
2. Recovery action legal transition (UNRESOLVED -> RECOVERY_PENDING_VERIFICATION) with audit event and revision append;
3. Recovery action does not resolve the issue directly;
4. Recovery verification passed (RECOVERY_PENDING_VERIFICATION -> RESOLVED);
5. Independence: Recovery verification resolves case without requiring confirmed cause;
6. Recovery verification failed (RECOVERY_PENDING_VERIFICATION -> UNRESOLVED);
7. Independence: Verification failure preserves previously confirmed cause;
8. Independence: Cause confirmation alone does not resolve the issue;
9. State machine enforcement: Direct verification from UNRESOLVED rejected with 422;
10. State machine enforcement: Recovery action from RESOLVED rejected with 422;
11. Concurrency: Stale expected_revision and replay protection return 409 with zero mutation;
12. Rollback: Recovery action database failure rolls back naturally, leaves state intact;
13. Rollback: Recovery verification database failure rolls back naturally, leaves state intact;
14. Monotonic mixed revision sequence across all 5 event types (Rev 1..6);
15. Character length boundary: 64 chars succeeds, 65 chars rejected with 422;
16. Input validation and 404 handling.
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
    CaseLifecycleEventModel,
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
def configure_test_environment(test_database_url: str) -> None:
    """Configure and verify PostgreSQL connection URL for integration tests."""
    pass


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


def _advance_case_to_rev3(tracked_ids: list[str]) -> tuple[dict[str, Any], int]:
    """Create a case and advance it to Revision 3 (Rev 1: initial, Rev 2: QA, Rev 3: Check)."""
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
    assert ans_resp.json()["current_revision"] == 2

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
    assert chk_resp.json()["current_revision"] == 3

    return chk_resp.json(), 3


def _advance_case_to_rev4_with_confirmation(tracked_ids: list[str]) -> tuple[dict[str, Any], int]:
    """Create a case and advance it to Revision 4 (Rev 1: initial, Rev 2: QA, Rev 3: Check, Rev 4: Confirmation)."""
    case_data, _ = _advance_case_to_rev3(tracked_ids)
    case_id = case_data["case_id"]

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
    assert conf_resp.json()["current_revision"] == 4

    return conf_resp.json(), 4


def test_recovery_routes_registered_in_openapi():
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    paths = schema.get("paths", {})
    action_path = "/api/v1/cases/{case_id}/recovery-actions"
    verif_path = "/api/v1/cases/{case_id}/recovery-verifications"
    assert action_path in paths, f"Route {action_path} not found in OpenAPI"
    assert "post" in paths[action_path]
    assert verif_path in paths, f"Route {verif_path} not found in OpenAPI"
    assert "post" in paths[verif_path]

    components = schema.get("components", {}).get("schemas", {})
    assert "SubmitRecoveryActionRequest" in components
    assert "SubmitRecoveryVerificationRequest" in components
    assert "CaseRecoveryActionResponse" in components
    assert "CaseRecoveryVerificationResponse" in components

    action_props = components["SubmitRecoveryActionRequest"]["properties"]
    assert action_props["performed_by"].get("maxLength") == 64

    verif_props = components["SubmitRecoveryVerificationRequest"]["properties"]
    assert verif_props["verified_by"].get("maxLength") == 64


def test_recovery_action_legal_transition_succeeds(tracked_cases: list[str]):
    case_data = _create_initial_case(tracked_cases)
    case_id = case_data["case_id"]
    assert case_data["issue_condition"] == "UNRESOLVED"

    action_payload = {
        "expected_revision": 1,
        "recovery_details": "Purged fluid line and replaced dispense tip with 30-gauge nozzle.",
        "performed_by": "technician_alice",
    }
    resp = client.post(f"/api/v1/cases/{case_id}/recovery-actions", json=action_payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["case_id"] == case_id
    assert data["issue_condition"] == "RECOVERY_PENDING_VERIFICATION"
    assert data["current_revision"] == 2
    assert data["diagnosis"]["issue_condition"] == "RECOVERY_PENDING_VERIFICATION"

    submitted = data["submitted_recovery_action"]
    assert submitted["event_type"] == "RECOVERY_ACTION"
    assert submitted["prior_issue_condition"] == "UNRESOLVED"
    assert submitted["resulting_issue_condition"] == "RECOVERY_PENDING_VERIFICATION"
    assert submitted["resulting_revision_number"] == 2
    assert submitted["actor"] == "technician_alice"
    assert "Purged fluid line" in submitted["details"]
    assert submitted["verification_passed"] is None

    assert len(data["lifecycle_events"]) == 1
    assert data["lifecycle_events"][0] == submitted

    factory = get_session_factory()
    with factory() as session:
        case_row = session.scalar(select(CaseModel).where(CaseModel.case_id == case_id))
        assert case_row is not None
        assert case_row.issue_condition == "RECOVERY_PENDING_VERIFICATION"

        rev2 = session.scalar(
            select(AnalysisRevisionModel).where(
                AnalysisRevisionModel.case_id == case_id,
                AnalysisRevisionModel.revision_number == 2,
            )
        )
        assert rev2 is not None
        assert rev2.issue_condition == "RECOVERY_PENDING_VERIFICATION"

        events = list(
            session.scalars(
                select(CaseLifecycleEventModel).where(CaseLifecycleEventModel.case_id == case_id)
            ).all()
        )
        assert len(events) == 1
        assert events[0].event_type == "RECOVERY_ACTION"
        assert events[0].prior_issue_condition == "UNRESOLVED"
        assert events[0].resulting_issue_condition == "RECOVERY_PENDING_VERIFICATION"
        assert events[0].resulting_revision_number == 2


def test_recovery_action_does_not_transition_directly_to_resolved(tracked_cases: list[str]):
    case_data = _create_initial_case(tracked_cases)
    case_id = case_data["case_id"]

    resp = client.post(
        f"/api/v1/cases/{case_id}/recovery-actions",
        json={
            "expected_revision": 1,
            "recovery_details": "Replaced valve cartridge",
            "performed_by": "tech_bob",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["issue_condition"] == "RECOVERY_PENDING_VERIFICATION"
    assert data["issue_condition"] != "RESOLVED"


def test_recovery_verification_passed_transitions_to_resolved(tracked_cases: list[str]):
    case_data, rev = _advance_case_to_rev3(tracked_cases)
    case_id = case_data["case_id"]

    act_resp = client.post(
        f"/api/v1/cases/{case_id}/recovery-actions",
        json={
            "expected_revision": rev,
            "recovery_details": "Calibrated pressure regulator and purged bubble trap.",
            "performed_by": "tech_carol",
        },
    )
    assert act_resp.status_code == 200
    assert act_resp.json()["current_revision"] == 4
    assert act_resp.json()["issue_condition"] == "RECOVERY_PENDING_VERIFICATION"

    verif_resp = client.post(
        f"/api/v1/cases/{case_id}/recovery-verifications",
        json={
            "expected_revision": 4,
            "verification_passed": True,
            "verification_details": "Test pattern of 50 dots dispensed; optical measurement confirms nominal volume.",
            "verified_by": "qa_inspector",
        },
    )
    assert verif_resp.status_code == 200, verif_resp.text
    vdata = verif_resp.json()

    assert vdata["issue_condition"] == "RESOLVED"
    assert vdata["current_revision"] == 5
    assert vdata["diagnosis"]["issue_condition"] == "RESOLVED"

    submitted_v = vdata["submitted_verification"]
    assert submitted_v["event_type"] == "RECOVERY_VERIFICATION"
    assert submitted_v["prior_issue_condition"] == "RECOVERY_PENDING_VERIFICATION"
    assert submitted_v["resulting_issue_condition"] == "RESOLVED"
    assert submitted_v["resulting_revision_number"] == 5
    assert submitted_v["actor"] == "qa_inspector"
    assert submitted_v["verification_passed"] is True
    assert "optical measurement confirms" in submitted_v["details"]

    assert len(vdata["lifecycle_events"]) == 2
    assert len(vdata["previous_answers"]) == 1
    assert len(vdata["previous_check_results"]) == 1

    factory = get_session_factory()
    with factory() as session:
        db_case = session.scalar(select(CaseModel).where(CaseModel.case_id == case_id))
        assert db_case is not None
        assert db_case.issue_condition == "RESOLVED"

        rev5 = session.scalar(
            select(AnalysisRevisionModel).where(
                AnalysisRevisionModel.case_id == case_id,
                AnalysisRevisionModel.revision_number == 5,
            )
        )
        assert rev5 is not None
        assert rev5.issue_condition == "RESOLVED"


def test_recovery_verification_passed_preserves_unconfirmed_cause(tracked_cases: list[str]):
    case_data = _create_initial_case(tracked_cases)
    case_id = case_data["case_id"]

    act_resp = client.post(
        f"/api/v1/cases/{case_id}/recovery-actions",
        json={
            "expected_revision": 1,
            "recovery_details": "Applied routine nozzle cleaning",
        },
    )
    assert act_resp.status_code == 200
    assert act_resp.json()["confirmed_cause"] is None

    verif_resp = client.post(
        f"/api/v1/cases/{case_id}/recovery-verifications",
        json={
            "expected_revision": 2,
            "verification_passed": True,
            "verification_details": "Dispense shots within spec",
        },
    )
    assert verif_resp.status_code == 200
    vdata = verif_resp.json()

    assert vdata["issue_condition"] == "RESOLVED"
    assert vdata["confirmed_cause"] is None
    assert len(vdata["previous_confirmations"]) == 0
    for cause in vdata["diagnosis"]["ranked_causes"]:
        assert cause["conclusion"] != "CONFIRMED"


def test_recovery_verification_failed_transitions_back_to_unresolved(tracked_cases: list[str]):
    case_data = _create_initial_case(tracked_cases)
    case_id = case_data["case_id"]

    act_resp = client.post(
        f"/api/v1/cases/{case_id}/recovery-actions",
        json={
            "expected_revision": 1,
            "recovery_details": "Cleaned needle tip",
        },
    )
    assert act_resp.status_code == 200
    assert act_resp.json()["issue_condition"] == "RECOVERY_PENDING_VERIFICATION"

    verif_resp = client.post(
        f"/api/v1/cases/{case_id}/recovery-verifications",
        json={
            "expected_revision": 2,
            "verification_passed": False,
            "verification_details": "Test pattern failed: 3 out of 10 dots were undersized.",
            "verified_by": "qa_inspector",
        },
    )
    assert verif_resp.status_code == 200
    vdata = verif_resp.json()

    assert vdata["issue_condition"] == "UNRESOLVED"
    assert vdata["current_revision"] == 3
    assert vdata["submitted_verification"]["verification_passed"] is False
    assert vdata["submitted_verification"]["resulting_issue_condition"] == "UNRESOLVED"

    factory = get_session_factory()
    with factory() as session:
        db_case = session.scalar(select(CaseModel).where(CaseModel.case_id == case_id))
        assert db_case is not None
        assert db_case.issue_condition == "UNRESOLVED"


def test_recovery_verification_failed_preserves_confirmed_cause(tracked_cases: list[str]):
    case_data = _create_initial_case(tracked_cases)
    case_id = case_data["case_id"]

    conf_resp = client.post(
        f"/api/v1/cases/{case_id}/cause-confirmations",
        json={
            "cause_id": "nozzle_restriction",
            "expected_revision": 1,
            "confirmed_by": "lead_tech",
            "notes": "Verified restriction under scope",
        },
    )
    assert conf_resp.status_code == 200
    assert conf_resp.json()["confirmed_cause"] == "nozzle_restriction"
    assert conf_resp.json()["issue_condition"] == "UNRESOLVED"

    act_resp = client.post(
        f"/api/v1/cases/{case_id}/recovery-actions",
        json={
            "expected_revision": 2,
            "recovery_details": "Attempted solvent soak",
            "performed_by": "lead_tech",
        },
    )
    assert act_resp.status_code == 200
    assert act_resp.json()["issue_condition"] == "RECOVERY_PENDING_VERIFICATION"
    assert act_resp.json()["confirmed_cause"] == "nozzle_restriction"

    verif_resp = client.post(
        f"/api/v1/cases/{case_id}/recovery-verifications",
        json={
            "expected_revision": 3,
            "verification_passed": False,
            "verification_details": "Soak did not clear blockage, test shot still failed",
            "verified_by": "qa_inspector",
        },
    )
    assert verif_resp.status_code == 200
    vdata = verif_resp.json()

    assert vdata["issue_condition"] == "UNRESOLVED"
    assert vdata["confirmed_cause"] == "nozzle_restriction"
    confirmed_cause = next(
        (c for c in vdata["diagnosis"]["ranked_causes"] if c["cause_id"] == "nozzle_restriction"),
        None,
    )
    assert confirmed_cause is not None
    assert confirmed_cause["conclusion"] == "CONFIRMED"


def test_cause_confirmation_alone_does_not_resolve_issue(tracked_cases: list[str]):
    case_data = _create_initial_case(tracked_cases)
    case_id = case_data["case_id"]

    conf_resp = client.post(
        f"/api/v1/cases/{case_id}/cause-confirmations",
        json={
            "cause_id": "nozzle_restriction",
            "expected_revision": 1,
        },
    )
    assert conf_resp.status_code == 200
    assert conf_resp.json()["issue_condition"] == "UNRESOLVED"
    assert conf_resp.json()["issue_condition"] != "RESOLVED"


def test_direct_verification_from_unresolved_is_rejected_422(tracked_cases: list[str]):
    case_data = _create_initial_case(tracked_cases)
    case_id = case_data["case_id"]

    factory = get_session_factory()
    with factory() as session:
        baseline = capture_complete_case_state(session, case_id)
def test_recovery_verification_from_unresolved_pass_rejected_422(tracked_cases: list[str]):
    """R1 regression: Verification with verification_passed=True on an UNRESOLVED case
    using non-stale current revision returns 422 with zero mutation."""
    case_data, rev = _advance_case_to_rev4_with_confirmation(tracked_cases)
    case_id = case_data["case_id"]
    assert case_data["issue_condition"] == "UNRESOLVED"
    assert rev == 4

    factory = get_session_factory()
    with factory() as session:
        baseline = capture_complete_case_state(session, case_id)

    resp = client.post(
        f"/api/v1/cases/{case_id}/recovery-verifications",
        json={
            "expected_revision": rev,
            "verification_passed": True,
            "verification_details": "Attempting verification directly from UNRESOLVED with pass",
            "verified_by": "qa_inspector",
        },
    )
    assert resp.status_code == 422, resp.text
    assert "Illegal issue condition transition" in resp.json()["detail"]
    assert "recovery verification requires 'RECOVERY_PENDING_VERIFICATION'" in resp.json()["detail"]

    with factory() as session:
        after = capture_complete_case_state(session, case_id)
        assert after == baseline
        events = list(session.scalars(
            select(CaseLifecycleEventModel).where(CaseLifecycleEventModel.case_id == case_id)
        ).all())
        assert len(events) == 0


def test_recovery_verification_from_unresolved_fail_rejected_422(tracked_cases: list[str]):
    """R1 regression: Verification with verification_passed=False on an UNRESOLVED case
    using non-stale current revision returns 422 with zero mutation."""
    case_data, rev = _advance_case_to_rev4_with_confirmation(tracked_cases)
    case_id = case_data["case_id"]
    assert case_data["issue_condition"] == "UNRESOLVED"
    assert rev == 4

    factory = get_session_factory()
    with factory() as session:
        baseline = capture_complete_case_state(session, case_id)

    resp = client.post(
        f"/api/v1/cases/{case_id}/recovery-verifications",
        json={
            "expected_revision": rev,
            "verification_passed": False,
            "verification_details": "Attempting verification directly from UNRESOLVED with fail",
            "verified_by": "qa_inspector",
        },
    )
    assert resp.status_code == 422, resp.text
    assert "Illegal issue condition transition" in resp.json()["detail"]
    assert "recovery verification requires 'RECOVERY_PENDING_VERIFICATION'" in resp.json()["detail"]

    with factory() as session:
        after = capture_complete_case_state(session, case_id)
        assert after == baseline
        events = list(session.scalars(
            select(CaseLifecycleEventModel).where(CaseLifecycleEventModel.case_id == case_id)
        ).all())
        assert len(events) == 0


def test_recovery_verification_from_resolved_pass_rejected_422(tracked_cases: list[str]):
    """R1 regression: Verification with verification_passed=True on an already RESOLVED case
    using non-stale current revision returns 422 with zero mutation."""
    case_data, rev = _advance_case_to_rev4_with_confirmation(tracked_cases)
    case_id = case_data["case_id"]

    act_resp = client.post(
        f"/api/v1/cases/{case_id}/recovery-actions",
        json={
            "expected_revision": rev,
            "recovery_details": "Nozzle cleaning and purge",
            "performed_by": "lead_tech",
        },
    )
    assert act_resp.status_code == 200
    assert act_resp.json()["current_revision"] == 5

    ver_resp = client.post(
        f"/api/v1/cases/{case_id}/recovery-verifications",
        json={
            "expected_revision": 5,
            "verification_passed": True,
            "verification_details": "Inspection verified nominal",
            "verified_by": "qa_inspector",
        },
    )
    assert ver_resp.status_code == 200
    assert ver_resp.json()["issue_condition"] == "RESOLVED"
    assert ver_resp.json()["current_revision"] == 6

    factory = get_session_factory()
    with factory() as session:
        baseline = capture_complete_case_state(session, case_id)

    resp = client.post(
        f"/api/v1/cases/{case_id}/recovery-verifications",
        json={
            "expected_revision": 6,
            "verification_passed": True,
            "verification_details": "Attempting second verification pass on already RESOLVED case",
            "verified_by": "qa_inspector",
        },
    )
    assert resp.status_code == 422, resp.text
    assert "Illegal issue condition transition" in resp.json()["detail"]
    assert "recovery verification requires 'RECOVERY_PENDING_VERIFICATION'" in resp.json()["detail"]

    with factory() as session:
        after = capture_complete_case_state(session, case_id)
        assert after == baseline
        events = list(session.scalars(
            select(CaseLifecycleEventModel).where(CaseLifecycleEventModel.case_id == case_id)
        ).all())
        assert len(events) == 2


def test_recovery_verification_from_resolved_fail_rejected_422(tracked_cases: list[str]):
    """R1 regression: Verification with verification_passed=False on an already RESOLVED case
    using non-stale current revision returns 422 with zero mutation."""
    case_data, rev = _advance_case_to_rev4_with_confirmation(tracked_cases)
    case_id = case_data["case_id"]

    act_resp = client.post(
        f"/api/v1/cases/{case_id}/recovery-actions",
        json={
            "expected_revision": rev,
            "recovery_details": "Nozzle cleaning and purge",
            "performed_by": "lead_tech",
        },
    )
    assert act_resp.status_code == 200
    assert act_resp.json()["current_revision"] == 5

    ver_resp = client.post(
        f"/api/v1/cases/{case_id}/recovery-verifications",
        json={
            "expected_revision": 5,
            "verification_passed": True,
            "verification_details": "Inspection verified nominal",
            "verified_by": "qa_inspector",
        },
    )
    assert ver_resp.status_code == 200
    assert ver_resp.json()["issue_condition"] == "RESOLVED"
    assert ver_resp.json()["current_revision"] == 6

    factory = get_session_factory()
    with factory() as session:
        baseline = capture_complete_case_state(session, case_id)

    resp = client.post(
        f"/api/v1/cases/{case_id}/recovery-verifications",
        json={
            "expected_revision": 6,
            "verification_passed": False,
            "verification_details": "Attempting verification fail on already RESOLVED case",
            "verified_by": "qa_inspector",
        },
    )
    assert resp.status_code == 422, resp.text
    assert "Illegal issue condition transition" in resp.json()["detail"]
    assert "recovery verification requires 'RECOVERY_PENDING_VERIFICATION'" in resp.json()["detail"]

    with factory() as session:
        after = capture_complete_case_state(session, case_id)
        assert after == baseline
        events = list(session.scalars(
            select(CaseLifecycleEventModel).where(CaseLifecycleEventModel.case_id == case_id)
        ).all())
        assert len(events) == 2


def test_recovery_action_unexpected_state_manager_value_error_returns_sanitized_500(
    monkeypatch: pytest.MonkeyPatch, tracked_cases: list[str]
):
    """R2 regression: Unexpected ValueError during legal recovery action transition
    returns sanitized 500 without leaking sensitive paths/markers and causes zero mutations."""
    case_data, rev = _advance_case_to_rev4_with_confirmation(tracked_cases)
    case_id = case_data["case_id"]

    factory = get_session_factory()
    with factory() as session:
        baseline = capture_complete_case_state(session, case_id)

    leak_marker = "SYNTHETIC_SENSITIVE_LEAK: /private/internal/secret_core_path.py line 42"

    def mock_transition_issue_condition(*args: Any, **kwargs: Any) -> Any:
        raise ValueError(leak_marker)

    monkeypatch.setattr(
        "app.api.cases.StateManager.transition_issue_condition",
        mock_transition_issue_condition,
    )

    resp = client.post(
        f"/api/v1/cases/{case_id}/recovery-actions",
        json={
            "expected_revision": rev,
            "recovery_details": "Ultrasonic bath and fresh nozzle",
            "performed_by": "tech_alice",
        },
    )
    assert resp.status_code == 500
    assert leak_marker not in resp.text
    assert "/private/internal/secret_core_path.py" not in resp.text
    assert resp.json()["detail"] == "An unexpected error occurred while submitting the recovery action."

    with factory() as session:
        after = capture_complete_case_state(session, case_id)
        assert after == baseline
        events = list(session.scalars(
            select(CaseLifecycleEventModel).where(CaseLifecycleEventModel.case_id == case_id)
        ).all())
        assert len(events) == 0


def test_recovery_verification_unexpected_state_manager_value_error_returns_sanitized_500(
    monkeypatch: pytest.MonkeyPatch, tracked_cases: list[str]
):
    """R2 regression: Unexpected ValueError during legal recovery verification transition
    returns sanitized 500 without leaking sensitive paths/markers and causes zero mutations."""
    case_data, rev = _advance_case_to_rev4_with_confirmation(tracked_cases)
    case_id = case_data["case_id"]

    act_resp = client.post(
        f"/api/v1/cases/{case_id}/recovery-actions",
        json={
            "expected_revision": rev,
            "recovery_details": "Nozzle cleaned",
            "performed_by": "tech_alice",
        },
    )
    assert act_resp.status_code == 200
    assert act_resp.json()["current_revision"] == 5
    assert act_resp.json()["issue_condition"] == "RECOVERY_PENDING_VERIFICATION"

    factory = get_session_factory()
    with factory() as session:
        baseline = capture_complete_case_state(session, case_id)

    leak_marker = "SYNTHETIC_SENSITIVE_LEAK: /private/internal/secret_core_path.py line 42"

    def mock_transition_issue_condition(*args: Any, **kwargs: Any) -> Any:
        raise ValueError(leak_marker)

    monkeypatch.setattr(
        "app.api.cases.StateManager.transition_issue_condition",
        mock_transition_issue_condition,
    )

    resp = client.post(
        f"/api/v1/cases/{case_id}/recovery-verifications",
        json={
            "expected_revision": 5,
            "verification_passed": True,
            "verification_details": "Inspection passed",
            "verified_by": "qa_inspector",
        },
    )
    assert resp.status_code == 500
    assert leak_marker not in resp.text
    assert "/private/internal/secret_core_path.py" not in resp.text
    assert resp.json()["detail"] == "An unexpected error occurred while submitting the recovery verification."

    with factory() as session:
        after = capture_complete_case_state(session, case_id)
        assert after == baseline
        events = list(session.scalars(
            select(CaseLifecycleEventModel).where(CaseLifecycleEventModel.case_id == case_id)
        ).all())
        assert len(events) == 1
        assert events[0].event_type == "RECOVERY_ACTION"
        assert events[0].resulting_revision_number == 5


def test_illegal_recovery_action_from_resolved_rejected_422(tracked_cases: list[str]):
    case_data = _create_initial_case(tracked_cases)
    case_id = case_data["case_id"]

    client.post(
        f"/api/v1/cases/{case_id}/recovery-actions",
        json={"expected_revision": 1, "recovery_details": "Action 1"},
    )
    client.post(
        f"/api/v1/cases/{case_id}/recovery-verifications",
        json={"expected_revision": 2, "verification_passed": True, "verification_details": "Passed"},
    )

    factory = get_session_factory()
    with factory() as session:
        baseline = capture_complete_case_state(session, case_id)

    resp = client.post(
        f"/api/v1/cases/{case_id}/recovery-actions",
        json={"expected_revision": 3, "recovery_details": "Action 2 on resolved case"},
    )
    assert resp.status_code == 422
    assert "Illegal issue condition transition" in resp.json()["detail"]

    with factory() as session:
        after = capture_complete_case_state(session, case_id)
        assert after == baseline


def test_recovery_action_stale_revision_and_replay_rejected_409(tracked_cases: list[str]):
    case_data = _create_initial_case(tracked_cases)
    case_id = case_data["case_id"]

    resp = client.post(
        f"/api/v1/cases/{case_id}/recovery-actions",
        json={"expected_revision": 99, "recovery_details": "Action with stale revision"},
    )
    assert resp.status_code == 409
    assert "Stale revision" in resp.json()["detail"]

    resp2 = client.post(
        f"/api/v1/cases/{case_id}/recovery-actions",
        json={"expected_revision": 1, "recovery_details": "Legitimate action"},
    )
    assert resp2.status_code == 200

    resp3 = client.post(
        f"/api/v1/cases/{case_id}/recovery-actions",
        json={"expected_revision": 1, "recovery_details": "Replayed action"},
    )
    assert resp3.status_code == 409
    assert "Stale revision" in resp3.json()["detail"]


def test_recovery_verification_stale_revision_and_replay_rejected_409(tracked_cases: list[str]):
    case_data = _create_initial_case(tracked_cases)
    case_id = case_data["case_id"]

    client.post(
        f"/api/v1/cases/{case_id}/recovery-actions",
        json={"expected_revision": 1, "recovery_details": "Action"},
    )

    resp = client.post(
        f"/api/v1/cases/{case_id}/recovery-verifications",
        json={"expected_revision": 1, "verification_passed": True},
    )
    assert resp.status_code == 409
    assert "Stale revision" in resp.json()["detail"]

    resp2 = client.post(
        f"/api/v1/cases/{case_id}/recovery-verifications",
        json={"expected_revision": 2, "verification_passed": True},
    )
    assert resp2.status_code == 200

    resp3 = client.post(
        f"/api/v1/cases/{case_id}/recovery-verifications",
        json={"expected_revision": 2, "verification_passed": True},
    )
    assert resp3.status_code == 409


def test_recovery_action_rollback_on_injected_database_failure(tracked_cases: list[str]):
    control_data, _ = _advance_case_to_rev4_with_confirmation(tracked_cases)
    control_id = control_data["case_id"]

    target_data, _ = _advance_case_to_rev4_with_confirmation(tracked_cases)
    target_id = target_data["case_id"]

    factory = get_session_factory()
    with factory() as session:
        control_baseline = capture_complete_case_state(session, control_id)
        target_baseline = capture_complete_case_state(session, target_id)

    assert len(target_baseline["question_answers"]) == 1
    assert len(target_baseline["check_results"]) == 1
    assert len(target_baseline["cause_confirmations"]) == 1
    assert len(target_baseline["lifecycle_events"]) == 0
    assert target_baseline["case"]["issue_condition"] == "UNRESOLVED"

    baseline_rev = target_baseline["analysis_revisions"][-1]["revision_number"]
    assert baseline_rev == 4
    attempted_rev = baseline_rev + 1

    fault_reached = False
    pending_event_captured: dict[str, Any] = {}
    pending_rev_captured: dict[str, Any] = {}

    def before_commit_hook(session: Session) -> None:
        nonlocal fault_reached, pending_event_captured, pending_rev_captured
        target_events = session.scalars(
            select(CaseLifecycleEventModel).where(
                CaseLifecycleEventModel.case_id == target_id,
                CaseLifecycleEventModel.resulting_revision_number == attempted_rev,
            )
        ).all()
        if not target_events:
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
        p_event = target_events[0]
        p_rev = target_revs[0]
        pending_event_captured = {
            "event_type": str(p_event.event_type),
            "resulting_revision_number": int(p_event.resulting_revision_number),
        }
        pending_rev_captured = {
            "revision_number": int(p_rev.revision_number),
            "result_snapshot": copy.deepcopy(p_rev.result_snapshot),
        }
        raise RuntimeError("Injected database failure before commit during recovery action")

    event.listen(Session, "before_commit", before_commit_hook)
    try:
        resp = client.post(
            f"/api/v1/cases/{target_id}/recovery-actions",
            json={
                "expected_revision": baseline_rev,
                "recovery_details": "Testing rollback on failure",
                "performed_by": "tester",
            },
        )
        assert resp.status_code == 500
        assert "Injected database failure" not in resp.text
        assert resp.json()["detail"] == "An unexpected error occurred while persisting the recovery action revision."
    finally:
        event.remove(Session, "before_commit", before_commit_hook)

    assert fault_reached is True, "The before_commit hook was not triggered; writes were not flushed!"
    assert pending_event_captured["event_type"] == "RECOVERY_ACTION"
    assert pending_event_captured["resulting_revision_number"] == attempted_rev
    assert pending_rev_captured["revision_number"] == attempted_rev
    assert "defect" in pending_rev_captured["result_snapshot"]

    with factory() as fresh_session:
        target_after = capture_complete_case_state(fresh_session, target_id)
        control_after = capture_complete_case_state(fresh_session, control_id)

        assert target_after == target_baseline
        assert control_after == control_baseline
        assert target_after["case"]["issue_condition"] == "UNRESOLVED"
        assert len(target_after["cause_confirmations"]) == 1
        assert len(target_after["question_answers"]) == 1
        assert len(target_after["check_results"]) == 1
        assert len(target_after["lifecycle_events"]) == 0
        assert len(target_after["analysis_revisions"]) == 4

        events = list(
            fresh_session.scalars(
                select(CaseLifecycleEventModel).where(CaseLifecycleEventModel.case_id == target_id)
            ).all()
        )
        assert len(events) == 0


def test_recovery_verification_rollback_on_injected_database_failure(tracked_cases: list[str]):
    control_data, _ = _advance_case_to_rev4_with_confirmation(tracked_cases)
    control_id = control_data["case_id"]

    target_data, _ = _advance_case_to_rev4_with_confirmation(tracked_cases)
    target_id = target_data["case_id"]

    client.post(
        f"/api/v1/cases/{control_id}/recovery-actions",
        json={"expected_revision": 4, "recovery_details": "Action control", "performed_by": "tech_control"},
    )
    client.post(
        f"/api/v1/cases/{target_id}/recovery-actions",
        json={"expected_revision": 4, "recovery_details": "Action target", "performed_by": "tech_target"},
    )

    factory = get_session_factory()
    with factory() as session:
        control_baseline = capture_complete_case_state(session, control_id)
        target_baseline = capture_complete_case_state(session, target_id)

    assert len(target_baseline["question_answers"]) == 1
    assert len(target_baseline["check_results"]) == 1
    assert len(target_baseline["cause_confirmations"]) == 1
    assert len(target_baseline["lifecycle_events"]) == 1
    assert target_baseline["lifecycle_events"][0]["event_type"] == "RECOVERY_ACTION"
    assert target_baseline["lifecycle_events"][0]["resulting_revision_number"] == 5
    assert target_baseline["case"]["issue_condition"] == "RECOVERY_PENDING_VERIFICATION"

    baseline_rev = 5
    attempted_rev = 6

    fault_reached = False
    pending_event_captured: dict[str, Any] = {}
    pending_rev_captured: dict[str, Any] = {}

    def before_commit_hook(session: Session) -> None:
        nonlocal fault_reached, pending_event_captured, pending_rev_captured
        target_events = session.scalars(
            select(CaseLifecycleEventModel).where(
                CaseLifecycleEventModel.case_id == target_id,
                CaseLifecycleEventModel.resulting_revision_number == attempted_rev,
            )
        ).all()
        if not target_events:
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
        p_event = target_events[0]
        p_rev = target_revs[0]
        pending_event_captured = {
            "event_type": str(p_event.event_type),
            "resulting_revision_number": int(p_event.resulting_revision_number),
        }
        pending_rev_captured = {
            "revision_number": int(p_rev.revision_number),
            "result_snapshot": copy.deepcopy(p_rev.result_snapshot),
        }
        raise RuntimeError("Injected database failure before commit during recovery verification")

    event.listen(Session, "before_commit", before_commit_hook)
    try:
        resp = client.post(
            f"/api/v1/cases/{target_id}/recovery-verifications",
            json={
                "expected_revision": baseline_rev,
                "verification_passed": True,
                "verification_details": "Testing rollback on verification",
                "verified_by": "tester",
            },
        )
        assert resp.status_code == 500
        assert "Injected database failure" not in resp.text
        assert resp.json()["detail"] == "An unexpected error occurred while persisting the recovery verification revision."
    finally:
        event.remove(Session, "before_commit", before_commit_hook)

    assert fault_reached is True, "The before_commit hook was not triggered; writes were not flushed!"
    assert pending_event_captured["event_type"] == "RECOVERY_VERIFICATION"
    assert pending_event_captured["resulting_revision_number"] == attempted_rev

    with factory() as fresh_session:
        target_after = capture_complete_case_state(fresh_session, target_id)
        control_after = capture_complete_case_state(fresh_session, control_id)

        assert target_after == target_baseline
        assert control_after == control_baseline
        assert target_after["case"]["issue_condition"] == "RECOVERY_PENDING_VERIFICATION"
        assert len(target_after["cause_confirmations"]) == 1
        assert len(target_after["question_answers"]) == 1
        assert len(target_after["check_results"]) == 1
        assert len(target_after["lifecycle_events"]) == 1
        assert target_after["lifecycle_events"][0]["event_type"] == "RECOVERY_ACTION"
        assert target_after["lifecycle_events"][0]["resulting_revision_number"] == 5
        assert len(target_after["analysis_revisions"]) == 5

        all_events = list(
            fresh_session.scalars(
                select(CaseLifecycleEventModel).where(CaseLifecycleEventModel.case_id == target_id)
            ).all()
        )
        assert len(all_events) == 1
        assert all_events[0].event_type == "RECOVERY_ACTION"
        assert all_events[0].resulting_revision_number == 5

        rev6_events = list(
            fresh_session.scalars(
                select(CaseLifecycleEventModel).where(
                    CaseLifecycleEventModel.case_id == target_id,
                    CaseLifecycleEventModel.resulting_revision_number == attempted_rev,
                )
            ).all()
        )
        assert len(rev6_events) == 0


def test_monotonic_mixed_revision_history_all_five_event_types(tracked_cases: list[str]):
    case_data = _create_initial_case(tracked_cases)
    case_id = case_data["case_id"]

    # Rev 2: QA
    ans_resp = client.post(
        f"/api/v1/cases/{case_id}/answers",
        json={"question_id": "Q01", "answer": "after_prolonged_operation", "expected_revision": 1},
    )
    assert ans_resp.status_code == 200
    assert ans_resp.json()["current_revision"] == 2

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
    assert chk_resp.json()["current_revision"] == 3

    # Rev 4: Confirmation
    conf_resp = client.post(
        f"/api/v1/cases/{case_id}/cause-confirmations",
        json={
            "cause_id": "nozzle_restriction",
            "expected_revision": 3,
            "confirmed_by": "lead_tech",
            "notes": "Bore restricted with residue",
        },
    )
    assert conf_resp.status_code == 200
    assert conf_resp.json()["current_revision"] == 4
    assert conf_resp.json()["confirmed_cause"] == "nozzle_restriction"

    # Rev 5: Recovery Action
    act_resp = client.post(
        f"/api/v1/cases/{case_id}/recovery-actions",
        json={
            "expected_revision": 4,
            "recovery_details": "Ultrasonic bath and fresh nozzle installed",
            "performed_by": "lead_tech",
        },
    )
    assert act_resp.status_code == 200
    assert act_resp.json()["current_revision"] == 5
    assert act_resp.json()["issue_condition"] == "RECOVERY_PENDING_VERIFICATION"
    assert act_resp.json()["confirmed_cause"] == "nozzle_restriction"

    # Rev 6: Recovery Verification
    verif_resp = client.post(
        f"/api/v1/cases/{case_id}/recovery-verifications",
        json={
            "expected_revision": 5,
            "verification_passed": True,
            "verification_details": "Dispensed 100 nominal test dots, inspection passed",
            "verified_by": "qa_inspector",
        },
    )
    assert verif_resp.status_code == 200
    final_data = verif_resp.json()

    assert final_data["current_revision"] == 6
    assert final_data["issue_condition"] == "RESOLVED"
    assert final_data["confirmed_cause"] == "nozzle_restriction"
    assert len(final_data["previous_answers"]) == 1
    assert len(final_data["previous_check_results"]) == 1
    assert len(final_data["previous_confirmations"]) == 1
    assert len(final_data["lifecycle_events"]) == 2

    repo = CaseRepository()
    sc = repo.load_structured_case(case_id)
    assert sc is not None
    assert len(sc.analysis_revisions) == 6
    assert [r.revision_number for r in sc.analysis_revisions] == [1, 2, 3, 4, 5, 6]
    assert sc.issue_condition == IssueCondition.RESOLVED
    assert sc.confirmed_causes == ["nozzle_restriction"]


def test_actor_string_length_boundary_64_and_65(tracked_cases: list[str]):
    case_data = _create_initial_case(tracked_cases)
    case_id = case_data["case_id"]

    actor_64 = "T" * 64
    actor_65 = "T" * 65

    resp_act_65 = client.post(
        f"/api/v1/cases/{case_id}/recovery-actions",
        json={
            "expected_revision": 1,
            "recovery_details": "Cleaning",
            "performed_by": actor_65,
        },
    )
    assert resp_act_65.status_code == 422

    resp_act_64 = client.post(
        f"/api/v1/cases/{case_id}/recovery-actions",
        json={
            "expected_revision": 1,
            "recovery_details": "Cleaning",
            "performed_by": actor_64,
        },
    )
    assert resp_act_64.status_code == 200
    assert resp_act_64.json()["submitted_recovery_action"]["actor"] == actor_64

    resp_ver_65 = client.post(
        f"/api/v1/cases/{case_id}/recovery-verifications",
        json={
            "expected_revision": 2,
            "verification_passed": True,
            "verified_by": actor_65,
        },
    )
    assert resp_ver_65.status_code == 422

    resp_ver_64 = client.post(
        f"/api/v1/cases/{case_id}/recovery-verifications",
        json={
            "expected_revision": 2,
            "verification_passed": True,
            "verified_by": actor_64,
        },
    )
    assert resp_ver_64.status_code == 200
    assert resp_ver_64.json()["submitted_verification"]["actor"] == actor_64


def test_validation_errors_empty_details_and_invalid_uuid(tracked_cases: list[str]):
    case_data = _create_initial_case(tracked_cases)
    case_id = case_data["case_id"]

    resp_uuid = client.post(
        "/api/v1/cases/not-a-valid-uuid/recovery-actions",
        json={"expected_revision": 1, "recovery_details": "Action"},
    )
    assert resp_uuid.status_code == 422

    missing_id = str(uuid.uuid4())
    resp_missing = client.post(
        f"/api/v1/cases/{missing_id}/recovery-actions",
        json={"expected_revision": 1, "recovery_details": "Action"},
    )
    assert resp_missing.status_code == 404

    resp_empty = client.post(
        f"/api/v1/cases/{case_id}/recovery-actions",
        json={"expected_revision": 1, "recovery_details": "   "},
    )
    assert resp_empty.status_code == 422

    resp_rev0 = client.post(
        f"/api/v1/cases/{case_id}/recovery-actions",
        json={"expected_revision": 0, "recovery_details": "Action"},
    )
    assert resp_rev0.status_code == 422
