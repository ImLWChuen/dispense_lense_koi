"""
DispenseIQ — Phases 6–8 Verification Test

Verifies:
  1. Cause Ranker produces ranked causes with score explanations
  2. Question Engine selects discriminating questions with stopping conditions
  3. Action Planner selects relevant checks, respects effort and prior attempts
  4. Full pipeline integration from description → action
"""

import sys
import os

# Ensure UTF-8 output on Windows terminals
if sys.platform == "win32":
    reconfigure_fn = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure_fn):
        try:
            reconfigure_fn(encoding="utf-8", errors="replace")
        except Exception:
            pass

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from backend.app.services.diagnosis.symptom_extractor import SymptomExtractor
from backend.app.services.diagnosis.defect_identifier import identify_defect
from backend.app.services.diagnosis.cause_ranker import CauseRanker, RankingResult
from backend.app.services.diagnosis.question_engine import QuestionEngine
from backend.app.services.diagnosis.action_planner import ActionPlanner
from backend.app.schemas.diagnosis import (
    Observation,
    Question,
    QuestionAnswer,
    TroubleshootingCheck,
    CheckResult,
    CheckExecutionStatus,
    CheckFinding,
)


def separator(title: str) -> None:
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


# ===================================================================
# Test 1: Cause Ranker
# ===================================================================

def _verify_cause_ranker() -> tuple[RankingResult, list[Observation], str]:
    separator("PHASE 6: Cause Ranker")

    # Setup: extract symptoms and identify defect
    extractor = SymptomExtractor()
    result = extractor.extract(
        "The dispensing dots become smaller after the machine "
        "has been running for around 20 minutes."
    )
    defect = identify_defect(result.observations)
    assert defect is not None, "Should identify a defect"

    # Rank causes
    ranker = CauseRanker()
    ranking = ranker.rank(result.observations, defect.code)

    print(f"Defect: {defect.code}")
    print(f"Ranked {len(ranking.ranked_causes)} causes:\n")

    for c in ranking.ranked_causes:
        print(f"  {c.cause_name:<30s}  Evidence Support: {c.score:.0f}/100")
        assert 0.0 <= c.score <= 100.0, f"Score for {c.cause_name} ({c.score}) must be at most 100"

    # Verify top cause has explanation
    top = ranking.top_cause
    assert top is not None, "Should have a top cause"
    explanation = ranking.get_cause_explanation(top.cause_id)
    assert "score_label" in explanation, "Explanation should include score_label"
    print(f"\n  Top cause explanation:")
    print(f"    {explanation['score_label']}")
    print(f"    Supporting: {len(explanation['supporting_evidence'])} items")
    print(f"    Contradicting: {len(explanation['contradicting_evidence'])} items")
    print(f"    Missing: {len(explanation['missing_evidence'])} items")

    # Verify high-confidence detection
    print(f"\n  High confidence causes: {len(ranking.high_confidence_causes)}")
    print(f"  Has sufficient evidence: {ranking.has_sufficient_evidence}")

    print("\n✓ Cause ranker passed")
    return ranking, result.observations, defect.code


# ===================================================================
# Test 2: Cause Ranker Re-ranking
# ===================================================================

def _verify_reranking(
    ranker: CauseRanker,
    observations: list[Observation],
    defect_code: str,
) -> None:
    separator("PHASE 6b: Re-ranking with Revision")

    # First ranking
    result1, revision1 = ranker.rerank(observations, defect_code)
    print(f"Revision {revision1.revision_number}: {len(result1.ranked_causes)} causes")
    for c in result1.ranked_causes:
        print(f"  {c.cause_name:<30s}  {c.score:.0f}")

    # Simulate: same observations (should produce same scores)
    result2, revision2 = ranker.rerank(observations, defect_code, revision1)
    print(f"\nRevision {revision2.revision_number}: {len(result2.ranked_causes)} causes")
    for c in result2.ranked_causes:
        print(f"  {c.cause_name:<30s}  {c.score:.0f}")

    assert revision2.revision_number == 2, "Should be revision 2"
    print(f"\n  Changes from previous: {revision2.changes_from_previous}")

    print("\n✓ Re-ranking passed")


# ===================================================================
# Test 3: Question Engine
# ===================================================================

def _verify_question_engine(ranking: RankingResult) -> Question:
    separator("PHASE 7: Question Engine")

    engine = QuestionEngine()

    # Select first question (no previous answers)
    result = engine.select_next_question(
        ranked_causes=ranking.ranked_causes,
        previous_answers=[],
        defect_code=ranking.defect_code,
    )

    assert result.selected_question is not None, "Should select a question"
    q = result.selected_question
    print(f"Selected: {q.question_id}")
    print(f"Text:     {q.text}")
    print(f"Purpose:  {q.purpose}")
    print(f"Score:    {q.usefulness_score:.1f}")
    print(f"Targets:  {q.target_causes}")
    print(f"\nAll candidates: {len(result.all_candidates)}")

    # Verify the selected question targets at least one ranked cause
    ranked_ids = {c.cause_id for c in ranking.ranked_causes}
    targets_overlap = set(q.target_causes) & ranked_ids
    assert len(targets_overlap) > 0, "Selected question should target ranked causes"
    print(f"  Overlapping causes: {targets_overlap}")

    print("\n✓ Question engine passed")
    return q


# ===================================================================
# Test 4: Question Engine — Already Answered Penalty
# ===================================================================

def _verify_question_already_answered(
    ranking: RankingResult,
    first_question: Question,
) -> None:
    separator("PHASE 7b: Already-Answered Penalty")

    engine = QuestionEngine()

    # Simulate answering the first question
    answer = QuestionAnswer(
        question_id=first_question.question_id,
        answer_value="YES",
    )

    result = engine.select_next_question(
        ranked_causes=ranking.ranked_causes,
        previous_answers=[answer],
        defect_code=ranking.defect_code,
    )

    if result.selected_question is not None:
        assert result.selected_question.question_id != first_question.question_id, \
            "Should NOT re-select the already-answered question"
        print(f"Selected: {result.selected_question.question_id} (different from {first_question.question_id})")
        print(f"Score:    {result.selected_question.usefulness_score:.1f}")
    else:
        print(f"Stopped: {result.reason_stopped}")

    print("\n✓ Already-answered penalty passed")


# ===================================================================
# Test 5: Question Engine — Stopping Condition
# ===================================================================

def _verify_question_stopping() -> None:
    separator("PHASE 7c: Stopping Condition")

    engine = QuestionEngine()

    # Create a mock high-confidence cause
    from backend.app.schemas.diagnosis import CandidateCause, CauseConclusion
    high_cause = CandidateCause(
        cause_id="air_supply_issue",
        cause_name="Air / Supply Issue",
        score=80.0,  # Above high_confidence_threshold (75)
        conclusion=CauseConclusion.SUSPECTED,
    )

    result = engine.select_next_question(
        ranked_causes=[high_cause],
        previous_answers=[],
    )

    assert not result.should_ask, "Should stop when high-confidence cause exists"
    print(f"Stopped: {result.reason_stopped}")

    print("\n✓ Stopping condition passed")


# ===================================================================
# Test 6: Action Planner
# ===================================================================

def _verify_action_planner(ranking: RankingResult) -> TroubleshootingCheck:
    separator("PHASE 8: Action Planner")

    planner = ActionPlanner()

    result = planner.select_next_action(
        ranked_causes=ranking.ranked_causes,
        previous_check_results=[],
        defect_code=ranking.defect_code,
    )

    assert result.selected_check is not None, "Should select a check"
    check = result.selected_check
    print(f"Selected: {check.check_id} — {check.name}")
    print(f"Priority: {check.priority_score:.1f}")
    print(f"Effort:   {check.effort_level}")
    print(f"Targets:  {check.target_causes}")
    print(f"Reason:   {check.reasoning}")
    print(f"\nAll candidates: {len(result.all_candidates)}")

    for c in result.all_candidates:
        marker = "→" if c.check_id == check.check_id else " "
        print(f"  {marker} {c.name:<35s}  Priority: {c.priority_score:.1f}  Effort: {c.effort_level}")

    print("\n✓ Action planner passed")
    return check


# ===================================================================
# Test 7: Action Planner — Already Attempted
# ===================================================================

def _verify_action_already_attempted(
    ranking: RankingResult,
    first_check: TroubleshootingCheck,
) -> None:
    separator("PHASE 8b: Already-Attempted Penalty")

    planner = ActionPlanner()

    # Simulate completing the first check
    check_result = CheckResult(
        check_id=first_check.check_id,
        execution_status=CheckExecutionStatus.COMPLETED,
        finding=CheckFinding.SUPPORTS,
        finding_details="Found blockage in nozzle.",
    )

    result = planner.select_next_action(
        ranked_causes=ranking.ranked_causes,
        previous_check_results=[check_result],
        defect_code=ranking.defect_code,
    )

    if result.selected_check is not None:
        assert result.selected_check.check_id != first_check.check_id, \
            "Should NOT re-select the already-attempted check"
        print(f"Selected: {result.selected_check.check_id} — {result.selected_check.name}")
        print(f"(Different from {first_check.check_id})")
    else:
        print(f"Stopped: {result.reason}")

    print("\n✓ Already-attempted penalty passed")


# ===================================================================
# Test 8: Full Pipeline Integration
# ===================================================================

def _verify_full_pipeline() -> None:
    separator("FULL PIPELINE INTEGRATION")

    description = "The dispensing dots become smaller after the machine has been running for around 20 minutes."

    # Phase 3: Extract symptoms
    extractor = SymptomExtractor()
    extraction = extractor.extract(description)
    print(f"1. Extracted {len(extraction.observations)} observations")

    # Phase 4: Identify defect
    defect = identify_defect(extraction.observations)
    assert defect is not None
    print(f"2. Defect: {defect.code} ({defect.name})")

    # Phase 6: Rank causes
    ranker = CauseRanker()
    ranking = ranker.rank(extraction.observations, defect.code)
    top_cause = ranking.top_cause
    assert top_cause is not None, "Should have top cause"
    print(f"3. Ranked {len(ranking.ranked_causes)} causes (top: {top_cause.cause_name} = {top_cause.score:.0f})")

    # Phase 7: Select question
    q_engine = QuestionEngine()
    q_result = q_engine.select_next_question(
        ranking.ranked_causes, [], defect.code
    )
    if q_result.selected_question is not None:
        print(f"4. Next question: {q_result.selected_question.question_id} — {q_result.selected_question.text[:60]}...")
    else:
        print(f"4. No question needed: {q_result.reason_stopped}")

    # Phase 8: Select action
    a_planner = ActionPlanner()
    a_result = a_planner.select_next_action(
        ranking.ranked_causes, [], defect.code
    )
    if a_result.selected_check is not None:
        print(f"5. Next check: {a_result.selected_check.check_id} — {a_result.selected_check.name}")
    else:
        print(f"5. No check needed: {a_result.reason}")

    print("\n✓ Full pipeline integration passed")


# ===================================================================
# Pytest entry point and script runner
# ===================================================================

def test_phases_6_through_8() -> None:
    """Run the ordered verification flow as one pytest test."""
    ranking, observations, defect_code = _verify_cause_ranker()

    ranker = CauseRanker()
    _verify_reranking(ranker, observations, defect_code)

    first_question = _verify_question_engine(ranking)
    _verify_question_already_answered(ranking, first_question)
    _verify_question_stopping()

    first_check = _verify_action_planner(ranking)
    _verify_action_already_attempted(ranking, first_check)

    _verify_full_pipeline()


if __name__ == "__main__":
    test_phases_6_through_8()

    separator("ALL PHASES 6–8 TESTS PASSED")
    print("Cause ranker, question engine, and action planner are working correctly.\n")
