"""
Unit tests for DiagnosticEngine.

Verifies:
1. prepare_case with question answers preserves answers and case state
2. Deterministic re-run (same input produces exact same output)
3. Revision immutability (historical revisions remain unchanged across multiple cycles)
"""

import copy
import os
import sys
import unittest

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.services.diagnosis.engine import DiagnosticEngine
from app.schemas.diagnosis import (
    DiagnosisRequest,
    EvidenceSource,
    Observation,
    ObservationType,
    QuestionAnswer,
    StructuredCase,
)


class TestDiagnosisEngine(unittest.TestCase):
    def setUp(self):
        self.engine = DiagnosticEngine()

    def test_prepare_case_with_question_answers(self):
        """Test that prepare_case correctly initializes a StructuredCase with answers."""
        answer = QuestionAnswer(
            question_id="Q01",
            answer_value="after_prolonged_operation",
            source=EvidenceSource.USER_ANSWER,
        )
        obs = Observation(
            observation_type=ObservationType.DEPOSIT_SIZE,
            value="undersized",
            source=EvidenceSource.USER,
        )
        req = DiagnosisRequest(
            description="Dots become smaller after prolonged operation",
            defect_code="D03_INCONSISTENT_SIZE",
            observations=[obs],
            previous_answers=[answer],
        )

        case = self.engine.prepare_case(req)
        self.assertIsInstance(case, StructuredCase)
        self.assertEqual(case.defect_code, "D03_INCONSISTENT_SIZE")
        self.assertEqual(len(case.observations), 1)
        self.assertEqual(len(case.previous_answers), 1)
        self.assertEqual(case.previous_answers[0].question_id, "Q01")
        self.assertEqual(case.previous_answers[0].answer_value, "after_prolonged_operation")

    def test_deterministic_rerun(self):
        """Test that running diagnosis on identical inputs yields 100% deterministic output."""
        req = DiagnosisRequest(
            description="The dispensing dots become smaller after running for 20 minutes.",
            defect_code="D03_INCONSISTENT_SIZE",
            observations=[
                Observation(
                    observation_type=ObservationType.DEPOSIT_SIZE,
                    value="undersized",
                    source=EvidenceSource.USER,
                ),
                Observation(
                    observation_type=ObservationType.RUNTIME_PATTERN,
                    value="after_prolonged_operation",
                    source=EvidenceSource.USER,
                ),
            ],
        )

        res1 = self.engine.diagnose(copy.deepcopy(req))
        res2 = self.engine.diagnose(copy.deepcopy(req))

        self.assertEqual(res1.defect, res2.defect)
        self.assertEqual(len(res1.ranked_causes), len(res2.ranked_causes))

        for c1, c2 in zip(res1.ranked_causes, res2.ranked_causes):
            self.assertEqual(c1.cause_id, c2.cause_id)
            self.assertAlmostEqual(c1.score, c2.score, places=4)
            self.assertEqual(c1.conclusion, c2.conclusion)

        if res1.next_question and res2.next_question:
            self.assertEqual(res1.next_question.question_id, res2.next_question.question_id)

    def test_revision_immutability(self):
        """Test that prior revisions in case.analysis_revisions remain immutable after re-ranking."""
        case = StructuredCase(
            case_id="test_case_immutability",
            description="Dots are smaller after 20 minutes",
            defect_code="D03_INCONSISTENT_SIZE",
            observations=[
                Observation(
                    observation_type=ObservationType.DEPOSIT_SIZE,
                    value="undersized",
                    source=EvidenceSource.USER,
                ),
            ],
        )

        # Initial diagnosis -> Revision 1
        res1 = self.engine.diagnose(case)
        self.assertEqual(len(case.analysis_revisions), 1)
        rev1 = case.analysis_revisions[0]
        rev1_num = rev1.revision_number
        rev1_scores = {c.cause_id: c.score for c in rev1.ranked_causes}

        # Technician submits an answer to Q02: all_points
        answer = QuestionAnswer(
            question_id="Q02",
            answer_value="all_points",
            source=EvidenceSource.USER_ANSWER,
        )
        case, res2 = self.engine.submit_question_answer(case, answer)

        # Check that Revision 2 exists and is distinct
        self.assertEqual(len(case.analysis_revisions), 2)
        rev2 = case.analysis_revisions[1]
        self.assertEqual(rev2.revision_number, rev1_num + 1)

        # CRITICAL CHECK: Revision 1 in history must be UNCHANGED
        rev1_stored = case.analysis_revisions[0]
        self.assertEqual(rev1_stored.revision_number, rev1_num)
        for c in rev1_stored.ranked_causes:
            self.assertEqual(c.score, rev1_scores[c.cause_id], f"Revision 1 score changed for {c.cause_id}")

    def test_intake_evidence_merge_both_text_and_image(self):
        """Verify intake merges independent text description symptoms and image observations once."""
        image_obs = Observation(
            observation_type=ObservationType.DEPOSIT_SIZE,
            value="undersized",
            source=EvidenceSource.IMAGE,
        )
        case = StructuredCase(
            description="pressure fluctuating across cycles",
            observations=[image_obs],
        )

        res = self.engine.diagnose(case)
        obs_types = {getattr(o.observation_type, "value", str(o.observation_type)) for o in case.observations}
        self.assertIn("deposit_size", obs_types)
        self.assertIn("pressure", obs_types)

        # Both observations should have contributed to ranking
        top_cause = res.ranked_causes[0]
        all_ev = top_cause.supporting_evidence + top_cause.contradicting_evidence + top_cause.neutral_evidence
        ev_sources = {getattr(e.source, "value", str(e.source)) for e in all_ev}
        self.assertTrue("IMAGE" in ev_sources or EvidenceSource.IMAGE.value in ev_sources)

    def test_intake_deduplication_exact_match(self):
        """Verify intake does not duplicate identical observations already provided."""
        image_obs = Observation(
            observation_type=ObservationType.DEPOSIT_SIZE,
            value="undersized",
            source=EvidenceSource.IMAGE,
        )
        case = StructuredCase(
            description="The dispensing dots are undersized.",
            observations=[image_obs],
        )

        res = self.engine.diagnose(case)
        deposit_size_obs = [
            o for o in case.observations
            if getattr(o.observation_type, "value", str(o.observation_type)) == "deposit_size"
        ]
        self.assertEqual(len(deposit_size_obs), 1)
        self.assertEqual(deposit_size_obs[0].source, EvidenceSource.IMAGE)

    def test_revisions_do_not_re_extract_description(self):
        """Verify follow-up diagnostic cycles do not re-extract the original description."""
        case = StructuredCase(
            case_id="test_case_no_re_extract",
            description="pressure fluctuating",
            observations=[],
        )
        res1 = self.engine.diagnose(case)
        initial_obs_count = len(case.observations)
        self.assertGreater(initial_obs_count, 0)

        # Diagnose again with revisions present
        res2 = self.engine.diagnose(case)
        self.assertEqual(len(case.observations), initial_obs_count)


if __name__ == "__main__":
    unittest.main()
