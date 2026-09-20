"""
Unit tests for AIAG / VDA Standardized 8D Quality Report Service and PDF Generator.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.models.case import (
    AnalysisRevisionModel,
    CaseCauseConfirmationModel,
    CaseLifecycleEventModel,
    CaseModel,
    QuestionAnswerModel,
    CaseCheckResultModel,
    ObservationModel,
)
from app.schemas.quality_8d import EightDReportResponse
from app.services.reporting.eight_d_service import build_8d_report
from app.services.reporting.eight_d_pdf_generator import render_8d_report_pdf


def _make_test_case() -> CaseModel:
    case = CaseModel()
    case.case_id = "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d"
    case.description = "Adhesive bead diameter fluctuates across 0402 pads on Line A."
    case.material = "UV-Curable Epoxy (Loctite 3922)"
    case.method = "jetting"
    case.machine_context = {"machine_id": "Line A - Jetting Unit 01", "pressure_kpa": 240}
    case.defect_code = "D01"
    case.defect_name = "Tailing / Stringing"
    case.issue_condition = "RESOLVED"
    case.created_at = datetime(2026, 9, 15, 10, 0, 0, tzinfo=timezone.utc)
    return case


def _mock_repository_for_8d():
    repo = MagicMock()
    case = _make_test_case()
    repo.get_case.return_value = case

    # Revision 1 with ranked causes
    rev = AnalysisRevisionModel()
    rev.case_id = case.case_id
    rev.revision_number = 1
    rev.created_at = datetime(2026, 9, 15, 10, 5, 0, tzinfo=timezone.utc)
    rev.result_snapshot = {
        "case_id": case.case_id,
        "defect": "D01",
        "defect_name": "Tailing / Stringing",
        "issue_condition": "RESOLVED",
        "explanation": "High restriction detected at orifice.",
        "ranked_causes": [
            {
                "cause_id": "nozzle_restriction",
                "cause_name": "Nozzle Restriction",
                "score": 0.92,
                "probability": 0.92,
                "confidence": 0.92,
                "explanation": "High restriction detected at orifice.",
            }
        ],
        "candidate_actions": [
            {
                "action_id": "ACT01",
                "action_name": "Ultrasonic Nozzle Clean",
                "description": "Submerge nozzle in solvent and cycle ultrasonic bath for 5 minutes.",
            }
        ],
    }
    repo.get_latest_analysis_revision.return_value = rev
    repo.get_analysis_revision.return_value = rev
    repo.get_revisions.return_value = [rev]

    # Cause confirmation
    conf = CaseCauseConfirmationModel()
    conf.id = 1
    conf.case_id = case.case_id
    conf.cause_id = "nozzle_restriction"
    conf.confirmed_by = "Elena Chen, PE"
    conf.notes = "Partial dried meniscus verified on tip under 50x microscope."
    conf.confirmed_at = datetime(2026, 9, 15, 10, 15, 0, tzinfo=timezone.utc)
    conf.resulting_revision_number = 2
    repo.get_cause_confirmations.return_value = [conf]
    repo.get_case_cause_confirmations.return_value = [conf]

    # Questions & Checks
    qa = QuestionAnswerModel()
    qa.id = 1
    qa.case_id = case.case_id
    qa.question_id = "Q_NOZZLE_VISUAL"
    qa.answer_value = "yes"
    qa.answer_text = "Yes, residue visible on orifice."
    qa.source = "technician"
    qa.answered_at = datetime(2026, 9, 15, 10, 2, 0, tzinfo=timezone.utc)
    qa.resulting_revision_number = 1
    repo.get_question_answers.return_value = [qa]
    repo.get_case_question_answers.return_value = [qa]

    cr = CaseCheckResultModel()
    cr.id = 1
    cr.case_id = case.case_id
    cr.check_id = "CHK_ORIFICE_INSPECT"
    cr.finding = "Confirmed residue at orifice"
    cr.execution_status = "COMPLETED"
    cr.source = "USER_CHECK_RESULT"
    cr.checked_at = datetime(2026, 9, 15, 10, 10, 0, tzinfo=timezone.utc)
    cr.resulting_revision_number = 2
    repo.get_check_results.return_value = [cr]
    repo.get_case_check_results.return_value = [cr]

    # Lifecycle events
    ev_res = CaseLifecycleEventModel()
    ev_res.id = 1
    ev_res.case_id = case.case_id
    ev_res.event_type = "CASE_RESOLVED"
    ev_res.prior_issue_condition = "RECOVERY_PENDING_VERIFICATION"
    ev_res.resulting_issue_condition = "RESOLVED"
    ev_res.resulting_revision_number = 3
    ev_res.actor = "Elena Chen, PE"
    ev_res.details = "30-shot test coupon pass. Cpk > 1.67."
    ev_res.verification_passed = True
    ev_res.created_at = datetime(2026, 9, 15, 11, 0, 0, tzinfo=timezone.utc)
    repo.get_lifecycle_events.return_value = [ev_res]
    repo.get_case_lifecycle_events.return_value = [ev_res]

    return repo


def test_build_8d_report_success():
    repo = _mock_repository_for_8d()
    report = build_8d_report("a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d", repo)

    assert report is not None
    assert isinstance(report, EightDReportResponse)
    assert report.report_number == "8D-RPT-A1B2C3D4"
    assert report.case_ref == "DSP-A1B2C3D4"
    assert report.is_resolved is True

    # D1
    assert report.d1_team.champion.name == "Dr. Marcus Vance"
    assert report.d1_team.team_leader.name == "Elena Chen, PE"
    assert len(report.d1_team.members) >= 3

    # D2
    assert "D01" in report.d2_problem_description.defect_code
    assert "UV-Curable" in report.d2_problem_description.fluid_material

    # D3
    assert report.d3_containment.containment_status == "CONTAINED"
    assert len(report.d3_containment.actions) == 3

    # D4
    assert report.d4_root_cause.root_cause_id == "nozzle_restriction"
    assert len(report.d4_root_cause.five_whys) == 5
    assert report.d4_root_cause.ishikawa_category == "Machine"

    # D5
    assert len(report.d5_corrective_actions.selected_actions) >= 1
    assert report.d5_corrective_actions.fmea_initial_rpn == 240

    # D6
    assert report.d6_validation.implementation_status == "VERIFIED_PASS"
    assert report.d6_validation.cpk_validation >= 1.67

    # D7
    assert report.d7_prevent_recurrence.pfmea_revised_rpn == 48

    # D8
    assert report.d8_closure.resolution_status == "RESOLVED"
    assert report.d8_closure.closure_date == "2026-09-15"


def test_render_8d_report_pdf():
    repo = _mock_repository_for_8d()
    report = build_8d_report("a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d", repo)
    assert report is not None

    pdf_bytes = render_8d_report_pdf(report)
    assert pdf_bytes is not None
    assert len(pdf_bytes) > 2000
    assert pdf_bytes.startswith(b"%PDF")


def test_8d_report_with_opencv_vision_and_telemetry():
    """Verify that 8D report integrates real OpenCV image metrology and physical cleanroom telemetry."""
    repo = _mock_repository_for_8d()
    case = repo.get_case.return_value

    # Attach OpenCV image observation
    img_obs = ObservationModel()
    img_obs.id = 1
    img_obs.case_id = case.case_id
    img_obs.observation_id = "obs_img_001"
    img_obs.observation_type = "deposit_size"
    img_obs.value = "undersized"
    img_obs.source = "IMAGE"
    img_obs.statement_type = "AI_INFERENCE"
    img_obs.observation_metadata = {
        "roi_id": "roi_1",
        "coverage_ratio": 0.118,
        "calibrated_diameter_mm": 0.41,
        "deposit_area_px": 380,
    }
    img_obs.created_at = datetime(2026, 9, 15, 10, 1, 0, tzinfo=timezone.utc)
    case.observations = [img_obs]

    report = build_8d_report(case.case_id, repo)
    assert report is not None

    # D2 Problem Description includes OpenCV metrology
    assert "OpenCV Vision Metrology" in report.d2_problem_description.what
    assert "deposit_size = 'undersized'" in report.d2_problem_description.what
    assert "Calibrated Dia: 0.41mm" in report.d2_problem_description.what

    # D2 Operational Context includes live physical telemetry
    ctx = report.d2_problem_description.operational_context
    assert "cleanroom_ambient" in ctx
    assert "fluid_feed_pressure" in ctx
    assert "nozzle_heater_temp" in ctx
    assert "active_syringe_lot" in ctx

    # D4 Evidence Summary includes OpenCV and cleanroom telemetry
    ev_summary = " ".join(report.d4_root_cause.evidence_summary)
    assert "OpenCV Vision Metrology" in ev_summary
    assert "Physical Cleanroom Telemetry" in ev_summary

    # PDF renders with enriched real data
    pdf_bytes = render_8d_report_pdf(report)
    assert pdf_bytes is not None
    assert len(pdf_bytes) > 2000
