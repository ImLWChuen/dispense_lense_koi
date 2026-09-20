"""
Dispense Lens - Phases 9–11 Verification Test

Verifies:
  1. Phase 9: Check Result Handling
     - Supports COMPLETED, BLOCKED, UNKNOWN, FAILED, NOT_APPLICABLE.
     - Separately records finding: SUPPORTS, CONTRADICTS, INCONCLUSIVE, UNKNOWN.
     - BLOCKED checks MUST remain UNKNOWN; never translated into "No nozzle blockage".
     - COMPLETED checks properly map to evidence.
  2. Phase 10: Re-ranking After New Evidence
     - Prior revisions are preserved in history (Revision 1 -> Revision 2 -> ...).
     - Recalculates evidence with new observations.
     - Detects and explains changes between revisions.
     - Multi-step investigation history remains complete and auditable.
  3. Phase 11: State Management
     - Keeps the four state dimensions strictly separate:
       1. Step Execution
       2. Step Finding
       3. Cause Conclusion
       4. Issue Condition
     - Completing a check NEVER automatically confirms a cause.
     - Completing a check NEVER automatically resolves the dispensing issue.
     - Resolving an issue strictly requires independent verification.
  4. DiagnosticEngine End-to-End Orchestration
"""

import os
import sys

# Ensure UTF-8 output on Windows terminals
if sys.platform == "win32":
    reconfigure_fn = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure_fn):
        try:
            reconfigure_fn(encoding="utf-8", errors="replace")
        except Exception:
            pass

from app.schemas.diagnosis import (
    CauseConclusion,
    CheckExecutionStatus,
    CheckFinding,
    CheckResult,
    DiagnosisRequest,
    IssueCondition,
    Observation,
    ObservationType,
    QuestionAnswer,
    StructuredCase,
)
from app.services.diagnosis.engine import (
    CheckResultHandler,
    DiagnosticEngine,
    QuestionAnswerHandler,
    StateManager,
)


def separator(title: str) -> None:
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


# ===================================================================
# Test 1: Phase 9 - Check Result Handling: All Statuses & Findings
# ===================================================================

def test_phase_9_statuses_and_findings() -> None:
    separator("PHASE 9: Check Result Statuses & Findings Support")

    # Verify technician can submit all execution statuses
    all_statuses = [
        CheckExecutionStatus.COMPLETED,
        CheckExecutionStatus.BLOCKED,
        CheckExecutionStatus.UNKNOWN,
        CheckExecutionStatus.FAILED,
        CheckExecutionStatus.NOT_APPLICABLE,
        CheckExecutionStatus.SKIPPED,
    ]

    all_findings = [
        CheckFinding.SUPPORTS,
        CheckFinding.CONTRADICTS,
        CheckFinding.INCONCLUSIVE,
        CheckFinding.UNKNOWN,
        CheckFinding.NOT_APPLICABLE,
    ]

    for status in all_statuses:
        for finding in all_findings:
            cr = CheckResult(
                check_id="ACT01",
                execution_status=status,
                finding=finding,
                finding_details=f"Testing {status.value} with {finding.value}",
            )
            assert cr.execution_status == status
            assert cr.finding == finding

    print(f"✓ All {len(all_statuses)} execution statuses supported:")
    for s in all_statuses:
        print(f"  • {s.value}")

    print(f"\n✓ All {len(all_findings)} finding values supported:")
    for f in all_findings:
        print(f"  • {f.value}")

    print("\n✓ Phase 9 status and finding types passed")


# ===================================================================
# Test 2: Phase 9 - Blocked Checks MUST Remain UNKNOWN
# ===================================================================

def test_phase_9_blocked_checks_remain_unknown() -> None:
    separator("PHASE 9: Blocked Checks Rule Enforcement")

    engine = DiagnosticEngine()

    # Create initial case
    case = StructuredCase(
        description="Dispensing dots become smaller after 20 minutes.",
        observations=[
            Observation(observation_type=ObservationType.DEPOSIT_SIZE, value="undersized"),
            Observation(observation_type=ObservationType.RUNTIME_PATTERN, value="after_prolonged_operation"),
        ],
    )

    # Initial diagnosis
    initial_res = engine.diagnose(case)
    nozzle_cause_initial = next(c for c in initial_res.ranked_causes if c.cause_id == "nozzle_restriction")
    initial_score = nozzle_cause_initial.score
    print(f"Initial Nozzle Restriction score: {initial_score:.0f}/100")

    # Technician attempts check ACT01 (Inspect Nozzle), but it is BLOCKED
    blocked_check = CheckResult(
        check_id="ACT01",
        execution_status=CheckExecutionStatus.BLOCKED,
        finding=CheckFinding.UNKNOWN,
        finding_details="Cannot access nozzle: safety enclosure locked by operator.",
    )

    # Process check result
    new_obs, summary = CheckResultHandler.handle(blocked_check)

    # ASSERTION 1: Blocked check must produce ZERO observations
    assert len(new_obs) == 0, "Blocked checks must NOT produce observations"

    # ASSERTION 2: Finding must remain UNKNOWN
    assert blocked_check.finding == CheckFinding.UNKNOWN, "Blocked check finding must be UNKNOWN"

    # ASSERTION 3: Summary must never claim nozzle is not blocked
    assert "no blockage" not in summary.lower(), "Must NOT claim 'No nozzle blockage'"
    print(f"Handler summary: {summary}")

    # Submit blocked check to engine
    updated_case, res_after_blocked = engine.submit_check_result(case, blocked_check)

    # ASSERTION 4: Nozzle restriction score must NOT drop or change
    nozzle_after_blocked = next(c for c in res_after_blocked.ranked_causes if c.cause_id == "nozzle_restriction")
    assert nozzle_after_blocked.score == initial_score, (
        f"Blocked check must NOT alter cause score! Expected {initial_score}, got {nozzle_after_blocked.score}"
    )
    print(f"Nozzle Restriction score after BLOCKED check: {nozzle_after_blocked.score:.0f}/100 (UNCHANGED)")

    # ASSERTION 5: Blocked check is recorded in case history
    assert len(updated_case.previous_check_results) == 1
    assert updated_case.previous_check_results[0].execution_status == CheckExecutionStatus.BLOCKED

    # ASSERTION 6: ActionPlanner recognizes ACT01 was attempted/blocked and does not re-select it
    if res_after_blocked.next_check:
        assert res_after_blocked.next_check.check_id != "ACT01", (
            "ActionPlanner should not re-select blocked check ACT01"
        )
        print(f"Next recommended check after blocked ACT01: {res_after_blocked.next_check.check_id} - {res_after_blocked.next_check.name}")

    print("\n✓ Phase 9 blocked checks rule passed")


# ===================================================================
# Test 3: Phase 9 - Completed Check Finding Affects Evidence
# ===================================================================

def test_phase_9_completed_check_finding() -> None:
    separator("PHASE 9: Completed Check Result Evaluation")

    engine = DiagnosticEngine()

    case = StructuredCase(
        description="Dispensing dots become smaller after 20 minutes.",
        observations=[
            Observation(observation_type=ObservationType.DEPOSIT_SIZE, value="undersized"),
            Observation(observation_type=ObservationType.RUNTIME_PATTERN, value="after_prolonged_operation"),
        ],
    )

    initial_res = engine.diagnose(case)
    nozzle_initial = next(c for c in initial_res.ranked_causes if c.cause_id == "nozzle_restriction")
    print(f"Initial Nozzle Restriction score: {nozzle_initial.score:.0f}/100")

    # Technician completes check ACT01 and finds NO BLOCKAGE (CONTRADICTS nozzle blockage)
    completed_check = CheckResult(
        check_id="ACT01",
        execution_status=CheckExecutionStatus.COMPLETED,
        finding=CheckFinding.CONTRADICTS,
        finding_details="No visible blockage.",
    )

    # Process check result
    new_obs, summary = CheckResultHandler.handle(completed_check)
    assert len(new_obs) > 0, "Completed check with finding must generate observation(s)"

    # Verify domain observation produced
    domain_obs = next((o for o in new_obs if str(o.observation_type) in (ObservationType.NOZZLE_CONDITION.value, "nozzle_condition")), None)
    assert domain_obs is not None, "Should generate nozzle_condition observation"
    assert domain_obs.value == "clean", f"Expected value 'clean', got '{domain_obs.value}'"
    obs_type_str = domain_obs.observation_type.value if hasattr(domain_obs.observation_type, "value") else domain_obs.observation_type
    print(f"Generated domain observation: {obs_type_str} = {domain_obs.value}")

    # Submit to engine
    updated_case, res_after = engine.submit_check_result(case, completed_check)
    nozzle_after = next(c for c in res_after.ranked_causes if c.cause_id == "nozzle_restriction")

    # Verify score dropped
    assert nozzle_after.score < nozzle_initial.score, (
        f"Nozzle Restriction score should drop after clean inspection! "
        f"Initial: {nozzle_initial.score}, After: {nozzle_after.score}"
    )
    print(f"Nozzle Restriction score after 'no visible blockage': {nozzle_after.score:.0f}/100 (DROPPED by {nozzle_initial.score - nozzle_after.score:.0f} pts)")

    # Verify contradicting evidence is recorded
    assert len(nozzle_after.contradicting_evidence) > 0, "Should have contradicting evidence recorded"

    print("\n✓ Phase 9 completed check evaluation passed")


# ===================================================================
# Test 4: Phase 10 - Re-ranking After New Evidence & Revision History
# ===================================================================

def test_phase_10_reranking_and_revisions() -> None:
    separator("PHASE 10: Re-ranking and Revision History Preservation")

    engine = DiagnosticEngine()

    case = StructuredCase(
        description="Dispensing dots become smaller after 20 minutes.",
        observations=[
            Observation(observation_type=ObservationType.DEPOSIT_SIZE, value="undersized"),
            Observation(observation_type=ObservationType.RUNTIME_PATTERN, value="after_prolonged_operation"),
        ],
    )

    # Revision 1
    res1 = engine.diagnose(case)
    assert len(case.analysis_revisions) == 1, "Should have 1 revision"
    rev1 = case.analysis_revisions[0]
    assert rev1.revision_number == 1

    print(f"Revision 1 ({len(rev1.ranked_causes)} causes):")
    for c in rev1.ranked_causes[:4]:
        print(f"  {c.cause_name:<30s}  {c.score:.0f}")

    # Technician completes check ACT01 (Inspect Nozzle) -> No visible blockage
    check_act01 = CheckResult(
        check_id="ACT01",
        execution_status=CheckExecutionStatus.COMPLETED,
        finding=CheckFinding.CONTRADICTS,
        finding_details="No visible blockage.",
    )

    # Submit check -> triggers Revision 2
    updated_case, res2 = engine.submit_check_result(case, check_act01)

    # ASSERTION 1: Prior Revision 1 is PRESERVED in case history
    assert len(updated_case.analysis_revisions) == 2, "Should preserve Revision 1 and have Revision 2"
    assert updated_case.analysis_revisions[0].revision_number == 1
    assert updated_case.analysis_revisions[1].revision_number == 2

    rev2 = updated_case.analysis_revisions[1]
    print(f"\nRevision 2 ({len(rev2.ranked_causes)} causes):")
    for c in rev2.ranked_causes[:4]:
        print(f"  {c.cause_name:<30s}  {c.score:.0f}")

    # ASSERTION 2: Nozzle restriction dropped in Revision 2
    r1_nozzle = next(c for c in rev1.ranked_causes if c.cause_id == "nozzle_restriction")
    r2_nozzle = next(c for c in rev2.ranked_causes if c.cause_id == "nozzle_restriction")
    assert r2_nozzle.score < r1_nozzle.score, "Nozzle Restriction should drop in Revision 2"

    # ASSERTION 3: Revision 2 documents changes from Revision 1
    assert len(rev2.changes_from_previous) > 0, "Revision 2 must list changes from Revision 1"
    print("\nChanges documented in Revision 2:")
    for change in rev2.changes_from_previous:
        print(f"  • {change}")

    # ASSERTION 4: Explanation in DiagnosisResult explains what changed
    assert "Nozzle Restriction" in res2.explanation
    print(f"\nEngine explanation:\n{res2.explanation}")

    print("\n✓ Phase 10 re-ranking and revision preservation passed")


# ===================================================================
# Test 5: Phase 10 - Multi-step Investigation
# ===================================================================

def test_phase_10_multistep_investigation() -> None:
    separator("PHASE 10: Multi-Step Investigation History")

    engine = DiagnosticEngine()

    case = StructuredCase(
        description="Dispensing dots become smaller after 20 minutes.",
        observations=[
            Observation(observation_type=ObservationType.DEPOSIT_SIZE, value="undersized"),
        ],
    )

    # Step 1: Initial diagnosis -> Rev 1
    engine.diagnose(case)
    assert len(case.analysis_revisions) == 1

    # Step 2: Answer question Q01 -> Rev 2
    ans_q01 = QuestionAnswer(
        question_id="Q01",
        answer_value="after_prolonged_operation",
        answer_text="Dots only become small after 20 minutes of operation.",
    )
    engine.submit_question_answer(case, ans_q01)
    assert len(case.analysis_revisions) == 2

    # Step 3: Run check ACT01 (nozzle clear) -> Rev 3
    chk_act01 = CheckResult(
        check_id="ACT01",
        execution_status=CheckExecutionStatus.COMPLETED,
        finding=CheckFinding.CONTRADICTS,
        finding_details="No visible blockage.",
    )
    engine.submit_check_result(case, chk_act01)
    assert len(case.analysis_revisions) == 3

    # Step 4: Run check ACT04 (pressure fluctuating) -> Rev 4
    chk_act04 = CheckResult(
        check_id="ACT04",
        execution_status=CheckExecutionStatus.COMPLETED,
        finding=CheckFinding.SUPPORTS,
        finding_details="Pressure fluctuating during operation.",
    )
    _, res4 = engine.submit_check_result(case, chk_act04)
    assert len(case.analysis_revisions) == 4

    print("Investigation Revisions:")
    for rev in case.analysis_revisions:
        top = rev.ranked_causes[0] if rev.ranked_causes else None
        top_str = f"{top.cause_name} ({top.score:.0f})" if top else "None"
        print(f"  Rev {rev.revision_number}: Top = {top_str:<32s} Summary = {rev.new_evidence_summary}")

    # Verify all revisions have distinct sequential numbers
    rev_numbers = [r.revision_number for r in case.analysis_revisions]
    assert rev_numbers == [1, 2, 3, 4], f"Expected revisions [1, 2, 3, 4], got {rev_numbers}"

    # Verify final result has top causes evaluated
    top_final = res4.ranked_causes[0]
    print(f"\nFinal leading hypothesis: {top_final.cause_name} ({top_final.score:.0f}/100)")

    print("\n✓ Phase 10 multi-step investigation history passed")


# ===================================================================
# Test 6: Phase 11 - State Management: 4 Separate Dimensions
# ===================================================================

def test_phase_11_four_state_dimensions() -> None:
    separator("PHASE 11: Independence of the Four State Dimensions")

    # Dimension 1: Step Execution
    execution = CheckExecutionStatus.COMPLETED

    # Dimension 2: Step Finding
    finding = CheckFinding.SUPPORTS

    # Dimension 3: Cause Conclusion
    cause_conclusion = CauseConclusion.SUSPECTED

    # Dimension 4: Issue Condition
    issue_condition = IssueCondition.UNRESOLVED

    # Validate legal combination
    is_valid, warnings = StateManager.validate_state_independence(
        execution_status=execution,
        finding=finding,
        cause_conclusion=cause_conclusion,
        issue_condition=issue_condition,
    )
    assert is_valid, "Legal state combination should be valid"
    assert len(warnings) == 0

    print("Verified independent state dimensions:")
    print(f"  1. Step Execution:  {execution.value}")
    print(f"  2. Step Finding:    {finding.value}")
    print(f"  3. Cause Conclusion:{cause_conclusion.value}")
    print(f"  4. Issue Condition: {issue_condition.value}")

    # TEST PROHIBITED BEHAVIOR:
    # "if check_completed: cause = 'confirmed', issue = 'resolved'"
    # Completing a check must NOT automatically resolve an issue!
    is_valid_bad, bad_warnings = StateManager.validate_state_independence(
        execution_status=CheckExecutionStatus.COMPLETED,
        finding=CheckFinding.SUPPORTS,
        cause_conclusion=CauseConclusion.CONFIRMED,
        issue_condition=IssueCondition.RESOLVED,  # PROHIBITED!
    )
    assert not is_valid_bad, "Should detect violation when check completion sets issue to RESOLVED"
    print(f"\nCorrectly caught prohibited state conflation:\n  ⚠ {bad_warnings[0]}")

    # Check that DiagnosticEngine maintains issue_condition as UNRESOLVED after check
    engine = DiagnosticEngine()
    case = StructuredCase(
        description="Dispensing dots become smaller.",
        observations=[Observation(observation_type=ObservationType.DEPOSIT_SIZE, value="undersized")],
        issue_condition=IssueCondition.UNRESOLVED,
    )

    check = CheckResult(
        check_id="ACT01",
        execution_status=CheckExecutionStatus.COMPLETED,
        finding=CheckFinding.SUPPORTS,
        finding_details="Heavy nozzle blockage found.",
    )

    updated_case, res = engine.submit_check_result(case, check)

    # Completing a check MUST NOT resolve the machine defect!
    assert updated_case.issue_condition == IssueCondition.UNRESOLVED, (
        "Completing a check MUST NOT resolve the dispensing issue!"
    )
    assert res.issue_condition == IssueCondition.UNRESOLVED, (
        "DiagnosisResult issue_condition must remain UNRESOLVED!"
    )
    print("\n✓ Completing check leaves IssueCondition as UNRESOLVED (not resolved)")

    print("\n✓ Phase 11 state independence passed")


# ===================================================================
# Test 7: Phase 11 - Issue Condition State Machine & Verification
# ===================================================================

def test_phase_11_issue_lifecycle_and_verification() -> None:
    separator("PHASE 11: Issue Condition Lifecycle & Verification")

    # 1. Legal transition: UNRESOLVED -> RECOVERY_PENDING_VERIFICATION
    cond1, msg1 = StateManager.transition_issue_condition(
        current_condition=IssueCondition.UNRESOLVED,
        target_condition=IssueCondition.RECOVERY_PENDING_VERIFICATION,
        verification_details="Replaced clogged nozzle with 0.25mm ceramic tip.",
    )
    assert cond1 == IssueCondition.RECOVERY_PENDING_VERIFICATION
    print(f"Step 1: {cond1.value} - {msg1}")

    # 2. Illegal transition: Trying to jump to RESOLVED without verification
    try:
        StateManager.transition_issue_condition(
            current_condition=IssueCondition.RECOVERY_PENDING_VERIFICATION,
            target_condition=IssueCondition.RESOLVED,
            verification_passed=False,  # NOT verified!
        )
        assert False, "Should have raised ValueError for unverified resolution"
    except ValueError as e:
        print(f"Step 2: Correctly blocked unverified resolution: {e}")

    # 3. Legal transition: RECOVERY_PENDING_VERIFICATION -> RESOLVED with verification
    cond3, msg3 = StateManager.transition_issue_condition(
        current_condition=IssueCondition.RECOVERY_PENDING_VERIFICATION,
        target_condition=IssueCondition.RESOLVED,
        verification_passed=True,
        verification_details="20 test shots performed; CV = 2.1%, all dot diameters within nominal spec.",
    )
    assert cond3 == IssueCondition.RESOLVED
    print(f"Step 3: {cond3.value} - {msg3}")

    # 4. Legal transition: RESOLVED -> RECURRED
    cond4, msg4 = StateManager.transition_issue_condition(
        current_condition=IssueCondition.RESOLVED,
        target_condition=IssueCondition.RECURRED,
        verification_details="Defect re-appeared after 4 hours on shift 2.",
    )
    assert cond4 == IssueCondition.RECURRED
    print(f"Step 4: {cond4.value} - {msg4}")

    # 5. Illegal transition: Direct UNRESOLVED -> RESOLVED
    try:
        StateManager.transition_issue_condition(
            current_condition=IssueCondition.UNRESOLVED,
            target_condition=IssueCondition.RESOLVED,
            verification_passed=True,
        )
        assert False, "Should have raised ValueError for direct UNRESOLVED -> RESOLVED"
    except ValueError as e:
        print(f"Step 5: Correctly blocked direct transition UNRESOLVED -> RESOLVED: {e}")

    print("\n✓ Phase 11 issue lifecycle and verification rules passed")


# ===================================================================
# Test 8: End-to-End Orchestration via DiagnosisRequest
# ===================================================================

def test_engine_orchestration_with_request() -> None:
    separator("PHASE 13: End-to-End Engine Orchestration with DiagnosisRequest")

    engine = DiagnosticEngine()

    req = DiagnosisRequest(
        description="The dispensing dots become smaller after the machine has been running for around 20 minutes.",
        material="Epoxy",
        method="Time-Pressure",
    )

    res = engine.diagnose(req)

    assert res.case_id is not None
    assert res.defect == "D03_INCONSISTENT_SIZE"
    assert res.defect_name == "Inconsistent Dispensing Size"
    assert len(res.ranked_causes) > 0
    assert res.next_question is not None
    assert res.next_check is not None
    assert res.analysis_revision is not None
    assert res.analysis_revision.revision_number == 1
    assert res.issue_condition == IssueCondition.UNRESOLVED
    assert len(res.explanation) > 0

    print(f"Defect:      {res.defect} ({res.defect_name})")
    print(f"Top Cause:   {res.ranked_causes[0].cause_name} ({res.ranked_causes[0].score:.0f}/100)")
    print(f"Next Action: {res.next_check.name} ({res.next_check.check_id})")
    print(f"Next Q:      {res.next_question.text[:65]}...")
    print(f"Condition:   {res.issue_condition.value}")
    print(f"Revision:    #{res.analysis_revision.revision_number}")

    print("\n✓ End-to-end orchestration passed")


# ===================================================================
# Main Runner
# ===================================================================

if __name__ == "__main__":
    test_phase_9_statuses_and_findings()
    test_phase_9_blocked_checks_remain_unknown()
    test_phase_9_completed_check_finding()
    test_phase_10_reranking_and_revisions()
    test_phase_10_multistep_investigation()
    test_phase_11_four_state_dimensions()
    test_phase_11_issue_lifecycle_and_verification()
    test_engine_orchestration_with_request()

    separator("ALL PHASES 9–11 TESTS PASSED")
    print("Check result handling, re-ranking with revisions, and 4-dimension state management")
    print("are completely implemented and verified.\n")
