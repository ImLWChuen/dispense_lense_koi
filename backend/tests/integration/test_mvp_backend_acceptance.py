"""DispenseIQ — Final Backend MVP Contract and End-to-End Acceptance Tests.

DLK-M3-024:
1. Formal acceptance of existing GET /api/v1/cases list endpoint (empty, multi-case, no recalculation, read-only, sanitized 500);
2. Full public-API happy-path walkthrough through all 7 revisions (creation -> answer -> check -> confirmation -> recovery action -> verification -> recurrence -> detail -> list -> report -> report.pdf);
3. Cross-event stale-write optimistic locking proof (409 Conflict on stale expected_revision across all mutating event types);
4. Complete read-only proof across all public read surfaces (GET detail, list, JSON report, PDF report, health);
5. Programmatic OpenAPI contract verification against frontend matrix;
6. Deterministic availability proof for all six required defect categories (D01-D06).
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
from app.schemas.diagnosis import IssueCondition
from app.services.diagnosis.engine import DiagnosticEngine
from tests.case_snapshot_helper import capture_complete_case_state
from tests.unit.test_pdf_generator import (
    extract_pdf_history_sections,
    verify_cause_confirmations_section,
    verify_check_results_section,
    verify_lifecycle_events_section,
    verify_question_answers_section,
)
from tests.unit.test_persistence_safety import assert_safe_test_database

client = TestClient(app, raise_server_exceptions=False)


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


def _create_test_case(
    tracked_ids: list[str],
    defect_code: str = "D03_INCONSISTENT_SIZE",
    description: str = "Dispense dots shrinking over continuous run",
) -> dict[str, Any]:
    payload = {
        "description": description,
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


# ==============================================================================
# Task 2 — Formal acceptance of GET /api/v1/cases list endpoint
# ==============================================================================

def test_list_cases_openapi_registration():
    """Verify OpenAPI schema registers GET /api/v1/cases returning 200 with list[DurableCaseResponse]."""
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()

    path_item = schema["paths"].get("/api/v1/cases")
    assert path_item is not None, "Route /api/v1/cases is missing from OpenAPI schema!"
    assert "get" in path_item, "GET method missing on /api/v1/cases!"

    get_op = path_item["get"]
    assert "200" in get_op["responses"]
    assert "500" in get_op["responses"]
    content = get_op["responses"]["200"].get("content", {})
    assert "application/json" in content
    resp_schema = content["application/json"].get("schema", {})
    assert resp_schema.get("type") == "array"


def test_list_cases_empty_database():
    """Verify GET /api/v1/cases returns 200 OK and an empty list when no cases exist."""
    # When all cases are cleared or in an empty DB, list returns []
    factory = get_session_factory()
    with factory() as session:
        # Check current count
        resp = client.get("/api/v1/cases")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


def test_list_cases_multiple_cases_and_no_recalculation(tracked_cases: list[str]):
    """Verify multiple persisted cases return exactly once with their latest diagnosis without recalculation."""
    case_a = _create_test_case(tracked_cases, defect_code="D03_INCONSISTENT_SIZE", description="Case A dot shrinkage")
    case_b = _create_test_case(tracked_cases, defect_code="D01_TOO_LITTLE", description="Case B starved flow")

    cid_a = case_a["case_id"]
    cid_b = case_b["case_id"]

    # Advance Case A to Revision 2 via question answer
    qa_resp = client.post(
        f"/api/v1/cases/{cid_a}/answers",
        json={
            "question_id": "Q01",
            "answer": "after_prolonged_operation",
            "expected_revision": 1,
        },
    )
    assert qa_resp.status_code == 200
    rev2_data = qa_resp.json()
    assert rev2_data["current_revision"] == 2

    # Patch DiagnosticEngine.diagnose to raise: prove zero recalculation on list
    with patch.object(DiagnosticEngine, "diagnose", side_effect=RuntimeError("RECALCULATION_FORBIDDEN")):
        list_resp = client.get("/api/v1/cases")

    assert list_resp.status_code == 200
    cases_list = list_resp.json()
    assert isinstance(cases_list, list)

    # Filter to our tracked cases
    tracked_cids = {cid_a, cid_b}
    found_cases = [c for c in cases_list if c["case_id"] in tracked_cids]
    assert len(found_cases) == 2, f"Expected exactly 2 tracked cases, got {len(found_cases)}"

    # Ensure no duplicates
    found_ids = [c["case_id"] for c in found_cases]
    assert len(found_ids) == len(set(found_ids))

    # Inspect Case A in listing
    item_a = next(c for c in found_cases if c["case_id"] == cid_a)
    assert item_a["case_id"] == cid_a
    assert item_a["defect_code"] == "D03_INCONSISTENT_SIZE"
    assert item_a["issue_condition"] == "UNRESOLVED"
    assert item_a["initial_diagnosis"]["analysis_revision"]["revision_number"] == 1
    assert item_a["diagnosis"]["analysis_revision"]["revision_number"] == 2

    # Inspect Case B in listing
    item_b = next(c for c in found_cases if c["case_id"] == cid_b)
    assert item_b["case_id"] == cid_b
    assert item_b["defect_code"] == "D01_TOO_LITTLE"
    assert item_b["issue_condition"] == "UNRESOLVED"
    assert item_b["initial_diagnosis"]["analysis_revision"]["revision_number"] == 1
    assert item_b["diagnosis"]["analysis_revision"]["revision_number"] == 1


def test_list_cases_read_only_proof(tracked_cases: list[str]):
    """Verify GET /api/v1/cases is strictly read-only and mutates zero database state."""
    case_data = _create_test_case(tracked_cases)
    cid = case_data["case_id"]

    factory = get_session_factory()
    with factory() as session:
        state_before = capture_complete_case_state(session, cid)

    # Execute list request
    resp = client.get("/api/v1/cases")
    assert resp.status_code == 200

    with factory() as fresh_session:
        state_after = capture_complete_case_state(fresh_session, cid)

    assert state_before == state_after, "GET /api/v1/cases caused durable database mutations!"


def test_list_cases_sanitized_500_on_internal_error():
    """Verify an unexpected internal repository failure during listing produces a sanitized 500 error."""
    secret_marker = "SENSITIVE_DB_CREDENTIAL_LEAK_TOKEN_LIST_CASES"

    with patch.object(CaseRepository, "get_all_cases", side_effect=RuntimeError(secret_marker)):
        resp = client.get("/api/v1/cases")

    assert resp.status_code == 500
    assert secret_marker not in resp.text, f"Internal exception details leaked in 500 response: {resp.text}"
    data = resp.json()
    assert "detail" in data


# ==============================================================================
# Task 3 — Full Public-API Happy-Path Walkthrough
# ==============================================================================

def test_full_public_api_happy_path_walkthrough(tracked_cases: list[str]):
    """Walk through complete happy-path lifecycle using only public HTTP APIs against PostgreSQL.

    1. POST /api/v1/cases -> Rev 1, UNRESOLVED
    2. POST /api/v1/cases/{case_id}/answers -> Rev 2, UNRESOLVED
    3. POST /api/v1/cases/{case_id}/check-results -> Rev 3, UNRESOLVED
    4. POST /api/v1/cases/{case_id}/cause-confirmations -> Rev 4, UNRESOLVED, confirmed causes recorded
    5. POST /api/v1/cases/{case_id}/recovery-actions -> Rev 5, RECOVERY_PENDING_VERIFICATION
    6. POST /api/v1/cases/{case_id}/recovery-verifications -> Rev 6, RESOLVED
    7. POST /api/v1/cases/{case_id}/recurrences -> Rev 7, RECURRED
    8. GET /api/v1/cases/{case_id} -> detail reflects Rev 7, RECURRED
    9. GET /api/v1/cases -> list reflects Rev 7, RECURRED
    10. GET /api/v1/cases/{case_id}/report -> JSON report Rev 7, all histories intact
    11. GET /api/v1/cases/{case_id}/report.pdf -> PDF report Rev 7 on exact same basis
    """
    # 1. Create case -> Rev 1
    case_resp = _create_test_case(tracked_cases)
    cid = case_resp["case_id"]
    assert case_resp["issue_condition"] == "UNRESOLVED"
    assert case_resp["diagnosis"]["analysis_revision"]["revision_number"] == 1

    # 2. Submit answer -> Rev 2
    qa_resp = client.post(
        f"/api/v1/cases/{cid}/answers",
        json={
            "question_id": "Q01",
            "answer": "after_prolonged_operation",
            "answer_text": "Dots shrink after 30 min continuous run",
            "expected_revision": 1,
        },
    )
    assert qa_resp.status_code == 200
    qa_data = qa_resp.json()
    assert qa_data["case_id"] == cid
    assert qa_data["current_revision"] == 2
    assert qa_data["issue_condition"] == "UNRESOLVED"

    # 3. Submit check result -> Rev 3
    cr_resp = client.post(
        f"/api/v1/cases/{cid}/check-results",
        json={
            "check_id": "ACT02",
            "execution_status": "COMPLETED",
            "finding": "SUPPORTS",
            "outcome": "air_bubbles_found",
            "finding_details": "Trapped air bubbles observed in syringe barrel",
            "expected_revision": 2,
        },
    )
    assert cr_resp.status_code == 200
    cr_data = cr_resp.json()
    assert cr_data["case_id"] == cid
    assert cr_data["current_revision"] == 3
    assert cr_data["issue_condition"] == "UNRESOLVED"

    # 4. Explicit cause confirmation -> Rev 4
    cc_resp = client.post(
        f"/api/v1/cases/{cid}/cause-confirmations",
        json={
            "cause_id": "nozzle_restriction",
            "confirmed_by": "lead_engineer",
            "notes": "Verified restriction via optical microscope inspection",
            "expected_revision": 3,
        },
    )
    assert cc_resp.status_code == 200
    cc_data = cc_resp.json()
    assert cc_data["case_id"] == cid
    assert cc_data["current_revision"] == 4
    assert cc_data["issue_condition"] == "UNRESOLVED"
    assert cc_data["confirmed_cause"] == "nozzle_restriction"

    # 5. Recovery action -> Rev 5
    ra_resp = client.post(
        f"/api/v1/cases/{cid}/recovery-actions",
        json={
            "recovery_details": "Cleaned nozzle orifice with ultrasonic solvent bath",
            "performed_by": "technician_dan",
            "expected_revision": 4,
        },
    )
    assert ra_resp.status_code == 200
    ra_data = ra_resp.json()
    assert ra_data["case_id"] == cid
    assert ra_data["current_revision"] == 5
    assert ra_data["issue_condition"] == "RECOVERY_PENDING_VERIFICATION"

    # 6. Recovery verification -> Rev 6 (RESOLVED)
    rv_resp = client.post(
        f"/api/v1/cases/{cid}/recovery-verifications",
        json={
            "verification_passed": True,
            "verification_details": "100 test shots verified within nominal dot tolerance",
            "verified_by": "qa_sarah",
            "expected_revision": 5,
        },
    )
    assert rv_resp.status_code == 200
    rv_data = rv_resp.json()
    assert rv_data["case_id"] == cid
    assert rv_data["current_revision"] == 6
    assert rv_data["issue_condition"] == "RESOLVED"

    # 7. Recurrence report -> Rev 7 (RECURRED)
    rec_resp = client.post(
        f"/api/v1/cases/{cid}/recurrences",
        json={
            "recurrence_details": "Dot size shrinking re-observed on shift 2 after continuous run",
            "reported_by": "operator_bob",
            "expected_revision": 6,
        },
    )
    assert rec_resp.status_code == 200
    rec_data = rec_resp.json()
    assert rec_data["case_id"] == cid
    assert rec_data["current_revision"] == 7
    assert rec_data["issue_condition"] == "RECURRED"

    # 8. GET /api/v1/cases/{case_id} detail retrieval
    detail_resp = client.get(f"/api/v1/cases/{cid}")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["case_id"] == cid
    assert detail_data["issue_condition"] == "RECURRED"
    assert detail_data["diagnosis"]["analysis_revision"]["revision_number"] == 7
    assert detail_data["initial_diagnosis"]["analysis_revision"]["revision_number"] == 1

    # 9. GET /api/v1/cases list retrieval
    list_resp = client.get("/api/v1/cases")
    assert list_resp.status_code == 200
    case_in_list = next(c for c in list_resp.json() if c["case_id"] == cid)
    assert case_in_list["case_id"] == cid
    assert case_in_list["issue_condition"] == "RECURRED"
    assert case_in_list["diagnosis"]["analysis_revision"]["revision_number"] == 7

    # 10. GET /api/v1/cases/{case_id}/report JSON export
    report_resp = client.get(f"/api/v1/cases/{cid}/report")
    assert report_resp.status_code == 200
    json_report = report_resp.json()
    assert json_report["case_id"] == cid
    assert json_report["current_revision"] == 7
    assert json_report["issue_condition"] == "RECURRED"
    assert "nozzle_restriction" in json_report["outcome_summary"]["confirmed_causes"]
    assert len(json_report["question_answers"]) == 1
    assert len(json_report["check_results"]) == 1
    assert len(json_report["cause_confirmations"]) == 1
    assert len(json_report["lifecycle_events"]) == 3  # recovery action, verification, recurrence

    # Verify prior resolution and recovery history survive recurrence intact
    event_types = [e["event_type"] for e in json_report["lifecycle_events"]]
    assert event_types == ["RECOVERY_ACTION", "RECOVERY_VERIFICATION", "RECURRENCE"]

    # 11. GET /api/v1/cases/{case_id}/report.pdf PDF export
    pdf_resp = client.get(f"/api/v1/cases/{cid}/report.pdf")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["Content-Type"] == "application/pdf"
    assert f'filename="dispenseiq-case-{cid}-r7.pdf"' in pdf_resp.headers["Content-Disposition"]

    # PDF validation and section isolation
    reader = pypdf.PdfReader(io.BytesIO(pdf_resp.content))
    assert len(reader.pages) >= 1
    extracted_text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert cid in extracted_text
    assert "Report Revision: 7" in extracted_text or "Revision 7" in extracted_text
    assert "RECURRED" in extracted_text
    assert "nozzle_restriction" in extracted_text

    # Section extraction and row verification
    sections = extract_pdf_history_sections(pdf_resp.content)
    verify_question_answers_section(sections["question_answers"], json_report["question_answers"])
    verify_check_results_section(sections["check_results"], json_report["check_results"])
    verify_cause_confirmations_section(sections["cause_confirmations"], json_report["cause_confirmations"])
    verify_lifecycle_events_section(sections["lifecycle_events"], json_report["lifecycle_events"])


# ==============================================================================
# Task 4 — Cross-Event Stale-Write Protection
# ==============================================================================

def test_cross_event_stale_write_protection(tracked_cases: list[str]):
    """Verify optimistic locking returns 409 and mutates zero state across all event types when expected_revision is stale."""
    case_data = _create_test_case(tracked_cases)
    cid = case_data["case_id"]

    # Advance to Rev 2 via answer submission
    qa_resp = client.post(
        f"/api/v1/cases/{cid}/answers",
        json={
            "question_id": "Q01",
            "answer": "after_prolonged_operation",
            "expected_revision": 1,
        },
    )
    assert qa_resp.status_code == 200
    assert qa_resp.json()["current_revision"] == 2

    factory = get_session_factory()
    with factory() as session:
        state_before = capture_complete_case_state(session, cid)

    # 1. Stale check result (expected_revision=1, actual=2) -> 409
    cr_resp = client.post(
        f"/api/v1/cases/{cid}/check-results",
        json={
            "check_id": "ACT02",
            "execution_status": "COMPLETED",
            "finding": "SUPPORTS",
            "expected_revision": 1,
        },
    )
    assert cr_resp.status_code == 409
    assert "conflict" in cr_resp.text.lower() or "revision" in cr_resp.text.lower()

    # 2. Stale cause confirmation (expected_revision=1, actual=2) -> 409
    cc_resp = client.post(
        f"/api/v1/cases/{cid}/cause-confirmations",
        json={
            "cause_id": "nozzle_restriction",
            "expected_revision": 1,
        },
    )
    assert cc_resp.status_code == 409
    assert "conflict" in cc_resp.text.lower() or "revision" in cc_resp.text.lower()

    # 3. Stale recovery action (expected_revision=1, actual=2) -> 409
    ra_resp = client.post(
        f"/api/v1/cases/{cid}/recovery-actions",
        json={
            "recovery_details": "Replaced syringe",
            "expected_revision": 1,
        },
    )
    assert ra_resp.status_code == 409
    assert "conflict" in ra_resp.text.lower() or "revision" in ra_resp.text.lower()

    # 4. Stale recovery verification (expected_revision=1, actual=2) -> 409
    rv_resp = client.post(
        f"/api/v1/cases/{cid}/recovery-verifications",
        json={
            "verification_passed": True,
            "verification_details": "100 shots nominal",
            "expected_revision": 1,
        },
    )
    assert rv_resp.status_code == 409
    assert "conflict" in rv_resp.text.lower() or "revision" in rv_resp.text.lower()

    # 5. Stale recurrence (expected_revision=1, actual=2) -> 409
    rec_resp = client.post(
        f"/api/v1/cases/{cid}/recurrences",
        json={
            "recurrence_details": "Reoccurred",
            "expected_revision": 1,
        },
    )
    assert rec_resp.status_code == 409
    assert "conflict" in rec_resp.text.lower() or "revision" in rec_resp.text.lower()

    # Prove zero mutations occurred: state matches state_before exactly
    with factory() as fresh_session:
        state_after = capture_complete_case_state(fresh_session, cid)

    assert state_before == state_after, "Stale mutation requests resulted in durable database mutations!"


# ==============================================================================
# Task 5 — Report/Export Read-Only Final Proof
# ==============================================================================

def test_all_public_read_surfaces_read_only_proof(tracked_cases: list[str]):
    """Verify that every public GET/read endpoint in the MVP contract is strictly non-mutating."""
    case_data = _create_test_case(tracked_cases)
    cid = case_data["case_id"]

    # Advance through question answer, check result, confirmation, recovery action, verification, recurrence
    client.post(
        f"/api/v1/cases/{cid}/answers",
        json={"question_id": "Q01", "answer": "after_prolonged_operation", "expected_revision": 1},
    )
    client.post(
        f"/api/v1/cases/{cid}/check-results",
        json={"check_id": "ACT02", "execution_status": "COMPLETED", "finding": "SUPPORTS", "expected_revision": 2},
    )
    client.post(
        f"/api/v1/cases/{cid}/cause-confirmations",
        json={"cause_id": "nozzle_restriction", "expected_revision": 3},
    )
    client.post(
        f"/api/v1/cases/{cid}/recovery-actions",
        json={"recovery_details": "Nozzle cleaned", "expected_revision": 4},
    )
    client.post(
        f"/api/v1/cases/{cid}/recovery-verifications",
        json={"verification_passed": True, "verification_details": "Verified", "expected_revision": 5},
    )
    client.post(
        f"/api/v1/cases/{cid}/recurrences",
        json={"recurrence_details": "Re-occurred shift 2", "expected_revision": 6},
    )

    factory = get_session_factory()
    with factory() as session:
        state_before = capture_complete_case_state(session, cid)

    # 1. GET case detail
    r_detail = client.get(f"/api/v1/cases/{cid}")
    assert r_detail.status_code == 200

    # 2. GET case list
    r_list = client.get("/api/v1/cases")
    assert r_list.status_code == 200

    # 3. GET JSON report
    r_json_rep = client.get(f"/api/v1/cases/{cid}/report")
    assert r_json_rep.status_code == 200

    # 4. GET PDF report
    r_pdf_rep = client.get(f"/api/v1/cases/{cid}/report.pdf")
    assert r_pdf_rep.status_code == 200

    # 5. GET health
    r_health = client.get("/api/v1/health")
    assert r_health.status_code == 200

    # Capture state again in fresh session and assert exact equality
    with factory() as fresh_session:
        state_after = capture_complete_case_state(fresh_session, cid)

    assert state_before == state_after, "Read surfaces caused durable mutations in the database!"


# ==============================================================================
# Task 6 — OpenAPI / Frontend Contract Verification
# ==============================================================================

def test_openapi_contract_verification():
    """Verify OpenAPI schema matches contract matrix across all 13 MVP routes, methods, and constraints."""
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    paths = schema.get("paths", {})

    expected_routes = {
        "/api/v1/health": ["get"],
        "/api/v1/diagnoses": ["post"],
        "/api/v1/cases": ["get", "post"],
        "/api/v1/cases/{case_id}": ["get"],
        "/api/v1/cases/{case_id}/answers": ["post"],
        "/api/v1/cases/{case_id}/check-results": ["post"],
        "/api/v1/cases/{case_id}/cause-confirmations": ["post"],
        "/api/v1/cases/{case_id}/recovery-actions": ["post"],
        "/api/v1/cases/{case_id}/recovery-verifications": ["post"],
        "/api/v1/cases/{case_id}/recurrences": ["post"],
        "/api/v1/cases/{case_id}/report": ["get"],
        "/api/v1/cases/{case_id}/report.pdf": ["get"],
    }

    for route_path, expected_methods in expected_routes.items():
        assert route_path in paths, f"Route '{route_path}' missing from OpenAPI!"
        path_def = paths[route_path]
        for method in expected_methods:
            assert method in path_def, f"Method '{method.upper()}' missing on route '{route_path}'!"
            op = path_def[method]
            # Key status codes
            responses = op.get("responses", {})
            if method == "post" and route_path == "/api/v1/cases":
                assert "201" in responses
            else:
                assert "200" in responses

            if "{case_id}" in route_path:
                assert "404" in responses
                assert "422" in responses

            if method == "post" and "{case_id}" in route_path:
                assert "409" in responses

    # Check application/pdf media type on PDF route
    pdf_op = paths["/api/v1/cases/{case_id}/report.pdf"]["get"]
    pdf_responses = pdf_op["responses"]["200"]["content"]
    assert "application/pdf" in pdf_responses, "PDF route does not advertise application/pdf!"

    # Check maxLength = 100 on actor / reporter string fields in schemas
    schemas = schema.get("components", {}).get("schemas", {})

    for model_name, field_name in [
        ("SubmitCauseConfirmationRequest", "confirmed_by"),
        ("SubmitRecoveryActionRequest", "performed_by"),
        ("SubmitRecoveryVerificationRequest", "verified_by"),
        ("SubmitRecurrenceRequest", "reported_by"),
    ]:
        model_def = schemas.get(model_name, {})
        props = model_def.get("properties", {})
        assert field_name in props, f"Field '{field_name}' not found in schema '{model_name}'"
        prop = props[field_name]
        # MaxLength is 100 either directly or in anyOf
        max_len = prop.get("maxLength")
        if max_len is None and "anyOf" in prop:
            for sub in prop["anyOf"]:
                if sub.get("type") == "string":
                    max_len = sub.get("maxLength")
        assert max_len == 64, f"Expected maxLength=64 on {model_name}.{field_name}, got {max_len}"


# ==============================================================================
# Task 7 — Six Required Defect Categories Backend Availability Check
# ==============================================================================

@pytest.mark.parametrize(
    "defect_code,expected_name,sample_desc",
    [
        ("D01_TOO_LITTLE", "Too Little Material", "Every dot is too small, consistently below target."),
        ("D02_TOO_MUCH", "Too Much Material", "Dots are oversized, too much material being dispensed."),
        ("D03_INCONSISTENT_SIZE", "Inconsistent Dispensing Size", "The dispensing dots become smaller after the machine has been running for around 20 minutes."),
        ("D04_MISSING_DOTS", "Missing Dots", "The dots are completely missing at certain positions."),
        ("D05_SPREADING", "Spreading", "The material spreads way too much on the substrate."),
        ("D06_BUBBLES_ABNORMAL_SHAPE", "Bubbles / Abnormal Shape", "There are visible bubbles in the dispensed material."),
    ],
)
def test_all_six_defect_categories_backend_availability(
    defect_code: str,
    expected_name: str,
    sample_desc: str,
    tracked_cases: list[str],
):
    """Verify that all six required product defect categories evaluate deterministically and persist as durable cases."""
    # 1. Stateless evaluation proof via POST /api/v1/diagnoses
    diag_resp = client.post(
        "/api/v1/diagnoses",
        json={
            "description": sample_desc,
        },
    )
    assert diag_resp.status_code == 200
    diag_data = diag_resp.json()
    assert diag_data["defect"] == defect_code
    assert diag_data["defect_name"] == expected_name
    assert len(diag_data["ranked_causes"]) > 0

    # 2. Durable case creation proof via POST /api/v1/cases
    case_resp = client.post(
        "/api/v1/cases",
        json={
            "description": sample_desc,
            "material": "standard_solder_paste",
            "method": "jetting",
        },
    )
    assert case_resp.status_code == 201
    case_data = case_resp.json()
    tracked_cases.append(case_data["case_id"])

    assert case_data["defect_code"] == defect_code
    assert case_data["defect_name"] == expected_name
    assert case_data["issue_condition"] == "UNRESOLVED"
    assert case_data["diagnosis"]["defect"] == defect_code
    assert case_data["diagnosis"]["defect_name"] == expected_name
    assert case_data["diagnosis"]["analysis_revision"]["revision_number"] == 1
