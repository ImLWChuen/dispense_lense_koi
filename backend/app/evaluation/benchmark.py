"""
Dispense Lens - Diagnostic Evaluation Benchmark Runner (Phase 15)

Runs the controlled evaluation scenarios through the DiagnosticEngine,
computes all 8 evaluation metrics defined in Section 22 of the implementation plan:
1. Defect Classification Accuracy
2. Top-1 Cause Accuracy
3. Top-3 Cause Coverage
4. Average Number of Questions
5. Evidence Traceability Rate
6. Contradiction Handling Pass Rate
7. Duplicate Evidence Pass Rate
8. Model Failure Resilience Rate
"""

from __future__ import annotations

import logging
from typing import Any

from app.evaluation.metrics import (
    MetricSummary,
    calculate_average_questions,
    calculate_defect_accuracy,
    calculate_evidence_traceability,
    calculate_top1_accuracy,
    calculate_top3_coverage,
    evaluate_contradiction_handling,
    evaluate_duplicate_handling,
    evaluate_model_failure_handling,
)
from app.evaluation.scenarios import SCENARIOS, EvaluationScenario
from app.schemas.diagnosis import (
    DiagnosisRequest,
    Observation,
    ObservationType,
)
from app.services.diagnosis.engine import DiagnosticEngine

logger = logging.getLogger(__name__)


class BenchmarkRunner:
    """Executes evaluation scenarios against DiagnosticEngine."""

    def __init__(self, engine: DiagnosticEngine | None = None) -> None:
        self.engine = engine or DiagnosticEngine()

    def run_scenario(self, scenario: EvaluationScenario) -> dict[str, Any]:
        """Run a single evaluation scenario and collect metrics."""
        obs_list: list[Observation] = []
        for o in scenario.initial_observations:
            obs_type = None
            for ot in ObservationType:
                if ot.value == o.get("type"):
                    obs_type = ot
                    break
            if obs_type:
                obs_list.append(
                    Observation(
                        observation_type=obs_type,
                        value=str(o.get("value", "")),
                    )
                )

        request = DiagnosisRequest(
            description=scenario.description,
            observations=obs_list,
        )

        result = self.engine.diagnose(request)

        top_cause_id = result.ranked_causes[0].cause_id if result.ranked_causes else None
        top_3_ids = [c.cause_id for c in result.ranked_causes[:3]]

        # Evidence traceability verification:
        # Every ranked cause must have traceable evidence with recorded provenance and explanation
        traceability_checks: list[dict[str, Any]] = []
        for cause in result.ranked_causes:
            for ev in cause.supporting_evidence + cause.contradicting_evidence:
                is_traceable = bool(ev.source and ev.explanation and ev.observation_id)
                traceability_checks.append({
                    "cause_id": cause.cause_id,
                    "relation": ev.relation.value if hasattr(ev.relation, "value") else str(ev.relation),
                    "source": ev.source.value if hasattr(ev.source, "value") else str(ev.source),
                    "is_traceable": is_traceable,
                })

        return {
            "scenario_id": scenario.id,
            "scenario_name": scenario.name,
            "expected_defect": scenario.expected_defect,
            "identified_defect": result.defect,
            "expected_top_causes": scenario.expected_top_causes,
            "acceptable_causes": scenario.acceptable_causes,
            "top_cause_id": top_cause_id,
            "top_3_cause_ids": top_3_ids,
            "questions_asked_count": 1 if result.next_question else 0,
            "traceability_checks": traceability_checks,
            "explanation": result.explanation,
        }

    def run_all(self, scenarios: list[EvaluationScenario] | None = None) -> MetricSummary:
        """Run all evaluation scenarios and compute aggregate metrics for all 8 criteria."""
        target_scenarios = scenarios or SCENARIOS
        results = [self.run_scenario(s) for s in target_scenarios]

        # Metric 1: Defect Accuracy
        defect_acc = calculate_defect_accuracy(results)

        # Metric 2: Top-1 Accuracy
        top1_acc = calculate_top1_accuracy(results)

        # Metric 3: Top-3 Coverage
        top3_cov = calculate_top3_coverage(results)

        # Metric 4: Average Questions Asked
        avg_q = calculate_average_questions(results)

        # Metric 5: Evidence Traceability Rate
        traceability_rate = calculate_evidence_traceability(results)

        # Metric 6: Contradiction Handling
        contra_result = evaluate_contradiction_handling(self.engine)
        contra_pass_rate = 100.0 if contra_result.get("pass") else 0.0

        # Metric 7: Duplicate Evidence Handling
        dup_result = evaluate_duplicate_handling(self.engine)
        dup_pass_rate = 100.0 if dup_result.get("pass") else 0.0

        # Metric 8: Model Failure Handling
        failure_result = evaluate_model_failure_handling(self.engine)
        failure_pass_rate = 100.0 if failure_result.get("pass") else 0.0

        summary = MetricSummary(
            total_scenarios=len(results),
            defect_classification_accuracy=defect_acc,
            top_1_cause_accuracy=top1_acc,
            top_3_cause_coverage=top3_cov,
            average_questions_asked=avg_q,
            evidence_traceability_rate=traceability_rate,
            contradiction_handling_pass_rate=contra_pass_rate,
            duplicate_evidence_pass_rate=dup_pass_rate,
            model_failure_resilience_rate=failure_pass_rate,
            details={
                "individual_results": results,
                "contradiction_evaluation": contra_result,
                "duplicate_evaluation": dup_result,
                "model_failure_evaluation": failure_result,
            },
        )
        return summary


def run_benchmark() -> MetricSummary:
    """Convenience entry point for running the evaluation benchmark."""
    runner = BenchmarkRunner()
    return runner.run_all()


if __name__ == "__main__":
    summary = run_benchmark()
    print("=" * 65)
    print("Dispense Lens Diagnostic Evaluation Benchmark Results (Phase 15)")
    print("=" * 65)
    print(f"Total Scenarios Evaluated:      {summary.total_scenarios}")
    print(f"Metric 1 - Defect Accuracy:      {summary.defect_classification_accuracy:.1f}%")
    print(f"Metric 2 - Top-1 Cause Accuracy: {summary.top_1_cause_accuracy:.1f}%")
    print(f"Metric 3 - Top-3 Cause Coverage: {summary.top_3_cause_coverage:.1f}%")
    print(f"Metric 4 - Avg Questions Asked:  {summary.average_questions_asked:.2f}")
    print(f"Metric 5 - Traceability Rate:    {summary.evidence_traceability_rate:.1f}%")
    print(f"Metric 6 - Contradiction Pass:   {summary.contradiction_handling_pass_rate:.1f}%")
    print(f"Metric 7 - Duplicate Pass:       {summary.duplicate_evidence_pass_rate:.1f}%")
    print(f"Metric 8 - Failure Resilience:   {summary.model_failure_resilience_rate:.1f}%")
    print("=" * 65)
