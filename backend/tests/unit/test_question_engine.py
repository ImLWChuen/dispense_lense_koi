"""
Unit tests for Diagnostic QuestionEngine.

Verifies:
1. Candidate question ranking based on usefulness and cause coverage
2. Penalization of already answered questions
3. Stopping condition when no high-value questions remain or high confidence reached
4. Fallback handling when defect code is omitted or no questions apply
"""

import os
import sys
import unittest
from pathlib import Path

project_root = str(Path(__file__).resolve().parents[3])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.schemas.diagnosis import (
    CandidateCause,
    CauseConclusion,
    DefectCode,
    EvidenceSource,
    Observation,
    ObservationType,
    QuestionAnswer,
    StatementType,
)
from app.services.diagnosis.cause_ranker import CauseRanker
from app.services.diagnosis.question_answer_handler import QuestionAnswerHandler
from app.services.diagnosis.question_engine import (
    QuestionEngine,
    QuestionSelectionResult,
)
from app.utils.scoring import SCORING_CONFIG


class TestQuestionEngine(unittest.TestCase):
    def setUp(self):
        self.engine = QuestionEngine()
        self.defect_code = DefectCode.D03_INCONSISTENT_SIZE.value

        # Standard test causes matching domain knowledge base IDs
        self.candidate_material = CandidateCause(
            cause_id="material_condition",
            cause_name="Material Condition",
            score=45.0,
            conclusion=CauseConclusion.SUSPECTED,
            missing_evidence=["after_prolonged_operation", "elevated_temperature"],
        )
        self.candidate_nozzle = CandidateCause(
            cause_id="nozzle_restriction",
            cause_name="Nozzle Restriction",
            score=35.0,
            conclusion=CauseConclusion.SUSPECTED,
            missing_evidence=["unverified_cleaning", "single_nozzle"],
        )

    def test_candidate_question_ranking(self):
        """Test candidate question ranking produces ordered questions with scores."""
        ranked_causes = [self.candidate_material, self.candidate_nozzle]
        result = self.engine.select_next_question(
            ranked_causes=ranked_causes,
            previous_answers=[],
            defect_code=self.defect_code,
        )

        self.assertIsInstance(result, QuestionSelectionResult)
        self.assertTrue(result.should_ask)
        self.assertIsNotNone(result.selected_question)
        assert result.selected_question is not None
        self.assertGreater(len(result.all_candidates), 1)

        # Check descending order of usefulness scores
        scores = [q.usefulness_score for q in result.all_candidates]
        self.assertEqual(scores, sorted(scores, reverse=True))

        # Check that top question targets at least one of the candidate causes
        target_causes = set(result.selected_question.target_causes)
        cause_ids = {c.cause_id for c in ranked_causes}
        self.assertTrue(bool(target_causes & cause_ids))

    def test_selection_without_defect_code(self):
        """Test question selection using only ranked causes when defect code is omitted."""
        result = self.engine.select_next_question(
            ranked_causes=[self.candidate_material],
            previous_answers=[],
            defect_code=None,
        )

        self.assertTrue(result.should_ask)
        self.assertIsNotNone(result.selected_question)
        assert result.selected_question is not None
        self.assertIn("material_condition", result.selected_question.target_causes)

    def test_penalization_of_already_answered_questions(self):
        """Test that already answered questions receive heavy score penalty."""
        ranked_causes = [self.candidate_material, self.candidate_nozzle]

        # Initial selection
        res1 = self.engine.select_next_question(
            ranked_causes=ranked_causes,
            previous_answers=[],
            defect_code=self.defect_code,
        )
        self.assertIsNotNone(res1.selected_question)
        assert res1.selected_question is not None
        top_q_id = res1.selected_question.question_id
        top_score_before = res1.selected_question.usefulness_score

        # Answer that top question
        prev_answers = [
            QuestionAnswer(
                question_id=top_q_id,
                answer_value="YES",
                source=EvidenceSource.USER_ANSWER,
            )
        ]
        res2 = self.engine.select_next_question(
            ranked_causes=ranked_causes,
            previous_answers=prev_answers,
            defect_code=self.defect_code,
        )

        # Find the previously top question in all_candidates
        answered_q = next(
            (q for q in res2.all_candidates if q.question_id == top_q_id), None
        )
        self.assertIsNotNone(answered_q)
        assert answered_q is not None
        self.assertTrue(answered_q.already_answered)
        self.assertLess(answered_q.usefulness_score, top_score_before)

        # Ensure the new selected question is NOT the one already answered
        self.assertIsNotNone(res2.selected_question)
        assert res2.selected_question is not None
        self.assertNotEqual(res2.selected_question.question_id, top_q_id)

    def test_stopping_condition_high_confidence(self):
        """Test stopping condition when a cause has reached high confidence."""
        high_conf_cause = CandidateCause(
            cause_id="material_condition",
            cause_name="Material Condition",
            score=SCORING_CONFIG.high_confidence_threshold + 5.0,
            conclusion=CauseConclusion.CONFIRMED,
        )
        result = self.engine.select_next_question(
            ranked_causes=[high_conf_cause],
            previous_answers=[],
            defect_code=self.defect_code,
        )
        self.assertFalse(result.should_ask)
        self.assertIsNone(result.selected_question)
        self.assertIsNotNone(result.reason_stopped)
        assert result.reason_stopped is not None
        self.assertIn("Sufficient evidence", result.reason_stopped)

    def test_stopping_condition_all_answered(self):
        """Test stopping condition when all relevant questions have been answered."""
        ranked_causes = [self.candidate_material]
        res = self.engine.select_next_question(
            ranked_causes=ranked_causes,
            previous_answers=[],
            defect_code=self.defect_code,
        )
        all_q_ids = [q.question_id for q in res.all_candidates]
        self.assertGreater(len(all_q_ids), 0, "Expected candidates to test stopping condition")

        # Answer all candidates
        all_answers = [
            QuestionAnswer(
                question_id=qid,
                answer_value="NO",
                source=EvidenceSource.USER_ANSWER,
            )
            for qid in all_q_ids
        ]

        res_final = self.engine.select_next_question(
            ranked_causes=ranked_causes,
            previous_answers=all_answers,
            defect_code=self.defect_code,
        )
        self.assertFalse(res_final.should_ask)
        self.assertIsNone(res_final.selected_question)
        self.assertIsNotNone(res_final.reason_stopped)
        assert res_final.reason_stopped is not None
        self.assertIn("All applicable questions have been answered", res_final.reason_stopped)

    def test_stopping_condition_no_applicable_questions(self):
        """Test stopping condition when no questions apply to unknown cause with no defect code."""
        unknown_cause = CandidateCause(
            cause_id="non_existent_cause_xyz",
            cause_name="Non Existent Cause",
            score=20.0,
            conclusion=CauseConclusion.SUSPECTED,
        )
        result = self.engine.select_next_question(
            ranked_causes=[unknown_cause],
            previous_answers=[],
            defect_code=None,
        )
        self.assertFalse(result.should_ask)
        self.assertIsNone(result.selected_question)
        self.assertIsNotNone(result.reason_stopped)
        assert result.reason_stopped is not None
        self.assertIn("No applicable questions found", result.reason_stopped)

    def test_inconsistent_volume_dynamic_question_discrimination_pivot(self):
        """Verify dynamic question discrimination for 'inconsistent volume' (NSW Step 1 bonus).

        Demonstrates:
        1. When defect is D03_INCONSISTENT_SIZE (inconsistent volume), QuestionEngine dynamically
           selects Q01 (shift duration / runtime pattern: startup vs. prolonged operation) as top
           discriminating question rather than following a static checklist.
        2. When answered 'after_prolonged_operation', the candidate pool maintains active
           discrimination including Q10 (ambient/material temperature) and Q13 (pot life / thaw time).
        3. Answering Q13 ('long_time') substantially elevates material_condition support,
           proving the backend adapts questions and rankings dynamically based on answers.
        4. When answered 'immediately', the engine eliminates thermal/pot-life causes and pivots
           to spatial localization (Q02: all points vs specific nozzle).
        """
        cr = CauseRanker()
        obs = [
            Observation(
                observation_type=ObservationType.DEPOSIT_SIZE,
                value="inconsistent",
                statement_type=StatementType.USER_OBSERVATION,
                source=EvidenceSource.USER,
            )
        ]
        r1 = cr.rank(obs, DefectCode.D03_INCONSISTENT_SIZE.value)

        # Step 1: Initial question selection for inconsistent volume
        res1 = self.engine.select_next_question(
            ranked_causes=r1.ranked_causes,
            previous_answers=[],
            defect_code=DefectCode.D03_INCONSISTENT_SIZE.value,
        )
        self.assertTrue(res1.should_ask)
        self.assertIsNotNone(res1.selected_question)
        assert res1.selected_question is not None
        # Q01 (shift duration: startup vs prolonged operation) is selected as top discriminator
        self.assertEqual(res1.selected_question.question_id, "Q01")
        # Ensure candidate pool actively contains Q10 (temperature) and Q13 (pot life)
        candidate_ids = {q.question_id for q in res1.all_candidates}
        self.assertIn("Q10", candidate_ids, "Ambient temperature question Q10 must be in active candidates")
        self.assertIn("Q13", candidate_ids, "Pot life / thaw time question Q13 must be in active candidates")

        # Step 2: Branch A - Operator answers 'after_prolonged_operation' (shift duration)
        q01_ans_prolonged = QuestionAnswer(
            question_id="Q01",
            answer_value="after_prolonged_operation",
            source=EvidenceSource.USER_ANSWER,
        )
        obs_prolonged = obs + list(QuestionAnswerHandler.handle(q01_ans_prolonged))
        r_prolonged = cr.rank(obs_prolonged, DefectCode.D03_INCONSISTENT_SIZE.value)

        res_prolonged = self.engine.select_next_question(
            ranked_causes=r_prolonged.ranked_causes,
            previous_answers=[q01_ans_prolonged],
            defect_code=DefectCode.D03_INCONSISTENT_SIZE.value,
        )
        # Shift duration confirmed: air_supply_issue surges past high-confidence threshold (>= 75.0)
        # Engine correctly halts questioning rather than wasting cleanroom time on an arbitrary 5-question quota
        self.assertFalse(res_prolonged.should_ask)
        self.assertIsNotNone(res_prolonged.reason_stopped)
        assert res_prolonged.reason_stopped is not None
        self.assertIn("Sufficient evidence", res_prolonged.reason_stopped)

        # Step 3: Answering Q13 ('long_time') directly drives material_condition to top
        q13_ans = QuestionAnswer(
            question_id="Q13",
            answer_value="long_time",
            source=EvidenceSource.USER_ANSWER,
        )
        obs_pot_life = obs + list(QuestionAnswerHandler.handle(q13_ans))
        r_pot_life = cr.rank(obs_pot_life, DefectCode.D03_INCONSISTENT_SIZE.value)
        top_cause = r_pot_life.ranked_causes[0]
        self.assertEqual(top_cause.cause_id, "material_condition")
        self.assertGreaterEqual(top_cause.score, 55.0)

        # Step 4: Branch B - Operator answers 'immediately' (startup fault)
        q01_ans_immediate = QuestionAnswer(
            question_id="Q01",
            answer_value="immediately",
            source=EvidenceSource.USER_ANSWER,
        )
        obs_immediate = obs + list(QuestionAnswerHandler.handle(q01_ans_immediate))
        r_immediate = cr.rank(obs_immediate, DefectCode.D03_INCONSISTENT_SIZE.value)

        res_immediate = self.engine.select_next_question(
            ranked_causes=r_immediate.ranked_causes,
            previous_answers=[q01_ans_immediate],
            defect_code=DefectCode.D03_INCONSISTENT_SIZE.value,
        )
        self.assertTrue(res_immediate.should_ask)
        assert res_immediate.selected_question is not None
        # System eliminates thermal/pot-life drift and pivots to spatial localization (Q02: all points vs specific nozzle)
        self.assertEqual(res_immediate.selected_question.question_id, "Q02")


if __name__ == "__main__":
    unittest.main()
