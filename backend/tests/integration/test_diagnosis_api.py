from __future__ import annotations

import copy
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from app.api.diagnoses import get_diagnosis_engine
from app.main import app
from app.schemas.diagnosis import (
    DiagnosisRequest,
    EvidenceSource,
    Observation,
    ObservationType,
    StatementType,
)
from app.services.diagnosis.engine import DiagnosticEngine

client = TestClient(app)


def _normalize_diagnosis_result(result_dict: dict) -> dict:
    """Normalize a DiagnosisResult dict by stripping only nondeterministic generated IDs and timestamps."""
    normalized = copy.deepcopy(result_dict)
    normalized.pop("case_id", None)

    if normalized.get("analysis_revision"):
        normalized["analysis_revision"].pop("timestamp", None)

    def clean_evidence(causes: list[dict]) -> None:
        for cause in causes:
            for rel_type in ("supporting_evidence", "contradicting_evidence", "neutral_evidence"):
                for ev in cause.get(rel_type, []):
                    ev.pop("observation_id", None)

    clean_evidence(normalized.get("ranked_causes", []))
    if normalized.get("analysis_revision"):
        clean_evidence(normalized["analysis_revision"].get("ranked_causes", []))

    return normalized


def test_diagnosis_endpoint_in_openapi():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "/api/v1/diagnoses" in schema["paths"]
    post_op = schema["paths"]["/api/v1/diagnoses"]["post"]
    assert "200" in post_op["responses"]


def test_valid_initial_diagnosis_supported_scenario():
    payload = {
        "description": "The dispensing dots become smaller after the machine has been running for around 20 minutes.",
        "material": "Epoxy-300",
        "method": "time_pressure",
    }
    response = client.post("/api/v1/diagnoses", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["case_id"]
    assert data["defect"] == "D03_INCONSISTENT_SIZE"
    assert data["defect_name"]
    assert len(data["ranked_causes"]) > 0
    top_cause = data["ranked_causes"][0]
    assert "cause_id" in top_cause
    assert "cause_name" in top_cause
    assert 0.0 <= top_cause["score"] <= 100.0
    assert data["explanation"]
    assert data["analysis_revision"] is not None
    assert data["analysis_revision"]["revision_number"] == 1


def test_scores_and_evidence_match_direct_engine_call():
    payload = {
        "description": "The dispensing dots become smaller after the machine has been running for around 20 minutes.",
        "material": "epoxy",
        "method": "time_pressure",
    }

    # API call
    response = client.post("/api/v1/diagnoses", json=payload)
    assert response.status_code == 200
    api_data = response.json()

    # Direct engine call with same initial request
    engine = DiagnosticEngine()
    direct_req = DiagnosisRequest(
        description=payload["description"],
        material=payload["material"],
        method=payload["method"],
    )
    direct_result = engine.diagnose(direct_req)
    direct_data = direct_result.model_dump(mode="json")

    # Complete semantic parity check after excluding only nondeterministic generated IDs/timestamps
    norm_api = _normalize_diagnosis_result(api_data)
    norm_direct = _normalize_diagnosis_result(direct_data)
    assert norm_api == norm_direct

    # Detailed semantic checks on preserved domain content and evidence
    assert api_data["defect"] == direct_result.defect
    assert api_data["defect_name"] == direct_result.defect_name
    assert len(api_data["ranked_causes"]) > 0
    top_cause = api_data["ranked_causes"][0]
    assert top_cause["supporting_evidence"]
    first_ev = top_cause["supporting_evidence"][0]
    assert first_ev["relation"] == "SUPPORTS"
    assert first_ev["strength"] in ("STRONG", "MODERATE", "WEAK")
    assert first_ev["source"] == "USER"
    assert first_ev["explanation"]
    assert "positive_evidence" in top_cause["score_breakdown"]
    assert api_data["analysis_revision"]["revision_number"] == 1
    assert api_data["next_question"] is not None
    assert api_data["next_check"] is not None


def test_independent_submissions_generate_unique_case_ids_and_do_not_leak_state():
    payload = {
        "description": "The dispensing dots become smaller after the machine has been running for around 20 minutes."
    }

    resp1 = client.post("/api/v1/diagnoses", json=payload)
    resp2 = client.post("/api/v1/diagnoses", json=payload)

    assert resp1.status_code == 200
    assert resp2.status_code == 200

    data1 = resp1.json()
    data2 = resp2.json()

    # Each initial request receives an independent, distinct case ID
    assert data1["case_id"] != data2["case_id"]
    # Revisions start at 1 independently
    assert data1["analysis_revision"]["revision_number"] == 1
    assert data2["analysis_revision"]["revision_number"] == 1

    # Extract all generated evidence observation IDs from both responses
    def extract_evidence_obs_ids(data: dict) -> set[str]:
        obs_ids = set()
        for cause in data.get("ranked_causes", []):
            for rel_type in ("supporting_evidence", "contradicting_evidence", "neutral_evidence"):
                for item in cause.get(rel_type, []):
                    oid = item.get("observation_id")
                    if oid:
                        obs_ids.add(oid)
        if data.get("analysis_revision"):
            for cause in data["analysis_revision"].get("ranked_causes", []):
                for rel_type in ("supporting_evidence", "contradicting_evidence", "neutral_evidence"):
                    for item in cause.get(rel_type, []):
                        oid = item.get("observation_id")
                        if oid:
                            obs_ids.add(oid)
        return obs_ids

    obs_ids_1 = extract_evidence_obs_ids(data1)
    obs_ids_2 = extract_evidence_obs_ids(data2)

    assert len(obs_ids_1) > 0
    assert len(obs_ids_2) > 0
    # Assert generated evidence/observation identities do not leak across runs
    assert obs_ids_1.isdisjoint(obs_ids_2)


def test_unidentifiable_problem_returns_200_with_warning():
    payload = {
        "description": "Room lighting was slightly dim today and the ambient temperature was comfortable."
    }
    response = client.post("/api/v1/diagnoses", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["defect"] is None
    assert data["defect_name"] is None
    assert data["ranked_causes"] == []
    assert data["analysis_revision"] is None
    assert len(data["warnings"]) > 0
    assert any("Could not identify defect" in w for w in data["warnings"])


def test_observations_without_description_accepted():
    obs = Observation(
        id="obs_test_1",
        observation_type=ObservationType.DEPOSIT_SIZE,
        value="undersized",
        original_text="dots become smaller",
        statement_type=StatementType.USER_OBSERVATION,
        source=EvidenceSource.USER,
    )
    payload = {
        "description": "",
        "observations": [obs.model_dump(mode="json")],
    }
    response = client.post("/api/v1/diagnoses", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["defect"] == "D01_TOO_LITTLE"


def test_validation_empty_or_whitespace_description_without_observations():
    # Empty payload
    r1 = client.post("/api/v1/diagnoses", json={})
    assert r1.status_code == 422
    errors1 = r1.json().get("detail", [])
    assert any("Insufficient evidence input" in err.get("msg", "") for err in errors1)

    # Whitespace only
    r2 = client.post("/api/v1/diagnoses", json={"description": "   "})
    assert r2.status_code == 422
    errors2 = r2.json().get("detail", [])
    assert any("Insufficient evidence input" in err.get("msg", "") for err in errors2)


def test_defect_code_alone_is_insufficient_evidence():
    payload = {
        "defect_code": "D01_TOO_LITTLE",
        "description": "",
        "observations": [],
    }
    response = client.post("/api/v1/diagnoses", json=payload)
    assert response.status_code == 422
    errors = response.json().get("detail", [])
    assert any("Insufficient evidence input" in err.get("msg", "") for err in errors)


def test_unknown_defect_code_returns_422():
    payload = {
        "description": "Some dispensing anomaly noticed",
        "defect_code": "D99_UNKNOWN_CODE",
    }
    response = client.post("/api/v1/diagnoses", json=payload)
    assert response.status_code == 422
    errors = response.json().get("detail", [])
    assert any("Unknown defect code" in err.get("msg", "") for err in errors)


def test_extra_forbidden_fields_return_422():
    # Attempting to supply case_id
    r1 = client.post(
        "/api/v1/diagnoses",
        json={"description": "Valid problem", "case_id": "custom-uuid-123"},
    )
    assert r1.status_code == 422

    # Attempting to supply revision history
    r2 = client.post(
        "/api/v1/diagnoses",
        json={"description": "Valid problem", "analysis_revision": 3},
    )
    assert r2.status_code == 422

    # Attempting to supply previous answers
    r3 = client.post(
        "/api/v1/diagnoses",
        json={"description": "Valid problem", "previous_answers": []},
    )
    assert r3.status_code == 422


def test_injected_failing_engine_returns_sanitized_500():
    mock_engine = MagicMock()
    mock_engine.diagnose.side_effect = RuntimeError(
        "Secret database connection string: postgres://superadmin:TopSecretPassword@db.internal:5432/dispense"
    )

    app.dependency_overrides[get_diagnosis_engine] = lambda: mock_engine
    try:
        response = client.post(
            "/api/v1/diagnoses",
            json={"description": "The dispensing dots become smaller after 20 minutes."},
        )
        assert response.status_code == 500
        data = response.json()
        assert data["detail"] == "An unexpected error occurred during diagnosis evaluation."
        # Ensure secrets, stack trace, and paths are not leaked in the response
        assert "Secret" not in response.text
        assert "TopSecretPassword" not in response.text
        assert "postgres" not in response.text
        assert "RuntimeError" not in response.text
    finally:
        app.dependency_overrides.clear()
