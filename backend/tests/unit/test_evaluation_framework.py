"""
DispenseIQ — Evaluation Framework Unit Tests (Phase 15)

Verifies:
1. All 12 evaluation scenarios exist and cover all 6 defects (2 each)
2. All 8 evaluation metric formulas produce valid percentages and metrics
3. BenchmarkRunner executes successfully without exceptions
"""

from __future__ import annotations

import pytest

from app.evaluation.benchmark import BenchmarkRunner, run_benchmark
from app.evaluation.metrics import (
    calculate_average_questions,
    calculate_defect_accuracy,
    calculate_evidence_traceability,
    calculate_top1_accuracy,
    calculate_top3_coverage,
    evaluate_contradiction_handling,
    evaluate_duplicate_handling,
    evaluate_model_failure_handling,
)
from app.evaluation.scenarios import SCENARIOS
from app.services.diagnosis.engine import DiagnosticEngine


def test_12_scenarios_exist_and_cover_all_defects() -> None:
    """Ensure at least 12 scenarios are defined with 2 scenarios per defect."""
    assert len(SCENARIOS) >= 12

    defect_counts: dict[str, int] = {}
    for s in SCENARIOS:
        defect_counts[s.expected_defect] = defect_counts.get(s.expected_defect, 0) + 1

    mandatory_defects = [
        "D01_TOO_LITTLE",
        "D02_TOO_MUCH",
        "D03_INCONSISTENT_SIZE",
        "D04_MISSING_DOTS",
        "D05_SPREADING",
        "D06_BUBBLES_ABNORMAL_SHAPE",
    ]

    for d in mandatory_defects:
        assert d in defect_counts, f"Defect {d} missing from evaluation scenarios"
        assert defect_counts[d] >= 2, f"Defect {d} has fewer than 2 scenarios"


def test_metric_calculations_with_synthetic_results() -> None:
    """Verify calculation functions for accuracy, coverage, and questions."""
    synthetic = [
        {
            "identified_defect": "D01_TOO_LITTLE",
            "expected_defect": "D01_TOO_LITTLE",
            "top_cause_id": "nozzle_restriction",
            "expected_top_causes": ["nozzle_restriction"],
            "top_3_cause_ids": ["nozzle_restriction", "air_supply_issue"],
            "acceptable_causes": ["nozzle_restriction"],
            "questions_asked_count": 1,
            "traceability_checks": [{"is_traceable": True}],
        },
        {
            "identified_defect": "D02_TOO_MUCH",
            "expected_defect": "D02_TOO_MUCH",
            "top_cause_id": "parameter_issue",
            "expected_top_causes": ["parameter_issue"],
            "top_3_cause_ids": ["parameter_issue", "valve_issue"],
            "acceptable_causes": ["parameter_issue"],
            "questions_asked_count": 2,
            "traceability_checks": [{"is_traceable": True}],
        },
    ]

    defect_acc = calculate_defect_accuracy(synthetic)
    assert defect_acc == 100.0

    top1_acc = calculate_top1_accuracy(synthetic)
    assert top1_acc == 100.0

    top3_cov = calculate_top3_coverage(synthetic)
    assert top3_cov == 100.0

    avg_q = calculate_average_questions(synthetic)
    assert avg_q == 1.5

    trace_rate = calculate_evidence_traceability(synthetic)
    assert trace_rate == 100.0


def test_contradiction_handling_metric() -> None:
    """Verify contradiction handling test succeeds and drops score."""
    engine = DiagnosticEngine()
    result = evaluate_contradiction_handling(engine)
    assert result["pass"] is True
    assert result["reduced"] is True
    assert result["score_after"] < result["score_before"]


def test_duplicate_handling_metric() -> None:
    """Verify duplicate evidence handling test succeeds with no score inflation."""
    engine = DiagnosticEngine()
    result = evaluate_duplicate_handling(engine)
    assert result["pass"] is True
    assert result["no_score_inflation"] is True


def test_model_failure_handling_metric() -> None:
    """Verify model failure handling test succeeds with fallback explanation."""
    engine = DiagnosticEngine()
    result = evaluate_model_failure_handling(engine)
    assert result["pass"] is True
    assert result["resilient"] is True


def test_benchmark_runner_full_execution() -> None:
    """Verify complete benchmark runner executes all 8 metrics on 12 scenarios."""
    summary = run_benchmark()
    assert summary.total_scenarios == 12
    assert summary.defect_classification_accuracy >= 90.0
    assert summary.top_1_cause_accuracy >= 80.0
    assert summary.top_3_cause_coverage == 100.0
    assert summary.evidence_traceability_rate == 100.0
    assert summary.contradiction_handling_pass_rate == 100.0
    assert summary.duplicate_evidence_pass_rate == 100.0
    assert summary.model_failure_resilience_rate == 100.0
