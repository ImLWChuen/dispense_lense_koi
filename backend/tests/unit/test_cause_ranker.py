"""
Unit tests for CauseRanker.

Verifies:
1. Score change after adding question-answer evidence
2. Rank reordering when new evidence favors a different hypothesis
3. Cause explanation generation containing evidence and score labels
4. Score bounding (each cause score <= 100, not summing to 100)
"""

import os
import sys
import unittest

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.app.services.diagnosis.cause_ranker import CauseRanker
from backend.app.schemas.diagnosis import (
    EvidenceSource,
    Observation,
    ObservationType,
)


class TestCauseRanker(unittest.TestCase):
    def setUp(self):
        self.ranker = CauseRanker()
        self.defect_code = "D03_INCONSISTENT_SIZE"

    def test_score_change_after_answer_evidence(self):
        """Test that adding answer evidence alters the cause scores."""
        # Initial symptom: undersized dots
        obs_initial = [
            Observation(
                observation_type=ObservationType.DEPOSIT_SIZE,
                value="undersized",
                source=EvidenceSource.USER,
            )
        ]
        res1 = self.ranker.rank(obs_initial, self.defect_code)
        air_score_before = next(c.score for c in res1.ranked_causes if c.cause_id == "air_supply_issue")

        # Now add answer to Q01: after_prolonged_operation (supports air_supply_issue)
        obs_answer = Observation(
            observation_type=ObservationType.RUNTIME_PATTERN,
            value="after_prolonged_operation",
            source=EvidenceSource.USER_ANSWER,
        )
        res2 = self.ranker.rank(obs_initial + [obs_answer], self.defect_code)
        air_score_after = next(c.score for c in res2.ranked_causes if c.cause_id == "air_supply_issue")

        # Score should increase
        self.assertGreater(air_score_after, air_score_before)

    def test_rank_reordering_after_answer_evidence(self):
        """Test that new answer evidence can reorder the ranking of candidate causes."""
        # Initial symptom: undersized
        # In rules.json, deposit_size: undersized gives STRONG to nozzle_restriction and WEAK to material_condition
        obs_initial = [
            Observation(
                observation_type=ObservationType.DEPOSIT_SIZE,
                value="undersized",
                source=EvidenceSource.USER,
            )
        ]
        res1 = self.ranker.rank(obs_initial, self.defect_code)
        # nozzle_restriction should initially rank higher than material_condition
        nozzle_idx1 = next(i for i, c in enumerate(res1.ranked_causes) if c.cause_id == "nozzle_restriction")
        material_idx1 = next(i for i, c in enumerate(res1.ranked_causes) if c.cause_id == "material_condition")
        self.assertLess(nozzle_idx1, material_idx1)

        # Now technician answers Q02: all_points (contradicts nozzle_restriction, supports material_condition)
        # and answers Q13: long_time (material_state = high_viscosity supports material_condition)
        obs_q02 = Observation(
            observation_type=ObservationType.QUESTION_ANSWER,
            value="Q02:all_points",
            source=EvidenceSource.USER_ANSWER,
        )
        obs_q13 = Observation(
            observation_type=ObservationType.MATERIAL_STATE,
            value="high_viscosity",
            source=EvidenceSource.USER_ANSWER,
        )
        res2 = self.ranker.rank(obs_initial + [obs_q02, obs_q13], self.defect_code)

        # Now material_condition should rank higher than nozzle_restriction
        nozzle_idx2 = next(i for i, c in enumerate(res2.ranked_causes) if c.cause_id == "nozzle_restriction")
        material_idx2 = next(i for i, c in enumerate(res2.ranked_causes) if c.cause_id == "material_condition")
        self.assertLess(material_idx2, nozzle_idx2)

    def test_cause_explanation_generation(self):
        """Test structured cause explanation generation containing evidence details."""
        obs = [
            Observation(
                observation_type=ObservationType.RUNTIME_PATTERN,
                value="after_prolonged_operation",
                source=EvidenceSource.USER_ANSWER,
            )
        ]
        result = self.ranker.rank(obs, self.defect_code)
        explanation = result.get_cause_explanation("air_supply_issue")

        self.assertIn("cause", explanation)
        self.assertEqual(explanation["cause"], "air_supply_issue")
        self.assertIn("score_label", explanation)
        self.assertTrue(explanation["score_label"].startswith("Evidence Support:"))
        self.assertIn("supporting_evidence", explanation)
        self.assertGreater(len(explanation["supporting_evidence"]), 0)

    def test_score_bounding_and_no_sum_to_100(self):
        """Test that cause scores are bounded [0, 100] and do not sum to 100."""
        obs = [
            Observation(
                observation_type=ObservationType.DEPOSIT_SIZE,
                value="undersized",
                source=EvidenceSource.USER,
            ),
            Observation(
                observation_type=ObservationType.RUNTIME_PATTERN,
                value="after_prolonged_operation",
                source=EvidenceSource.USER_ANSWER,
            ),
            Observation(
                observation_type=ObservationType.RUNTIME_PATTERN,
                value="worsens_over_time",
                source=EvidenceSource.USER_ANSWER,
            ),
        ]
        result = self.ranker.rank(obs, self.defect_code)
        for cause in result.ranked_causes:
            self.assertGreaterEqual(cause.score, 0.0)
            self.assertLessEqual(cause.score, 100.0)

        total_score = sum(c.score for c in result.ranked_causes)
        self.assertNotEqual(total_score, 100.0)


if __name__ == "__main__":
    unittest.main()
