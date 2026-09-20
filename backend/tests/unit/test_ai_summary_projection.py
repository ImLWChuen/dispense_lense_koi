"""
DispenseIQ — AI Summary Evidence Projection & Safety Unit Tests (DLK-M3-030)

Verifies:
1. Bounded text-only observation projection into summary prompt (observation type,
   value, source, confidence, first-seen revision, safe image provenance).
2. Strict rejection and omission of raw image bytes, base64 strings, filesystem paths,
   secrets, and unwhitelisted metadata.
3. PromptManager backward compatibility when observations parameter is omitted or None.
4. ExplanationService integration passing safe observations.
5. Mocked LLM provider success returning source="llm" with observations present in prompt.
6. Provider failure / unavailability gracefully falling back to source="deterministic".
7. Strict case state invariance (diagnosis scores, revision, condition unchanged before/after).
"""

from __future__ import annotations

import json
from typing import Any, Generator
from unittest.mock import MagicMock, patch
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.db.session import get_session_factory
from app.main import app
from app.models.case import CaseModel
from app.schemas.diagnosis import (
    EvidenceSource,
    IssueCondition,
    Observation,
    ObservationType,
    StatementType,
    StructuredCase,
)
from app.services.ai.explanation_service import ExplanationService
from app.services.ai.llm_service import LLMService
from app.services.ai.prompt_manager import PromptManager

client = TestClient(app)


@pytest.fixture
def tracked_cases() -> Generator[list[str], None, None]:
    """Track created case IDs and clean them up after test execution."""
    case_ids: list[str] = []
    yield case_ids

    if case_ids:
        factory = get_session_factory()
        with factory() as session:
            session.execute(delete(CaseModel).where(CaseModel.case_id.in_(case_ids)))
            session.commit()


# ===========================================================================
# 1. Observation Projection & Provenance Whitelist Tests
# ===========================================================================

def test_project_safe_observations_image_provenance():
    """Verify calibrated image observations project with safe provenance fields."""
    raw_observations = [
        Observation(
            observation_type=ObservationType.DEPOSIT_SIZE,
            value="undersized",
            source=EvidenceSource.IMAGE,
            statement_type=StatementType.AI_INFERENCE,
            confidence=0.92,
            metadata={
                "roi_id": "ROI_1",
                "mode": "PROCESS_LIMITS",
                "status": "CALIBRATED",
                "coverage_ratio": 0.12,
                "overflow_ratio": 0.02,
                "calibrated_diameter_mm": 1.25,
                "segmentation_quality": "good",
                "comparison_basis": {
                    "min_coverage_ratio": 0.15,
                    "max_coverage_ratio": 0.85,
                },
            },
        ),
        Observation(
            observation_type=ObservationType.SPREADING_BEHAVIOUR,
            value="tailing",
            source=EvidenceSource.USER,
            statement_type=StatementType.USER_OBSERVATION,
            confidence=None,
            metadata={},
        ),
    ]

    projected = PromptManager.project_safe_observations(raw_observations)
    assert len(projected) == 2

    # Verify IMAGE observation
    img_obs = projected[0]
    assert img_obs["observation_type"] == "deposit_size"
    assert img_obs["value"] == "undersized"
    assert img_obs["source"] == "IMAGE"
    assert img_obs["confidence"] == 0.92
    assert "provenance" in img_obs

    prov = img_obs["provenance"]
    assert prov["roi_id"] == "ROI_1"
    assert prov["mode"] == "PROCESS_LIMITS"
    assert prov["status"] == "CALIBRATED"
    assert prov["coverage_ratio"] == 0.12
    assert prov["overflow_ratio"] == 0.02
    assert prov["calibrated_diameter_mm"] == 1.25
    assert prov["segmentation_quality"] == "good"
    assert prov["comparison_basis"]["min_coverage_ratio"] == 0.15

    # Verify USER observation
    usr_obs = projected[1]
    assert usr_obs["observation_type"] == "spreading_behaviour"
    assert usr_obs["value"] == "tailing"
    assert usr_obs["source"] == "USER"
    assert "confidence" not in usr_obs
    assert "provenance" not in usr_obs


def test_project_safe_observations_rejects_paths_secrets_bytes_and_unwhitelisted():
    """Verify raw image bytes, base64 strings, paths, secrets, and unapproved metadata are omitted."""
    dirty_observations = [
        {
            "observation_type": "deposit_size",
            "value": "undersized",
            "source": "IMAGE",
            "confidence": 0.88,
            "first_seen_revision": 1,
            "metadata": {
                # Safe fields
                "mode": "PROCESS_LIMITS",
                "status": "CALIBRATED",
                "roi_id": 2,
                # Prohibited: Raw bytes
                "raw_bytes": b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR",
                # Prohibited: Base64 data URI
                "encoded_preview": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA",
                # Prohibited: Local filesystem paths
                "file_path_win": "C:\\Users\\admin\\AppData\\Local\\Temp\\defect_roi.png",
                "file_path_unix": "/var/app/uploads/2026/09/image_01.jpg",
                "relative_path": "./uploads/preview.png",
                # Prohibited: Secrets / API keys / tokens
                "secret_key": "sk-proj-supersecretkey12345",
                "auth_token": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6",
                "password": "production_database_password",
                # Prohibited: Unwhitelisted arbitrary metadata
                "unrestricted_internal_state": {"arbitrary": "data"},
            },
        }
    ]

    projected = PromptManager.project_safe_observations(dirty_observations)
    assert len(projected) == 1

    item = projected[0]
    prov = item.get("provenance", {})

    # Safe fields preserved
    assert prov.get("mode") == "PROCESS_LIMITS"
    assert prov.get("status") == "CALIBRATED"
    assert prov.get("roi_id") == 2

    # Prohibited fields must be strictly absent
    assert "raw_bytes" not in prov
    assert "encoded_preview" not in prov
    assert "file_path_win" not in prov
    assert "file_path_unix" not in prov
    assert "relative_path" not in prov
    assert "secret_key" not in prov
    assert "auth_token" not in prov
    assert "password" not in prov
    assert "unrestricted_internal_state" not in prov

    # String representation of projected output must have zero paths or secret strings
    dumped = json.dumps(projected)
    assert "base64" not in dumped
    assert "sk-proj" not in dumped
    assert "AppData" not in dumped
    assert "uploads" not in dumped
    assert ".png" not in dumped
    assert ".jpg" not in dumped


# ===========================================================================
# 2. PromptManager Interface & Backward Compatibility Tests
# ===========================================================================

def test_prompt_manager_summary_prompt_embeds_observations():
    """Verify get_case_summary_prompt includes projected observations in user prompt."""
    observations = [
        {
            "observation_type": "deposit_size",
            "value": "undersized",
            "source": "IMAGE",
            "first_seen_revision": 1,
            "provenance": {"mode": "PROCESS_LIMITS", "status": "CALIBRATED"},
        }
    ]

    sys_prompt, user_prompt = PromptManager.get_case_summary_prompt(
        case_id="case-summary-001",
        defect_name="Inconsistent Deposit Size",
        description="Dispense dot volume drift",
        total_revisions=3,
        confirmed_causes=["C01"],
        attempted_checks=[{"check_id": "CHK_01", "status": "COMPLETED", "finding": "SUPPORTS"}],
        issue_condition="RESOLVED",
        observations=observations,
    )

    assert "case-summary-001" in user_prompt
    assert "Inconsistent Deposit Size" in user_prompt
    assert "observations" in user_prompt
    assert "deposit_size" in user_prompt
    assert "undersized" in user_prompt
    assert "PROCESS_LIMITS" in user_prompt


def test_prompt_manager_summary_prompt_backward_compatibility():
    """Verify get_case_summary_prompt functions without observations parameter."""
    sys_prompt, user_prompt = PromptManager.get_case_summary_prompt(
        case_id="case-compat-001",
        defect_name="Nozzle Clog",
        description="Tip blocked",
        total_revisions=1,
        confirmed_causes=[],
        attempted_checks=[],
        issue_condition="UNRESOLVED",
    )

    assert "case-compat-001" in user_prompt
    assert "Nozzle Clog" in user_prompt
    # Must parse cleanly as JSON payload without error
    lines = user_prompt.split("\n", 1)[1]
    parsed = json.loads(lines)
    assert parsed["case_id"] == "case-compat-001"
    assert "observations" not in parsed


def test_explanation_service_summarize_case_with_observations():
    """Verify ExplanationService.summarize_case projects observations and calls LLM."""
    mock_llm = MagicMock(spec=LLMService)
    mock_llm.is_available = True
    mock_llm.generate_text.return_value = "Executive summary with image evidence taken into account."

    service = ExplanationService(llm_service=mock_llm)

    case = StructuredCase(
        case_id=str(uuid.uuid4()),
        defect_name="Inconsistent Deposit Size",
        defect_code="D03",
        description="Volume drift observed",
        observations=[
            Observation(
                observation_type=ObservationType.DEPOSIT_SIZE,
                value="undersized",
                source=EvidenceSource.IMAGE,
                statement_type=StatementType.AI_INFERENCE,
                confidence=0.95,
                metadata={"mode": "PROCESS_LIMITS", "status": "CALIBRATED"},
            )
        ],
        previous_answers=[],
        previous_check_results=[],
        confirmed_causes=[],
        analysis_revisions=[],
        issue_condition=IssueCondition.UNRESOLVED,
    )

    summary = service.summarize_case(case)
    assert summary == "Executive summary with image evidence taken into account."
    assert mock_llm.generate_text.called

    prompt_call = mock_llm.generate_text.call_args[0][0]
    assert "undersized" in prompt_call
    assert "PROCESS_LIMITS" in prompt_call


# ===========================================================================
# 3. HTTP API Endpoint Tests: Mocked LLM Success & Deterministic Fallback
# ===========================================================================

def test_ai_summary_endpoint_mocked_llm_success(tracked_cases):
    """POST /api/v1/cases/{id}/ai-summary returns source='llm' when LLM succeeds."""
    # 1. Create a durable case
    create_res = client.post(
        "/api/v1/cases",
        json={
            "description": "The dispensing dots become smaller after the machine has been running for around 20 minutes.",
            "material": "Solder-Paste",
            "method": "time_pressure",
            "machine_context": {"operator": "Alex Chen"},
        },
    )
    assert create_res.status_code == 201
    case_id = create_res.json()["case_id"]
    tracked_cases.append(case_id)

    mock_summary = "AI Summary: Case demonstrates nozzle restriction with consistent drift pattern."

    with patch("app.api.cases.LLMService") as MockLLMClass:
        mock_instance = MagicMock()
        mock_instance.is_available = True
        mock_instance.generate_text.return_value = mock_summary
        MockLLMClass.return_value = mock_instance

        res = client.post(f"/api/v1/cases/{case_id}/ai-summary")
        assert res.status_code == 200
        data = res.json()

        assert data["case_id"] == case_id
        assert data["source"] == "llm"
        assert data["summary"] == mock_summary
        assert data["revision"] >= 1

        # Verify prompt contained observation projection
        assert mock_instance.generate_text.called
        call_prompt = mock_instance.generate_text.call_args[0][0]
        assert "observations" in call_prompt


def test_ai_summary_endpoint_provider_failure_falls_back_to_deterministic(tracked_cases):
    """POST /api/v1/cases/{id}/ai-summary returns source='deterministic' when LLM fails."""
    create_res = client.post(
        "/api/v1/cases",
        json={
            "description": "Epoxy deposit spreading excessively",
            "material": "Epoxy-300",
            "method": "jetting",
        },
    )
    assert create_res.status_code == 201
    case_id = create_res.json()["case_id"]
    tracked_cases.append(case_id)

    with patch("app.api.cases.LLMService") as MockLLMClass:
        mock_instance = MagicMock()
        mock_instance.is_available = True
        # Provider raises network error
        mock_instance.generate_text.side_effect = RuntimeError("OpenAI connection timed out")
        MockLLMClass.return_value = mock_instance

        res = client.post(f"/api/v1/cases/{case_id}/ai-summary")
        assert res.status_code == 200
        data = res.json()

        assert data["case_id"] == case_id
        assert data["source"] == "deterministic"
        assert "Diagnostic Case Report" in data["summary"]
        assert data["revision"] >= 1


def test_ai_summary_endpoint_case_state_invariance(tracked_cases):
    """Calling ai-summary does not mutate case revision, diagnostic ranking, scores, or condition."""
    create_res = client.post(
        "/api/v1/cases",
        json={
            "description": "The dispensing dots become smaller after the machine has been running for around 20 minutes.",
            "material": "Epoxy-300",
            "method": "time_pressure",
        },
    )
    assert create_res.status_code == 201
    case_id = create_res.json()["case_id"]
    tracked_cases.append(case_id)

    # Fetch initial state
    before_res = client.get(f"/api/v1/cases/{case_id}")
    assert before_res.status_code == 200
    before_data = before_res.json()

    # Call ai-summary multiple times (both LLM and deterministic fallback)
    with patch("app.api.cases.LLMService") as MockLLMClass:
        mock_instance = MagicMock()
        mock_instance.is_available = True
        mock_instance.generate_text.return_value = "Mocked LLM summary"
        MockLLMClass.return_value = mock_instance

        summary_res1 = client.post(f"/api/v1/cases/{case_id}/ai-summary")
        assert summary_res1.status_code == 200
        assert summary_res1.json()["source"] == "llm"

    # Second call falling back
    summary_res2 = client.post(f"/api/v1/cases/{case_id}/ai-summary")
    assert summary_res2.status_code == 200
    assert summary_res2.json()["source"] == "deterministic"

    # Fetch state after summaries
    after_res = client.get(f"/api/v1/cases/{case_id}")
    assert after_res.status_code == 200
    after_data = after_res.json()

    # Assert absolute invariance
    assert before_data["case_id"] == after_data["case_id"]
    assert before_data["issue_condition"] == after_data["issue_condition"]
    assert before_data["defect_code"] == after_data["defect_code"]
    assert before_data["defect_name"] == after_data["defect_name"]
    assert len(before_data["observations"]) == len(after_data["observations"])
    assert len(before_data["analysis_revisions"]) == len(after_data["analysis_revisions"])
    assert before_data["diagnosis"]["ranked_causes"] == after_data["diagnosis"]["ranked_causes"]
    assert before_data["diagnosis"]["analysis_revision"] == after_data["diagnosis"]["analysis_revision"]
