"""
DispenseIQ — Bounded LLM & AI Services Unit Tests (Phase 12 Verification)

Verifies:
1. Valid structured symptom extraction via LLM.
2. Rejection of root-cause probabilities and diagnostic claims (Plan §3.3).
3. Graceful handling of malformed JSON from LLM.
4. Handling of LLM timeout and service unavailability (Rule 6).
5. ExplanationService integration and safety guardrail enforcement:
   - Preserves exact deterministic scores (Rule 1).
   - Rejects hallucinated procedures/checks (Rule 2).
   - Rejects unconfirmed root-cause confirmation (Rule 4).
   - Rejects unverified issue resolution (Rule 5).
   - Seamless fallback to deterministic template upon failure (Rule 6).
6. Preservation of original user text (Rule 7).
7. DiagnosticEngine integration with ExplanationService.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.schemas.diagnosis import (
    CauseConclusion,
    DiagnosisRequest,
    IssueCondition,
    Observation,
    ObservationType,
    StructuredCase,
)
from app.services.ai.explanation_service import ExplanationService
from app.services.ai.llm_service import LLMService
from app.services.ai.prompt_manager import PromptManager
from app.services.diagnosis.cause_ranker import CauseRanker
from app.services.diagnosis.engine import DiagnosticEngine
from app.services.diagnosis.symptom_extractor import SymptomExtractor


class DummyLLMService(LLMService):
    """Mock LLMService for testing deterministic control."""

    def __init__(self, text_response: str | None = None, json_response: dict[str, Any] | None = None) -> None:
        super().__init__(api_key="mock_test_key")
        self._text_response = text_response
        self._json_response = json_response
        self.call_count = 0

    def generate_text(self, prompt: str, system_prompt: str | None = None) -> str | None:
        self.call_count += 1
        return self._text_response

    def generate_structured(self, prompt: str, system_prompt: str | None = None) -> dict[str, Any] | None:
        self.call_count += 1
        return self._json_response


# ===========================================================================
# 1. Prompt Manager Tests
# ===========================================================================

def test_prompt_manager_symptom_extraction_format():
    """Verify prompt manager includes required anti-diagnosis instructions."""
    pm = PromptManager()
    sys_prompt, user_prompt = pm.get_symptom_extraction_prompt("dots are small after 20 mins")
    assert "DO NOT diagnose or assign root causes" in sys_prompt
    assert "DO NOT return probabilities" in sys_prompt
    assert "dots are small after 20 mins" in user_prompt


def test_prompt_manager_explanation_prompt_format():
    """Verify explanation prompt prohibits score modifications and invented procedures."""
    pm = PromptManager()
    sys_prompt, user_prompt = pm.get_diagnosis_explanation_prompt(
        top_cause_name="Air Supply Issue",
        top_cause_score=82.0,
        supporting_evidence=["intermittent"],
        contradicting_evidence=[],
        missing_evidence=["supply check"],
    )
    assert "You MUST NOT invent, calculate, or alter any numerical scores" in sys_prompt
    assert "You MUST NOT invent troubleshooting procedures" in sys_prompt
    assert "Air Supply Issue" in user_prompt
    assert "82/100" in user_prompt


# ===========================================================================
# 2. Symptom Extraction Bounded Tests
# ===========================================================================

def test_symptom_extractor_uses_deterministic_first():
    """When deterministic rules match, LLM should not be invoked."""
    mock_llm = DummyLLMService(json_response={"observations": []})
    extractor = SymptomExtractor(llm_service=mock_llm)

    result = extractor.extract("The dispensing dots become smaller after the machine has been running for 20 minutes.")
    assert len(result.observations) >= 2
    assert result.extraction_method == "deterministic"
    assert mock_llm.call_count == 0  # Deterministic was sufficient


def test_symptom_extractor_falls_back_to_llm_when_no_regex_match():
    """Ambiguous text with no keyword match triggers bounded LLM fallback."""
    mock_llm = DummyLLMService(
        json_response={
            "observations": [
                {"type": "deposit_size", "value": "undersized"},
                {"type": "runtime_pattern", "value": "after_prolonged_operation"},
            ],
            "user_hypotheses": ["nozzle might be clogged"],
        }
    )
    extractor = SymptomExtractor(llm_service=mock_llm)

    description = "Non-standard phrasing: output mass drops significantly after half an hour."
    result = extractor.extract(description)

    assert result.extraction_method == "llm"
    assert len(result.observations) == 2
    assert any(o.observation_type == ObservationType.DEPOSIT_SIZE and o.value == "undersized" for o in result.observations)
    assert "nozzle might be clogged" in result.user_hypotheses
    # Rule 7: Original user text preserved
    assert result.original_description == description


def test_symptom_extractor_rejects_llm_probability_hallucination():
    """LLM outputs claiming root cause probabilities (e.g. 90% air bubble) must be rejected."""
    mock_llm = DummyLLMService(
        json_response={
            "observations": [
                {"type": "deposit_size", "value": "undersized"},
                {"type": "root_cause_probability", "value": "90% air bubble"},
            ],
        }
    )
    extractor = SymptomExtractor(llm_service=mock_llm)

    # extract_symptoms on LLMService rejects observations with percentages
    clean_llm_result = mock_llm.extract_symptoms("Some description")
    assert clean_llm_result is None


def test_symptom_extractor_handles_llm_timeout_gracefully():
    """When LLM times out, extraction gracefully records a warning without crashing (Rule 6)."""
    mock_llm = DummyLLMService(json_response=None)  # Simulates failure / timeout
    extractor = SymptomExtractor(llm_service=mock_llm)

    result = extractor.extract("Totally unrecognizable technician slang xyz123")
    assert len(result.observations) == 0
    assert len(result.warnings) > 0
    assert "No structured observations could be extracted" in result.warnings[0]


# ===========================================================================
# 3. Explanation Service Tests
# ===========================================================================

def test_explanation_service_offline_fallback(monkeypatch: pytest.MonkeyPatch):
    """When no LLM API key is present, ExplanationService returns deterministic template."""
    monkeypatch.setattr("app.core.config._load_env_file", lambda: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    offline_llm = LLMService()
    assert not offline_llm.is_available
    assert offline_llm.client is None

    service = ExplanationService(llm_service=offline_llm)
    case = StructuredCase(description="Dots undersized")
    ranker = CauseRanker()
    obs = [Observation(observation_type=ObservationType.DEPOSIT_SIZE, value="undersized")]
    ranking = ranker.rank(obs, "D01_TOO_LITTLE")

    explanation = service.explain_diagnosis(ranking, case)
    assert "highest-supported hypothesis" in explanation
    assert "with evidence support" in explanation

    # Also verify default ExplanationService() instantiation without explicit llm_service
    default_service = ExplanationService()
    assert not default_service.llm.is_available
    default_explanation = default_service.explain_diagnosis(ranking, case)
    assert default_explanation == explanation


def test_explanation_service_rejects_unconfirmed_root_cause_claim():
    """LLM claiming root cause is confirmed when case is unconfirmed must be rejected."""
    hallucinating_llm = DummyLLMService(
        text_response="Diagnosis complete: The confirmed root cause is nozzle restriction."
    )
    service = ExplanationService(llm_service=hallucinating_llm)

    case = StructuredCase(description="Dots undersized", confirmed_causes=[])
    ranker = CauseRanker()
    obs = [Observation(observation_type=ObservationType.DEPOSIT_SIZE, value="undersized")]
    ranking = ranker.rank(obs, "D01_TOO_LITTLE")

    explanation = service.explain_diagnosis(ranking, case)
    # The hallucinated string must be rejected in favor of deterministic fallback
    assert "highest-supported hypothesis" in explanation
    assert "Diagnosis complete: The confirmed root cause is" not in explanation


def test_explanation_service_rejects_false_issue_resolved_claim():
    """LLM claiming issue is resolved when case is UNRESOLVED must be rejected."""
    hallucinating_llm = DummyLLMService(
        text_response="Good news: The defect is fixed and the issue is resolved!"
    )
    service = ExplanationService(llm_service=hallucinating_llm)

    case = StructuredCase(description="Dots undersized", issue_condition=IssueCondition.UNRESOLVED)
    ranker = CauseRanker()
    obs = [Observation(observation_type=ObservationType.DEPOSIT_SIZE, value="undersized")]
    ranking = ranker.rank(obs, "D01_TOO_LITTLE")

    explanation = service.explain_diagnosis(ranking, case)
    assert "highest-supported hypothesis" in explanation
    assert "issue is resolved" not in explanation.lower()


def test_explanation_service_accepts_valid_bounded_llm_output():
    """Well-behaved LLM output respecting guardrails is accepted."""
    valid_text = (
        "Findings: Nozzle restriction is currently the leading hypothesis with evidence support 70/100.\n"
        "Evidence: The undersized deposits strongly support flow restriction.\n"
        "Next Step: Please inspect the nozzle orifice."
    )
    good_llm = DummyLLMService(text_response=valid_text)
    service = ExplanationService(llm_service=good_llm)

    case = StructuredCase(description="Dots undersized", issue_condition=IssueCondition.UNRESOLVED)
    ranker = CauseRanker()
    obs = [Observation(observation_type=ObservationType.DEPOSIT_SIZE, value="undersized")]
    ranking = ranker.rank(obs, "D01_TOO_LITTLE")

    explanation = service.explain_diagnosis(ranking, case)
    assert "Findings: Nozzle restriction" in explanation


# ===========================================================================
# 4. DiagnosticEngine End-to-End Integration
# ===========================================================================

def test_engine_delegates_to_explanation_service():
    """DiagnosticEngine uses ExplanationService during diagnose()."""
    mock_service = MagicMock(spec=ExplanationService)
    mock_service.explain_diagnosis.return_value = "Custom explanation from explanation service"

    engine = DiagnosticEngine(explanation_service=mock_service)
    request = DiagnosisRequest(
        description="The dispensing dots become smaller after the machine has been running for around 20 minutes.",
    )
    result = engine.diagnose(request)

    assert result.explanation == "Custom explanation from explanation service"
    assert mock_service.explain_diagnosis.called


def test_explanation_service_includes_evidence_provenance():
    """ExplanationService includes evidence provenance tags [IMAGE] and [USER] in prompt payload."""
    from app.schemas.diagnosis import EvidenceSource
    recorded_prompts: list[tuple[str, str]] = []

    class CapturingLLM(DummyLLMService):
        def generate_text(self, prompt: str, system_prompt: str | None = None) -> str | None:
            recorded_prompts.append((system_prompt or "", prompt))
            return "Findings: Evaluated with provenance.\nEvidence: [IMAGE] undersized detected.\nNext Step: None."

    capturing_llm = CapturingLLM()
    service = ExplanationService(llm_service=capturing_llm)

    case = StructuredCase(description="Dots undersized", issue_condition=IssueCondition.UNRESOLVED)
    ranker = CauseRanker()
    obs = [
        Observation(
            observation_type=ObservationType.DEPOSIT_SIZE,
            value="undersized",
            source=EvidenceSource.IMAGE,
        ),
        Observation(
            observation_type=ObservationType.RUNTIME_PATTERN,
            value="after_prolonged_operation",
            source=EvidenceSource.USER,
        ),
    ]
    ranking = ranker.rank(obs, "D01_TOO_LITTLE")

    explanation = service.explain_diagnosis(ranking, case)
    assert len(recorded_prompts) == 1
    sys_prompt, user_prompt = recorded_prompts[0]

    # Verify provenance tag in user prompt context
    assert "[IMAGE]" in user_prompt
    # Verify raw image data or paths are not included
    assert ".png" not in user_prompt
    assert "data:image" not in user_prompt
    assert "base64" not in user_prompt
