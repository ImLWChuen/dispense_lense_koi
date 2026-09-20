"""
DispenseIQ — Durable Case API Integration Tests

Tests persistent case creation (POST /api/v1/cases) and retrieval (GET /api/v1/cases/{case_id})
against real PostgreSQL. Verifies atomicity, provenance preservation, absence of recalculation
on retrieval, and strict decoupling of stateless endpoints.
"""

from __future__ import annotations

import copy
import os
import uuid
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_database_url
from app.db.database import get_engine, reset_engine
from app.db.repository import CaseRepository
from app.db.session import get_session_factory
from app.main import app
from app.models.case import AnalysisRevisionModel, CaseModel, ObservationModel
from app.schemas.diagnosis import (
    EvidenceSource,
    Observation,
    ObservationType,
    StatementType,
)
from app.services.diagnosis.engine import DiagnosticEngine
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
            # Cascades to case_observations and case_analysis_revisions
            session.execute(delete(CaseModel).where(CaseModel.case_id.in_(case_ids)))
            session.commit()


# ===========================================================================
# 1. OpenAPI & Route Registration Verification
# ===========================================================================

def test_case_endpoints_registered_in_openapi():
    """Verify that /api/v1/cases and /api/v1/cases/{case_id} are present in OpenAPI specification."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema["paths"]

    assert "/api/v1/cases" in paths
    assert "post" in paths["/api/v1/cases"]
    assert "201" in paths["/api/v1/cases"]["post"]["responses"]

    assert "/api/v1/cases/{case_id}" in paths
    assert "get" in paths["/api/v1/cases/{case_id}"]
    assert "200" in paths["/api/v1/cases/{case_id}"]["get"]["responses"]
    assert "404" in paths["/api/v1/cases/{case_id}"]["get"]["responses"]


# ===========================================================================
# 2. Scenario 1: Create + Retrieve Happy Path (Semantic Parity)
# ===========================================================================

def test_create_and_retrieve_durable_case_happy_path(tracked_cases):
    """POST a valid case, expect 201, GET returned case_id, assert semantic parity."""
    payload = {
        "description": "The dispensing dots become smaller after the machine has been running for around 20 minutes.",
        "material": "Epoxy-300",
        "method": "time_pressure",
        "machine_context": {"nozzle_id": "NZ-01", "pressure_bar": 2.4},
    }

    # 1. POST /api/v1/cases -> 201 Created
    post_res = client.post("/api/v1/cases", json=payload)
    assert post_res.status_code == 201
    post_data = post_res.json()

    case_id = post_data["case_id"]
    assert case_id is not None
    uuid.UUID(case_id)  # Must be valid UUID
    tracked_cases.append(case_id)

    assert post_data["description"] == payload["description"]
    assert post_data["material"] == payload["material"]
    assert post_data["method"] == payload["method"]
    assert post_data["machine_context"] == payload["machine_context"]
    assert post_data["defect_code"] == "D03_INCONSISTENT_SIZE"
    assert post_data["defect_name"]
    assert post_data["issue_condition"] == "UNRESOLVED"
    assert post_data["created_at"] is not None
    assert len(post_data["observations"]) > 0

    init_diag = post_data["initial_diagnosis"]
    assert init_diag["defect"] == "D03_INCONSISTENT_SIZE"
    assert init_diag["analysis_revision"]["revision_number"] == 1
    assert len(init_diag["ranked_causes"]) > 0

    # 2. GET /api/v1/cases/{case_id} -> 200 OK
    get_res = client.get(f"/api/v1/cases/{case_id}")
    assert get_res.status_code == 200
    get_data = get_res.json()

    # 3. Assert parity for stable case fields and diagnosis semantics
    for field in [
        "case_id",
        "description",
        "material",
        "method",
        "machine_context",
        "defect_code",
        "defect_name",
        "issue_condition",
        "created_at",
        "observations",
        "initial_diagnosis",
        "diagnosis",
        "previous_answers",
        "previous_check_results",
        "previous_confirmations",
        "lifecycle_events",
    ]:
        assert get_data[field] == post_data[field], f"Mismatch in field: {field}"

    # Explicitly assert POST creation leaves analysis_revisions empty while GET hydrates revision-1 history
    assert post_data["analysis_revisions"] == []
    assert len(get_data["analysis_revisions"]) == 1
    rev1 = get_data["analysis_revisions"][0]
    assert rev1["revision_number"] == 1
    assert rev1["defect_code"] == post_data["defect_code"]
    assert rev1 == init_diag["analysis_revision"]

    # 4. Verify persisted relational records and stored snapshot in PostgreSQL directly
    factory = get_session_factory()
    with factory() as db_session:
        db_case = db_session.get(CaseModel, case_id)
        assert db_case is not None
        assert db_case.case_id == case_id
        assert db_case.description == payload["description"]
        assert db_case.material == payload["material"]
        assert db_case.method == payload["method"]
        assert db_case.machine_context == payload["machine_context"]
        assert db_case.defect_code == post_data["defect_code"]
        assert db_case.defect_name == post_data["defect_name"]
        assert db_case.issue_condition == post_data["issue_condition"]

        db_obs = db_session.scalars(
            select(ObservationModel).where(ObservationModel.case_id == case_id)
        ).all()
        assert len(db_obs) == len(post_data["observations"])
        post_obs_map = {o["id"]: o for o in post_data["observations"]}
        for o_model in db_obs:
            assert o_model.observation_id in post_obs_map
            o_resp = post_obs_map[o_model.observation_id]
            assert o_model.observation_type == o_resp["observation_type"]
            assert o_model.value == o_resp["value"]
            assert o_model.statement_type == o_resp["statement_type"]
            assert o_model.source == o_resp["source"]
            assert o_model.first_seen_revision == o_resp["first_seen_revision"]
            assert o_resp["first_seen_revision"] == 1

        db_rev = db_session.scalars(
            select(AnalysisRevisionModel).where(AnalysisRevisionModel.case_id == case_id)
        ).one()
        assert db_rev.revision_number == 1
        assert db_rev.defect_code == post_data["defect_code"]
        assert db_rev.result_snapshot == post_data["initial_diagnosis"]
        assert db_rev.result_snapshot == get_data["initial_diagnosis"]



# ===========================================================================
# 3. Scenario 2: Generated Observation Persistence
# ===========================================================================

def test_generated_observation_persistence(tracked_cases):
    """Verify input causing symptom extraction generates observations persisted with provenance."""
    payload = {
        "description": "The dispensing dots become smaller after the machine has been running for around 20 minutes.",
        "material": "solder_paste",
        "method": "jetting",
    }

    res = client.post("/api/v1/cases", json=payload)
    assert res.status_code == 201
    data = res.json()
    case_id = data["case_id"]
    tracked_cases.append(case_id)

    # Symptom extractor generates observations
    assert len(data["observations"]) > 0
    for obs in data["observations"]:
        assert obs["id"] is not None
        assert obs["observation_type"] is not None
        assert obs["value"] is not None
        assert obs["source"] in ("USER", "MEASUREMENT", "IMAGE", "SYSTEM", "HISTORICAL_CASE")
        assert obs["statement_type"] in ("USER_OBSERVATION", "USER_INTERPRETATION", "AI_INFERENCE")
        assert obs["first_seen_revision"] == 1

    # Verify via direct GET
    get_res = client.get(f"/api/v1/cases/{case_id}")
    assert get_res.status_code == 200
    get_obs = get_res.json()["observations"]
    assert len(get_obs) == len(data["observations"])
    assert {o["id"] for o in get_obs} == {o["id"] for o in data["observations"]}


# ===========================================================================
# 4. Scenario 3: Client-Supplied Observation Persistence
# ===========================================================================

def test_client_supplied_observation_persistence(tracked_cases):
    """Verify client-supplied observations are stored and retrieved without provenance loss."""
    custom_obs_id = str(uuid.uuid4())
    payload = {
        "description": "Dispensing dots inconsistent across board",
        "defect_code": "D03_INCONSISTENT_SIZE",
        "observations": [
            {
                "id": custom_obs_id,
                "observation_type": "deposit_size",
                "value": "undersized",
                "original_text": "Manual technician measurement",
                "statement_type": "USER_OBSERVATION",
                "source": "MEASUREMENT",
                "confidence": 0.88,
            }
        ],
    }

    res = client.post("/api/v1/cases", json=payload)
    assert res.status_code == 201
    data = res.json()
    case_id = data["case_id"]
    tracked_cases.append(case_id)

    # Retrieve and verify observation properties
    get_res = client.get(f"/api/v1/cases/{case_id}")
    assert get_res.status_code == 200
    observations = get_res.json()["observations"]

    matching = [o for o in observations if o["id"] == custom_obs_id]
    assert len(matching) == 1
    obs = matching[0]
    assert obs["observation_type"] == "deposit_size"
    assert obs["value"] == "undersized"
    assert obs["original_text"] == "Manual technician measurement"
    assert obs["statement_type"] == "USER_OBSERVATION"
    assert obs["source"] == "MEASUREMENT"
    assert obs["confidence"] == pytest.approx(0.88, abs=0.001)
    assert obs["first_seen_revision"] == 1


# ===========================================================================
# 5. Scenario 4: Long-String Regression (>64 char IDs, >255 char fields)
# ===========================================================================

def test_long_string_regression_round_trip(tracked_cases):
    """Observation IDs >64 chars and values/material/method >255 chars round trip without truncation."""
    long_obs_id = "obs_long_id_" + "uuid_suffix_segment_" * 4  # > 64 chars
    assert len(long_obs_id) > 64

    long_value = "LongObsValue_" + "segment_" * 35  # > 255 chars
    assert len(long_value) > 255

    long_material = "PolymerEpoxy_GradeHighPurity_" + "component_additive_variant_" * 12  # > 255 chars
    assert len(long_material) > 255

    long_method = "JettingDispenser_TimePressureMicroValving_" + "spec_parameter_" * 15  # > 255 chars
    assert len(long_method) > 255

    payload = {
        "description": "Dots become smaller after 20 minutes of production run.",
        "defect_code": "D03_INCONSISTENT_SIZE",
        "material": long_material,
        "method": long_method,
        "observations": [
            {
                "id": long_obs_id,
                "observation_type": "runtime_pattern",
                "value": long_value,
                "confidence": 0.95,
            }
        ],
    }

    res = client.post("/api/v1/cases", json=payload)
    assert res.status_code == 201
    data = res.json()
    case_id = data["case_id"]
    tracked_cases.append(case_id)

    # Verify POST response has untruncated values
    assert data["material"] == long_material
    assert data["method"] == long_method

    # Verify GET returns exact long strings
    get_res = client.get(f"/api/v1/cases/{case_id}")
    assert get_res.status_code == 200
    get_data = get_res.json()

    assert get_data["material"] == long_material
    assert get_data["method"] == long_method

    obs_dict = {o["id"]: o for o in get_data["observations"]}
    assert long_obs_id in obs_dict
    assert obs_dict[long_obs_id]["value"] == long_value
    assert obs_dict[long_obs_id]["confidence"] == pytest.approx(0.95, abs=0.001)


# ===========================================================================
# 6. Scenario 5 & 6: Missing Case (404) & Malformed Case ID (422)
# ===========================================================================

def test_get_unknown_case_id_returns_404():
    """GET with valid-format UUID not in database returns 404 Not Found."""
    unknown_id = str(uuid.uuid4())
    res = client.get(f"/api/v1/cases/{unknown_id}")
    assert res.status_code == 404
    assert f"Case '{unknown_id}' not found" in res.json()["detail"]


def test_get_malformed_case_id_returns_422():
    """GET with an invalid UUID string returns 422 Unprocessable Entity."""
    res = client.get("/api/v1/cases/not-a-valid-uuid-12345")
    assert res.status_code == 422
    assert "must be a valid UUID" in res.json()["detail"]


# ===========================================================================
# 7. Scenario 7: No Recalculation on GET
# ===========================================================================

def test_get_does_not_invoke_diagnostic_engine(tracked_cases):
    """GET must load persisted state without invoking DiagnosticEngine.diagnose()."""
    payload = {
        "description": "The dispensing dots become smaller after 20 minutes.",
        "defect_code": "D03_INCONSISTENT_SIZE",
    }
    res = client.post("/api/v1/cases", json=payload)
    assert res.status_code == 201
    case_id = res.json()["case_id"]
    tracked_cases.append(case_id)

    # Patch DiagnosticEngine.diagnose to raise an error if invoked
    with patch.object(DiagnosticEngine, "diagnose", side_effect=AssertionError("Engine must not be called on GET")):
        get_res = client.get(f"/api/v1/cases/{case_id}")
        assert get_res.status_code == 200
        get_data = get_res.json()
        assert get_data["case_id"] == case_id
        assert get_data["defect_code"] == "D03_INCONSISTENT_SIZE"
        assert get_data["initial_diagnosis"]["defect"] == "D03_INCONSISTENT_SIZE"


def test_get_is_idempotent_and_does_not_mutate_revisions(tracked_cases):
    """Repeated GET requests must not create new revisions or alter case state."""
    payload = {
        "description": "The dispensing dots become smaller after 20 minutes.",
        "defect_code": "D03_INCONSISTENT_SIZE",
    }
    res = client.post("/api/v1/cases", json=payload)
    assert res.status_code == 201
    case_id = res.json()["case_id"]
    tracked_cases.append(case_id)

    # Issue multiple GET calls
    res1 = client.get(f"/api/v1/cases/{case_id}")
    res2 = client.get(f"/api/v1/cases/{case_id}")
    res3 = client.get(f"/api/v1/cases/{case_id}")

    assert res1.status_code == 200
    assert res2.status_code == 200
    assert res3.status_code == 200
    assert res1.json() == res2.json() == res3.json()

    # Query DB directly to assert revision count remains exactly 1
    factory = get_session_factory()
    with factory() as session:
        revisions = session.scalars(
            select(AnalysisRevisionModel).where(AnalysisRevisionModel.case_id == case_id)
        ).all()
        assert len(revisions) == 1
        assert revisions[0].revision_number == 1


# ===========================================================================
# 8. Scenario 8: Atomic Persistence Failure
# ===========================================================================

def test_rollback_after_real_flushed_writes_leaves_no_partial_case(tracked_cases):
    """
    Induce a failure AFTER real repository writes and session.flush() have executed in the request transaction,
    proving that PostgreSQL transaction rollback cleans up all flushed rows across cases,
    observations, and analysis revisions without corrupting unrelated control data.
    """
    # 1. Establish an unrelated control case in PostgreSQL
    control_payload = {
        "description": "Unrelated control case that must remain completely intact after failure rollback.",
        "defect_code": "D01_TOO_LITTLE",
        "material": "Epoxy-Control",
        "method": "time_pressure",
        "observations": [
            {
                "observation_type": "deposit_size",
                "value": "undersized",
                "confidence": 0.9,
            }
        ],
    }
    control_res = client.post("/api/v1/cases", json=control_payload)
    assert control_res.status_code == 201
    control_case_id = control_res.json()["case_id"]
    tracked_cases.append(control_case_id)

    # Verify control case exists in PostgreSQL
    factory = get_session_factory()
    with factory() as init_session:
        assert init_session.get(CaseModel, control_case_id) is not None

    # 2. Prepare payload for the failing case
    failing_payload = {
        "description": "The dispensing dots become smaller after 20 minutes under test.",
        "defect_code": "D03_INCONSISTENT_SIZE",
        "material": "Polymer-Failing",
        "method": "jetting",
        "observations": [
            {
                "observation_type": "deposit_size",
                "value": "undersized",
                "confidence": 0.92,
            }
        ],
    }

    synthetic_secret = "SYNTHETIC_TEST_SECRET_KEY_99887766_XYZ"
    captured_failed_id: list[str] = []
    flushed_verification: list[bool] = []

    real_save_initial_case = CaseRepository.save_initial_case

    def fault_injection_save_initial_case(self: CaseRepository, case, result):
        # Execute real writes which add CaseModel, ObservationModels, AnalysisRevisionModel and call session.flush()
        real_save_initial_case(self, case, result)

        captured_failed_id.append(case.case_id)

        # Inspect the active request session to verify rows were actually written and flushed
        req_session = self._session
        assert req_session is not None, "Request session must be present"
        flushed_case = req_session.get(CaseModel, case.case_id)
        assert flushed_case is not None, "CaseModel must be flushed to the request transaction"
        assert flushed_case.case_id == case.case_id

        flushed_obs = req_session.scalars(
            select(ObservationModel).where(ObservationModel.case_id == case.case_id)
        ).all()
        assert len(flushed_obs) > 0, "ObservationModels must be flushed to the request transaction"

        flushed_revs = req_session.scalars(
            select(AnalysisRevisionModel).where(AnalysisRevisionModel.case_id == case.case_id)
        ).all()
        assert len(flushed_revs) == 1, "AnalysisRevisionModel must be flushed to the request transaction"

        flushed_verification.append(True)

        # Induce synthetic failure before session.commit()
        raise RuntimeError(f"Simulated transaction commit failure with sensitive credential: {synthetic_secret}")

    # 3. Execute POST with fault injection seam
    with patch.object(CaseRepository, "save_initial_case", fault_injection_save_initial_case):
        res = client.post("/api/v1/cases", json=failing_payload)

    # 4. Verify request failed with sanitized 500
    assert res.status_code == 500
    assert len(captured_failed_id) == 1
    assert flushed_verification == [True], "Flushed writes must be verified in the transaction before exception"
    failed_case_id = captured_failed_id[0]

    res_json = res.json()
    assert res_json == {"detail": "An unexpected error occurred during case creation."}

    # Verify sensitive data / synthetic secrets are never leaked
    res_text = res.text
    assert synthetic_secret not in res_text
    assert "password" not in res_text
    assert "postgresql" not in res_text
    assert "Traceback" not in res_text
    assert "RuntimeError" not in res_text

    # 5. Verify from a fresh, independent session that all 3 tables have 0 rows for the failed case ID
    with factory() as check_session:
        # Check cases table
        persisted_cases = check_session.scalars(
            select(CaseModel).where(CaseModel.case_id == failed_case_id)
        ).all()
        assert len(persisted_cases) == 0, f"Expected 0 case records for {failed_case_id}, found {len(persisted_cases)}"

        # Check case_observations table
        persisted_obs = check_session.scalars(
            select(ObservationModel).where(ObservationModel.case_id == failed_case_id)
        ).all()
        assert len(persisted_obs) == 0, f"Expected 0 observation records for {failed_case_id}, found {len(persisted_obs)}"

        # Check case_analysis_revisions table
        persisted_revs = check_session.scalars(
            select(AnalysisRevisionModel).where(AnalysisRevisionModel.case_id == failed_case_id)
        ).all()
        assert len(persisted_revs) == 0, f"Expected 0 revision records for {failed_case_id}, found {len(persisted_revs)}"

        # 6. Verify unrelated control case remains completely intact
        db_control = check_session.get(CaseModel, control_case_id)
        assert db_control is not None
        assert db_control.case_id == control_case_id
        assert db_control.description == control_payload["description"]

        control_obs = check_session.scalars(
            select(ObservationModel).where(ObservationModel.case_id == control_case_id)
        ).all()
        assert len(control_obs) > 0

        control_revs = check_session.scalars(
            select(AnalysisRevisionModel).where(AnalysisRevisionModel.case_id == control_case_id)
        ).all()
        assert len(control_revs) == 1


def test_immediate_repository_failure_handles_error_safely():
    """An immediate exception raised before repository writes must return sanitized 500 without lingering rows."""
    payload = {
        "description": "Dispense needle drips fluid after dispensing stops",
        "defect_code": "D01_TOO_LITTLE",
    }

    # Patch repository.save_initial_case to simulate immediate initialization error
    with patch.object(
        CaseRepository,
        "save_initial_case",
        side_effect=RuntimeError("Simulated immediate database initialization error"),
    ):
        res = client.post("/api/v1/cases", json=payload)
        assert res.status_code == 500
        assert "An unexpected error occurred" in res.json()["detail"]
        err_text = res.text
        assert "password" not in err_text
        assert "postgresql" not in err_text

    # Verify no records were persisted
    factory = get_session_factory()
    with factory() as session:
        cases = session.scalars(
            select(CaseModel).where(CaseModel.description == payload["description"])
        ).all()
        assert len(cases) == 0



# ===========================================================================
# 9. Scenario 9: Two Identical POSTs Create Distinct Cases
# ===========================================================================

def test_identical_posts_create_distinct_isolated_cases(tracked_cases):
    """Two identical POST requests must create distinct cases without cross-request state sharing."""
    payload = {
        "description": "The dispensing dots become smaller after 20 minutes.",
        "defect_code": "D03_INCONSISTENT_SIZE",
        "material": "PolymerA",
        "method": "time_pressure",
    }

    res1 = client.post("/api/v1/cases", json=payload)
    assert res1.status_code == 201
    case_id_1 = res1.json()["case_id"]
    tracked_cases.append(case_id_1)

    res2 = client.post("/api/v1/cases", json=payload)
    assert res2.status_code == 201
    case_id_2 = res2.json()["case_id"]
    tracked_cases.append(case_id_2)

    assert case_id_1 != case_id_2

    # Verify both exist independently
    get1 = client.get(f"/api/v1/cases/{case_id_1}")
    get2 = client.get(f"/api/v1/cases/{case_id_2}")
    assert get1.status_code == 200
    assert get2.status_code == 200
    assert get1.json()["case_id"] == case_id_1
    assert get2.json()["case_id"] == case_id_2


# ===========================================================================
# 10. Scenario 10: Input Validation & Edge Cases (422)
# ===========================================================================

def test_create_case_validation_errors():
    """Empty input, invalid defect code, or forbidden fields must return 422."""
    # 1. Empty description and observations
    res = client.post("/api/v1/cases", json={"description": "", "observations": []})
    assert res.status_code == 422
    assert "Insufficient evidence input" in res.text

    # 2. Unknown defect code
    res = client.post(
        "/api/v1/cases",
        json={"description": "Some description", "defect_code": "D99_NON_EXISTENT"},
    )
    assert res.status_code == 422
    assert "Unknown defect code" in res.text

    # 3. Forbidden extra fields (e.g. caller attempting to supply case_id or revision)
    res = client.post(
        "/api/v1/cases",
        json={
            "description": "Some problem description",
            "case_id": "00000000-0000-0000-0000-000000000001",
        },
    )
    assert res.status_code == 422


# ===========================================================================
# 11. Scenario 11: Stateless Diagnosis Endpoint Regression
# ===========================================================================

def test_stateless_diagnosis_endpoint_remains_stateless():
    """POST /api/v1/diagnoses continues to work statelessly without creating database rows."""
    payload = {
        "description": "Dispense needle drips fluid after dispensing stops",
        "material": "epoxy",
        "method": "time_pressure",
    }
    res = client.post("/api/v1/diagnoses", json=payload)
    assert res.status_code == 200
    data = res.json()
    stateless_case_id = data["case_id"]

    # That case_id must NOT exist in the database
    get_res = client.get(f"/api/v1/cases/{stateless_case_id}")
    assert get_res.status_code == 404


# ===========================================================================
# 12. Scenario 12: Inconclusive Diagnosis Limitation (Stateless vs Durable)
# ===========================================================================

def test_inconclusive_diagnosis_behavior_difference():
    """
    Test the documented contract difference when input yields no identified defect:
    - Stateless endpoint (POST /api/v1/diagnoses) returns 200 OK with defect=None and analysis_revision=None.
    - Durable endpoint (POST /api/v1/cases) rejects the request with 422 because the persistence
      contract requires Revision 1 for initial case storage, producing zero database records.
    """
    inconclusive_payload = {
        "description": "Cleaned and calibrated the machine as part of standard shift startup.",
    }

    # 1. Stateless endpoint accepts input and returns inconclusive 200 OK
    stateless_res = client.post("/api/v1/diagnoses", json=inconclusive_payload)
    assert stateless_res.status_code == 200
    stateless_data = stateless_res.json()
    assert stateless_data["defect"] is None
    assert stateless_data["analysis_revision"] is None
    stateless_case_id = stateless_data["case_id"]

    # Ephemeral case_id must not exist in database
    factory = get_session_factory()
    with factory() as session:
        assert session.get(CaseModel, stateless_case_id) is None

    # 2. Durable endpoint rejects inconclusive input with 422 Unprocessable Entity
    durable_res = client.post("/api/v1/cases", json=inconclusive_payload)
    assert durable_res.status_code == 422
    assert "could not identify a defect category" in durable_res.json()["detail"]

    # 3. Verify zero database records were created for this description
    with factory() as session:
        cases = session.scalars(
            select(CaseModel).where(CaseModel.description == inconclusive_payload["description"])
        ).all()
        assert len(cases) == 0


# ===========================================================================
# 13. Scenario 13: GET Case Hydrates Complete Confirmation & Lifecycle History
# ===========================================================================

def test_get_case_returns_ordered_confirmations_and_lifecycle_events(tracked_cases: list[str]):
    """
    Verify that advancing a case through:
    1. Cause confirmation
    2. Recovery action
    3. Failed recovery verification (returns issue condition to UNRESOLVED)
    4. Second recovery action
    5. Passed recovery verification (transitions issue condition to RESOLVED)
    6. Recurrence (transitions issue condition to RECURRED)

    returns complete, deterministically ordered previous_confirmations and
    lifecycle_events from a fresh GET /cases/{id} request without diagnostic
    recalculation or mutating revision state.
    """
    # 1. Create durable case
    create_payload = {
        "description": "The dispensing dots become smaller after prolonged operation on the line.",
        "material": "Epoxy-300",
        "method": "time_pressure",
        "machine_context": {"nozzle_id": "NZ-01", "pressure_bar": 2.4},
    }
    create_res = client.post("/api/v1/cases", json=create_payload)
    assert create_res.status_code == 201
    case_data = create_res.json()
    case_id = case_data["case_id"]
    tracked_cases.append(case_id)

    assert case_data["issue_condition"] == "UNRESOLVED"
    assert case_data["previous_confirmations"] == []
    assert case_data["lifecycle_events"] == []
    top_cause_id = case_data["initial_diagnosis"]["ranked_causes"][0]["cause_id"]

    # 2. Confirm root cause (Rev 1 -> 2)
    conf_res = client.post(
        f"/api/v1/cases/{case_id}/cause-confirmations",
        json={
            "cause_id": top_cause_id,
            "expected_revision": 1,
            "confirmed_by": "lead_technician",
            "notes": "Verified restriction under microscope.",
        },
    )
    assert conf_res.status_code == 200
    assert conf_res.json()["current_revision"] == 2
    assert conf_res.json()["issue_condition"] == "UNRESOLVED"

    # 3. Submit recovery action 1 (Rev 2 -> 3)
    rec1_res = client.post(
        f"/api/v1/cases/{case_id}/recovery-actions",
        json={
            "expected_revision": 2,
            "recovery_details": "Cleaned nozzle orifice with ultrasonic bath.",
            "performed_by": "maintenance_tech",
        },
    )
    assert rec1_res.status_code == 200
    assert rec1_res.json()["current_revision"] == 3
    assert rec1_res.json()["issue_condition"] == "RECOVERY_PENDING_VERIFICATION"

    # 4. Submit failed recovery verification (Rev 3 -> 4)
    ver1_res = client.post(
        f"/api/v1/cases/{case_id}/recovery-verifications",
        json={
            "expected_revision": 3,
            "verification_passed": False,
            "verification_details": "Dispense volume test failed; dots still 30% undersized.",
            "verified_by": "quality_tech",
        },
    )
    assert ver1_res.status_code == 200
    assert ver1_res.json()["current_revision"] == 4
    assert ver1_res.json()["issue_condition"] == "UNRESOLVED"

    # 5. Submit recovery action 2 (Rev 4 -> 5)
    rec2_res = client.post(
        f"/api/v1/cases/{case_id}/recovery-actions",
        json={
            "expected_revision": 4,
            "recovery_details": "Replaced nozzle tip with new verified component.",
            "performed_by": "maintenance_tech",
        },
    )
    assert rec2_res.status_code == 200
    assert rec2_res.json()["current_revision"] == 5
    assert rec2_res.json()["issue_condition"] == "RECOVERY_PENDING_VERIFICATION"

    # 6. Submit passed recovery verification (Rev 5 -> 6)
    ver2_res = client.post(
        f"/api/v1/cases/{case_id}/recovery-verifications",
        json={
            "expected_revision": 5,
            "verification_passed": True,
            "verification_details": "Test shot pattern nominal; 50 consecutive dots within tolerance.",
            "verified_by": "quality_tech",
        },
    )
    assert ver2_res.status_code == 200
    assert ver2_res.json()["current_revision"] == 6
    assert ver2_res.json()["issue_condition"] == "RESOLVED"

    # 7. Submit recurrence (Rev 6 -> 7)
    recur_res = client.post(
        f"/api/v1/cases/{case_id}/recurrences",
        json={
            "expected_revision": 6,
            "recurrence_details": "Dots became undersized again during next production shift.",
            "reported_by": "shift_operator",
        },
    )
    assert recur_res.status_code == 200
    assert recur_res.json()["current_revision"] == 7
    assert recur_res.json()["issue_condition"] == "RECURRED"

    # 8. GET /api/v1/cases/{case_id} — verify complete populated histories and no mutation
    get_res = client.get(f"/api/v1/cases/{case_id}")
    assert get_res.status_code == 200
    get_data = get_res.json()

    assert get_data["case_id"] == case_id
    assert get_data["issue_condition"] == "RECURRED"

    # Verify previous_confirmations
    confirmations = get_data["previous_confirmations"]
    assert len(confirmations) == 1
    assert confirmations[0]["cause_id"] == top_cause_id
    assert confirmations[0]["confirmed_by"] == "lead_technician"
    assert confirmations[0]["notes"] == "Verified restriction under microscope."
    assert confirmations[0]["resulting_revision_number"] == 2

    # Verify lifecycle_events (ordered by revision number ascending)
    events = get_data["lifecycle_events"]
    assert len(events) == 5

    # Event 1: Recovery Action 1 (Rev 3)
    assert events[0]["event_type"] == "RECOVERY_ACTION"
    assert events[0]["prior_issue_condition"] == "UNRESOLVED"
    assert events[0]["resulting_issue_condition"] == "RECOVERY_PENDING_VERIFICATION"
    assert events[0]["resulting_revision_number"] == 3
    assert events[0]["actor"] == "maintenance_tech"
    assert events[0]["details"] == "Cleaned nozzle orifice with ultrasonic bath."

    # Event 2: Verification Failed (Rev 4)
    assert events[1]["event_type"] == "RECOVERY_VERIFICATION"
    assert events[1]["prior_issue_condition"] == "RECOVERY_PENDING_VERIFICATION"
    assert events[1]["resulting_issue_condition"] == "UNRESOLVED"
    assert events[1]["resulting_revision_number"] == 4
    assert events[1]["verification_passed"] is False
    assert events[1]["actor"] == "quality_tech"

    # Event 3: Recovery Action 2 (Rev 5)
    assert events[2]["event_type"] == "RECOVERY_ACTION"
    assert events[2]["prior_issue_condition"] == "UNRESOLVED"
    assert events[2]["resulting_issue_condition"] == "RECOVERY_PENDING_VERIFICATION"
    assert events[2]["resulting_revision_number"] == 5
    assert events[2]["actor"] == "maintenance_tech"

    # Event 4: Verification Passed (Rev 6)
    assert events[3]["event_type"] == "RECOVERY_VERIFICATION"
    assert events[3]["prior_issue_condition"] == "RECOVERY_PENDING_VERIFICATION"
    assert events[3]["resulting_issue_condition"] == "RESOLVED"
    assert events[3]["resulting_revision_number"] == 6
    assert events[3]["verification_passed"] is True
    assert events[3]["actor"] == "quality_tech"

    # Event 5: Recurrence (Rev 7)
    assert events[4]["event_type"] == "RECURRENCE"
    assert events[4]["prior_issue_condition"] == "RESOLVED"
    assert events[4]["resulting_issue_condition"] == "RECURRED"
    assert events[4]["resulting_revision_number"] == 7
    assert events[4]["actor"] == "shift_operator"
    assert events[4]["details"] == "Dots became undersized again during next production shift."

    # Verify that a second GET is idempotent and does not mutate anything
    get_res2 = client.get(f"/api/v1/cases/{case_id}")
    assert get_res2.status_code == 200
    assert get_res2.json() == get_data
