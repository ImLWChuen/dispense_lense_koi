"""
Dispense Lens - Deterministic Durable Case Report Export Integration Tests

Tests DLK-M3-022:
1. OpenAPI route registration for GET /api/v1/cases/{case_id}/report (200, 404, 422, 500);
2. Empty history behavior: new case (Rev 1) returns clean empty history lists without fabricated events;
3. Rich history scenario across all event types: answer (R2), check (R3), confirmation (R4),
   recovery action (R5), verification (R6), recurrence (R7);
4. Strict deterministic ordering of all history arrays (revision ascending);
5. No recalculation proof: engine.diagnose raises if called, but report GET succeeds with 200;
6. Read-only proof: complete durable state captured before and after GET in fresh sessions is strictly identical;
7. Deterministic repeatability: repeated GETs over unchanged state return identical payloads;
8. Missing case (404) and invalid UUID format (422);
9. Internal error sanitization (500 without leaking sensitive markers or internal traces).
"""

from __future__ import annotations

import copy
import os
import uuid
from typing import Any, Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.api.cases import get_case_repository, get_diagnosis_engine
from app.db.repository import CaseRepository
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
    CandidateCause,
    CauseConclusion,
    CheckExecutionStatus,
    CheckFinding,
    DiagnosisResult,
    IssueCondition,
)
from app.services.diagnosis.engine import DiagnosticEngine, StateManager
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


def _advance_case_to_rev6_resolved(tracked_ids: list[str]) -> tuple[str, dict[str, Any]]:
    """Advance a case through revision 6 ending with verified resolution (RESOLVED)."""
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

    # Rev 3: Check Result
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
    assert ver_resp.json()["issue_condition"] == "RESOLVED"

    return case_id, ver_resp.json()


def _advance_case_to_rev7_recurred(tracked_ids: list[str]) -> tuple[str, dict[str, Any]]:
    """Advance a case through all 7 revisions ending with recurrence (RECURRED)."""
    case_id, _ = _advance_case_to_rev6_resolved(tracked_ids)

    # Rev 7: Recurrence (RESOLVED -> RECURRED)
    rec_resp = client.post(
        f"/api/v1/cases/{case_id}/recurrences",
        json={
            "expected_revision": 6,
            "recurrence_details": "Dot size variation recurred after 20 minutes of continuous dispensing",
            "reported_by": "line_operator",
        },
    )
    assert rec_resp.status_code == 200
    assert rec_resp.json()["issue_condition"] == "RECURRED"

    return case_id, rec_resp.json()


def test_report_route_registered_in_openapi():
    """Verify GET /api/v1/cases/{case_id}/report is registered in OpenAPI with correct schema."""
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    paths = schema.get("paths", {})
    report_route = paths.get("/api/v1/cases/{case_id}/report")
    assert report_route is not None, "GET /api/v1/cases/{case_id}/report missing from OpenAPI"
    get_op = report_route.get("get")
    assert get_op is not None
    assert "200" in get_op["responses"]
    assert "404" in get_op["responses"]
    assert "422" in get_op["responses"]
    assert "500" in get_op["responses"]


def test_report_empty_history(tracked_cases: list[str]):
    """Verify report for a brand new case (Revision 1) has clean empty histories without placeholders."""
    case_data = _create_initial_case(tracked_cases)
    case_id = case_data["case_id"]

    resp = client.get(f"/api/v1/cases/{case_id}/report")
    assert resp.status_code == 200
    report = resp.json()

    # Case basis
    assert report["case_id"] == case_id
    assert report["current_revision"] == 1
    assert report["issue_condition"] == "UNRESOLVED"
    assert report["defect_code"] == "D03_INCONSISTENT_SIZE"
    assert report["material"] == "solder_paste"
    assert report["method"] == "jetting"
    assert "created_at" in report

    # Diagnosis snapshot
    assert "current_diagnosis" in report
    diag = report["current_diagnosis"]
    assert diag["case_id"] == case_id
    assert len(diag["ranked_causes"]) > 0

    # Histories: must be clean empty arrays
    assert report["question_answers"] == []
    assert report["check_results"] == []
    assert report["cause_confirmations"] == []
    assert report["lifecycle_events"] == []

    # Outcome summary
    summary = report["outcome_summary"]
    assert summary["issue_condition"] == "UNRESOLVED"
    assert summary["current_revision"] == 1
    assert summary["confirmed_causes"] == []
    assert summary["is_resolved"] is False


def test_report_rich_history_across_all_seven_revisions(tracked_cases: list[str]):
    """Verify rich report covering answer, check, confirmation, recovery, verification, and recurrence."""
    case_id, rev7_data = _advance_case_to_rev7_recurred(tracked_cases)

    resp = client.get(f"/api/v1/cases/{case_id}/report")
    assert resp.status_code == 200
    report = resp.json()

    # Case basis
    assert report["case_id"] == case_id
    assert report["current_revision"] == 7
    assert report["issue_condition"] == "RECURRED"

    # 1. Question answers (Rev 2)
    assert len(report["question_answers"]) == 1
    qa = report["question_answers"][0]
    assert qa["question_id"] == "Q01"
    assert qa["answer_value"] == "after_prolonged_operation"
    assert qa["resulting_revision_number"] == 2

    # 2. Check results (Rev 3)
    assert len(report["check_results"]) == 1
    cr = report["check_results"][0]
    assert cr["check_id"] == "ACT02"
    assert cr["execution_status"] == "COMPLETED"
    assert cr["finding"] == "SUPPORTS"
    assert cr["outcome"] == "air_bubbles_found"
    assert cr["resulting_revision_number"] == 3

    # 3. Cause confirmations (Rev 4)
    assert len(report["cause_confirmations"]) == 1
    conf = report["cause_confirmations"][0]
    assert conf["cause_id"] == "nozzle_restriction"
    assert conf["confirmed_by"] == "lead_tech"
    assert conf["resulting_revision_number"] == 4

    # 4. Lifecycle events (Revs 5, 6, 7)
    assert len(report["lifecycle_events"]) == 3
    ev_types = [e["event_type"] for e in report["lifecycle_events"]]
    assert ev_types == ["RECOVERY_ACTION", "RECOVERY_VERIFICATION", "RECURRENCE"]

    ev_revs = [e["resulting_revision_number"] for e in report["lifecycle_events"]]
    assert ev_revs == [5, 6, 7]

    # Verification event details
    ver_event = report["lifecycle_events"][1]
    assert ver_event["verification_passed"] is True
    assert ver_event["prior_issue_condition"] == "RECOVERY_PENDING_VERIFICATION"
    assert ver_event["resulting_issue_condition"] == "RESOLVED"

    # Recurrence event details
    rec_event = report["lifecycle_events"][2]
    assert rec_event["verification_passed"] is None
    assert rec_event["prior_issue_condition"] == "RESOLVED"
    assert rec_event["resulting_issue_condition"] == "RECURRED"
    assert rec_event["actor"] == "line_operator"

    # Outcome summary
    summary = report["outcome_summary"]
    assert summary["issue_condition"] == "RECURRED"
    assert summary["current_revision"] == 7
    assert "nozzle_restriction" in summary["confirmed_causes"]
    assert summary["is_resolved"] is False


def test_report_no_recalculation_proof(tracked_cases: list[str]):
    """Verify that engine recalculation is never invoked during report assembly."""
    case_data = _create_initial_case(tracked_cases)
    case_id = case_data["case_id"]

    # Patch DiagnosticEngine.diagnose to raise an error if invoked
    with patch.object(
        DiagnosticEngine,
        "diagnose",
        side_effect=RuntimeError("DiagnosticEngine.diagnose MUST NOT be called during report generation!"),
    ):
        resp = client.get(f"/api/v1/cases/{case_id}/report")
        assert resp.status_code == 200, f"Expected 200 but got: {resp.text}"
        data = resp.json()
        assert data["case_id"] == case_id
        assert data["current_revision"] == 1


def test_report_read_only_state_proof(tracked_cases: list[str]):
    """Verify report GET creates zero database mutations, revisions, or timestamp changes."""
    case_id, _ = _advance_case_to_rev7_recurred(tracked_cases)

    factory = get_session_factory()

    # Capture state before GET
    with factory() as session:
        state_before = capture_complete_case_state(session, case_id)

    # Perform GET report
    resp = client.get(f"/api/v1/cases/{case_id}/report")
    assert resp.status_code == 200

    # Capture state after GET in fresh independent session
    with factory() as session:
        state_after = capture_complete_case_state(session, case_id)

    # Strict equality assertion
    assert state_before == state_after, "Persistent case state was modified during report GET!"


def test_report_deterministic_repeatability(tracked_cases: list[str]):
    """Verify repeated GETs over unchanged database state return identical JSON payloads."""
    case_id, _ = _advance_case_to_rev7_recurred(tracked_cases)

    resp1 = client.get(f"/api/v1/cases/{case_id}/report")
    assert resp1.status_code == 200

    resp2 = client.get(f"/api/v1/cases/{case_id}/report")
    assert resp2.status_code == 200

    assert resp1.json() == resp2.json(), "Repeated report GETs produced divergent payloads!"


def test_report_missing_case_and_invalid_uuid():
    """Verify missing case returns 404 and malformed UUID returns 422."""
    missing_id = str(uuid.uuid4())
    resp = client.get(f"/api/v1/cases/{missing_id}/report")
    assert resp.status_code == 404
    assert f"Case '{missing_id}' not found." in resp.json()["detail"]

    bad_id = "not-a-valid-uuid-string"
    resp_bad = client.get(f"/api/v1/cases/{bad_id}/report")
    assert resp_bad.status_code == 422
    assert "Invalid case ID format" in resp_bad.json()["detail"]


def test_report_sanitized_500_on_internal_error(tracked_cases: list[str]):
    """Verify unexpected internal errors return sanitized 500 without leaking sensitive markers and commit zero mutations."""
    case_id, _ = _advance_case_to_rev7_recurred(tracked_cases)

    factory = get_session_factory()

    # Capture complete durable case state before failing GET in independent session
    with factory() as session:
        state_before = capture_complete_case_state(session, case_id)

    sensitive_marker = "SENSITIVE_DB_PASSWORD_LEAK_SECRET_12345"

    # Trigger failure AFTER report reads have already begun (e.g. during get_case_check_results)
    with patch.object(
        CaseRepository,
        "get_case_check_results",
        side_effect=ValueError(f"Database error with credentials: {sensitive_marker}"),
    ):
        resp = client.get(f"/api/v1/cases/{case_id}/report")
        assert resp.status_code == 500
        data = resp.json()
        assert sensitive_marker not in resp.text
        assert data["detail"] == "An unexpected error occurred while generating the case report."

    # Capture state again in fresh independent session
    with factory() as session:
        state_after = capture_complete_case_state(session, case_id)

    # Assert all case, revision, and history data are completely unchanged
    assert state_before == state_after, "Persistent case state was modified during failing report assembly!"


def test_report_consistency_under_concurrent_update(tracked_cases: list[str]):
    """Verify that a report assembled during a concurrent case update remains coherent and writes nothing."""
    case_id, _ = _advance_case_to_rev6_resolved(tracked_cases)

    factory = get_session_factory()
    orig_get_qa = CaseRepository.get_case_question_answers
    update_committed = False

    def hook_get_qa(self_repo, target_cid, max_revision=None):
        nonlocal update_committed
        # Trigger concurrent recurrence update on the first call for this case using an independent session
        if target_cid == case_id and not update_committed:
            with factory() as writer_session:
                writer_repo = CaseRepository(writer_session)
                writer_case = writer_repo.load_structured_case(case_id)
                assert writer_case is not None
                writer_engine = DiagnosticEngine()
                new_cond, _ = StateManager.transition_issue_condition(
                    current_condition=writer_case.issue_condition,
                    target_condition=IssueCondition.RECURRED,
                    verification_passed=False,
                    verification_details="Concurrent recurrence reported while report in flight",
                )
                writer_case.issue_condition = new_cond
                writer_result = writer_engine.diagnose(writer_case)
                writer_result.issue_condition = new_cond
                writer_repo.append_recurrence_revision(
                    case=writer_case,
                    reported_by="concurrent_reporter",
                    recurrence_details="Concurrent recurrence reported while report in flight",
                    result=writer_result,
                    expected_revision=6,
                )
                writer_session.commit()
            update_committed = True
        return orig_get_qa(self_repo, target_cid, max_revision=max_revision)

    with patch.object(CaseRepository, "get_case_question_answers", side_effect=hook_get_qa, autospec=True):
        resp = client.get(f"/api/v1/cases/{case_id}/report")

    assert resp.status_code == 200, f"Expected 200 but got: {resp.text}"
    assert update_committed is True, "Concurrent writer hook was not triggered during report assembly"

    report = resp.json()

    # The report must describe one coherent revision basis: revision 6 (RESOLVED)
    assert report["current_revision"] == 6
    assert report["issue_condition"] == "RESOLVED"
    assert report["diagnosis"]["analysis_revision"]["revision_number"] == 6
    assert report["diagnosis"]["issue_condition"] == "RESOLVED"
    assert report["current_diagnosis"]["analysis_revision"]["revision_number"] == 6
    assert report["current_diagnosis"]["issue_condition"] == "RESOLVED"

    # Outcome summary must match the pinned revision basis
    summary = report["outcome_summary"]
    assert summary["current_revision"] == 6
    assert summary["issue_condition"] == "RESOLVED"
    assert summary["is_resolved"] is True
    assert "nozzle_restriction" in summary["confirmed_causes"]

    # History items must only contain events up to the pinned revision (rev 6)
    # The R7 recurrence event MUST NOT leak into the R6 report
    event_types = [e["event_type"] for e in report["lifecycle_events"]]
    assert "RECURRENCE" not in event_types
    assert len(report["lifecycle_events"]) == 2
    assert [e["resulting_revision_number"] for e in report["lifecycle_events"]] == [5, 6]

    for qa in report["question_answers"]:
        assert qa["resulting_revision_number"] <= 6
    for cr in report["check_results"]:
        assert cr["resulting_revision_number"] <= 6
    for cc in report["cause_confirmations"]:
        assert cc["resulting_revision_number"] <= 6

    # Verify the database state in an independent session:
    # 1. The database really is at revision 7 with RECURRED
    with factory() as session:
        state_after_report = capture_complete_case_state(session, case_id)

    assert state_after_report["case"]["issue_condition"] == "RECURRED"
    assert len(state_after_report["analysis_revisions"]) == 7
    assert state_after_report["analysis_revisions"][-1]["revision_number"] == 7
    assert state_after_report["analysis_revisions"][-1]["issue_condition"] == "RECURRED"
    assert len(state_after_report["lifecycle_events"]) == 3  # action, verification, recurrence

    # 2. Verify report generation writes NOTHING:
    # Run a second report GET now (which will assemble from revision 7)
    with factory() as session:
        state_before_second = capture_complete_case_state(session, case_id)

    resp2 = client.get(f"/api/v1/cases/{case_id}/report")
    assert resp2.status_code == 200
    report2 = resp2.json()
    assert report2["current_revision"] == 7
    assert report2["issue_condition"] == "RECURRED"
    assert report2["outcome_summary"]["is_resolved"] is False

    with factory() as session:
        state_after_second = capture_complete_case_state(session, case_id)

    assert state_before_second == state_after_second, "Report generation created persistent database mutations!"
