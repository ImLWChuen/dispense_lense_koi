"""
DispenseIQ — Technician Question-Answer Submission API Integration Tests

Tests persistent technician question-answer submission (POST /api/v1/cases/{case_id}/answers)
against real PostgreSQL. Verifies atomicity, provenance preservation, optimistic concurrency
via expected_revision, clean 409 stale-revision handling, 404 missing case handling, 422 validation
rejections, UNKNOWN/NOT_APPLICABLE semantics, prior revision immutability, and API regression safety.
"""

from __future__ import annotations

import copy
import os
import uuid
from typing import Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, event
from sqlalchemy.orm import Session

from app.core.config import get_database_url
from app.db.database import get_engine, reset_engine
from app.db.repository import CaseRepository
from app.db.session import get_session_factory
from app.main import app
from app.models.case import AnalysisRevisionModel, CaseModel, ObservationModel, QuestionAnswerModel
from app.schemas.diagnosis import CauseConclusion, DiagnosisResult, EvidenceSource, ObservationType, QuestionAnswer
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
            # Cascades to case_observations, case_analysis_revisions, and case_question_answers
            session.execute(delete(CaseModel).where(CaseModel.case_id.in_(case_ids)))
            session.commit()


# ===========================================================================
# 1. OpenAPI & Route Registration Verification
# ===========================================================================

def test_question_answer_endpoint_registered_in_openapi():
    """Verify that POST /api/v1/cases/{case_id}/answers is present in OpenAPI specification."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema["paths"]

    assert "/api/v1/cases/{case_id}/answers" in paths
    answer_path = paths["/api/v1/cases/{case_id}/answers"]
    assert "post" in answer_path
    responses = answer_path["post"]["responses"]
    assert "200" in responses
    assert "404" in responses
    assert "409" in responses
    assert "422" in responses


# ===========================================================================
# 2. Scenario 1: Valid Answer Creates Revision 2
# ===========================================================================

def test_valid_answer_creates_revision_2(tracked_cases: list[str]):
    """Scenario 1:
    - Create a durable case;
    - Submit valid answer for case's recommended question;
    - Assert 200;
    - Assert revision changes from 1 to 2;
    - Reload durable state and verify answer + revision 2.
    """
    # 1. Create durable case
    create_payload = {
        "description": "Dispense dots are shrinking over time during continuous operation",
        "defect_code": "D03_INCONSISTENT_SIZE",
        "material": "solder_paste",
        "method": "jetting",
    }
    create_resp = client.post("/api/v1/cases", json=create_payload)
    assert create_resp.status_code == 201
    case_data = create_resp.json()
    case_id = case_data["case_id"]
    tracked_cases.append(case_id)

    assert case_data["initial_diagnosis"]["analysis_revision"]["revision_number"] == 1

    # 2. Submit question answer for Q01 with expected_revision=1
    answer_payload = {
        "question_id": "Q01",
        "answer": "after_prolonged_operation",
        "expected_revision": 1,
        "answer_text": "Shrinking starts after 30 minutes of running",
    }
    ans_resp = client.post(f"/api/v1/cases/{case_id}/answers", json=answer_payload)
    assert ans_resp.status_code == 200
    ans_data = ans_resp.json()

    # 3. Assert revision changes from 1 to 2
    assert ans_data["case_id"] == case_id
    assert ans_data["current_revision"] == 2
    assert ans_data["diagnosis"]["analysis_revision"]["revision_number"] == 2
    assert ans_data["submitted_answer"]["question_id"] == "Q01"
    assert ans_data["submitted_answer"]["answer_value"] == "after_prolonged_operation"
    assert ans_data["submitted_answer"]["resulting_revision_number"] == 2
    assert len(ans_data["previous_answers"]) == 1
    assert ans_data["previous_answers"][0]["question_id"] == "Q01"

    # 4. Reload durable state via repository and verify
    factory = get_session_factory()
    with factory() as session:
        repo = CaseRepository(session)
        loaded = repo.load_structured_case(case_id)
        assert loaded is not None
        assert len(loaded.analysis_revisions) == 2
        assert loaded.analysis_revisions[0].revision_number == 1
        assert loaded.analysis_revisions[1].revision_number == 2
        assert len(loaded.previous_answers) == 1
        assert loaded.previous_answers[0].question_id == "Q01"
        assert loaded.previous_answers[0].answer_value == "after_prolonged_operation"

        # Check raw DB tables
        qa_rows = repo.get_case_question_answers(case_id)
        assert len(qa_rows) == 1
        assert qa_rows[0].question_id == "Q01"
        assert qa_rows[0].resulting_revision_number == 2

        rev_nums = repo.list_case_revisions(case_id)
        assert rev_nums == [1, 2]


# ===========================================================================
# 3. Scenario 2: Evidence-Producing Answer
# ===========================================================================

def test_evidence_producing_answer_semantics_and_provenance(tracked_cases: list[str]):
    """Scenario 2:
    - Select a stable Member 2 question/answer pair known to create evidence (Q01: after_prolonged_operation);
    - Verify exact observation semantics and provenance after reload;
    - Verify diagnosis result reflects the accepted Member 2 behavior.
    """
    create_payload = {
        "description": "Dispensing dots become smaller",
        "defect_code": "D03_INCONSISTENT_SIZE",
    }
    create_resp = client.post("/api/v1/cases", json=create_payload)
    assert create_resp.status_code == 201
    case_data = create_resp.json()
    case_id = case_data["case_id"]
    tracked_cases.append(case_id)

    initial_obs_count = len(case_data["observations"])

    # Submit Q01
    answer_payload = {
        "question_id": "Q01",
        "answer": "after_prolonged_operation",
        "expected_revision": 1,
    }
    ans_resp = client.post(f"/api/v1/cases/{case_id}/answers", json=answer_payload)
    assert ans_resp.status_code == 200
    ans_data = ans_resp.json()

    # Evidence should have been added
    assert len(ans_data["observations"]) > initial_obs_count

    # Check that newly generated observations have first_seen_revision == 2 and source == USER
    new_obs = [o for o in ans_data["observations"] if o["first_seen_revision"] == 2]
    assert len(new_obs) >= 1
    for o in new_obs:
        assert o["source"] in ("USER", "USER_ANSWER")
        assert o["first_seen_revision"] == 2

    # Verify reload from repository reflects exact observations
    factory = get_session_factory()
    with factory() as session:
        repo = CaseRepository(session)
        obs_models = repo.get_case_observations(case_id)
        rev2_obs = [o for o in obs_models if o.first_seen_revision == 2]
        assert len(rev2_obs) >= 1
        obs_types = {o.observation_type for o in rev2_obs}
        # Member 2's Q01 produces RUNTIME_PATTERN and QUESTION_ANSWER observations
        assert any("runtime_pattern" in ot.lower() for ot in obs_types) or any(
            "question_answer" in ot.lower() for ot in obs_types
        )


# ===========================================================================
# 4. Scenario 3: UNKNOWN Handling
# ===========================================================================

def test_unknown_answer_persists_without_fabricated_evidence(tracked_cases: list[str]):
    """Scenario 3:
    - Submit UNKNOWN;
    - Answer history persists;
    - Revision advances;
    - No fabricated evidence observation is added for the question answer.
    """
    create_payload = {
        "description": "Needle drips fluid after dispensing",
        "defect_code": "D03_INCONSISTENT_SIZE",
    }
    create_resp = client.post("/api/v1/cases", json=create_payload)
    assert create_resp.status_code == 201
    case_data = create_resp.json()
    case_id = case_data["case_id"]
    tracked_cases.append(case_id)

    initial_obs_count = len(case_data["observations"])

    # Submit UNKNOWN
    answer_payload = {
        "question_id": "Q01",
        "answer": "UNKNOWN",
        "expected_revision": 1,
    }
    ans_resp = client.post(f"/api/v1/cases/{case_id}/answers", json=answer_payload)
    assert ans_resp.status_code == 200
    ans_data = ans_resp.json()

    # Revision advances
    assert ans_data["current_revision"] == 2
    assert ans_data["submitted_answer"]["question_id"] == "Q01"
    assert ans_data["submitted_answer"]["answer_value"] == "UNKNOWN"

    # Observation count must NOT increase (no fabricated evidence)
    assert len(ans_data["observations"]) == initial_obs_count

    # Database verification
    factory = get_session_factory()
    with factory() as session:
        repo = CaseRepository(session)
        loaded = repo.load_structured_case(case_id)
        assert loaded is not None
        assert len(loaded.observations) == initial_obs_count
        assert len(loaded.previous_answers) == 1
        assert loaded.previous_answers[0].answer_value == "UNKNOWN"


# ===========================================================================
# 5. Scenario 4: NOT_APPLICABLE Handling
# ===========================================================================

def test_not_applicable_answer_persists_without_fabricated_evidence(tracked_cases: list[str]):
    """Scenario 4:
    - Submit NOT_APPLICABLE;
    - Same expectations as UNKNOWN regarding diagnostic evidence.
    """
    create_payload = {
        "description": "Dispensing dots inconsistent",
        "defect_code": "D03_INCONSISTENT_SIZE",
    }
    create_resp = client.post("/api/v1/cases", json=create_payload)
    assert create_resp.status_code == 201
    case_data = create_resp.json()
    case_id = case_data["case_id"]
    tracked_cases.append(case_id)

    initial_obs_count = len(case_data["observations"])

    # Submit NOT_APPLICABLE
    answer_payload = {
        "question_id": "Q02",
        "answer": "NOT_APPLICABLE",
        "expected_revision": 1,
    }
    ans_resp = client.post(f"/api/v1/cases/{case_id}/answers", json=answer_payload)
    assert ans_resp.status_code == 200
    ans_data = ans_resp.json()

    # Revision advances
    assert ans_data["current_revision"] == 2
    assert ans_data["submitted_answer"]["question_id"] == "Q02"
    assert ans_data["submitted_answer"]["answer_value"] == "NOT_APPLICABLE"

    # Observation count must NOT increase (no fabricated evidence)
    assert len(ans_data["observations"]) == initial_obs_count

    # Database verification
    factory = get_session_factory()
    with factory() as session:
        repo = CaseRepository(session)
        loaded = repo.load_structured_case(case_id)
        assert loaded is not None
        assert len(loaded.observations) == initial_obs_count
        assert len(loaded.previous_answers) == 1
        assert loaded.previous_answers[0].answer_value == "NOT_APPLICABLE"


# ===========================================================================
# 6. Scenario 5: Stale Revision Returns 409
# ===========================================================================

def test_stale_expected_revision_returns_409(tracked_cases: list[str]):
    """Scenario 5:
    - Successfully submit one answer;
    - Submit another request using the prior revision number;
    - Expect 409;
    - Verify counts/state unchanged after the rejected request.
    """
    create_payload = {
        "description": "Inconsistent dot size",
        "defect_code": "D03_INCONSISTENT_SIZE",
    }
    create_resp = client.post("/api/v1/cases", json=create_payload)
    assert create_resp.status_code == 201
    case_id = create_resp.json()["case_id"]
    tracked_cases.append(case_id)

    # 1. Advance to revision 2
    ans1_resp = client.post(
        f"/api/v1/cases/{case_id}/answers",
        json={"question_id": "Q01", "answer": "after_prolonged_operation", "expected_revision": 1},
    )
    assert ans1_resp.status_code == 200
    assert ans1_resp.json()["current_revision"] == 2

    # Snapshot DB counts at revision 2
    factory = get_session_factory()
    with factory() as session:
        repo = CaseRepository(session)
        revs_before = repo.list_case_revisions(case_id)
        qas_before = len(repo.get_case_question_answers(case_id))
        obs_before = len(repo.get_case_observations(case_id))

    # 2. Submit another answer with stale expected_revision=1
    ans2_resp = client.post(
        f"/api/v1/cases/{case_id}/answers",
        json={"question_id": "Q02", "answer": "all_points", "expected_revision": 1},
    )
    assert ans2_resp.status_code == 409
    err = ans2_resp.json()
    assert "stale revision" in err["detail"].lower()
    assert "expected revision 1" in err["detail"].lower()
    assert "current revision is 2" in err["detail"].lower()

    # 3. Verify counts/state completely unchanged
    with factory() as session:
        repo = CaseRepository(session)
        assert repo.list_case_revisions(case_id) == revs_before
        assert len(repo.get_case_question_answers(case_id)) == qas_before
        assert len(repo.get_case_observations(case_id)) == obs_before


# ===========================================================================
# 7. Scenario 6: Invalid Answer Rejected (422) Without Mutation
# ===========================================================================

def test_invalid_answer_for_supported_question_rejected_with_422(tracked_cases: list[str]):
    """Scenario 6:
    - Valid question, unsupported answer;
    - Expect client error 422;
    - No answer/revision/observation appended.
    """
    create_payload = {
        "description": "Dots are inconsistent",
        "defect_code": "D03_INCONSISTENT_SIZE",
    }
    create_resp = client.post("/api/v1/cases", json=create_payload)
    assert create_resp.status_code == 201
    case_id = create_resp.json()["case_id"]
    tracked_cases.append(case_id)

    factory = get_session_factory()
    with factory() as session:
        repo = CaseRepository(session)
        obs_before = len(repo.get_case_observations(case_id))
        qas_before = len(repo.get_case_question_answers(case_id))
        revs_before = repo.list_case_revisions(case_id)

    # Submit invalid answer for Q01
    resp = client.post(
        f"/api/v1/cases/{case_id}/answers",
        json={"question_id": "Q01", "answer": "completely_invalid_choice", "expected_revision": 1},
    )
    assert resp.status_code == 422
    assert "invalid answer" in resp.json()["detail"].lower()

    # Verify no database mutation
    with factory() as session:
        repo = CaseRepository(session)
        assert len(repo.get_case_observations(case_id)) == obs_before
        assert len(repo.get_case_question_answers(case_id)) == qas_before
        assert repo.list_case_revisions(case_id) == revs_before


# ===========================================================================
# 8. Scenario 7: Unknown Question ID Rejected (422) Without Mutation
# ===========================================================================

def test_unknown_question_id_rejected_with_422(tracked_cases: list[str]):
    """Scenario 7:
    - Unsupported question ID;
    - Expect client error 422;
    - No mutation.
    """
    create_payload = {
        "description": "Dots are inconsistent",
        "defect_code": "D03_INCONSISTENT_SIZE",
    }
    create_resp = client.post("/api/v1/cases", json=create_payload)
    assert create_resp.status_code == 201
    case_id = create_resp.json()["case_id"]
    tracked_cases.append(case_id)

    resp = client.post(
        f"/api/v1/cases/{case_id}/answers",
        json={"question_id": "Q99_NOT_REAL", "answer": "yes", "expected_revision": 1},
    )
    assert resp.status_code == 422
    assert "unknown question_id" in resp.json()["detail"].lower()

    # Verify no mutation
    factory = get_session_factory()
    with factory() as session:
        repo = CaseRepository(session)
        assert repo.list_case_revisions(case_id) == [1]
        assert len(repo.get_case_question_answers(case_id)) == 0


# ===========================================================================
# 9. Scenario 8: Missing Case Returns 404
# ===========================================================================

def test_missing_case_returns_404():
    """Scenario 8:
    - Valid-looking unknown case ID;
    - Expect 404.
    """
    unknown_case_id = str(uuid.uuid4())
    resp = client.post(
        f"/api/v1/cases/{unknown_case_id}/answers",
        json={"question_id": "Q01", "answer": "after_prolonged_operation", "expected_revision": 1},
    )
    assert resp.status_code == 404
    assert f"Case '{unknown_case_id}' not found" in resp.json()["detail"]


def test_invalid_uuid_format_returns_422():
    """Invalid non-UUID string returns 422 Unprocessable Entity."""
    resp = client.post(
        "/api/v1/cases/not-a-valid-uuid/answers",
        json={"question_id": "Q01", "answer": "after_prolonged_operation", "expected_revision": 1},
    )
    assert resp.status_code == 422
    assert "Invalid case ID format" in resp.json()["detail"]


# ===========================================================================
# 10. Scenario 9: Atomic Rollback on Persistence Failure
# ===========================================================================

def test_atomic_rollback_on_persistence_failure(tracked_cases: list[str]):
    """Scenario 9:
    - Induce failure at the persistence seam;
    - Verify no partial appended state.
    """
    create_payload = {
        "description": "Dots inconsistent",
        "defect_code": "D03_INCONSISTENT_SIZE",
    }
    create_resp = client.post("/api/v1/cases", json=create_payload)
    assert create_resp.status_code == 201
    case_id = create_resp.json()["case_id"]
    tracked_cases.append(case_id)

    factory = get_session_factory()
    with factory() as session:
        repo = CaseRepository(session)
        obs_before = len(repo.get_case_observations(case_id))
        qas_before = len(repo.get_case_question_answers(case_id))
        revs_before = repo.list_case_revisions(case_id)

    # Induce an error inside append_question_answer_revision
    with patch.object(
        CaseRepository,
        "append_question_answer_revision",
        side_effect=RuntimeError("Simulated database failure"),
    ):
        resp = client.post(
            f"/api/v1/cases/{case_id}/answers",
            json={"question_id": "Q01", "answer": "after_prolonged_operation", "expected_revision": 1},
        )
        assert resp.status_code == 500
        # Check no internal secrets or trace leaked
        assert "Simulated database failure" not in resp.json()["detail"]

    # Verify complete rollback: zero partial writes
    with factory() as session:
        repo = CaseRepository(session)
        assert len(repo.get_case_observations(case_id)) == obs_before
        assert len(repo.get_case_question_answers(case_id)) == qas_before
        assert repo.list_case_revisions(case_id) == revs_before


# ===========================================================================
# 11. Scenario 10: Prior Revision Immutability
# ===========================================================================

def test_prior_revision_immutability(tracked_cases: list[str]):
    """Scenario 10:
    - Capture revision 1 snapshot;
    - Append answer / revision 2;
    - Reload revision 1 and prove unchanged.
    """
    create_payload = {
        "description": "Dots are inconsistent in size",
        "defect_code": "D03_INCONSISTENT_SIZE",
    }
    create_resp = client.post("/api/v1/cases", json=create_payload)
    assert create_resp.status_code == 201
    case_id = create_resp.json()["case_id"]
    tracked_cases.append(case_id)

    # Fetch revision 1 directly from database
    factory = get_session_factory()
    with factory() as session:
        repo = CaseRepository(session)
        rev1_initial = repo.get_analysis_revision(case_id, revision_number=1)
        assert rev1_initial is not None
        snapshot_rev1_initial = copy.deepcopy(rev1_initial.result_snapshot)
        analyzed_at_rev1 = rev1_initial.analyzed_at

    # Append revision 2 via API
    ans_resp = client.post(
        f"/api/v1/cases/{case_id}/answers",
        json={"question_id": "Q01", "answer": "after_prolonged_operation", "expected_revision": 1},
    )
    assert ans_resp.status_code == 200

    # Fetch revision 1 again and verify it is completely unchanged
    with factory() as session:
        repo = CaseRepository(session)
        rev1_after = repo.get_analysis_revision(case_id, revision_number=1)
        assert rev1_after is not None
        assert rev1_after.analyzed_at == analyzed_at_rev1
        assert rev1_after.result_snapshot == snapshot_rev1_initial
        assert rev1_after.revision_number == 1

        # Also verify via GET /api/v1/cases/{case_id}
        get_resp = client.get(f"/api/v1/cases/{case_id}")
        assert get_resp.status_code == 200
        get_data = get_resp.json()
        assert get_data["initial_diagnosis"]["analysis_revision"]["revision_number"] == 1


# ===========================================================================
# 12. Replay Safety / Idempotence
# ===========================================================================

def test_replaying_successful_request_returns_409(tracked_cases: list[str]):
    """Replaying an identical request with the now-stale expected_revision returns 409."""
    create_payload = {
        "description": "Inconsistent dot size",
        "defect_code": "D03_INCONSISTENT_SIZE",
    }
    create_resp = client.post("/api/v1/cases", json=create_payload)
    assert create_resp.status_code == 201
    case_id = create_resp.json()["case_id"]
    tracked_cases.append(case_id)

    payload = {
        "question_id": "Q01",
        "answer": "after_prolonged_operation",
        "expected_revision": 1,
    }

    # First attempt: succeeds
    resp1 = client.post(f"/api/v1/cases/{case_id}/answers", json=payload)
    assert resp1.status_code == 200
    assert resp1.json()["current_revision"] == 2

    # Second attempt with same payload (expected_revision=1): returns 409
    resp2 = client.post(f"/api/v1/cases/{case_id}/answers", json=payload)
    assert resp2.status_code == 409

    # DB state remains at revision 2
    factory = get_session_factory()
    with factory() as session:
        repo = CaseRepository(session)
        assert repo.list_case_revisions(case_id) == [1, 2]
        assert len(repo.get_case_question_answers(case_id)) == 1


# ===========================================================================
# 13. Scenario 11: API Regression
# ===========================================================================

def test_api_regression_existing_endpoints_unaffected(tracked_cases: list[str]):
    """Scenario 11:
    - Existing case create/retrieve API continues passing;
    - Existing stateless /api/v1/diagnoses API continues passing.
    """
    # 1. Stateless /api/v1/diagnoses
    diag_resp = client.post(
        "/api/v1/diagnoses",
        json={
            "description": "Dispense needle drips fluid",
            "defect_code": "D03_INCONSISTENT_SIZE",
            "observations": [{"observation_type": "nozzle_condition", "value": "drips_after_dispense"}],
        },
    )
    assert diag_resp.status_code == 200
    assert diag_resp.json()["defect"] == "D03_INCONSISTENT_SIZE"

    # 2. Durable POST /api/v1/cases
    case_resp = client.post(
        "/api/v1/cases",
        json={
            "description": "Dispense needle drips fluid",
            "defect_code": "D03_INCONSISTENT_SIZE",
        },
    )
    assert case_resp.status_code == 201
    case_id = case_resp.json()["case_id"]
    tracked_cases.append(case_id)

    # 3. Durable GET /api/v1/cases/{case_id}
    get_resp = client.get(f"/api/v1/cases/{case_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["case_id"] == case_id


# ===========================================================================
# 14. Domain Ownership Boundary Safety: User Hypothesis
# ===========================================================================

def test_user_hypothesis_answer_does_not_become_confirmed_cause(tracked_cases: list[str]):
    """Verify that a technician answer containing a hypothesis is not converted to a confirmed cause."""
    create_payload = {
        "description": "Inconsistent dot sizes",
        "defect_code": "D03_INCONSISTENT_SIZE",
    }
    create_resp = client.post("/api/v1/cases", json=create_payload)
    assert create_resp.status_code == 201
    case_id = create_resp.json()["case_id"]
    tracked_cases.append(case_id)

    # Submit hypothesis answer
    resp = client.post(
        f"/api/v1/cases/{case_id}/answers",
        json={
            "question_id": "Q01",
            "answer": "C01_FLUID_VISCOSITY_INCREASE",
            "answer_text": "I think the fluid viscosity increased",
            "expected_revision": 1,
        },
    )
    assert resp.status_code == 200
    data = resp.json()

    # None of the ranked causes should be marked as CONFIRMED merely from technician answer
    for cause in data["diagnosis"]["ranked_causes"]:
        assert cause["conclusion"] != "CONFIRMED"


def test_next_question_excludes_already_answered_questions(tracked_cases: list[str]):
    """Verify that updated next_question does not select an already answered question."""
    create_payload = {
        "description": "Inconsistent dots during dispensing",
        "defect_code": "D03_INCONSISTENT_SIZE",
    }
    create_resp = client.post("/api/v1/cases", json=create_payload)
    assert create_resp.status_code == 201
    case_id = create_resp.json()["case_id"]
    tracked_cases.append(case_id)

    # Submit Q01
    ans_resp = client.post(
        f"/api/v1/cases/{case_id}/answers",
        json={
            "question_id": "Q01",
            "answer": "after_prolonged_operation",
            "expected_revision": 1,
        },
    )
    assert ans_resp.status_code == 200
    data = ans_resp.json()

    # If a next question is selected, it must not be Q01
    if data["next_question"]:
        assert data["next_question"]["question_id"] != "Q01"
    if data["diagnosis"]["next_question"]:
        assert data["diagnosis"]["next_question"]["question_id"] != "Q01"


def test_concurrent_second_answer_cannot_contaminate_first_response(tracked_cases: list[str]):
    """Verify that if a second answer and revision are committed before the first
    request returns its response, the first response is not contaminated.

    Assert:
    - current_revision matches diagnosis.analysis_revision.revision_number.
    - submitted_answer.resulting_revision_number matches current_revision.
    - Every returned answer and observation belongs to that revision or earlier.
    - The first response never identifies the second request's answer.
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

    factory = get_session_factory()
    diag_engine = DiagnosticEngine()

    interleaved = False

    def on_after_commit(session: Session):
        nonlocal interleaved
        if interleaved:
            return

        interleaved = True
        with factory() as session2:
            repo2 = CaseRepository(session=session2)
            case_revs = repo2.list_case_revisions(case_id)
            if 2 in case_revs:
                loaded_case = repo2.load_structured_case(case_id)
                if loaded_case is not None:
                    ans2 = QuestionAnswer(
                        question_id="Q02",
                        answer_value="all_points",
                        source=EvidenceSource.USER,
                    )
                    updated_case, res2 = diag_engine.submit_question_answer(loaded_case, ans2)
                    repo2.append_question_answer_revision(
                        case=updated_case,
                        answer=ans2,
                        result=res2,
                        expected_revision=2,
                    )
                    session2.commit()

    try:
        event.listen(Session, "after_commit", on_after_commit)

        # Submit answer Q01 (Revision 2) via API
        ans1_payload = {
            "question_id": "Q01",
            "answer": "after_prolonged_operation",
            "expected_revision": 1,
            "answer_text": "Shrinking starts after continuous dispensing",
        }
        ans_resp = client.post(f"/api/v1/cases/{case_id}/answers", json=ans1_payload)
    finally:
        event.remove(Session, "after_commit", on_after_commit)

    assert ans_resp.status_code == 200
    data = ans_resp.json()

    # Verify that Revision 3 was indeed committed in PostgreSQL during the test
    with factory() as verify_session:
        verify_repo = CaseRepository(session=verify_session)
        assert verify_repo.list_case_revisions(case_id) == [1, 2, 3]
        all_qas = verify_repo.get_case_question_answers(case_id)
        assert len(all_qas) == 2
        assert {q.question_id for q in all_qas} == {"Q01", "Q02"}

    # Assertions required by contract:
    # 1. current_revision matches diagnosis.analysis_revision.revision_number
    assert data["current_revision"] == 2
    assert data["diagnosis"]["analysis_revision"]["revision_number"] == 2
    assert data["current_revision"] == data["diagnosis"]["analysis_revision"]["revision_number"]

    # 2. submitted_answer.resulting_revision_number matches current_revision
    assert data["submitted_answer"]["resulting_revision_number"] == data["current_revision"]
    assert data["submitted_answer"]["resulting_revision_number"] == 2

    # 3. Every returned answer and observation belongs to that revision or earlier
    assert len(data["previous_answers"]) == 1
    for ans in data["previous_answers"]:
        assert ans["resulting_revision_number"] <= data["current_revision"]

    for obs in data["observations"]:
        assert obs["first_seen_revision"] <= data["current_revision"]

    # 4. The first response never identifies the second request's answer
    assert data["submitted_answer"]["question_id"] == "Q01"
    assert data["submitted_answer"]["question_id"] != "Q02"
    assert not any(ans["question_id"] == "Q02" for ans in data["previous_answers"])


def test_internal_value_error_after_append_returns_sanitized_500_and_rolls_back(tracked_cases: list[str]):
    """Verify that an internal ValueError raised after append has flushed
    (e.g., during snapshot or response validation) is classified as an internal 500
    error, raw exception details are not exposed, and database writes are rolled back,
    while ordinary invalid technician inputs still return 422.
    """
    # 1. Create durable case at Revision 1
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

    factory = get_session_factory()
    with factory() as session:
        repo = CaseRepository(session)
        obs_before = len(repo.get_case_observations(case_id))
        qas_before = len(repo.get_case_question_answers(case_id))
        revs_before = repo.list_case_revisions(case_id)
        assert qas_before == 0
        assert revs_before == [1]

    # 2. Induce an internal response/snapshot validation ValueError after append has flushed
    error_msg = "Corrupted diagnosis snapshot: invalid confidence value"
    with patch.object(
        DiagnosisResult,
        "model_validate",
        side_effect=ValueError(error_msg),
    ):
        resp = client.post(
            f"/api/v1/cases/{case_id}/answers",
            json={
                "question_id": "Q01",
                "answer": "after_prolonged_operation",
                "expected_revision": 1,
                "answer_text": "Shrinking starts after 30 minutes",
            },
        )
        # 1. Endpoint returns 500
        assert resp.status_code == 500
        data = resp.json()
        # 2. Raw exception message is absent from the response
        assert error_msg not in resp.text
        assert "detail" in data
        assert data["detail"] == "An unexpected error occurred while persisting the question answer revision."

    # 3. The answer, observations, and new revision are rolled back
    with factory() as session:
        repo = CaseRepository(session)
        assert len(repo.get_case_observations(case_id)) == obs_before
        assert len(repo.get_case_question_answers(case_id)) == qas_before
        assert repo.list_case_revisions(case_id) == revs_before

    # 4. Ordinary invalid question/answer inputs still return 422
    # 4a. Invalid answer for supported question returns 422 with validation detail
    invalid_ans_resp = client.post(
        f"/api/v1/cases/{case_id}/answers",
        json={
            "question_id": "Q01",
            "answer": "invalid_unsupported_choice",
            "expected_revision": 1,
        },
    )
    assert invalid_ans_resp.status_code == 422
    assert "Invalid answer" in invalid_ans_resp.json()["detail"]

    # 4b. Unknown question ID returns 422 with validation detail
    unknown_q_resp = client.post(
        f"/api/v1/cases/{case_id}/answers",
        json={
            "question_id": "Q999_NONEXISTENT",
            "answer": "yes",
            "expected_revision": 1,
        },
    )
    assert unknown_q_resp.status_code == 422
    assert "unknown question_id" in unknown_q_resp.json()["detail"].lower()

    # 4c. Verify that database is still clean at Revision 1 after the 422 requests
    with factory() as session:
        repo = CaseRepository(session)
        assert len(repo.get_case_observations(case_id)) == obs_before
        assert len(repo.get_case_question_answers(case_id)) == 0
        assert repo.list_case_revisions(case_id) == [1]
