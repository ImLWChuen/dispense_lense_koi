"""
DispenseIQ — Teammate Integration & Zero-Hardcoding Contracts Tests

Verifies:
1. CORS headers allowing Next.js frontend on http://localhost:3000
2. Knowledge catalog endpoints (defects, causes, questions, actions)
3. Zero-dependency .env loader and centralized Settings
4. LLMService configurability (model name, api base, offline resilience)
"""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, _load_env_file, get_settings
from app.main import create_app
from app.services.ai.llm_service import LLMService


@pytest.fixture
def client() -> TestClient:
    """Create a FastAPI test client with CORS and routers configured."""
    app = create_app()
    return TestClient(app)


# ===========================================================================
# 1. CORS Middleware & Frontend Usability
# ===========================================================================

def test_cors_preflight_for_nextjs_frontend(client: TestClient) -> None:
    """Ensure OPTIONS preflight requests from Next.js on port 3000 are approved."""
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert "access-control-allow-credentials" in response.headers


def test_cors_simple_request_for_nextjs_frontend(client: TestClient) -> None:
    """Ensure GET requests include access-control-allow-origin for Next.js."""
    response = client.get(
        "/api/v1/health",
        headers={"Origin": "http://localhost:3000"},
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_preflight_for_nextjs_frontend_port_3001(client: TestClient) -> None:
    """Ensure OPTIONS preflight requests from Next.js on port 3001 are approved."""
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:3001",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3001"
    assert "access-control-allow-credentials" in response.headers


def test_cors_simple_request_for_nextjs_frontend_port_3001(client: TestClient) -> None:
    """Ensure GET requests include access-control-allow-origin for Next.js on port 3001."""
    response = client.get(
        "/api/v1/health",
        headers={"Origin": "http://localhost:3001"},
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3001"


# ===========================================================================
# 2. Dynamic Knowledge Catalog Endpoints
# ===========================================================================

def test_list_defects_catalog(client: TestClient) -> None:
    """GET /api/v1/defects returns all 6 canonical defect categories."""
    response = client.get("/api/v1/defects")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 6
    codes = {d["code"] for d in data}
    assert "D01_TOO_LITTLE" in codes
    assert "D03_INCONSISTENT_SIZE" in codes
    assert "D04_MISSING_DOTS" in codes


def test_list_causes_catalog_all(client: TestClient) -> None:
    """GET /api/v1/causes returns all authorized root causes."""
    response = client.get("/api/v1/causes")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 5
    cause_ids = {c["id"] for c in data}
    assert "nozzle_restriction" in cause_ids
    assert "pressure_instability" in cause_ids


def test_list_causes_catalog_filtered_by_defect(client: TestClient) -> None:
    """GET /api/v1/causes?defect_code=D03_INCONSISTENT_SIZE returns filtered causes."""
    response = client.get("/api/v1/causes?defect_code=D03_INCONSISTENT_SIZE")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    cause_ids = {c["id"] for c in data}
    assert "nozzle_restriction" in cause_ids


def test_list_questions_catalog_all(client: TestClient) -> None:
    """GET /api/v1/questions returns all authorized diagnostic questions."""
    response = client.get("/api/v1/questions")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 5
    q_ids = {q["id"] for q in data}
    assert any("Q" in qid for qid in q_ids)


def test_list_questions_catalog_filtered_by_cause(client: TestClient) -> None:
    """GET /api/v1/questions?cause_id=nozzle_restriction filters questions for nozzle restriction."""
    response = client.get("/api/v1/questions?cause_id=nozzle_restriction")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    for q in data:
        assert "nozzle_restriction" in q["applicable_causes"]


def test_list_actions_catalog_endpoint(client: TestClient) -> None:
    """GET /api/v1/actions returns all authorized checks."""
    response = client.get("/api/v1/actions")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 5
    action_ids = {a["id"] for a in data}
    assert "ACT_INSPECT_NOZZLE" in action_ids or any("ACT" in aid for aid in action_ids)


# ===========================================================================
# 3. Settings & Zero-Dependency .env Loader
# ===========================================================================

def test_settings_load_defaults() -> None:
    """Verify Settings defaults include Next.js origins (port 3000 and 3001) and openai model."""
    settings = get_settings()
    assert "http://localhost:3000" in settings.cors_origins
    assert "http://127.0.0.1:3000" in settings.cors_origins
    assert "http://localhost:3001" in settings.cors_origins
    assert "http://127.0.0.1:3001" in settings.cors_origins
    assert settings.openai_model == "gpt-4o-mini"
    assert settings.llm_timeout_seconds == 10.0


def test_custom_cors_origins_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure CORS_ORIGINS parses comma-separated lists and wildcard."""
    monkeypatch.setenv("CORS_ORIGINS", "http://custom-frontend:3000, http://qa.internal:8080")
    settings = Settings.load()
    assert settings.cors_origins == ["http://custom-frontend:3000", "http://qa.internal:8080"]

    monkeypatch.setenv("CORS_ORIGINS", "*")
    settings_wildcard = Settings.load()
    assert settings_wildcard.cors_origins == ["*"]


# ===========================================================================
# 4. LLM Service Decoupling & Configurability
# ===========================================================================

def test_llm_service_custom_model_and_api_base(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify LLMService respects custom model names and settings for alternative models."""
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-12345")

    service = LLMService()
    assert service.model_name == "gpt-4o"
    assert service.is_available is True


def test_llm_service_offline_when_no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify LLMService gracefully reports unavailable when unconfigured."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    service = LLMService(api_key="")
    assert service.is_available is False
    assert service.generate_text("Test prompt") is None
