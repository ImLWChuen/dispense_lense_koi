"""
Unit tests for EvidenceEngine.

Verifies:
1. User answer observation support evaluation (positive score contribution, SUPPORTS relation)
2. User answer contradiction evaluation (negative score contribution, CONTRADICTS relation)
3. Duplicate evidence handling (no score inflation for semantic duplicates)
"""

import os
import sys
import unittest

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.services.diagnosis.evidence_engine import EvidenceEngine
from app.schemas.diagnosis import (
    EvidenceRelation,
    EvidenceSource,
    Observation,
    ObservationType,
    StatementType,
)


class TestEvidenceEngine(unittest.TestCase):
    def setUp(self):
        self.engine = EvidenceEngine()
        self.defect_code = "D03_INCONSISTENT_SIZE"

    def test_user_answer_observation_support_evaluation(self):
        """Test that user answer observation matching a cause produces SUPPORTS relation."""
        # Q01/Q04 -> after_prolonged_operation supports air_supply_issue and material_condition
        obs = Observation(
            observation_type=ObservationType.RUNTIME_PATTERN,
            value="after_prolonged_operation",
            original_text="Dots become smaller after 20 minutes",
            source=EvidenceSource.USER_ANSWER,
        )

        candidates = self.engine.evaluate([obs], self.defect_code)
        self.assertGreater(len(candidates), 0)

        air = next((c for c in candidates if c.cause_id == "air_supply_issue"), None)
        self.assertIsNotNone(air)
        assert air is not None

        # Check supporting evidence
        supporting_items = [e for e in air.evidence if e.relation == EvidenceRelation.SUPPORTS]
        self.assertGreater(len(supporting_items), 0)
        self.assertEqual(supporting_items[0].source, EvidenceSource.USER_ANSWER)
        self.assertGreater(supporting_items[0].score_contribution, 0.0)

    def test_user_answer_observation_contradiction_evaluation(self):
        """Test that user answer observation contradicting a cause produces CONTRADICTS relation."""
        # Q02: all_points contradicts nozzle_restriction
        obs_all_points = Observation(
            observation_type=ObservationType.QUESTION_ANSWER,
            value="Q02:all_points",
            original_text="All nozzles show the issue",
            source=EvidenceSource.USER_ANSWER,
        )

        candidates = self.engine.evaluate([obs_all_points], self.defect_code)
        nozzle = next((c for c in candidates if c.cause_id == "nozzle_restriction"), None)
        self.assertIsNotNone(nozzle)
        assert nozzle is not None

        # all_points contradicts localized cause nozzle_restriction
        contradicting = [e for e in nozzle.evidence if e.relation == EvidenceRelation.CONTRADICTS]
        self.assertGreater(len(contradicting), 0)
        self.assertEqual(contradicting[0].source, EvidenceSource.USER_ANSWER)
        self.assertLess(contradicting[0].score_contribution, 0.0)

    def test_duplicate_evidence_handling(self):
        """Test that submitting duplicate observations does NOT inflate the cause score."""
        obs1 = Observation(
            observation_type=ObservationType.RUNTIME_PATTERN,
            value="after_prolonged_operation",
            source=EvidenceSource.USER,
        )
        # Second identical observation from user answer
        obs2 = Observation(
            observation_type=ObservationType.RUNTIME_PATTERN,
            value="after_prolonged_operation",
            source=EvidenceSource.USER_ANSWER,
        )

        # Evaluate single observation
        res_single = self.engine.evaluate([obs1], self.defect_code)
        air_single = next(c for c in res_single if c.cause_id == "air_supply_issue")

        # Evaluate both observations
        res_dup = self.engine.evaluate([obs1, obs2], self.defect_code)
        air_dup = next(c for c in res_dup if c.cause_id == "air_supply_issue")

        # Scores should be identical because the duplicate is ignored
        self.assertEqual(air_single.score, air_dup.score)

        # Verify duplicate flag is set on the second evidence
        dup_ev = [e for e in air_dup.evidence if e.is_duplicate]
        self.assertEqual(len(dup_ev), 1)
        self.assertEqual(dup_ev[0].score_contribution, 0.0)

    def test_conflicting_pressure_observations_not_suppressed_as_duplicates(self):
        """Ensure 'Pressure is stable' and 'Pressure is fluctuating' are not marked duplicates."""
        obs_stable = Observation(
            observation_type=ObservationType.PRESSURE,
            value="stable",
            original_text="Pressure is stable.",
            source=EvidenceSource.USER,
        )
        obs_unstable = Observation(
            observation_type=ObservationType.PRESSURE,
            value="fluctuating",
            original_text="Pressure is fluctuating.",
            source=EvidenceSource.USER,
        )
        candidates = self.engine.evaluate([obs_stable, obs_unstable], self.defect_code)
        air = next((c for c in candidates if c.cause_id == "pressure_instability"), None)
        if air:
            dup_ev = [e for e in air.evidence if e.is_duplicate]
            self.assertEqual(len(dup_ev), 0)

    def test_image_undersized_and_user_oversized_distinct_conflicting_facts(self):
        """IMAGE undersized and USER oversized are conflicting facts, not duplicates."""
        obs_img = Observation(
            observation_type=ObservationType.DEPOSIT_SIZE,
            value="undersized",
            source=EvidenceSource.IMAGE,
        )
        obs_user = Observation(
            observation_type=ObservationType.DEPOSIT_SIZE,
            value="oversized",
            source=EvidenceSource.USER,
        )
        candidates = self.engine.evaluate([obs_img, obs_user], self.defect_code)
        for c in candidates:
            dup_ev = [e for e in c.evidence if e.is_duplicate]
            self.assertEqual(len(dup_ev), 0)

    def test_image_undersized_and_text_blockage_independent(self):
        """IMAGE undersized and nozzle blockage are independent evidence, not duplicates."""
        obs_img = Observation(
            observation_type=ObservationType.DEPOSIT_SIZE,
            value="undersized",
            original_text="Nozzle deposit is small",
            source=EvidenceSource.IMAGE,
        )
        obs_blockage = Observation(
            observation_type=ObservationType.NOZZLE_CONDITION,
            value="blocked",
            original_text="Nozzle deposit is blocked",
            source=EvidenceSource.USER,
        )
        candidates = self.engine.evaluate([obs_img, obs_blockage], self.defect_code)
        for c in candidates:
            dup_ev = [e for e in c.evidence if e.is_duplicate]
            self.assertEqual(len(dup_ev), 0)


if __name__ == "__main__":
    unittest.main()
