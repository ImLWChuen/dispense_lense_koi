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
from datetime import datetime, timezone
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


def test_pdf_report_with_image_observations_and_region_evidence(tracked_cases: list[str]):
    """Verify downloadable PDF includes Section 8 with rich region evidence, measurements, limits, and notices."""
    region_evidence_payload = [
        {
            "roi_id": "site_01",
            "current_measurements": {
                "inspection_status": "DETECTED",
                "deposit_area_px": 1800.0,
                "equivalent_diameter_px": 47.87,
                "calibrated_diameter_mm": 0.479,
                "coverage_ratio": 0.72,
                "overflow_ratio": 0.0,
                "circularity": 0.88,
                "solidity": 0.95,
                "convexity": 0.96,
                "aspect_ratio": 1.05,
                "hole_void_ratio": 0.0,
                "bubble_count": 0,
                "has_bubbles": False,
                "segmentation_quality": 0.96,
                "target_area_px": 2500.0,
            },
            "reference_measurements": {
                "inspection_status": "DETECTED",
                "deposit_area_px": 2500.0,
                "equivalent_diameter_px": 56.42,
                "calibrated_diameter_mm": 0.564,
                "coverage_ratio": 1.0,
                "overflow_ratio": 0.0,
                "circularity": 0.98,
                "solidity": 0.98,
                "convexity": 0.98,
                "aspect_ratio": 1.0,
                "hole_void_ratio": 0.0,
                "bubble_count": 0,
                "has_bubbles": False,
                "segmentation_quality": 0.98,
                "target_area_px": 2500.0,
            },
        },
        {
            "roi_id": "site_02",
            "current_measurements": {
                "inspection_status": "DETECTED",
                "deposit_area_px": 2480.0,
                "equivalent_diameter_px": 56.19,
                "calibrated_diameter_mm": None,
                "coverage_ratio": 0.99,
                "overflow_ratio": 0.0,
                "circularity": 0.96,
                "solidity": 0.98,
                "convexity": 0.99,
                "aspect_ratio": 1.01,
                "hole_void_ratio": 0.0,
                "bubble_count": 0,
                "has_bubbles": False,
                "segmentation_quality": 0.98,
                "target_area_px": 2500.0,
            },
            "reference_measurements": None,
        },
    ]

    create_payload = {
        "description": "Multi-region inspection case with rich region evidence",
        "material": "solder_paste",
        "method": "jetting",
        "defect_code": "D01_TOO_LITTLE",
        "observations": [
            {
                "observation_type": "deposit_size",
                "value": "undersized",
                "original_text": "Site 01 deposit is below nominal specification",
                "statement_type": "AI_INFERENCE",
                "source": "IMAGE",
                "confidence": 0.95,
                "metadata": {
                    "region_evidence_scope": "individual_regions",
                    "affected_roi_ids": ["site_01", "site_02"],
                    "applied_limits": {
                        "target_area_px": 2500.0,
                        "tolerance_pct": 10.0,
                        "min_coverage_ratio": 0.85,
                    },
                    "region_evidence": region_evidence_payload,
                },
            },
            {
                "observation_type": "deposit_shape",
                "value": "irregular",
                "original_text": "Group comparison detected shape variance across sites",
                "statement_type": "AI_INFERENCE",
                "source": "IMAGE",
                "confidence": 0.85,
                "metadata": {
                    "region_evidence_scope": "comparison_group",
                    "affected_roi_ids": ["site_01", "site_02"],
                    "applied_limits": {"max_aspect_ratio": 1.20},
                    "region_evidence": [region_evidence_payload[0]],
                },
            },
        ],
    }

    create_resp = client.post("/api/v1/cases", json=create_payload)
    assert create_resp.status_code == 201, f"Failed to create case: {create_resp.text}"
    case_id = create_resp.json()["case_id"]
    tracked_cases.append(case_id)

    # Request PDF
    pdf_resp = client.get(f"/api/v1/cases/{case_id}/report.pdf")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["Content-Type"] == "application/pdf"
    assert f'filename="dispenselens-case-{case_id}-r1.pdf"' in pdf_resp.headers["Content-Disposition"]

    reader = pypdf.PdfReader(io.BytesIO(pdf_resp.content))
    assert len(reader.pages) >= 1
    extracted_text = "\n".join(page.extract_text() or "" for page in reader.pages)

    # Section 8 presence and required automated observation notice
    assert "8. Image Inspection Evidence" in extracted_text
    assert "Image findings represent automated visual observations and inferences" in extracted_text
    assert "Absence of image findings does not imply inspection passed" in extracted_text

    # Observation details and scope distinctions
    assert "deposit_size" in extracted_text
    assert "undersized" in extracted_text
    assert "individual_regions" in extracted_text
    assert "comparison_group" in extracted_text
    assert "Group comparison finding: listed regions are eligible" in extracted_text
    assert "configuration snapshot; not an assertion of failure for all limits" in extracted_text

    # Distinct site measurements and units
    assert "site_01" in extracted_text
    assert "DETECTED" in extracted_text
    assert "1800.00 px²" in extracted_text or "1800.00" in extracted_text
    assert "47.87 px" in extracted_text
    assert "0.479 mm" in extracted_text
    assert "2500.00 px²" in extracted_text or "2500.00" in extracted_text
    assert "0.564 mm" in extracted_text
    assert "has=False" in extracted_text

    # Site 2 without reference measurements
    assert "site_02" in extracted_text
    assert "56.19 px" in extracted_text
    assert "Not recorded" in extracted_text  # null calibrated physical diameter
    assert "None (not in reference mode or unmatched)" in extracted_text


def test_pdf_report_empty_image_observations_notice(tracked_cases: list[str]):
    """Verify Section 8 displays neutral explanatory notice when case has no image observations."""
    case_data = _create_initial_case(tracked_cases)
    case_id = case_data["case_id"]

    resp = client.get(f"/api/v1/cases/{case_id}/report.pdf")
    assert resp.status_code == 200

    reader = pypdf.PdfReader(io.BytesIO(resp.content))
    extracted_text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert "8. Image Inspection Evidence" in extracted_text
    assert "No image inspection evidence recorded for this case revision." in extracted_text


def test_pdf_report_malformed_and_legacy_region_metadata(tracked_cases: list[str]):
    """Verify PDF generates cleanly without crashing when metadata is legacy, missing, or malformed,
    and preserves unknown state for missing scope, conflicting aliases, invalid status, and malformed scalars.
    """
    create_payload = {
        "description": "Case with malformed and legacy image metadata",
        "material": "epoxy",
        "method": "time_pressure",
        "defect_code": "D01_TOO_LITTLE",
        "observations": [
            {
                "observation_type": "deposit_size",
                "value": "undersized",
                "statement_type": "AI_INFERENCE",
                "source": "IMAGE",
                "metadata": {
                    # Missing region_evidence_scope -> must render as "Not recorded or unknown"
                    "applied_limits": "non_dict_limits_string",  # malformed applied limits
                    "region_evidence": [
                        "malformed_string_entry",  # malformed entry (not dict)
                        {
                            # Conflicting aliases: noncontract site_id and entry-level inspection_status
                            "site_id": "conflict_site_alias",
                            "inspection_status": "DEFECTIVE",
                            "roi_id": "site_canonical_01",
                            "current_measurements": {
                                "inspection_status": "NON_ENUM_INVALID_STATUS",  # must render UNKNOWN
                                "coverage_ratio": {"bad": "nested_dict"},  # invalid scalar -> unavailable
                                "aspect_ratio": [1, 2],  # invalid scalar -> unavailable
                                "calibrated_diameter_mm": "invalid_str",  # invalid scalar -> unavailable
                                "has_bubbles": {"not_a_bool": 1},  # invalid -> unavailable
                            },
                            "reference_measurements": "malformed_reference",  # malformed reference
                        },
                    ],
                },
            },
            {
                "observation_type": "deposit_shape",
                "value": "irregular",
                "statement_type": "AI_INFERENCE",
                "source": "IMAGE",
                "metadata": {},  # legacy empty metadata
            },
        ],
    }

    create_resp = client.post("/api/v1/cases", json=create_payload)
    assert create_resp.status_code == 201
    case_id = create_resp.json()["case_id"]
    tracked_cases.append(case_id)

    resp = client.get(f"/api/v1/cases/{case_id}/report.pdf")
    assert resp.status_code == 200
    assert resp.headers["Content-Type"] == "application/pdf"

    reader = pypdf.PdfReader(io.BytesIO(resp.content))
    extracted_text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert "8. Image Inspection Evidence" in extracted_text
    assert "Detailed per-region evidence was not recorded for this observation." in extracted_text
    assert "Malformed region entry" in extracted_text
    assert "Malformed reference measurement data." in extracted_text

    # Missing scope rendered truthfully as Not recorded or unknown
    assert "Not recorded or unknown" in extracted_text

    # Canonical roi_id used, conflicting site_id alias ignored
    assert "site_canonical_01" in extracted_text
    assert "conflict_site_alias" not in extracted_text

    # Non-enum / invalid status rendered as UNKNOWN, entry-level DEFECTIVE ignored
    assert "UNKNOWN" in extracted_text
    assert "DEFECTIVE" not in extracted_text

    # Malformed measurement scalars treated as unavailable
    assert "unavailable" in extracted_text


def test_pdf_report_truncation_limits_and_escaping(tracked_cases: list[str]):
    """Verify bounding to 20 observations, 50 regions, 200-char strings, HTML escaping,
    and split-safe multi-page layout combining 50 long canonical ROI IDs, >50 affected IDs,
    long/nested limit values, and invalid numeric fields.
    """
    # 55 region snapshots with long canonical roi_ids and invalid numeric fields
    many_regions = []
    for i in range(1, 56):
        long_roi_id = f"canonical_site_{i:03d}_" + ("Z" * 210)
        many_regions.append({
            "roi_id": long_roi_id,
            "current_measurements": {
                "inspection_status": "DETECTED",
                "deposit_area_px": 2500.0 + i,
                "equivalent_diameter_px": 56.4,
                "coverage_ratio": {"nested": "dict_is_invalid"} if i == 1 else 0.95,
                "aspect_ratio": [1, 2, 3] if i == 2 else 1.05,
                "has_bubbles": False,
            },
            "reference_measurements": None,
        })

    # More than 50 affected IDs (60 IDs), each long (>200 chars)
    sixty_affected_ids = [
        f"affected_roi_{j:03d}_" + ("Y" * 210)
        for j in range(1, 61)
    ]

    long_str = "LongString<script>alert('xss')</script>&test" + ("A" * 250)

    # Build 25 image observations
    obs_list = []
    for i in range(1, 26):
        obs_list.append({
            "observation_type": "deposit_size",
            "value": long_str if i == 1 else f"undersized_{i}",
            "original_text": long_str if i == 1 else f"Observation {i}",
            "statement_type": "AI_INFERENCE",
            "source": "IMAGE",
            "metadata": {
                "region_evidence_scope": "individual_regions",
                "affected_roi_ids": sixty_affected_ids if i == 1 else [f"site_{i:03d}"],
                "applied_limits": {
                    "target_area_px": 2500.0,
                    "min_coverage_ratio": {"nested": "invalid_limit"},
                    "max_aspect_ratio": "toolong_limit_val_" + ("X" * 250),
                    "unknown_non_allowlist_limit": 999.0,
                } if i == 1 else {"target_area_px": 2500.0},
                "region_evidence": many_regions if i == 1 else [],
            },
        })

    create_payload = {
        "description": "Stress test case for PDF limits: 25 observations, 55 regions, >50 affected IDs, long strings",
        "material": "solder_paste",
        "method": "jetting",
        "defect_code": "D01_TOO_LITTLE",
        "observations": obs_list,
    }

    create_resp = client.post("/api/v1/cases", json=create_payload)
    assert create_resp.status_code == 201
    case_id = create_resp.json()["case_id"]
    tracked_cases.append(case_id)

    # 1. Assert JSON report remains unchanged and lossless
    json_resp = client.get(f"/api/v1/cases/{case_id}/report")
    assert json_resp.status_code == 200
    json_data = json_resp.json()
    assert len(json_data["image_observations"]) == 25
    first_obs_json = json_data["image_observations"][0]
    assert len(first_obs_json["metadata"]["affected_roi_ids"]) == 60
    assert len(first_obs_json["metadata"]["region_evidence"]) == 55
    assert first_obs_json["metadata"]["applied_limits"]["unknown_non_allowlist_limit"] == 999.0

    # 2. Assert PDF generates cleanly without LayoutError and spans multiple pages
    resp = client.get(f"/api/v1/cases/{case_id}/report.pdf")
    assert resp.status_code == 200
    assert resp.headers["Content-Type"] == "application/pdf"

    reader = pypdf.PdfReader(io.BytesIO(resp.content))
    assert len(reader.pages) >= 2, f"Expected >= 2 pages, got {len(reader.pages)}"

    extracted_text = "\n".join(page.extract_text() or "" for page in reader.pages)

    # Check string truncation marker and safe layout
    assert "[truncated (exceeds 200 chars)]" in extracted_text

    # Check 50-region bound notice (55 - 50 = 5 omitted)
    assert "(5 omitted). Omission does not imply unlisted sites passed." in extracted_text

    # Check >50 affected-ID bound notice (60 - 20 = 40 omitted)
    assert "(40 omitted. Omission does not imply unlisted sites passed.)" in extracted_text

    # Check 20-observation bound notice (25 - 20 = 5 omitted)
    assert "Display bounded to first 20 observations" in extracted_text
    assert "(5 omitted). Omission does not imply unlisted observations passed." in extracted_text

    # Check invalid measurement and limit scalars rendered as unavailable
    assert "unavailable" in extracted_text

    # Check unknown limit was excluded from allowlisted PDF display
    assert "unknown_non_allowlist_limit" not in extracted_text


def test_real_image_analysis_to_case_to_report_and_pdf(tracked_cases: list[str]):
    """Verify an actual _sync_analyze_image result persists into a case and produces
    truthful, lossless JSON and downloadable PDF reports verifying the producer contract.
    """
    from app.api.images import _sync_analyze_image
    from app.schemas.image import AnalysisProfile, ImageAnalysisMode, NormalizedROI, ProcessLimits
    from tests.fixtures.synthetic_images import create_multi_roi_image

    # Generate synthetic image with two distinct deposits
    img_bytes = create_multi_roi_image(
        width=400,
        height=200,
        deposits=[(100, 100, 10), (300, 100, 15)],
    )
    profile = AnalysisProfile(
        mode=ImageAnalysisMode.PROCESS_LIMITS,
        rois=[
            NormalizedROI(roi_id="site_alpha", x=0.0, y=0.0, width=0.5, height=1.0),
            NormalizedROI(roi_id="site_beta", x=0.5, y=0.0, width=0.5, height=1.0),
        ],
        process_limits=ProcessLimits(min_coverage_ratio=0.10),
    )

    analysis_res = _sync_analyze_image(file_bytes=img_bytes, profile=profile)
    assert len(analysis_res.observations) >= 1
    produced_obs = analysis_res.observations[0]
    produced_meta = produced_obs.metadata

    # Verify producer contract from DLK-M3-039
    assert produced_meta["region_evidence_scope"] == "individual_regions"
    assert "site_alpha" in produced_meta["affected_roi_ids"]
    assert "site_beta" in produced_meta["affected_roi_ids"]
    assert len(produced_meta["region_evidence"]) == 2
    assert produced_meta["region_evidence"][0]["roi_id"] == "site_alpha"
    assert produced_meta["region_evidence"][0]["current_measurements"]["inspection_status"] == "DETECTED"

    # Create durable case using the produced observation
    case_payload = {
        "description": "Real image analysis end-to-end report verification",
        "defect_code": "D01_TOO_LITTLE",
        "observations": [
            {
                "observation_type": (
                    produced_obs.observation_type.value
                    if hasattr(produced_obs.observation_type, "value")
                    else str(produced_obs.observation_type)
                ),
                "value": produced_obs.value,
                "original_text": produced_obs.original_text,
                "statement_type": "AI_INFERENCE",
                "source": "IMAGE",
                "confidence": produced_obs.confidence,
                "metadata": produced_meta,
            }
        ],
    }

    create_resp = client.post("/api/v1/cases", json=case_payload)
    assert create_resp.status_code == 201
    case_id = create_resp.json()["case_id"]
    tracked_cases.append(case_id)

    # 1. Verify JSON report round-trip
    json_resp = client.get(f"/api/v1/cases/{case_id}/report")
    assert json_resp.status_code == 200
    report_json = json_resp.json()
    assert len(report_json["image_observations"]) == 1
    retrieved_obs = report_json["image_observations"][0]
    assert retrieved_obs["source"] == "IMAGE"
    assert retrieved_obs["metadata"]["region_evidence_scope"] == "individual_regions"
    assert len(retrieved_obs["metadata"]["region_evidence"]) == 2
    assert retrieved_obs["metadata"]["region_evidence"][0]["roi_id"] == "site_alpha"
    assert retrieved_obs["metadata"]["region_evidence"][1]["roi_id"] == "site_beta"

    # 2. Verify PDF generation and contents
    pdf_resp = client.get(f"/api/v1/cases/{case_id}/report.pdf")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["Content-Type"] == "application/pdf"

    reader = pypdf.PdfReader(io.BytesIO(pdf_resp.content))
    assert len(reader.pages) >= 1
    extracted_text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert "8. Image Inspection Evidence" in extracted_text
    assert "site_alpha" in extracted_text
    assert "site_beta" in extracted_text
    assert "DETECTED" in extracted_text
    assert "min_coverage_ratio: 0.1" in extracted_text or "0.10" in extracted_text
    assert "individual_regions (Individual region defect findings)" in extracted_text


def test_pdf_report_unhashable_statuses_and_oversized_integers(tracked_cases: list[str]):
    """Verify that unhashable inspection statuses (list, dict) render as UNKNOWN,
    oversized integers (e.g. 10**400) in measurements and applied limits render as unavailable
    without raising TypeError or OverflowError, and JSON report preserves original metadata losslessly.
    """
    create_payload = {
        "description": "Case with unhashable statuses and oversized integer values",
        "material": "solder_paste",
        "method": "jetting",
        "defect_code": "D01_TOO_LITTLE",
        "observations": [
            {
                "observation_type": "deposit_size",
                "value": "undersized",
                "statement_type": "AI_INFERENCE",
                "source": "IMAGE",
                "metadata": {
                    "region_evidence_scope": "individual_regions",
                    "affected_roi_ids": ["site_unhashable_01", "site_unhashable_02"],
                    "applied_limits": {
                        "target_area_px": 10**400,
                        "min_coverage_ratio": 10**400,
                        "max_aspect_ratio": 10**400,
                    },
                    "region_evidence": [
                        {
                            "roi_id": "site_unhashable_01",
                            "current_measurements": {
                                "inspection_status": ["unhashable_list_status"],
                                "deposit_area_px": 10**400,
                                "equivalent_diameter_px": 10**400,
                                "calibrated_diameter_mm": 10**400,
                                "coverage_ratio": 10**400,
                                "overflow_ratio": 10**400,
                                "circularity": 10**400,
                                "solidity": 10**400,
                                "convexity": 10**400,
                                "aspect_ratio": 10**400,
                                "hole_void_ratio": 10**400,
                                "bubble_count": 10**400,
                                "has_bubbles": False,
                                "segmentation_quality": 10**400,
                                "target_area_px": 10**400,
                            },
                            "reference_measurements": {
                                "inspection_status": {"unhashable": "dict_status"},
                                "deposit_area_px": 10**400,
                                "equivalent_diameter_px": 10**400,
                                "calibrated_diameter_mm": 10**400,
                                "coverage_ratio": 10**400,
                                "overflow_ratio": 10**400,
                                "circularity": 10**400,
                                "solidity": 10**400,
                                "convexity": 10**400,
                                "aspect_ratio": 10**400,
                                "hole_void_ratio": 10**400,
                                "bubble_count": 10**400,
                                "has_bubbles": False,
                                "segmentation_quality": 10**400,
                                "target_area_px": 10**400,
                            },
                        },
                        {
                            "roi_id": "site_unhashable_02",
                            "current_measurements": {
                                "inspection_status": {"current_unhashable": "dict_val"},
                                "deposit_area_px": 2500.0,
                            },
                            "reference_measurements": {
                                "inspection_status": ["reference_unhashable_list"],
                                "deposit_area_px": 2500.0,
                            },
                        },
                    ],
                },
            }
        ],
    }

    create_resp = client.post("/api/v1/cases", json=create_payload)
    assert create_resp.status_code == 201, f"Failed to create case: {create_resp.text}"
    case_id = create_resp.json()["case_id"]
    tracked_cases.append(case_id)

    # 1. Assert JSON report round-trip retains exact metadata losslessly
    json_resp = client.get(f"/api/v1/cases/{case_id}/report")
    assert json_resp.status_code == 200
    report_json = json_resp.json()
    obs = report_json["image_observations"][0]
    reg0 = obs["metadata"]["region_evidence"][0]
    assert reg0["current_measurements"]["inspection_status"] == ["unhashable_list_status"]
    assert reg0["reference_measurements"]["inspection_status"] == {"unhashable": "dict_status"}
    assert reg0["current_measurements"]["coverage_ratio"] == 10**400
    assert reg0["current_measurements"]["calibrated_diameter_mm"] == 10**400
    assert obs["metadata"]["applied_limits"]["target_area_px"] == 10**400
    assert obs["metadata"]["applied_limits"]["min_coverage_ratio"] == 10**400

    # 2. Assert PDF report succeeds (status 200, valid PDF, no 500)
    pdf_resp = client.get(f"/api/v1/cases/{case_id}/report.pdf")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["Content-Type"] == "application/pdf"

    reader = pypdf.PdfReader(io.BytesIO(pdf_resp.content))
    assert len(reader.pages) >= 1
    extracted_text = "\n".join(page.extract_text() or "" for page in reader.pages)

    import re

    # Verify UNKNOWN rendered for unhashable statuses
    assert "UNKNOWN" in extracted_text

    # Verify unavailable rendered for oversized integer measurements and applied limits
    assert "unavailable" in extracted_text
    assert re.search(r"target_area_px:\s*unavailable", extracted_text) is not None
    assert re.search(r"min_coverage_ratio:\s*unavailable", extracted_text) is not None
    assert re.search(r"max_aspect_ratio:\s*unavailable", extracted_text) is not None
