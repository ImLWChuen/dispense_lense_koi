"""
Unit tests for QuestionAnswerHandler.

Verifies:
1. Normal answer -> typed observation conversion
2. All 15 questions test matrix (normal values)
3. UNKNOWN handling (no false evidence / empty observations)
4. NOT_APPLICABLE handling (no false evidence / empty observations)
5. User hypothesis preserving behavior (marked as hypothesis, not confirmed cause)
6. Negative test: unknown question ID rejection (ValueError)
7. Negative test: invalid answer value rejection (ValueError)
"""

import os
import sys
import unittest

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.services.diagnosis.question_answer_handler import (
    QuestionAnswerHandler,
    QuestionAnswerResult,
)
from app.schemas.diagnosis import Observation, EvidenceSource, ObservationType


class TestQuestionAnswerHandler(unittest.TestCase):
    def setUp(self):
        self.handler = QuestionAnswerHandler()

    def test_single_normal_answer_conversion(self):
        """Test conversion of a single normal answer to a typed observation."""
        result = self.handler.process_answer("Q01", "after_prolonged_operation")
        self.assertIsInstance(result, QuestionAnswerResult)
        self.assertGreaterEqual(len(result), 1)
        obs = result[0]
        self.assertEqual(obs.observation_type, ObservationType.RUNTIME_PATTERN)
        self.assertEqual(obs.value, "after_prolonged_operation")
        self.assertEqual(obs.source, EvidenceSource.USER_ANSWER)

    def test_all_15_questions_matrix(self):
        """Test matrix ensuring all Q01-Q15 produce valid typed observations for normal answers."""
        test_cases = [
            ("Q01", "after_prolonged_operation", ObservationType.RUNTIME_PATTERN, "after_prolonged_operation"),
            ("Q01", "all_points", ObservationType.SPATIAL_PATTERN, "systemic"),
            ("Q02", "all_points", ObservationType.SPATIAL_PATTERN, "systemic"),
            ("Q02", "specific_nozzle", ObservationType.SPATIAL_PATTERN, "localized"),
            ("Q03", "YES", ObservationType.NOZZLE_CONDITION, "clean"),
            ("Q04", "YES", ObservationType.RUNTIME_PATTERN, "after_prolonged_operation"),
            ("Q05", "YES", ObservationType.MATERIAL_STATE, "separated"),
            ("Q06", "YES", ObservationType.PROCESS_PARAMETER, "deviated"),
            ("Q07", "YES", ObservationType.BUBBLE_PRESENCE, "visible_bubbles"),
            ("Q08", "YES", ObservationType.PRESSURE, "stable"),
            ("Q09", "YES", ObservationType.EQUIPMENT_CONDITION, "worn"),
            ("Q10", "YES", ObservationType.TEMPERATURE, "elevated"),
            ("Q11", "YES", ObservationType.SPREADING_BEHAVIOUR, "normal"),
            ("Q12", "YES", ObservationType.FREQUENCY_PATTERN, "consistent"),
            ("Q13", "long_time", ObservationType.MATERIAL_STATE, "high_viscosity"),
            ("Q14", "YES", ObservationType.DEPOSIT_SHAPE, "tailing"),
            ("Q15", "YES", ObservationType.MATERIAL_STATE, "depleted"),
        ]

        for q_id, ans_val, exp_type, exp_val in test_cases:
            with self.subTest(question_id=q_id, answer_val=ans_val):
                res = self.handler.process_answer(q_id, ans_val)
                self.assertGreater(len(res), 0, f"Question {q_id} with answer {ans_val} produced no observations")
                obs = res[0]
                self.assertEqual(obs.observation_type, exp_type)
                self.assertEqual(obs.value, exp_val)
                self.assertEqual(obs.source, EvidenceSource.USER_ANSWER)

    def test_unknown_handling(self):
        """Test that UNKNOWN answer produces empty observations and sets flag."""
        for q_id in ["Q01", "Q03", "Q08", "Q14"]:
            res = self.handler.process_answer(q_id, "UNKNOWN")
            self.assertEqual(len(res), 0)
            self.assertTrue(res.is_unknown)
            self.assertEqual(res.observations, [])

    def test_not_applicable_handling(self):
        """Test that NOT_APPLICABLE answer produces empty observations and sets flag."""
        for q_id in ["Q02", "Q04", "Q10", "Q12"]:
            res = self.handler.process_answer(q_id, "NOT_APPLICABLE")
            self.assertEqual(len(res), 0)
            self.assertFalse(res.is_applicable)
            self.assertEqual(res.observations, [])

    def test_user_hypothesis_preservation(self):
        """Test that user hypothesis (e.g. Q15) preserves hypothesis metadata and is not confirmed."""
        res = self.handler.process_answer("Q15", "C01_FLUID_VISCOSITY_INCREASE")
        self.assertEqual(len(res), 1)
        obs = res[0]
        self.assertTrue(res.metadata.get("is_hypothesis", False))
        self.assertEqual(obs.metadata.get("hypothesis_cause"), "C01_FLUID_VISCOSITY_INCREASE")
        self.assertEqual(obs.metadata.get("is_user_hypothesis"), True)
        self.assertIsNone(res.confirmed_cause)

    def test_negative_unknown_question_id(self):
        """Test that an unknown question ID raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            self.handler.process_answer("Q999", "any_value")
        self.assertIn("unknown question", str(ctx.exception).lower())

    def test_negative_invalid_answer_value(self):
        """Test that an invalid answer value for a valid question ID raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            self.handler.process_answer("Q01", "RANDOM_VALUE")
        self.assertIn("invalid answer", str(ctx.exception).lower())

    def test_case_insensitivity_and_alias_support(self):
        """Test case-insensitivity and formatting aliases (e.g. UPPERCASE, hyphens vs underscores)."""
        res1 = self.handler.process_answer("q01", "AFTER_PROLONGED_OPERATION")
        self.assertEqual(res1[0].value, "after_prolonged_operation")

        res2 = self.handler.process_answer("Q03", "CLEANED")
        self.assertEqual(res2[0].value, "clean")

        res3 = self.handler.process_answer("Q07", "NO")
        self.assertEqual(res3[0].value, "none")


if __name__ == "__main__":
    unittest.main()
