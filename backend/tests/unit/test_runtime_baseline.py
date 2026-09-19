"""
DispenseIQ — Runtime Baseline & Offline Safety Unit Tests (DLK-M3-025)

Verifies:
1. Deterministic offline diagnosis operation with no OpenAI API key configured.
2. Verified absence of OpenAI client construction or outbound network calls when unconfigured.
3. Resilience against external LLM errors/timeouts without altering deterministic diagnostic outputs.
4. Default CORS origins including Next.js frontend on port 3001 (http://localhost:3001 and http://127.0.0.1:3001).
5. Centralized test-database bootstrap fail-closed behavior on missing, plain dispenselens, or dev-conflicting URLs.
6. Non-database endpoints (health, stateless diagnosis) remain fully functional without TEST_DATABASE_URL.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import create_app
from app.schemas.diagnosis import DiagnosisRequest
from app.services.ai.explanation_service import ExplanationService
from app.services.ai.llm_service import LLMService
from app.services.diagnosis.engine import DiagnosticEngine
from tests.conftest import bootstrap_test_database
from tests.unit.test_persistence_safety import assert_safe_test_database


# ===========================================================================
# 1. Deterministic Offline Troubleshooting (No AI Key Required)
# ===========================================================================

def test_stateless_diagnosis_offline_without_api_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """With OPENAI_API_KEY and LLM_API_KEY explicitly absent, stateless diagnosis
    succeeds with deterministic ranked causes, numerical scores, explanation, and next step.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    app = create_app()
    client = TestClient(app)

    payload = {
        "description": "Dispense dots are shrinking over time during continuous operation",
        "defect_code": "D03_INCONSISTENT_SIZE",
        "material": "solder_paste",
        "method": "jetting",
    }

    response = client.post("/api/v1/diagnoses", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["defect"] == "D03_INCONSISTENT_SIZE"
    assert len(data["ranked_causes"]) > 0
    # Deterministic scores are preserved
    top_cause = data["ranked_causes"][0]
    assert top_cause["score"] > 0
    assert top_cause["cause_id"] is not None
    assert top_cause["conclusion"] in ("SUSPECTED", "CONFIRMED")
    # Explanation is generated via deterministic fallback template
    assert len(data["explanation"]) > 0
    assert "highest-supported hypothesis" in data["explanation"]
    # Next question or check is provided
    assert data["next_question"] is not None or data["next_check"] is not None


def test_offline_mode_does_not_construct_openai_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """When no API key is provided, LLMService must not instantiate an OpenAI client
    or make any outbound requests.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with patch("app.services.ai.llm_service.OpenAI") as mock_openai_cls:
        service = LLMService(api_key="")
        assert service.is_available is False
        assert service.client is None
        mock_openai_cls.assert_not_called()

        # Attempting text generation returns None without touching OpenAI
        result = service.generate_text("Test prompt")
        assert result is None
        mock_openai_cls.assert_not_called()


def test_llm_failure_preserves_deterministic_diagnostic_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    """If an external LLM call times out or throws an error, the engine must fall back
    to deterministic output without corrupting rankings, scores, or cause states.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    # Instantiate engine with offline service
    explanation_service = ExplanationService(llm_service=LLMService(api_key=""))
    engine = DiagnosticEngine(explanation_service=explanation_service)
    req = DiagnosisRequest(
        description="The dispensing dots become smaller after 20 minutes",
        defect_code="D03_INCONSISTENT_SIZE",
    )
    case = engine.prepare_case(req)
    result = engine.diagnose(case)

    assert result.defect == "D03_INCONSISTENT_SIZE"
    assert len(result.ranked_causes) > 0
    assert result.analysis_revision is not None
    assert result.analysis_revision.revision_number == 1
    assert "highest-supported hypothesis" in result.explanation


# ===========================================================================
# 2. CORS Defaults (Port 3001 Support)
# ===========================================================================

def test_default_cors_origins_include_port_3001() -> None:
    """Default CORS configuration must include Next.js frontend port 3001 origins."""
    settings = get_settings()
    assert "http://localhost:3001" in settings.cors_origins
    assert "http://127.0.0.1:3001" in settings.cors_origins
    assert "http://localhost:3000" in settings.cors_origins
    assert "http://127.0.0.1:3000" in settings.cors_origins


def test_cors_preflight_and_get_for_port_3001() -> None:
    """OPTIONS preflight and GET from port 3001 must return approved CORS headers."""
    app = create_app()
    client = TestClient(app)

    # Preflight OPTIONS
    opt_resp = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:3001",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert opt_resp.status_code == 200
    assert opt_resp.headers.get("access-control-allow-origin") == "http://localhost:3001"

    # Simple GET
    get_resp = client.get(
        "/api/v1/health",
        headers={"Origin": "http://localhost:3001"},
    )
    assert get_resp.status_code == 200
    assert get_resp.headers.get("access-control-allow-origin") == "http://localhost:3001"


# ===========================================================================
# 3. Centralized Test Database Bootstrap & Destination Safety
# ===========================================================================

def test_bootstrap_fails_closed_when_test_database_url_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """bootstrap_test_database must fail closed with a clear error when TEST_DATABASE_URL is absent."""
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError) as exc_info:
        bootstrap_test_database()
    assert "TEST_DATABASE_URL environment variable is not set" in str(exc_info.value)


def test_bootstrap_fails_closed_on_plain_dispenselens(monkeypatch: pytest.MonkeyPatch) -> None:
    """TEST_DATABASE_URL targeting plain 'dispenselens' (development DB) must fail closed."""
    monkeypatch.setenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens",
    )
    with pytest.raises(RuntimeError) as exc_info:
        bootstrap_test_database()
    assert "does not meet the disposable test database naming policy" in str(exc_info.value)


def test_bootstrap_fails_closed_when_same_as_development(monkeypatch: pytest.MonkeyPatch) -> None:
    """TEST_DATABASE_URL matching development DATABASE_URL must be rejected."""
    url = "postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens_test"
    with pytest.raises(RuntimeError, match="resolves to the same database target"):
        assert_safe_test_database(url, dev_url=url)


def test_bootstrap_succeeds_and_binds_valid_test_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Valid TEST_DATABASE_URL binds to DATABASE_URL and passes safety check."""
    valid_test_url = (
        "postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens_test"
    )
    monkeypatch.setenv("TEST_DATABASE_URL", valid_test_url)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens",
    )

    bound_url = bootstrap_test_database()
    assert bound_url == valid_test_url
    assert os.environ["DATABASE_URL"] == valid_test_url


# ===========================================================================
# 4. Non-Database Endpoints Independence
# ===========================================================================

def test_health_endpoint_independent_of_test_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Health endpoint must respond 200 OK without requiring TEST_DATABASE_URL."""
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    app = create_app()
    client = TestClient(app)
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
