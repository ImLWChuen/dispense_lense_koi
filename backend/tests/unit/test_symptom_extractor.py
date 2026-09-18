"""
DispenseIQ — Symptom Extractor Unit Tests (Section 23)

Verifies:
1. Regex extraction across all observation dimensions
2. User hypothesis isolation (never auto-promote to confirmed cause)
3. Observation statement type and provenance tracking
4. Empty/whitespace input handling
5. Fallback behaviour when deterministic rules find no observations
"""

from __future__ import annotations

import pytest

from app.schemas.diagnosis import (
    EvidenceSource,
    ObservationType,
    StatementType,
)
from app.services.diagnosis.symptom_extractor import SymptomExtractor


@pytest.fixture
def extractor() -> SymptomExtractor:
    """Provide a fresh SymptomExtractor instance with LLM disabled for deterministic testing."""
    return SymptomExtractor(llm_service=None)


def test_extract_deposit_size_undersized(extractor: SymptomExtractor) -> None:
    """Verify extraction of undersized / small dot symptoms."""
    result = extractor.extract("Dispensing dots are too small and tiny on board.")
    types = [o.observation_type for o in result.observations]
    values = [o.value for o in result.observations]

    assert ObservationType.DEPOSIT_SIZE in types
    assert "undersized" in values
    assert result.extraction_method == "deterministic"


def test_extract_deposit_size_oversized(extractor: SymptomExtractor) -> None:
    """Verify extraction of oversized dot symptoms."""
    result = extractor.extract("Dots are too large and oversized with excessive material.")
    types = [o.observation_type for o in result.observations]
    values = [o.value for o in result.observations]

    assert ObservationType.DEPOSIT_SIZE in types
    assert "oversized" in values


def test_extract_inconsistent_size(extractor: SymptomExtractor) -> None:
    """Verify extraction of inconsistent size symptoms."""
    result = extractor.extract("Deposit dots have inconsistent and uneven volume.")
    values = [o.value for o in result.observations]
    assert "inconsistent" in values


def test_extract_missing_dots(extractor: SymptomExtractor) -> None:
    """Verify extraction of missing deposit presence."""
    result = extractor.extract("Skipped shots and missing dots observed at nozzle.")
    types = [o.observation_type for o in result.observations]
    assert ObservationType.DEPOSIT_PRESENCE in types
    assert any(o.value == "missing" for o in result.observations)


def test_extract_bubbles_and_craters(extractor: SymptomExtractor) -> None:
    """Verify extraction of visible bubbles and crater shapes."""
    result = extractor.extract("Visible air bubbles and voids inside dots, leaves crater shapes.")
    types = [o.observation_type for o in result.observations]
    assert ObservationType.BUBBLE_PRESENCE in types
    assert any(o.value == "visible_bubbles" for o in result.observations)
    assert any(o.value == "crater_shape" for o in result.observations)


def test_extract_runtime_pattern(extractor: SymptomExtractor) -> None:
    """Verify runtime duration pattern extraction."""
    result = extractor.extract("Problem appears after the machine has been running for 25 minutes.")
    types = [o.observation_type for o in result.observations]
    assert ObservationType.RUNTIME_PATTERN in types
    assert any(o.value == "after_prolonged_operation" for o in result.observations)


def test_extract_frequency_and_location(extractor: SymptomExtractor) -> None:
    """Verify frequency (intermittent) and location (specific nozzle) extraction."""
    result = extractor.extract("Dots fail intermittently at specific nozzle 2.")
    types = [o.observation_type for o in result.observations]
    assert ObservationType.FREQUENCY_PATTERN in types
    assert ObservationType.LOCATION_PATTERN in types
    assert any(o.value == "intermittent" for o in result.observations)
    assert any(o.value == "specific_nozzle" for o in result.observations)


def test_user_hypothesis_isolation(extractor: SymptomExtractor) -> None:
    """Ensure user hypothesis is stored separately and NOT converted into an observation or confirmed cause."""
    text = "Dots are too small. I think the nozzle is blocked."
    result = extractor.extract(text)

    # Hypothesis must be detected
    assert len(result.user_hypotheses) > 0
    assert any("nozzle is blocked" in h.lower() for h in result.user_hypotheses)

    # Hypothesis must NOT appear as an observation
    obs_texts = [o.value for o in result.observations]
    assert "nozzle is blocked" not in obs_texts

    # Observation statement type must be USER_OBSERVATION
    for obs in result.observations:
        assert obs.statement_type == StatementType.USER_OBSERVATION
        assert obs.source == EvidenceSource.USER


def test_empty_description_handling(extractor: SymptomExtractor) -> None:
    """Ensure empty or whitespace descriptions return empty observations with warnings."""
    result = extractor.extract("   ")
    assert result.observations == []
    assert len(result.warnings) > 0


def test_llm_fallback_when_deterministic_finds_nothing() -> None:
    """Ensure bounded LLM fallback is triggered when regex matches nothing."""
    class MockLLM:
        def __init__(self) -> None:
            self.is_available = True

        def extract_symptoms(self, text: str) -> dict:
            return {
                "observations": [{"type": "deposit_size", "value": "undersized"}],
                "user_hypotheses": ["suspected regulator"],
            }

    extractor_with_llm = SymptomExtractor(llm_service=MockLLM())
    result = extractor_with_llm.extract("Unusual colloquial problem with fluid deposition.")
    assert len(result.observations) == 1
    assert result.observations[0].value == "undersized"
    assert result.extraction_method == "llm"
    assert "suspected regulator" in result.user_hypotheses
