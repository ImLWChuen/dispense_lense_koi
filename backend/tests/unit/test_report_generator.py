"""
Unit tests for deterministic durable case report assembler.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.models.case import (
    AnalysisRevisionModel,
    CaseCauseConfirmationModel,
    CaseCheckResultModel,
    CaseLifecycleEventModel,
    CaseModel,
    ObservationModel,
    QuestionAnswerModel,
)
from app.schemas.diagnosis import (
    CandidateCause,
    CauseConclusion,
    CheckExecutionStatus,
    CheckFinding,
    DiagnosisResult,
    EvidenceSource,
    IssueCondition,
)
from app.services.reporting.report_generator import (
    _map_cause_confirmation,
    _map_check_result,
    _map_lifecycle_event,
    _map_question_answer,
    build_case_report,
)


def _make_dummy_case_model(
    case_id: str = "11111111-1111-4111-8111-111111111111",
    issue_condition: str = "UNRESOLVED",
) -> CaseModel:
    case = CaseModel()
    case.case_id = case_id
    case.description = "Test problem description"
    case.material = "Epoxy"
    case.method = "time_pressure"
    case.machine_context = {"pressure_kpa": 200}
    case.defect_code = "D03_INCONSISTENT_SIZE"
    case.defect_name = "Inconsistent Dot Size"
    case.issue_condition = issue_condition
    case.created_at = datetime(2026, 9, 15, 10, 0, 0, tzinfo=timezone.utc)
    return case


def _make_dummy_diagnosis_snapshot(
    case_id: str = "11111111-1111-4111-8111-111111111111",
    revision_number: int = 1,
    issue_condition: IssueCondition = IssueCondition.UNRESOLVED,
    confirmed_cause_id: str | None = None,
) -> dict:
    ranked_causes = [
        CandidateCause(
            cause_id="C01_FLUID_PRESSURE",
            cause_name="Fluid Pressure Inconsistency",
            score=0.85,
            conclusion=(
                CauseConclusion.CONFIRMED
                if confirmed_cause_id == "C01_FLUID_PRESSURE"
                else CauseConclusion.SUSPECTED
            ),
        ),
        CandidateCause(
            cause_id="C02_VISCOSITY",
            cause_name="Fluid Viscosity Fluctuation",
            score=0.45,
            conclusion=CauseConclusion.SUSPECTED,
        ),
    ]
    diag = DiagnosisResult(
        case_id=case_id,
        defect="D03_INCONSISTENT_SIZE",
        defect_name="Inconsistent Dot Size",
        ranked_causes=ranked_causes,
        issue_condition=issue_condition,
        explanation="Test explanation",
    )
    return diag.model_dump(mode="json")


def test_map_question_answer():
    qm = QuestionAnswerModel()
    qm.question_id = "Q01_TEMPERATURE"
    qm.answer_value = "yes"
    qm.answer_text = "Temperature rose slightly"
    qm.source = "USER"
    qm.answered_at = datetime(2026, 9, 15, 10, 5, 0, tzinfo=timezone.utc)
    qm.resulting_revision_number = 2

    record = _map_question_answer(qm)
    assert record.question_id == "Q01_TEMPERATURE"
    assert record.answer_value == "yes"
    assert record.answer_text == "Temperature rose slightly"
    assert record.source == EvidenceSource.USER
    assert record.answered_at == qm.answered_at
    assert record.resulting_revision_number == 2


def test_map_check_result():
    cm = CaseCheckResultModel()
    cm.check_id = "ACT01_CHECK_PRESSURE"
    cm.execution_status = "COMPLETED"
    cm.finding = "SUPPORTS"
    cm.finding_details = "Pressure gauge reading drifted"
    cm.outcome = "pressure_drop"
    cm.source = "USER_CHECK_RESULT"
    cm.checked_at = datetime(2026, 9, 15, 10, 10, 0, tzinfo=timezone.utc)
    cm.resulting_revision_number = 3

    record = _map_check_result(cm)
    assert record.check_id == "ACT01_CHECK_PRESSURE"
    assert record.execution_status == CheckExecutionStatus.COMPLETED
    assert record.finding == CheckFinding.SUPPORTS
    assert record.finding_details == "Pressure gauge reading drifted"
    assert record.outcome == "pressure_drop"
    assert record.resulting_revision_number == 3


def test_map_cause_confirmation():
    conf = CaseCauseConfirmationModel()
    conf.cause_id = "C01_FLUID_PRESSURE"
    conf.confirmed_by = "lead_tech"
    conf.notes = "Verified transducer fault"
    conf.confirmed_at = datetime(2026, 9, 15, 10, 15, 0, tzinfo=timezone.utc)
    conf.resulting_revision_number = 4

    record = _map_cause_confirmation(conf)
    assert record.cause_id == "C01_FLUID_PRESSURE"
    assert record.confirmed_by == "lead_tech"
    assert record.notes == "Verified transducer fault"
    assert record.resulting_revision_number == 4


def test_map_lifecycle_event():
    lc = CaseLifecycleEventModel()
    lc.id = 101
    lc.case_id = "11111111-1111-4111-8111-111111111111"
    lc.event_type = "RECOVERY_ACTION"
    lc.prior_issue_condition = "UNRESOLVED"
    lc.resulting_issue_condition = "RECOVERY_PENDING_VERIFICATION"
    lc.resulting_revision_number = 5
    lc.actor = "maintenance"
    lc.details = "Replaced pressure regulator"
    lc.verification_passed = None
    lc.created_at = datetime(2026, 9, 15, 10, 20, 0, tzinfo=timezone.utc)

    record = _map_lifecycle_event(lc)
    assert record.id == 101
    assert record.event_type == "RECOVERY_ACTION"
    assert record.prior_issue_condition == IssueCondition.UNRESOLVED
    assert record.resulting_issue_condition == IssueCondition.RECOVERY_PENDING_VERIFICATION
    assert record.resulting_revision_number == 5
    assert record.actor == "maintenance"
    assert record.verification_passed is None


def test_build_case_report_missing_case_returns_none():
    mock_repo = MagicMock()
    mock_repo.get_case.return_value = None

    report = build_case_report("nonexistent-case-id", mock_repo)
    assert report is None


def test_build_case_report_empty_history():
    case_id = "11111111-1111-4111-8111-111111111111"
    mock_repo = MagicMock()
    case_model = _make_dummy_case_model(case_id, issue_condition="UNRESOLVED")
    mock_repo.get_case.return_value = case_model

    rev_model = AnalysisRevisionModel()
    rev_model.revision_number = 1
    rev_model.analyzed_at = case_model.created_at
    rev_model.defect_code = case_model.defect_code
    rev_model.issue_condition = "UNRESOLVED"
    rev_model.result_snapshot = _make_dummy_diagnosis_snapshot(case_id, revision_number=1)

    mock_repo.get_latest_analysis_revision.return_value = rev_model
    mock_repo.get_case_question_answers.return_value = []
    mock_repo.get_case_check_results.return_value = []
    mock_repo.get_case_cause_confirmations.return_value = []
    mock_repo.get_case_lifecycle_events.return_value = []

    report = build_case_report(case_id, mock_repo)
    assert report is not None
    assert report.case_id == case_id
    assert report.current_revision == 1
    assert report.issue_condition == IssueCondition.UNRESOLVED
    assert report.description == "Test problem description"
    assert report.defect_code == "D03_INCONSISTENT_SIZE"
    assert report.material == "Epoxy"
    assert report.method == "time_pressure"
    assert report.question_answers == []
    assert report.check_results == []
    assert report.cause_confirmations == []
    assert report.lifecycle_events == []
    assert report.outcome_summary.confirmed_causes == []
    assert report.outcome_summary.is_resolved is False
    assert report.outcome_summary.current_revision == 1


def test_build_case_report_deterministic_ordering():
    case_id = "11111111-1111-4111-8111-111111111111"
    mock_repo = MagicMock()
    case_model = _make_dummy_case_model(case_id, issue_condition="RESOLVED")
    mock_repo.get_case.return_value = case_model

    rev_model = AnalysisRevisionModel()
    rev_model.revision_number = 6
    rev_model.analyzed_at = datetime(2026, 9, 15, 11, 0, 0, tzinfo=timezone.utc)
    rev_model.defect_code = case_model.defect_code
    rev_model.issue_condition = "RESOLVED"
    rev_model.result_snapshot = _make_dummy_diagnosis_snapshot(
        case_id,
        revision_number=6,
        issue_condition=IssueCondition.RESOLVED,
        confirmed_cause_id="C01_FLUID_PRESSURE",
    )
    mock_repo.get_latest_analysis_revision.return_value = rev_model

    # Intentionally provide out-of-order lists to verify report sorting
    qa1 = QuestionAnswerModel()
    qa1.question_id = "Q01"
    qa1.answer_value = "yes"
    qa1.source = "USER"
    qa1.answered_at = datetime(2026, 9, 15, 10, 5, 0, tzinfo=timezone.utc)
    qa1.resulting_revision_number = 2

    qa2 = QuestionAnswerModel()
    qa2.question_id = "Q02"
    qa2.answer_value = "no"
    qa2.source = "USER"
    qa2.answered_at = datetime(2026, 9, 15, 10, 7, 0, tzinfo=timezone.utc)
    qa2.resulting_revision_number = 3

    mock_repo.get_case_question_answers.return_value = [qa2, qa1]  # out of order

    cr1 = CaseCheckResultModel()
    cr1.check_id = "ACT01"
    cr1.execution_status = "COMPLETED"
    cr1.finding = "SUPPORTS"
    cr1.source = "USER_CHECK_RESULT"
    cr1.checked_at = datetime(2026, 9, 15, 10, 10, 0, tzinfo=timezone.utc)
    cr1.resulting_revision_number = 4

    mock_repo.get_case_check_results.return_value = [cr1]

    conf1 = CaseCauseConfirmationModel()
    conf1.cause_id = "C01_FLUID_PRESSURE"
    conf1.confirmed_by = "tech"
    conf1.confirmed_at = datetime(2026, 9, 15, 10, 12, 0, tzinfo=timezone.utc)
    conf1.resulting_revision_number = 5

    mock_repo.get_case_cause_confirmations.return_value = [conf1]

    lc1 = CaseLifecycleEventModel()
    lc1.id = 1
    lc1.case_id = case_id
    lc1.event_type = "RECOVERY_ACTION"
    lc1.prior_issue_condition = "UNRESOLVED"
    lc1.resulting_issue_condition = "RECOVERY_PENDING_VERIFICATION"
    lc1.resulting_revision_number = 5
    lc1.created_at = datetime(2026, 9, 15, 10, 15, 0, tzinfo=timezone.utc)

    lc2 = CaseLifecycleEventModel()
    lc2.id = 2
    lc2.case_id = case_id
    lc2.event_type = "RECOVERY_VERIFICATION"
    lc2.prior_issue_condition = "RECOVERY_PENDING_VERIFICATION"
    lc2.resulting_issue_condition = "RESOLVED"
    lc2.resulting_revision_number = 6
    lc2.verification_passed = True
    lc2.created_at = datetime(2026, 9, 15, 10, 20, 0, tzinfo=timezone.utc)

    mock_repo.get_case_lifecycle_events.return_value = [lc2, lc1]  # out of order

    report = build_case_report(case_id, mock_repo)
    assert report is not None

    # Assert sorted order
    assert [q.resulting_revision_number for q in report.question_answers] == [2, 3]
    assert [l.resulting_revision_number for l in report.lifecycle_events] == [5, 6]
    assert report.outcome_summary.confirmed_causes == ["C01_FLUID_PRESSURE"]
    assert report.outcome_summary.is_resolved is True
    assert report.outcome_summary.current_revision == 6


def test_build_case_report_pinned_revision_consistency():
    case_id = "11111111-1111-4111-8111-111111111111"
    mock_repo = MagicMock()
    # Case model has condition RECURRED (simulating a concurrent update to rev 7)
    case_model = _make_dummy_case_model(case_id, issue_condition="RECURRED")
    mock_repo.get_case.return_value = case_model

    # Target rev 6 is RESOLVED
    rev6_model = AnalysisRevisionModel()
    rev6_model.revision_number = 6
    rev6_model.analyzed_at = datetime(2026, 9, 15, 11, 0, 0, tzinfo=timezone.utc)
    rev6_model.defect_code = case_model.defect_code
    rev6_model.issue_condition = "RESOLVED"
    rev6_model.result_snapshot = _make_dummy_diagnosis_snapshot(
        case_id,
        revision_number=6,
        issue_condition=IssueCondition.RESOLVED,
    )
    mock_repo.get_analysis_revision.return_value = rev6_model
    mock_repo.get_case_question_answers.return_value = []
    mock_repo.get_case_check_results.return_value = []
    mock_repo.get_case_cause_confirmations.return_value = []
    mock_repo.get_case_lifecycle_events.return_value = []

    # Pin revision to 6
    report = build_case_report(case_id, mock_repo, pinned_revision=6)
    assert report is not None
    # Report condition MUST be RESOLVED (from rev 6), NOT RECURRED (from case_model)
    assert report.issue_condition == IssueCondition.RESOLVED
    assert report.current_revision == 6
    assert report.outcome_summary.issue_condition == IssueCondition.RESOLVED
    assert report.outcome_summary.current_revision == 6
    assert report.outcome_summary.is_resolved is True

    # Assert max_revision was passed to all history queries
    mock_repo.get_case_question_answers.assert_called_with(case_id, max_revision=6)
    mock_repo.get_case_check_results.assert_called_with(case_id, max_revision=6)
    mock_repo.get_case_cause_confirmations.assert_called_with(case_id, max_revision=6)
    mock_repo.get_case_lifecycle_events.assert_called_with(case_id, max_revision=6)
