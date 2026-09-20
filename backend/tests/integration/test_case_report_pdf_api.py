"""Dispense Lens - Deterministic Downloadable PDF Case Report Integration Tests.

Tests DLK-M3-023:
1. OpenAPI route registration for GET /api/v1/cases/{case_id}/report.pdf (200, 404, 422, 500);
2. Response headers (Content-Type: application/pdf, Content-Disposition with deterministic filename);
3. PDF validity & parseability via pypdf (signature, pages >= 1, structural text extraction);
4. Empty history behavior (new case Rev 1 returns clean PDF with neutral 'None recorded' notices);
5. Rich history scenario across all 7 revisions (answer, check, confirmation, recovery action, verification, recurrence);
6. Same-basis proof (asserts PDF describes the exact same revision, condition, defect, and event counts as the JSON report);
7. No recalculation proof (engine.diagnose raises if called, but PDF report GET succeeds with 200);
8. Read-only proof (complete durable database state captured before and after GET in fresh sessions is strictly identical);
9. Concurrent-write consistency (concurrent recurrence commit during PDF assembly preserves pinned Rev 6 report);
10. Missing case (404) and invalid UUID format (422);
11. Internal error sanitization (500 without leaking sensitive tokens and with zero durable mutations).
"""

from __future__ import annotations

import copy
import io
import os
from typing import Any, Generator
from unittest.mock import patch

import pypdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.api.cases import get_case_repository
from app.core.config import get_database_url
from app.db.database import reset_engine
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
                "value": "shrinking_over_time",
                "statement_type": "USER_OBSERVATION",
                "source": "USER",
            },
        ],
    }
    resp = client.post("/api/v1/cases", json=payload)
    assert resp.status_code == 201, f"Failed to create case: {resp.text}"
    data = resp.json()
    tracked_ids.append(data["case_id"])
    return data


def _advance_case_to_rev6_resolved(tracked_ids: list[str]) -> tuple[str, dict[str, Any]]:
    """Advance a case through revision 6 ending with verified resolution (RESOLVED)."""
    case_data = _create_initial_case(tracked_ids)
    case_id = case_data["case_id"]

    # Rev 2: Answer question
    qa_resp = client.post(
        f"/api/v1/cases/{case_id}/answers",
        json={
            "question_id": "Q01",
            "answer": "after_prolonged_operation",
            "expected_revision": 1,
        },
    )
    assert qa_resp.status_code == 200

    # Rev 3: Submit check result
    check_resp = client.post(
        f"/api/v1/cases/{case_id}/check-results",
        json={
            "check_id": "ACT02",
            "execution_status": "COMPLETED",
            "finding": "SUPPORTS",
            "outcome": "air_bubbles_found",
            "expected_revision": 2,
        },
    )
    assert check_resp.status_code == 200

    # Rev 4: Confirm cause
    conf_resp = client.post(
        f"/api/v1/cases/{case_id}/cause-confirmations",
        json={
            "cause_id": "nozzle_restriction",
            "notes": "Verified restriction via microscopic inspection",
            "confirmed_by": "lead_tech",
            "expected_revision": 3,
        },
    )
    assert conf_resp.status_code == 200

    # Rev 5: Recovery action
    recov_resp = client.post(
        f"/api/v1/cases/{case_id}/recovery-actions",
        json={
            "recovery_details": "Replaced fluid syringe and cleaned nozzle",
            "performed_by": "technician",
            "expected_revision": 4,
        },
    )
    assert recov_resp.status_code == 200

    # Rev 6: Recovery verification (RESOLVED)
    ver_resp = client.post(
        f"/api/v1/cases/{case_id}/recovery-verifications",
        json={
            "verification_passed": True,
            "verification_details": "100 test shots verified within nominal dot tolerance",
            "verified_by": "qa_engineer",
            "expected_revision": 5,
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
            "recurrence_details": "Dot size shrinking re-observed on shift 2",
            "reported_by": "line_operator",
            "expected_revision": 6,
        },
    )
    assert rec_resp.status_code == 200
    assert rec_resp.json()["issue_condition"] == "RECURRED"

    return case_id, rec_resp.json()


def _advance_case_with_multi_row_history(tracked_ids: list[str]) -> tuple[str, dict[str, Any]]:
    """Advance a case through 12 revisions with multiple distinguishable rows and repeated IDs in each history."""
    case_data = _create_initial_case(tracked_ids)
    case_id = case_data["case_id"]

    # Rev 2: Answer question Q01 (first response)
    qa1 = client.post(
        f"/api/v1/cases/{case_id}/answers",
        json={
            "question_id": "Q01",
            "answer": "after_prolonged_operation",
            "answer_text": "Dots shrink after 30 min",
            "expected_revision": 1,
        },
    )
    assert qa1.status_code == 200

    # Rev 3: Answer question Q01 again (repeated ID, different answer/text/rev)
    qa2 = client.post(
        f"/api/v1/cases/{case_id}/answers",
        json={
            "question_id": "Q01",
            "answer": "immediately",
            "answer_text": "Clarified: shrinking starts immediately on cold startup",
            "expected_revision": 2,
        },
    )
    assert qa2.status_code == 200

    # Rev 4: Submit check result ACT02 (first check)
    cr1 = client.post(
        f"/api/v1/cases/{case_id}/check-results",
        json={
            "check_id": "ACT02",
            "execution_status": "COMPLETED",
            "finding": "SUPPORTS",
            "outcome": "air_bubbles_found",
            "finding_details": "Trapped air bubbles observed in syringe barrel",
            "expected_revision": 3,
        },
    )
    assert cr1.status_code == 200

    # Rev 5: Submit check result ACT02 again (repeated ID, different finding/outcome/details/rev)
    cr2 = client.post(
        f"/api/v1/cases/{case_id}/check-results",
        json={
            "check_id": "ACT02",
            "execution_status": "COMPLETED",
            "finding": "CONTRADICTS",
            "outcome": "material_normal",
            "finding_details": "After fluid purge, syringe material inspected normal",
            "expected_revision": 4,
        },
    )
    assert cr2.status_code == 200

    # Rev 6: Confirm root cause nozzle_restriction (first confirmation)
    cc1 = client.post(
        f"/api/v1/cases/{case_id}/cause-confirmations",
        json={
            "cause_id": "nozzle_restriction",
            "notes": "Initial optical microscope inspection confirmed blockage",
            "confirmed_by": "lead_tech",
            "expected_revision": 5,
        },
    )
    assert cc1.status_code == 200

    # Rev 7: Confirm root cause nozzle_restriction again (repeated ID, different confirmed_by/notes/rev)
    cc2 = client.post(
        f"/api/v1/cases/{case_id}/cause-confirmations",
        json={
            "cause_id": "nozzle_restriction",
            "notes": "Secondary confirmation via flow meter differential pressure",
            "confirmed_by": "senior_tech",
            "expected_revision": 6,
        },
    )
    assert cc2.status_code == 200

    # Rev 8: Recovery action (first action)
    ra1 = client.post(
        f"/api/v1/cases/{case_id}/recovery-actions",
        json={
            "recovery_details": "Cleaned nozzle orifice with ultrasonic bath",
            "performed_by": "tech_dan",
            "expected_revision": 7,
        },
    )
    assert ra1.status_code == 200

    # Rev 9: Recovery verification (failed)
    rv1 = client.post(
        f"/api/v1/cases/{case_id}/recovery-verifications",
        json={
            "verification_passed": False,
            "verification_details": "50 test shots showed persistent dot shrinkage",
            "verified_by": "qa_sarah",
            "expected_revision": 8,
        },
    )
    assert rv1.status_code == 200
    assert rv1.json()["issue_condition"] == "UNRESOLVED"

    # Rev 10: Recovery action again (repeated event_type, different actor/details/rev)
    ra2 = client.post(
        f"/api/v1/cases/{case_id}/recovery-actions",
        json={
            "recovery_details": "Replaced entire nozzle assembly and syringe barrel",
            "performed_by": "tech_alex",
            "expected_revision": 9,
        },
    )
    assert ra2.status_code == 200

    # Rev 11: Recovery verification again (repeated event_type, passed)
    rv2 = client.post(
        f"/api/v1/cases/{case_id}/recovery-verifications",
        json={
            "verification_passed": True,
            "verification_details": "100 test shots verified within nominal dot tolerance",
            "verified_by": "qa_sarah",
            "expected_revision": 10,
        },
    )
    assert rv2.status_code == 200
    assert rv2.json()["issue_condition"] == "RESOLVED"

    # Rev 12: Recurrence
    rec = client.post(
        f"/api/v1/cases/{case_id}/recurrences",
        json={
            "recurrence_details": "Dot size shrinking re-observed on shift 3 after continuous run",
            "reported_by": "operator_bob",
            "expected_revision": 11,
        },
    )
    assert rec.status_code == 200
    assert rec.json()["issue_condition"] == "RECURRED"

    return case_id, rec.json()

from tests.unit.test_pdf_generator import (
    extract_pdf_history_sections,
    verify_cause_confirmations_section,
    verify_check_results_section,
    verify_lifecycle_events_section,
    verify_question_answers_section,
)


def test_pdf_report_openapi_registration():
    """Verify OpenAPI schema registers GET /api/v1/cases/{case_id}/report.pdf with expected responses."""
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()

    path_item = schema["paths"].get("/api/v1/cases/{case_id}/report.pdf")
    assert path_item is not None, "Route /api/v1/cases/{case_id}/report.pdf is not registered in OpenAPI!"
    assert "get" in path_item

    get_op = path_item["get"]
    assert "200" in get_op["responses"]
    assert "application/pdf" in get_op["responses"]["200"]["content"]
    assert "404" in get_op["responses"]
    assert "422" in get_op["responses"]
    assert "500" in get_op["responses"]


def test_pdf_report_empty_history_case(tracked_cases: list[str]):
    """Verify a newly created case with empty history returns a valid parseable PDF with neutral notices."""
    case_data = _create_initial_case(tracked_cases)
    case_id = case_data["case_id"]

    resp = client.get(f"/api/v1/cases/{case_id}/report.pdf")
    assert resp.status_code == 200, f"Expected 200 but got: {resp.text}"
    assert resp.headers["Content-Type"] == "application/pdf"
    assert f'filename="dispenselens-case-{case_id}-r1.pdf"' in resp.headers["Content-Disposition"]

    # Parse and extract text with pypdf
    reader = pypdf.PdfReader(io.BytesIO(resp.content))
    assert len(reader.pages) >= 1

    extracted_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Dispense Lens Diagnostic Case Report" in extracted_text
    assert case_id in extracted_text
    assert "Revision 1" in extracted_text or "Report Revision: 1" in extracted_text
    assert "D03_INCONSISTENT_SIZE" in extracted_text
    assert "UNRESOLVED" in extracted_text
    assert "None recorded." in extracted_text


def test_pdf_report_rich_history_content(tracked_cases: list[str]):
    """Verify a 7-revision rich case returns valid PDF with all historical and diagnostic sections."""
    case_id, _ = _advance_case_to_rev7_recurred(tracked_cases)

    resp = client.get(f"/api/v1/cases/{case_id}/report.pdf")
    assert resp.status_code == 200
    assert resp.headers["Content-Type"] == "application/pdf"
    assert f'filename="dispenselens-case-{case_id}-r7.pdf"' in resp.headers["Content-Disposition"]

    reader = pypdf.PdfReader(io.BytesIO(resp.content))
    assert len(reader.pages) >= 1

    extracted_text = "\n".join(page.extract_text() or "" for page in reader.pages)

    # Header and identity
    assert "Dispense Lens Diagnostic Case Report" in extracted_text
    assert case_id in extracted_text
    assert "Report Revision: 7" in extracted_text or "Revision 7" in extracted_text
    assert "D03_INCONSISTENT_SIZE" in extracted_text
    assert "RECURRED" in extracted_text

    # Outcome summary
    assert "nozzle_restriction" in extracted_text

    # Diagnosis snapshot & evidence
    assert "3. Current Diagnosis Snapshot" in extracted_text
    assert "Diagnostic Explanation:" in extracted_text
    assert "Evaluated Evidence" in extracted_text
    assert "SUPPORTS" in extracted_text

    # Histories
    assert "Q01" in extracted_text
    assert "after_prolonged_operation" in extracted_text
    assert "ACT02" in extracted_text
    assert "lead_tech" in extracted_text
    assert "technician" in extracted_text
    assert "qa_engineer" in extracted_text
    assert "line_operator" in extracted_text
    assert "RECURRENCE" in extracted_text

    # Provenance notice and absence of unsupported confidentiality label
    assert "Generated from persisted diagnostic records" in extracted_text
    assert "Confidential" not in extracted_text

    # Persisted timestamp and absence of live generation clock
    assert "Case Created:" in extracted_text
    assert "Generated:" not in extracted_text


def test_pdf_report_same_basis_as_json_report(tracked_cases: list[str]):
    """Verify PDF and JSON reports describe the exact same case basis, revision, and ordered events.

    Proves R3:
    1. Scopes assertions strictly to each history section (no whole-document fallback).
    2. Uses multiple distinguishable rows in every history collection, including repeated IDs with different values.
    3. Verifies complete row values and strict ordering against report arrays.
    4. Proves reversed rows fail with AssertionError.
    5. Proves mismatched row values fail with AssertionError.
    """
    case_id, _ = _advance_case_with_multi_row_history(tracked_cases)

    # Fetch JSON report
    json_resp = client.get(f"/api/v1/cases/{case_id}/report")
    assert json_resp.status_code == 200
    json_data = json_resp.json()

    # Fetch PDF report
    pdf_resp = client.get(f"/api/v1/cases/{case_id}/report.pdf")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["Content-Type"] == "application/pdf"

    # Verify filename basis
    expected_filename = f'dispenselens-case-{case_id}-r{json_data["current_revision"]}.pdf'
    assert f'filename="{expected_filename}"' in pdf_resp.headers["Content-Disposition"]

    # Verify PDF text matches JSON basis
    reader = pypdf.PdfReader(io.BytesIO(pdf_resp.content))
    extracted_text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert json_data["case_id"] in extracted_text
    assert f"Revision {json_data['current_revision']}" in extracted_text or f"Report Revision: {json_data['current_revision']}" in extracted_text
    assert json_data["defect_code"] in extracted_text
    assert json_data["issue_condition"] in extracted_text

    for cause_id in json_data["outcome_summary"]["confirmed_causes"]:
        assert cause_id in extracted_text

    # Extract sections strictly scoped to each history table
    sections = extract_pdf_history_sections(pdf_resp.content)

    # Positive: Verify complete row values and order against JSON report arrays
    verify_question_answers_section(sections["question_answers"], json_data["question_answers"])
    verify_check_results_section(sections["check_results"], json_data["check_results"])
    verify_cause_confirmations_section(sections["cause_confirmations"], json_data["cause_confirmations"])
    verify_lifecycle_events_section(sections["lifecycle_events"], json_data["lifecycle_events"])

    # Negative: Ensure reversed rows fail for all history sections
    with pytest.raises(AssertionError):
        verify_question_answers_section(sections["question_answers"], list(reversed(json_data["question_answers"])))
    with pytest.raises(AssertionError):
        verify_check_results_section(sections["check_results"], list(reversed(json_data["check_results"])))
    with pytest.raises(AssertionError):
        verify_cause_confirmations_section(sections["cause_confirmations"], list(reversed(json_data["cause_confirmations"])))
    with pytest.raises(AssertionError):
        verify_lifecycle_events_section(sections["lifecycle_events"], list(reversed(json_data["lifecycle_events"])))

    # Negative: Ensure mismatched row values fail for all history sections
    mismatched_qa = copy.deepcopy(json_data["question_answers"])
    mismatched_qa[0]["answer_value"] = "BOGUS_ANSWER_VALUE"
    with pytest.raises(AssertionError):
        verify_question_answers_section(sections["question_answers"], mismatched_qa)

    mismatched_cr = copy.deepcopy(json_data["check_results"])
    mismatched_cr[0]["finding"] = "BOGUS_FINDING"
    with pytest.raises(AssertionError):
        verify_check_results_section(sections["check_results"], mismatched_cr)

    mismatched_cc = copy.deepcopy(json_data["cause_confirmations"])
    mismatched_cc[0]["confirmed_by"] = "IMPOSTER_TECHNICIAN"
    with pytest.raises(AssertionError):
        verify_cause_confirmations_section(sections["cause_confirmations"], mismatched_cc)

    mismatched_lc = copy.deepcopy(json_data["lifecycle_events"])
    mismatched_lc[0]["actor"] = "IMPOSTER_ACTOR"
    with pytest.raises(AssertionError):
        verify_lifecycle_events_section(sections["lifecycle_events"], mismatched_lc)


def test_pdf_report_no_recalculation_proof(tracked_cases: list[str]):
    """Verify that engine recalculation is never invoked during PDF export."""
    case_data = _create_initial_case(tracked_cases)
    case_id = case_data["case_id"]

    # Patch DiagnosticEngine.diagnose to raise an error if invoked
    with patch.object(
        DiagnosticEngine,
        "diagnose",
        side_effect=RuntimeError("DiagnosticEngine.diagnose MUST NOT be called during PDF report export!"),
    ):
        resp = client.get(f"/api/v1/cases/{case_id}/report.pdf")
        assert resp.status_code == 200, f"Expected 200 but got: {resp.text}"
        assert resp.headers["Content-Type"] == "application/pdf"


def test_pdf_report_read_only_state_proof(tracked_cases: list[str]):
    """Verify PDF report GET creates zero database mutations, revisions, or timestamp changes."""
    case_id, _ = _advance_case_to_rev7_recurred(tracked_cases)

    factory = get_session_factory()

    # Capture state before GET
    with factory() as session:
        state_before = capture_complete_case_state(session, case_id)

    # Perform GET PDF report
    resp = client.get(f"/api/v1/cases/{case_id}/report.pdf")
    assert resp.status_code == 200
    assert resp.headers["Content-Type"] == "application/pdf"

    # Capture state after GET in fresh independent session
    with factory() as session:
        state_after = capture_complete_case_state(session, case_id)

    # Strict equality assertion
    assert state_before == state_after, "Persistent case state was modified during PDF report GET!"


def test_pdf_report_consistency_under_concurrent_update(tracked_cases: list[str]):
    """Verify that a PDF report assembled during a concurrent case update remains coherent and writes nothing."""
    case_id, _ = _advance_case_to_rev6_resolved(tracked_cases)

    factory = get_session_factory()
    orig_get_qa = CaseRepository.get_case_question_answers
    update_committed = False

    def hook_get_qa(self_repo, target_cid, max_revision=None):
        nonlocal update_committed
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
                    verification_details="Concurrent recurrence reported while PDF in flight",
                )
                writer_case.issue_condition = new_cond
                writer_result = writer_engine.diagnose(writer_case)
                writer_result.issue_condition = new_cond
                writer_repo.append_recurrence_revision(
                    case=writer_case,
                    reported_by="concurrent_reporter",
                    recurrence_details="Concurrent recurrence reported while PDF in flight",
                    result=writer_result,
                    expected_revision=6,
                )
                writer_session.commit()
            update_committed = True
        return orig_get_qa(self_repo, target_cid, max_revision=max_revision)

    with patch.object(CaseRepository, "get_case_question_answers", side_effect=hook_get_qa, autospec=True):
        resp = client.get(f"/api/v1/cases/{case_id}/report.pdf")

    assert resp.status_code == 200, f"Expected 200 but got: {resp.text}"
    assert update_committed is True, "Concurrent writer hook was not triggered during PDF assembly"

    # PDF filename must reflect revision 6
    assert f'filename="dispenselens-case-{case_id}-r6.pdf"' in resp.headers["Content-Disposition"]

    reader = pypdf.PdfReader(io.BytesIO(resp.content))
    extracted_text = "\n".join(page.extract_text() or "" for page in reader.pages)

    # Must describe revision 6 (RESOLVED) and NOT rev 7 (RECURRED)
    assert "RESOLVED" in extracted_text
    assert "RECURRED" not in extracted_text
    assert "RECURRENCE" not in extracted_text

    # Verify that the database did advance to Rev 7 in reality
    with factory() as session:
        db_state = capture_complete_case_state(session, case_id)
    assert db_state["case"]["issue_condition"] == "RECURRED"
    assert len(db_state["analysis_revisions"]) == 7


def test_pdf_report_missing_case_and_invalid_uuid():
    """Verify 404 for nonexistent case and 422 for malformed UUID."""
    missing_id = "00000000-0000-4000-8000-000000000000"
    resp = client.get(f"/api/v1/cases/{missing_id}/report.pdf")
    assert resp.status_code == 404
    assert resp.json()["detail"] == f"Case '{missing_id}' not found."

    invalid_id = "not-a-valid-uuid"
    resp2 = client.get(f"/api/v1/cases/{invalid_id}/report.pdf")
    assert resp2.status_code == 422
    assert resp2.json()["detail"] == f"Invalid case ID format: '{invalid_id}' must be a valid UUID."


def test_pdf_report_sanitized_500_on_internal_error(tracked_cases: list[str]):
    """Verify unexpected PDF rendering errors return sanitized 500 without leaking sensitive tokens and commit zero mutations."""
    case_id, _ = _advance_case_to_rev7_recurred(tracked_cases)

    factory = get_session_factory()
    with factory() as session:
        state_before = capture_complete_case_state(session, case_id)

    sensitive_marker = "SENSITIVE_PDF_RENDER_TOKEN_SECRET_98765"

    with patch(
        "app.api.cases.render_case_report_pdf",
        side_effect=RuntimeError(f"PDF engine crash with secret: {sensitive_marker}"),
    ):
        resp = client.get(f"/api/v1/cases/{case_id}/report.pdf")
        assert resp.status_code == 500
        assert sensitive_marker not in resp.text
        data = resp.json()
        assert data["detail"] == "An unexpected error occurred while generating the PDF case report."

    with factory() as session:
        state_after = capture_complete_case_state(session, case_id)

    assert state_before == state_after, "Durable database state was modified during failing PDF report GET!"
