"""
Dispense Lens - Runtime Baseline & Offline Safety Unit Tests (DLK-M3-025)

Verifies:
1. Deterministic offline diagnosis operation with no OpenAI API key configured.
2. Verified absence of OpenAI client construction or outbound network calls when unconfigured.
3. Resilience against external LLM errors and timeouts without altering deterministic diagnostic outputs.
4. Complete isolation of offline tests from developer .env files and synthetic .env parsing.
5. Default CORS origins including Next.js frontend on port 3001 (http://localhost:3001 and http://127.0.0.1:3001).
6. Centralized test-database bootstrap fail-closed behavior on missing, plain dispenselens,
   ambiguous development URLs, or dev-conflicting targets.
7. Non-database endpoints (health, stateless diagnosis) remain fully functional without TEST_DATABASE_URL.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import httpx
from openai import APITimeoutError, OpenAIError
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, _load_env_file as _real_load_env_file, get_settings
from app.main import create_app
from app.schemas.diagnosis import DiagnosisRequest
from app.services.ai.explanation_service import ExplanationService
from app.services.ai.llm_service import LLMService
from app.services.diagnosis.engine import DiagnosticEngine
from tests.conftest import bootstrap_test_database
from tests.unit.test_persistence_safety import assert_safe_test_database


@pytest.fixture(autouse=True)
def isolate_test_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent loading real developer .env files and isolate test environment keys."""
    monkeypatch.setattr("app.core.config._load_env_file", lambda: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)


# ===========================================================================
# 1. Deterministic Offline Troubleshooting (No AI Key Required)
# ===========================================================================

def test_stateless_diagnosis_offline_without_api_keys() -> None:
    """With OPENAI_API_KEY and LLM_API_KEY explicitly absent, stateless diagnosis
    succeeds with deterministic ranked causes, numerical scores, explanation, and next step.
    Guarantees no OpenAI client instantiation or outbound network calls across the full request.
    """
    app = create_app()
    client = TestClient(app)

    payload = {
        "description": "Dispense dots are shrinking over time during continuous operation",
        "defect_code": "D03_INCONSISTENT_SIZE",
        "material": "solder_paste",
        "method": "jetting",
    }

    # Block provider construction and all outbound HTTP transport traffic around the complete request
    # while preserving TestClient's in-process ASGI transport
    with patch("app.services.ai.llm_service.OpenAI") as mock_openai_cls, \
         patch("httpx.HTTPTransport.handle_request", side_effect=RuntimeError("Outbound network disabled")) as mock_http_transport, \
         patch("httpcore.ConnectionPool.handle_request", side_effect=RuntimeError("Outbound network disabled")) as mock_httpcore:
        response = client.post("/api/v1/diagnoses", json=payload)
        assert response.status_code == 200
        mock_openai_cls.assert_not_called()
        mock_http_transport.assert_not_called()
        mock_httpcore.assert_not_called()

    data = response.json()
    assert data["defect"] == "D03_INCONSISTENT_SIZE"
    assert len(data["ranked_causes"]) > 0
    # Deterministic scores and conclusions are preserved
    top_cause = data["ranked_causes"][0]
    assert top_cause["score"] > 0
    assert top_cause["cause_id"] is not None
    assert top_cause["conclusion"] in ("SUSPECTED", "CONFIRMED")
    # Explanation is generated via deterministic fallback template
    assert len(data["explanation"]) > 0
    assert "highest-supported hypothesis" in data["explanation"]
    # Next question or check is provided
    assert data["next_question"] is not None or data["next_check"] is not None


def test_offline_mode_does_not_construct_openai_client() -> None:
    """When no API key is provided, LLMService must not instantiate an OpenAI client
    or make any outbound requests.
    """
    with patch("app.services.ai.llm_service.OpenAI") as mock_openai_cls:
        # Test explicit empty key
        service_explicit = LLMService(api_key="")
        assert service_explicit.is_available is False
        assert service_explicit.client is None
        mock_openai_cls.assert_not_called()

        # Test default parameterless construction with unconfigured environment
        service_default = LLMService()
        assert service_default.is_available is False
        assert service_default.client is None
        mock_openai_cls.assert_not_called()

        # Attempting text generation returns None without touching OpenAI
        result = service_default.generate_text("Test prompt")
        assert result is None
        mock_openai_cls.assert_not_called()


def test_llm_timeout_preserves_deterministic_diagnostic_authority() -> None:
    """When a configured provider times out, LLMService catches the timeout and the engine
    preserves exact deterministic authority, matching the unconfigured baseline.
    """
    req = DiagnosisRequest(
        description="The dispensing dots become smaller after 20 minutes",
        defect_code="D03_INCONSISTENT_SIZE",
    )

    # 1. Baseline unconfigured execution
    baseline_engine = DiagnosticEngine(explanation_service=ExplanationService(llm_service=LLMService(api_key="")))
    baseline_case = baseline_engine.prepare_case(req)
    baseline_result = baseline_engine.diagnose(baseline_case)

    # 2. Configured provider that raises APITimeoutError during completion call
    with patch("app.services.ai.llm_service.OpenAI") as mock_openai_cls:
        mock_client = mock_openai_cls.return_value
        mock_request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
        mock_client.chat.completions.create.side_effect = APITimeoutError(request=mock_request)

        timeout_llm = LLMService(api_key="synthetic-configured-key")
        assert timeout_llm.is_available is True
        assert timeout_llm.client is not None

        timeout_engine = DiagnosticEngine(explanation_service=ExplanationService(llm_service=timeout_llm))
        timeout_case = timeout_engine.prepare_case(req)
        timeout_result = timeout_engine.diagnose(timeout_case)

        # Confirm completion method was called and handled via timeout path
        mock_client.chat.completions.create.assert_called()

    # 3. Assert exact deterministic parity between baseline and timeout results
    assert timeout_result.defect == baseline_result.defect
    assert [c.cause_id for c in timeout_result.ranked_causes] == [c.cause_id for c in baseline_result.ranked_causes]
    assert [c.score for c in timeout_result.ranked_causes] == [c.score for c in baseline_result.ranked_causes]
    assert [c.conclusion for c in timeout_result.ranked_causes] == [c.conclusion for c in baseline_result.ranked_causes]
    assert timeout_result.analysis_revision.revision_number == baseline_result.analysis_revision.revision_number
    assert timeout_result.issue_condition == baseline_result.issue_condition
    assert timeout_result.explanation == baseline_result.explanation
    assert "highest-supported hypothesis" in timeout_result.explanation


def test_llm_provider_error_preserves_deterministic_diagnostic_authority() -> None:
    """When a configured provider returns an API error, LLMService catches the error and the engine
    preserves exact deterministic authority, matching the unconfigured baseline.
    """
    req = DiagnosisRequest(
        description="The dispensing dots become smaller after 20 minutes",
        defect_code="D03_INCONSISTENT_SIZE",
    )

    # 1. Baseline unconfigured execution
    baseline_engine = DiagnosticEngine(explanation_service=ExplanationService(llm_service=LLMService(api_key="")))
    baseline_case = baseline_engine.prepare_case(req)
    baseline_result = baseline_engine.diagnose(baseline_case)

    # 2. Configured provider that raises OpenAIError during completion call
    with patch("app.services.ai.llm_service.OpenAI") as mock_openai_cls:
        mock_client = mock_openai_cls.return_value
        mock_client.chat.completions.create.side_effect = OpenAIError("Connection reset by peer")

        error_llm = LLMService(api_key="synthetic-configured-key")
        assert error_llm.is_available is True
        assert error_llm.client is not None

        error_engine = DiagnosticEngine(explanation_service=ExplanationService(llm_service=error_llm))
        error_case = error_engine.prepare_case(req)
        error_result = error_engine.diagnose(error_case)

        # Confirm completion method was called and handled via error path
        mock_client.chat.completions.create.assert_called()

    # 3. Assert exact deterministic parity between baseline and error results
    assert error_result.defect == baseline_result.defect
    assert [c.cause_id for c in error_result.ranked_causes] == [c.cause_id for c in baseline_result.ranked_causes]
    assert [c.score for c in error_result.ranked_causes] == [c.score for c in baseline_result.ranked_causes]
    assert [c.conclusion for c in error_result.ranked_causes] == [c.conclusion for c in baseline_result.ranked_causes]
    assert error_result.analysis_revision.revision_number == baseline_result.analysis_revision.revision_number
    assert error_result.issue_condition == baseline_result.issue_condition
    assert error_result.explanation == baseline_result.explanation
    assert "highest-supported hypothesis" in error_result.explanation


def test_load_env_file_synthetic_scenario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Zero-dependency .env loader parses synthetic .env files correctly and respects shell precedence."""
    # Control all environment keys under test to prevent ambient interference
    tested_keys = [
        "OPENAI_API_KEY",
        "LLM_API_KEY",
        "OPENAI_MODEL",
        "LLM_MODEL",
        "CORS_ORIGINS",
        "LLM_TIMEOUT_SECONDS",
        "PRE_EXISTING_KEY",
    ]
    for k in tested_keys:
        monkeypatch.delenv(k, raising=False)

    env_content = (
        "# Synthetic test comment\n"
        "\n"
        "OPENAI_API_KEY=synthetic-key-999\n"
        "OPENAI_MODEL='gpt-4o-custom'\n"
        'CORS_ORIGINS="http://custom:3000,http://custom:3001"\n'
        "LLM_TIMEOUT_SECONDS=25.0\n"
        "PRE_EXISTING_KEY=env_value_should_not_overwrite\n"
    )
    test_env_file = tmp_path / ".env"
    test_env_file.write_text(env_content, encoding="utf-8")

    # Set pre-existing shell variable to verify it is NOT overwritten by .env file
    monkeypatch.setenv("PRE_EXISTING_KEY", "shell_authority_value")

    # Point candidate resolution to tmp_path
    monkeypatch.chdir(tmp_path)
    # Restore the real _load_env_file implementation
    monkeypatch.setattr("app.core.config._load_env_file", _real_load_env_file)

    orig_env = os.environ.copy()
    try:
        # Invoke the real loader against the temporary synthetic .env
        _real_load_env_file()

        settings = Settings.load()
        assert settings.openai_api_key == "synthetic-key-999"
        assert settings.openai_model == "gpt-4o-custom"
        assert settings.cors_origins == ["http://custom:3000", "http://custom:3001"]
        assert settings.llm_timeout_seconds == 25.0
        assert os.environ["PRE_EXISTING_KEY"] == "shell_authority_value"
    finally:
        os.environ.clear()
        os.environ.update(orig_env)


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
    """TEST_DATABASE_URL matching development DATABASE_URL must be rejected before rebinding."""
    url = "postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens_test"
    monkeypatch.setenv("TEST_DATABASE_URL", url)
    monkeypatch.setenv("DATABASE_URL", url)
    with pytest.raises(RuntimeError, match="resolves to the same database target"):
        bootstrap_test_database()


def test_bootstrap_fails_closed_when_development_destination_has_ambiguous_query_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Development DATABASE_URL with destination query overrides (e.g. ?dbname=...) must fail closed."""
    test_url = "postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens_test"
    ambiguous_dev_url = (
        "postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens?dbname=dispenselens_test"
    )
    monkeypatch.setenv("TEST_DATABASE_URL", test_url)
    monkeypatch.setenv("DATABASE_URL", ambiguous_dev_url)

    with pytest.raises(RuntimeError, match="development DATABASE_URL contains ambiguous destination query parameter 'dbname'"):
        bootstrap_test_database()
    # Confirm DATABASE_URL was NOT rebound to test_url
    assert os.environ["DATABASE_URL"] == ambiguous_dev_url


def test_bootstrap_fails_closed_when_development_database_url_malformed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Malformed development DATABASE_URL fails closed before engine creation or rebinding."""
    test_url = "postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens_test"
    malformed_dev_url = "not-a-valid-database-url"
    monkeypatch.setenv("TEST_DATABASE_URL", test_url)
    monkeypatch.setenv("DATABASE_URL", malformed_dev_url)

    with pytest.raises(RuntimeError, match="development DATABASE_URL could not be parsed or is invalid"):
        bootstrap_test_database()
    assert os.environ["DATABASE_URL"] == malformed_dev_url


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
