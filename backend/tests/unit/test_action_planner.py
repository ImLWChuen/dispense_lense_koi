"""
Unit tests for Diagnostic ActionPlanner (DLK-M3-013).

Verifies:
1. Candidate troubleshooting checks ranking based on composite score (coverage, info gain, effort).
2. Penalization of already-attempted checks.
3. Proper filtering by defect code and candidate causes.
4. Fallback handling when ranked causes is empty or defect code is omitted.
"""

import os
import sys
import unittest
from pathlib import Path

backend_dir = str(Path(__file__).resolve().parents[2])
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
project_root = str(Path(__file__).resolve().parents[3])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.app.schemas.diagnosis import (
    CandidateCause,
    CauseConclusion,
    CheckExecutionStatus,
    CheckFinding,
    CheckResult,
    DefectCode,
    TroubleshootingCheck,
)
from backend.app.services.diagnosis.action_planner import (
    ActionPlanner,
    ActionSelectionResult,
)


class TestActionPlanner(unittest.TestCase):
    def setUp(self):
        self.planner = ActionPlanner()
        self.defect_code = DefectCode.D03_INCONSISTENT_SIZE.value

        self.cause_air = CandidateCause(
            cause_id="air_supply_issue",
            cause_name="Air / Supply Issue",
            score=50.0,
            conclusion=CauseConclusion.SUSPECTED,
        )
        self.cause_nozzle = CandidateCause(
            cause_id="nozzle_restriction",
            cause_name="Nozzle Restriction",
            score=40.0,
            conclusion=CauseConclusion.SUSPECTED,
        )
        self.cause_material = CandidateCause(
            cause_id="material_condition",
            cause_name="Material Condition",
            score=35.0,
            conclusion=CauseConclusion.SUSPECTED,
        )

    def test_candidate_action_ranking(self):
        """Action planner produces ordered candidate checks with priority scores."""
        ranked_causes = [self.cause_air, self.cause_nozzle, self.cause_material]
        result = self.planner.select_next_action(
            ranked_causes=ranked_causes,
            previous_check_results=[],
            defect_code=self.defect_code,
        )

        self.assertIsInstance(result, ActionSelectionResult)
        self.assertTrue(result.should_check)
        self.assertIsNotNone(result.selected_check)
        self.assertGreater(len(result.all_candidates), 1)

        # Check descending order of priority scores
        scores = [c.priority_score for c in result.all_candidates]
        self.assertEqual(scores, sorted(scores, reverse=True))

        # Selected check must be the top scored check
        assert result.selected_check is not None
        self.assertEqual(result.selected_check.check_id, result.all_candidates[0].check_id)

    def test_already_attempted_penalty(self):
        """Checks already attempted receive heavy penalty and are not re-selected."""
        ranked_causes = [self.cause_air, self.cause_nozzle, self.cause_material]

        # Initial selection
        res1 = self.planner.select_next_action(
            ranked_causes=ranked_causes,
            previous_check_results=[],
            defect_code=self.defect_code,
        )
        self.assertIsNotNone(res1.selected_check)
        assert res1.selected_check is not None
        first_check_id = res1.selected_check.check_id
        first_score_before = res1.selected_check.priority_score

        # Simulate attempting the first check
        attempt = CheckResult(
            check_id=first_check_id,
            execution_status=CheckExecutionStatus.COMPLETED,
            finding=CheckFinding.SUPPORTS,
        )

        res2 = self.planner.select_next_action(
            ranked_causes=ranked_causes,
            previous_check_results=[attempt],
            defect_code=self.defect_code,
        )

        # First check score should now be heavily penalized
        attempted_check = next((c for c in res2.all_candidates if c.check_id == first_check_id), None)
        self.assertIsNotNone(attempted_check)
        assert attempted_check is not None
        self.assertLess(attempted_check.priority_score, first_score_before)

        # New selected check must NOT be the already attempted check
        if res2.selected_check:
            self.assertNotEqual(res2.selected_check.check_id, first_check_id)

    def test_selection_without_defect_code(self):
        """Action planner selects checks based purely on ranked causes when defect_code is None."""
        result = self.planner.select_next_action(
            ranked_causes=[self.cause_nozzle],
            previous_check_results=[],
            defect_code=None,
        )
        self.assertTrue(result.should_check)
        self.assertIsNotNone(result.selected_check)
        assert result.selected_check is not None
        self.assertIn("nozzle_restriction", result.selected_check.target_causes)

    def test_empty_ranked_causes(self):
        """Action planner returns empty selection when ranked_causes is empty."""
        result = self.planner.select_next_action(
            ranked_causes=[],
            previous_check_results=[],
            defect_code=self.defect_code,
        )
        self.assertFalse(result.should_check)
        self.assertIsNone(result.selected_check)
        self.assertEqual(len(result.all_candidates), 0)


if __name__ == "__main__":
    unittest.main()
