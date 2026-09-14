"""
Integration Test: Question Answer to Diagnosis Revision Full Flow.

Simulates the end-to-end Member 2 workflow for DLK-M3-012:
1. Create case with initial observations.
2. Run initial diagnosis (Revision 1).
3. Inspect recommended questions.
4. Submit answer through QuestionAnswerHandler.
5. Update case observations with structured observations.
6. Re-run diagnosis engine.
7. Assert Revision 2:
   - Updated cause scores and ranking.
   - New top question (or no question if confidence high / stopping condition met).
   - Previous revision (Revision 1) unchanged in history.
"""

import copy
import os
import sys
import unittest

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.schemas.diagnosis import (
    EvidenceSource,
    Observation,
    ObservationType,
    QuestionAnswer,
    StructuredCase,
)
from app.services.diagnosis.engine import DiagnosticEngine
from app.services.diagnosis.question_answer_handler import QuestionAnswerHandler


class TestQuestionAnswerDiagnosisRevision(unittest.TestCase):
    def setUp(self):
        self.engine = DiagnosticEngine()
        self.handler = QuestionAnswerHandler()

    def test_full_question_answer_revision_cycle(self):
        """Execute complete end-to-end cycle from initial diagnosis to answer-driven Revision 2."""

        # Step 1: Create case with initial symptom observation
        case = StructuredCase(
            case_id="case_integ_rev_001",
            description="The dispensing dots become smaller after running for 20 minutes.",
            defect_code="D03_INCONSISTENT_SIZE",
            observations=[
                Observation(
                    observation_type=ObservationType.DEPOSIT_SIZE,
                    value="undersized",
                    original_text="Dots become smaller",
                    source=EvidenceSource.USER,
                ),
            ],
        )

        # Step 2: Run initial diagnosis (Revision 1)
        res1 = self.engine.diagnose(case)
        self.assertIsNotNone(res1.analysis_revision)
        assert res1.analysis_revision is not None
        self.assertEqual(res1.analysis_revision.revision_number, 1)
        self.assertEqual(len(case.analysis_revisions), 1)

        # Snapshot Revision 1 state for immutability verification
        rev1_snapshot = {
            "rev_num": res1.analysis_revision.revision_number,
            "scores": {c.cause_id: c.score for c in res1.analysis_revision.ranked_causes},
            "order": [c.cause_id for c in res1.analysis_revision.ranked_causes],
        }

        # Step 3: Inspect recommended question
        self.assertIsNotNone(res1.next_question, "Initial diagnosis must recommend a discriminating question")
        assert res1.next_question is not None
        selected_q = res1.next_question
        q_id = selected_q.question_id
        self.assertIn(q_id, QuestionAnswerHandler.get_supported_questions())

        # Step 4: Submit technician answer through handler
        # For Q01: answer 'after_prolonged_operation', for others choose first allowed option
        allowed_options = QuestionAnswerHandler.get_allowed_answers(q_id)
        if "after_prolonged_operation" in allowed_options:
            answer_val = "after_prolonged_operation"
        else:
            answer_val = allowed_options[0]

        handler_result = self.handler.process_answer(
            question_id=q_id,
            answer_value=answer_val,
            source=EvidenceSource.USER_ANSWER,
        )
        self.assertGreater(len(handler_result), 0, f"Handler produced no observations for {q_id}={answer_val}")

        # Step 5: Update case observations and previous answers
        ans_record = QuestionAnswer(
            question_id=q_id,
            answer_value=answer_val,
            source=EvidenceSource.USER_ANSWER,
        )
        case.previous_answers.append(ans_record)
        for new_obs in handler_result:
            case.observations.append(new_obs)

        # Step 6: Re-run diagnosis engine
        res2 = self.engine.diagnose(case)

        # Step 7: Assert Revision 2 properties
        self.assertEqual(len(case.analysis_revisions), 2)
        rev2 = case.analysis_revisions[1]
        self.assertEqual(rev2.revision_number, 2)

        # 7a: Cause scores updated
        rev2_scores = {c.cause_id: c.score for c in rev2.ranked_causes}
        # At least one cause score should have changed based on the answer evidence
        scores_changed = any(
            rev2_scores.get(cid) != rev1_snapshot["scores"].get(cid)
            for cid in rev1_snapshot["scores"]
        )
        self.assertTrue(scores_changed, "Revision 2 should reflect updated scores from answer evidence")

        # 7b: Recommended question updated (or stopped)
        if res2.next_question is not None:
            self.assertNotEqual(
                res2.next_question.question_id,
                q_id,
                f"Question {q_id} was answered and should not be re-asked as top question",
            )

        # 7c: CRITICAL: Revision 1 in history remains completely unchanged
        rev1_history = case.analysis_revisions[0]
        self.assertEqual(rev1_history.revision_number, rev1_snapshot["rev_num"])
        for cid, score in rev1_snapshot["scores"].items():
            cause_in_history = next((c for c in rev1_history.ranked_causes if c.cause_id == cid), None)
            self.assertIsNotNone(cause_in_history)
            assert cause_in_history is not None
            self.assertEqual(
                cause_in_history.score,
                score,
                f"Historical Revision 1 score for {cid} was mutated from {score} to {cause_in_history.score}",
            )


if __name__ == "__main__":
    unittest.main()
