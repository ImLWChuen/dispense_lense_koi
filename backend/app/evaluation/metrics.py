"""
DispenseIQ — Evaluation Metrics (Phase 15 Placeholder)

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
