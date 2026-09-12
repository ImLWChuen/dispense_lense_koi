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

    # 3. Assert exact parity between POST response and GET response
    assert get_data["case_id"] == case_id
    assert get_data["description"] == post_data["description"]
    assert get_data["material"] == post_data["material"]
    assert get_data["method"] == post_data["method"]
    assert get_data["machine_context"] == post_data["machine_context"]
    assert get_data["defect_code"] == post_data["defect_code"]
    assert get_data["defect_name"] == post_data["defect_name"]
    assert get_data["issue_condition"] == post_data["issue_condition"]
    assert len(get_data["observations"]) == len(post_data["observations"])

    # Verify initial diagnosis snapshot matches
    assert get_data["initial_diagnosis"]["defect"] == init_diag["defect"]
    assert get_data["initial_diagnosis"]["ranked_causes"] == init_diag["ranked_causes"]
    assert get_data["initial_diagnosis"]["explanation"] == init_diag["explanation"]
    assert (
        get_data["initial_diagnosis"]["analysis_revision"]["revision_number"]
        == init_diag["analysis_revision"]["revision_number"]
    )


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

def test_atomic_persistence_failure_leaves_no_partial_case():
    """An induced persistence failure must roll back cleanly and leave no partial records."""
    failing_case_id = str(uuid.uuid4())
    payload = {
        "description": "Dispense needle drips fluid after dispensing stops",
        "defect_code": "D01_TOO_LITTLE",
    }

    # Patch repository.save_initial_case to simulate database/transaction error
    with patch.object(
        CaseRepository,
        "save_initial_case",
        side_effect=RuntimeError("Simulated database constraint or disk error"),
    ):
        res = client.post("/api/v1/cases", json=payload)
        assert res.status_code == 500
        assert "An unexpected error occurred" in res.json()["detail"]
        # Error must never expose raw database URLs, credentials, or traces
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
