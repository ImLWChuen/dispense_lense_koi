"""
Integration Test: Check Result to Diagnosis Revision Full Flow (DLK-M3-013).

Verifies the end-to-end Member 2 troubleshooting check submission workflow:
1. End-to-End check result submission: Case -> Rev 1 -> Submit Check -> Rev 2.
2. Four independent state dimensions coexisting (Cases A, B, C, D).
3. Determinism: Run A == Run B on identical initial cases and check inputs.
4. Duplicate check protection: Repeated identical check results do NOT inflate evidence scores.
5. History & Revision Immutability: Prior revisions remain immutable in history.
6. State lifecycle: Issue resolution strictly requires post-repair verification.
"""

import copy
import os
import sys
import unittest
from pathlib import Path

project_root = str(Path(__file__).resolve().parents[3])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.app.schemas.diagnosis import (
    CauseConclusion,
    CheckExecutionStatus,
    CheckFinding,
    CheckResult,
    DefectCode,
    EvidenceSource,
    IssueCondition,
    Observation,
    ObservationType,
    StructuredCase,
)
from backend.app.services.diagnosis.engine import DiagnosticEngine, StateManager
from backend.app.utils.scoring import SCORING_CONFIG


class TestCheckResultDiagnosisRevision(unittest.TestCase):
    def setUp(self):
        self.engine = DiagnosticEngine()
        self.defect_code = DefectCode.D03_INCONSISTENT_SIZE.value

    def _create_standard_case(self) -> StructuredCase:
        """Create a standardized test case for deterministic evaluation."""
        return StructuredCase(
            case_id="case_integ_test_001",
            description="The dispensing dots become smaller after running for 20 minutes.",
            defect_code=self.defect_code,
            observations=[
                Observation(
                    observation_type=ObservationType.DEPOSIT_SIZE,
                    value="undersized",
                    original_text="Dots become smaller",
                    source=EvidenceSource.USER,
                ),
                Observation(
                    observation_type=ObservationType.RUNTIME_PATTERN,
                    value="after_prolonged_operation",
                    original_text="Occurs after 20 minutes",
                    source=EvidenceSource.USER,
                ),
            ],
            issue_condition=IssueCondition.UNRESOLVED,
        )

    # -----------------------------------------------------------------------
    # Section 13: Required End-to-End Test
    # -----------------------------------------------------------------------

    def test_e2e_check_result_revision_flow(self):
        """Execute full end-to-end check submission: Rev 1 -> Submit Check -> Rev 2."""
        case = self._create_standard_case()

        # Step 1: Initial diagnosis -> Revision 1
        res1 = self.engine.diagnose(case)
        self.assertEqual(len(case.analysis_revisions), 1)
        self.assertIsNotNone(res1.analysis_revision)
        assert res1.analysis_revision is not None
        self.assertEqual(res1.analysis_revision.revision_number, 1)

        # Snapshot Revision 1 state
        rev1_scores = {c.cause_id: c.score for c in res1.ranked_causes}
        nozzle_rev1_score = rev1_scores["nozzle_restriction"]

        # Step 2: Technician executes recommended check ACT01 (Inspect Nozzle)
        # Finds NO blockage -> CONTRADICTS nozzle restriction
        check_act01 = CheckResult(
            check_id="ACT01",
            execution_status=CheckExecutionStatus.COMPLETED,
            finding=CheckFinding.CONTRADICTS,
            finding_details="No visible blockage found during magnification inspection.",
            source=EvidenceSource.USER_CHECK_RESULT,
        )

        # Step 3: Submit check result to engine
        updated_case, res2 = self.engine.submit_check_result(case, check_act01)

        # Step 4: Verify Revision 2 properties
        self.assertEqual(len(updated_case.analysis_revisions), 2, "Must preserve Revision 1 and append Revision 2")
        self.assertEqual(updated_case.analysis_revisions[0].revision_number, 1)
        self.assertEqual(updated_case.analysis_revisions[1].revision_number, 2)
        self.assertIsNotNone(res2.analysis_revision)
        assert res2.analysis_revision is not None
        self.assertEqual(res2.analysis_revision.revision_number, 2)

        # Verify Nozzle Restriction score dropped in Revision 2
        nozzle_rev2 = next(c for c in res2.ranked_causes if c.cause_id == "nozzle_restriction")
        self.assertLess(nozzle_rev2.score, nozzle_rev1_score, "Contradicting check must lower cause score")

        # Verify state separation invariants:
        # Check completed != Cause confirmed != Issue resolved
        self.assertEqual(check_act01.execution_status, CheckExecutionStatus.COMPLETED)
        self.assertEqual(check_act01.finding, CheckFinding.CONTRADICTS)
        self.assertNotEqual(nozzle_rev2.conclusion, CauseConclusion.CONFIRMED, "Contradicted cause must NOT be confirmed")
        self.assertEqual(updated_case.issue_condition, IssueCondition.UNRESOLVED, "Issue must remain UNRESOLVED")
        self.assertEqual(res2.issue_condition, IssueCondition.UNRESOLVED)

    # -----------------------------------------------------------------------
    # Section 14: Four-State Separation Tests (Cases A, B, C, D)
    # -----------------------------------------------------------------------

    def test_case_a_check_completed_supports_cause_unconfirmed_issue_unresolved(self):
        """Case A: Check completed, supports cause, cause UNCONFIRMED, issue UNRESOLVED."""
        case = self._create_standard_case()

        # Check ACT01 supports nozzle restriction, but overall confidence remains below threshold (75)
        check = CheckResult(
            check_id="ACT01",
            execution_status=CheckExecutionStatus.COMPLETED,
            finding=CheckFinding.SUPPORTS,
            finding_details="Minor dried crust near tip.",
        )
        _, res = self.engine.submit_check_result(case, check)

        nozzle = next(c for c in res.ranked_causes if c.cause_id == "nozzle_restriction")
        self.assertEqual(check.execution_status, CheckExecutionStatus.COMPLETED)
        self.assertEqual(check.finding, CheckFinding.SUPPORTS)
        # Even though supported, score is ~58 (below 75 threshold) -> remains SUSPECTED
        self.assertEqual(nozzle.conclusion, CauseConclusion.SUSPECTED)
        self.assertEqual(res.issue_condition, IssueCondition.UNRESOLVED)

    def test_case_b_check_completed_supports_cause_confirmed_issue_unresolved(self):
        """Case B: Check completed, supports cause, cause CONFIRMED (high score), issue UNRESOLVED."""
        case = self._create_standard_case()

        # Add initial evidence that drives score near high confidence
        case.observations.append(
            Observation(
                observation_type=ObservationType.LOCATION_PATTERN,
                value="specific_nozzle",
                source=EvidenceSource.USER,
            )
        )
        case.observations.append(
            Observation(
                observation_type=ObservationType.DEPOSIT_PRESENCE,
                value="missing",
                source=EvidenceSource.USER,
            )
        )

        # Supporting check ACT01 directly targeting nozzle restriction
        check = CheckResult(
            check_id="ACT01",
            execution_status=CheckExecutionStatus.COMPLETED,
            finding=CheckFinding.SUPPORTS,
            finding_details="Severe solid blockage in nozzle bore.",
        )
        _, res = self.engine.submit_check_result(case, check)

        nozzle = next(c for c in res.ranked_causes if c.cause_id == "nozzle_restriction")
        self.assertGreaterEqual(nozzle.score, SCORING_CONFIG.high_confidence_threshold)
        # DLK-M3-013: Direct supporting check + high score raises score, but does NOT auto-confirm
        self.assertEqual(nozzle.conclusion, CauseConclusion.SUSPECTED, "Supporting check does not auto-confirm cause")

        # Explicit technician confirmation confirms cause
        case, res = self.engine.confirm_cause(
            case,
            cause_id="nozzle_restriction",
            confirmed_by="technician",
            confirmation_details="Direct visual bore inspection confirmed severe blockage.",
        )
        nozzle = next(c for c in res.ranked_causes if c.cause_id == "nozzle_restriction")
        self.assertEqual(nozzle.conclusion, CauseConclusion.CONFIRMED, "Explicit technician confirmation confirms cause")
        # Issue condition MUST STILL be UNRESOLVED!
        self.assertEqual(res.issue_condition, IssueCondition.UNRESOLVED, "Cause confirmed != issue resolved")


    def test_case_c_check_completed_inconclusive_cause_unconfirmed_issue_resolved(self):
        """Case C: Check completed, finding inconclusive, cause unconfirmed, issue RESOLVED with verification."""
        case = self._create_standard_case()

        # Step 1: Inconclusive check
        check = CheckResult(
            check_id="ACT07",
            execution_status=CheckExecutionStatus.COMPLETED,
            finding=CheckFinding.INCONCLUSIVE,
            finding_details="Valve response borderline.",
        )
        self.engine.submit_check_result(case, check)

        # Step 2: Transition through state manager to RECOVERY_PENDING_VERIFICATION
        StateManager.transition_issue_condition(
            current_condition=case.issue_condition,
            target_condition=IssueCondition.RECOVERY_PENDING_VERIFICATION,
            verification_details="Routine cleaning cycle run.",
        )
        case.issue_condition = IssueCondition.RECOVERY_PENDING_VERIFICATION

        # Step 3: Verified resolution (test shots nominal)
        cond, _ = StateManager.transition_issue_condition(
            current_condition=case.issue_condition,
            target_condition=IssueCondition.RESOLVED,
            verification_passed=True,
            verification_details="15 test shots pass CPK > 1.67.",
        )
        case.issue_condition = cond

        res = self.engine.diagnose(case)
        self.assertEqual(res.issue_condition, IssueCondition.RESOLVED)
        for c in res.ranked_causes:
            self.assertNotEqual(c.conclusion, CauseConclusion.CONFIRMED)

    def test_case_d_check_completed_supports_cause_confirmed_issue_resolved(self):
        """Case D: Check completed, supports cause, cause confirmed, issue RESOLVED with verification."""
        case = self._create_standard_case()

        # Supporting evidence to confirm cause
        case.observations.append(
            Observation(observation_type=ObservationType.LOCATION_PATTERN, value="specific_nozzle", source=EvidenceSource.USER)
        )
        case.observations.append(
            Observation(observation_type=ObservationType.DEPOSIT_PRESENCE, value="missing", source=EvidenceSource.USER)
        )
        check = CheckResult(
            check_id="ACT01",
            execution_status=CheckExecutionStatus.COMPLETED,
            finding=CheckFinding.SUPPORTS,
            finding_details="Blocked nozzle verified.",
        )
        self.engine.submit_check_result(case, check)
        self.engine.confirm_cause(
            case,
            cause_id="nozzle_restriction",
            confirmed_by="technician",
            confirmation_details="Direct bore inspection verified solid blockage.",
        )

        # Transition issue to RESOLVED with post-repair verification

        case.issue_condition = IssueCondition.RECOVERY_PENDING_VERIFICATION
        cond, _ = StateManager.transition_issue_condition(
            current_condition=case.issue_condition,
            target_condition=IssueCondition.RESOLVED,
            verification_passed=True,
            verification_details="Nozzle replaced, 20 test shots nominal.",
        )
        case.issue_condition = cond

        res = self.engine.diagnose(case)
        nozzle = next(c for c in res.ranked_causes if c.cause_id == "nozzle_restriction")
        self.assertEqual(nozzle.conclusion, CauseConclusion.CONFIRMED)
        self.assertEqual(res.issue_condition, IssueCondition.RESOLVED)

    # -----------------------------------------------------------------------
    # Section 10: Determinism (Run A == Run B)
    # -----------------------------------------------------------------------

    def test_deterministic_rerun_after_check_result(self):
        """Submitting identical check results on identical initial cases produces identical results."""
        case_a = self._create_standard_case()
        case_b = self._create_standard_case()

        check_a = CheckResult(
            check_id="ACT04",
            execution_status=CheckExecutionStatus.COMPLETED,
            finding=CheckFinding.SUPPORTS,
            finding_details="Pressure fluctuating by +/- 15 kPa.",
        )
        check_b = copy.deepcopy(check_a)

        _, res_a = self.engine.submit_check_result(case_a, check_a)
        _, res_b = self.engine.submit_check_result(case_b, check_b)

        # Scores must be identical
        scores_a = {c.cause_id: c.score for c in res_a.ranked_causes}
        scores_b = {c.cause_id: c.score for c in res_b.ranked_causes}
        self.assertEqual(scores_a, scores_b)

        # Cause ordering must be identical
        order_a = [c.cause_id for c in res_a.ranked_causes]
        order_b = [c.cause_id for c in res_b.ranked_causes]
        self.assertEqual(order_a, order_b)

        # Recommended next check must be identical
        next_a = res_a.next_check.check_id if res_a.next_check else None
        next_b = res_b.next_check.check_id if res_b.next_check else None
        self.assertEqual(next_a, next_b)

    # -----------------------------------------------------------------------
    # Section 11: Duplicate Protection
    # -----------------------------------------------------------------------

    def test_duplicate_check_results_do_not_inflate_evidence(self):
        """Submitting the exact same check result twice must NOT inflate cause score."""
        case = self._create_standard_case()

        check1 = CheckResult(
            check_id="ACT04",
            execution_status=CheckExecutionStatus.COMPLETED,
            finding=CheckFinding.SUPPORTS,
            finding_details="Pressure fluctuating.",
        )

        _, res1 = self.engine.submit_check_result(case, check1)
        pressure_score_first = next(c for c in res1.ranked_causes if c.cause_id == "pressure_instability").score

        # Submit second identical check result
        check2 = CheckResult(
            check_id="ACT04",
            execution_status=CheckExecutionStatus.COMPLETED,
            finding=CheckFinding.SUPPORTS,
            finding_details="Pressure fluctuating.",
        )
        _, res2 = self.engine.submit_check_result(case, check2)
        pressure_score_second = next(c for c in res2.ranked_causes if c.cause_id == "pressure_instability").score

        # Second submission must NOT increase score
        self.assertEqual(
            pressure_score_first,
            pressure_score_second,
            f"Repeated identical check must not inflate score! First: {pressure_score_first}, Second: {pressure_score_second}",
        )

    # -----------------------------------------------------------------------
    # Section 15: Revision Preservation & Post-Resolution Handling
    # -----------------------------------------------------------------------

    def test_subsequent_check_after_resolution_creates_new_revision(self):
        """A subsequent check submitted after issue resolution creates Revision N+1 without rewriting history."""
        case = self._create_standard_case()
        self.engine.diagnose(case)  # Rev 1

        # Check -> Rev 2
        chk1 = CheckResult(
            check_id="ACT01",
            execution_status=CheckExecutionStatus.COMPLETED,
            finding=CheckFinding.CONTRADICTS,
            finding_details="No blockage.",
        )
        self.engine.submit_check_result(case, chk1)
        self.assertEqual(len(case.analysis_revisions), 2)

        # Issue resolved
        case.issue_condition = IssueCondition.RESOLVED

        # Subsequent check submitted (e.g. routine post-maintenance audit check) -> Rev 3
        chk2 = CheckResult(
            check_id="ACT04",
            execution_status=CheckExecutionStatus.COMPLETED,
            finding=CheckFinding.SUPPORTS,
            finding_details="Pressure stable.",
        )
        updated_case, res3 = self.engine.submit_check_result(case, chk2)

        self.assertEqual(len(updated_case.analysis_revisions), 3, "Must append Revision 3 rather than overwriting")
        self.assertEqual(updated_case.analysis_revisions[0].revision_number, 1)
        self.assertEqual(updated_case.analysis_revisions[1].revision_number, 2)
        self.assertEqual(updated_case.analysis_revisions[2].revision_number, 3)


if __name__ == "__main__":
    unittest.main()
