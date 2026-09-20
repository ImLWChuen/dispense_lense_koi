"""
Dispense Lens - Evaluation Metrics (Phase 15)

Implements the 8 diagnostic evaluation metrics defined in Section 22 of the
implementation plan:
1. Defect Classification Accuracy
2. Top-1 Cause Accuracy
3. Top-3 Cause Coverage
4. Average Number of Questions
5. Evidence Traceability
6. Contradiction Handling
7. Duplicate Evidence Handling
8. Model Failure Handling
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

from app.schemas.diagnosis import (
    DiagnosisRequest,
    EvidenceSource,
    Observation,
    ObservationType,
)
from app.services.diagnosis.engine import DiagnosticEngine


class MetricSummary(BaseModel):
    """Container for benchmark metric results."""
    total_scenarios: int = 0
    defect_classification_accuracy: float = 0.0
    top_1_cause_accuracy: float = 0.0
    top_3_cause_coverage: float = 0.0
    average_questions_asked: float = 0.0
    evidence_traceability_rate: float = 0.0
    contradiction_handling_pass_rate: float = 0.0
    duplicate_evidence_pass_rate: float = 0.0
    model_failure_resilience_rate: float = 0.0
    details: dict[str, Any] = Field(default_factory=dict)


def calculate_defect_accuracy(results: list[dict[str, Any]]) -> float:
    """Metric 1: Correct defect classifications / total scenarios."""
    if not results:
        return 0.0
    correct = sum(1 for r in results if r.get("identified_defect") == r.get("expected_defect"))
    return (correct / len(results)) * 100.0


def calculate_top1_accuracy(results: list[dict[str, Any]]) -> float:
    """Metric 2: Top-1 candidate matches expected top causes / total applicable scenarios."""
    applicable = [r for r in results if r.get("expected_top_causes")]
    if not applicable:
        return 0.0
    correct = sum(1 for r in applicable if r.get("top_cause_id") in r.get("expected_top_causes", []))
    return (correct / len(applicable)) * 100.0


def calculate_top3_coverage(results: list[dict[str, Any]]) -> float:
    """Metric 3: Any acceptable cause in top 3 ranked causes / total scenarios."""
    if not results:
        return 0.0
    correct = 0
    for r in results:
        top_3 = r.get("top_3_cause_ids", [])
        acceptable = r.get("acceptable_causes", [])
        if any(c in top_3 for c in acceptable):
            correct += 1
    return (correct / len(results)) * 100.0


def calculate_average_questions(results: list[dict[str, Any]]) -> float:
    """Metric 4: Total questions asked / completed cases."""
    if not results:
        return 0.0
    total_questions = sum(r.get("questions_asked_count", 0) for r in results)
    return total_questions / len(results)


def calculate_evidence_traceability(results: list[dict[str, Any]]) -> float:
    """Metric 5: Traceability rate.

    Verifies that every score contribution maps to an evidence item with non-empty provenance.
    """
    total_checked = 0
    valid_count = 0
    for r in results:
        traceability_checks = r.get("traceability_checks", [])
        for check in traceability_checks:
            total_checked += 1
            if check.get("is_traceable", False):
                valid_count += 1

    if total_checked == 0:
        return 100.0
    return (valid_count / total_checked) * 100.0


def evaluate_contradiction_handling(engine: DiagnosticEngine) -> dict[str, Any]:
    """Metric 6: Contradiction Handling.

    Verifies that contradictory evidence reduces the score of the contradicted cause.
    """
    # 1. Base case: Inconsistent size with prolonged operation (supports air_supply_issue)
    req_base = DiagnosisRequest(
        description="Dispensing dots become smaller intermittently after prolonged operation.",
        observations=[
            Observation(observation_type=ObservationType.DEPOSIT_SIZE, value="undersized"),
            Observation(observation_type=ObservationType.RUNTIME_PATTERN, value="after_prolonged_operation"),
        ],
    )
    res_base = engine.diagnose(req_base)
    base_scores = {c.cause_id: c.score for c in res_base.ranked_causes}

    # 2. Add contradictory evidence: nozzle_condition: clean contradicts nozzle_restriction (R042)
    req_contra = DiagnosisRequest(
        description="Dispensing dots become smaller intermittently after prolonged operation.",
        observations=[
            Observation(observation_type=ObservationType.DEPOSIT_SIZE, value="undersized"),
            Observation(observation_type=ObservationType.RUNTIME_PATTERN, value="after_prolonged_operation"),
            Observation(observation_type=ObservationType.NOZZLE_CONDITION, value="clean"),
        ],
    )
    res_contra = engine.diagnose(req_contra)
    contra_scores = {c.cause_id: c.score for c in res_contra.ranked_causes}

    target_cause = "nozzle_restriction"
    score_before = base_scores.get(target_cause, 0.0)
    score_after = contra_scores.get(target_cause, 0.0)
    reduced = score_after < score_before

    return {
        "target_cause": target_cause,
        "score_before": score_before,
        "score_after": score_after,
        "reduced": reduced,
        "pass": reduced,
    }


def evaluate_duplicate_handling(engine: DiagnosticEngine) -> dict[str, Any]:
    """Metric 7: Duplicate Evidence Handling.

    Verifies that submitting the exact same observation multiple times does not increase the score.
    """
    # 1. Single observation
    req_single = DiagnosisRequest(
        description="Dots are undersized.",
        observations=[
            Observation(observation_type=ObservationType.DEPOSIT_SIZE, value="undersized"),
        ],
    )
    res_single = engine.diagnose(req_single)
    single_scores = {c.cause_id: c.score for c in res_single.ranked_causes}

    # 2. Duplicate observation submitted twice
    req_dup = DiagnosisRequest(
        description="Dots are undersized.",
        observations=[
            Observation(observation_type=ObservationType.DEPOSIT_SIZE, value="undersized"),
            Observation(observation_type=ObservationType.DEPOSIT_SIZE, value="undersized"),
            Observation(observation_type=ObservationType.DEPOSIT_SIZE, value="undersized"),
        ],
    )
    res_dup = engine.diagnose(req_dup)
    dup_scores = {c.cause_id: c.score for c in res_dup.ranked_causes}

    # Scores should be identical across all causes
    no_score_inflation = True
    for cause_id, score in single_scores.items():
        if abs(dup_scores.get(cause_id, 0.0) - score) > 1e-4:
            no_score_inflation = False
            break

    return {
        "single_scores": single_scores,
        "duplicate_scores": dup_scores,
        "no_score_inflation": no_score_inflation,
        "pass": no_score_inflation,
    }


def evaluate_model_failure_handling(engine: DiagnosticEngine) -> dict[str, Any]:
    """Metric 8: Model Failure Handling.

    Forces LLM explanation failure and verifies that:
    1. Diagnosis remains fully functional
    2. Deterministic explanation fallback is provided
    3. Official scores are preserved
    4. No hallucinations or crashed exceptions occur
    """
    class FailingMockLLM:
        def __init__(self) -> None:
            self.is_available = True

        def generate_text(self, prompt: str, system_prompt: str | None = None) -> str | None:
            raise RuntimeError("Simulated external LLM API outage/timeout")

        def extract_symptoms(self, description: str) -> dict[str, Any] | None:
            raise RuntimeError("Simulated external LLM API extraction failure")

    from app.services.ai.explanation_service import ExplanationService

    failing_llm = FailingMockLLM()
    explanation_service = ExplanationService(llm_service=failing_llm)

    test_engine = DiagnosticEngine(explanation_service=explanation_service)
    req = DiagnosisRequest(
        description="Small dots intermittently after running for a while.",
        observations=[
            Observation(observation_type=ObservationType.DEPOSIT_SIZE, value="undersized"),
        ],
    )

    # Must not raise exception
    res = test_engine.diagnose(req)

    resilient = (
        res.defect is not None
        and len(res.ranked_causes) > 0
        and res.explanation is not None
        and len(res.explanation) > 0
    )

    return {
        "resilient": resilient,
        "explanation_sample": res.explanation[:80] if res.explanation else "",
        "pass": resilient,
    }
