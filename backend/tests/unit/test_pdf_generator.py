"""Unit tests for deterministic downloadable PDF case report generator."""

from __future__ import annotations

import io
from datetime import datetime, timezone
import pypdf
import pytest

from app.schemas.case import (
    CaseOutcomeSummary,
    CaseReportResponse,
    CauseConfirmationRecord,
    CheckResultRecord,
    LifecycleEventRecord,
    QuestionAnswerRecord,
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
from app.services.reporting.pdf_generator import render_case_report_pdf


def _make_sample_report(
    case_id: str = "33333333-3333-4333-8333-333333333333",
    current_revision: int = 6,
    issue_condition: IssueCondition = IssueCondition.RESOLVED,
    with_history: bool = True,
    long_text: bool = False,
) -> CaseReportResponse:
    """Helper to build a valid CaseReportResponse fixture for testing."""
    desc = (
        "Dispense dots are shrinking over time during continuous high-speed operation. "
        * (10 if long_text else 1)
    )

    ranked_causes = [
        CandidateCause(
            cause_id="nozzle_restriction",
            cause_name="Nozzle Restriction / Clog",
            score=45.0,
            conclusion=CauseConclusion.CONFIRMED,
        ),
        CandidateCause(
            cause_id="air_entrapment",
            cause_name="Air Entrapment in Fluid Line",
            score=12.0,
            conclusion=CauseConclusion.SUSPECTED,
        ),
    ]

    diagnosis = DiagnosisResult(
        case_id=case_id,
        defect="D03_INCONSISTENT_SIZE",
        defect_name="Inconsistent Dot Size",
        ranked_causes=ranked_causes,
        issue_condition=issue_condition,
        explanation="Nozzle restriction is confirmed as primary root cause.",
    )

    outcome_summary = CaseOutcomeSummary(
        issue_condition=issue_condition,
        current_revision=current_revision,
        confirmed_causes=["nozzle_restriction"],
        currently_confirmed_causes=["nozzle_restriction"],
        is_resolved=(issue_condition == IssueCondition.RESOLVED),
        resolved=(issue_condition == IssueCondition.RESOLVED),
    )

    if with_history:
        qas = [
            QuestionAnswerRecord(
                question_id="Q01",
                answer_value="after_prolonged_operation",
                answer_text="Dots shrink after 30 minutes of continuous dispensing",
                source=EvidenceSource.USER,
                answered_at=datetime(2026, 9, 14, 10, 5, 0, tzinfo=timezone.utc),
                resulting_revision_number=2,
            )
        ]
        crs = [
            CheckResultRecord(
                check_id="ACT02",
                execution_status=CheckExecutionStatus.COMPLETED,
                finding=CheckFinding.SUPPORTS,
                finding_details="Observed partial blockage in fluid orifice",
                outcome="debris_in_orifice",
                source=EvidenceSource.USER_CHECK_RESULT,
                checked_at=datetime(2026, 9, 14, 10, 10, 0, tzinfo=timezone.utc),
                resulting_revision_number=3,
            )
        ]
        ccs = [
            CauseConfirmationRecord(
                cause_id="nozzle_restriction",
                confirmed_by="lead_tech",
                notes="Verified restriction via optical inspection",
                confirmed_at=datetime(2026, 9, 14, 10, 12, 0, tzinfo=timezone.utc),
                resulting_revision_number=4,
            )
        ]
        lcs = [
            LifecycleEventRecord(
                case_id=case_id,
                event_type="RECOVERY_ACTION",
                prior_issue_condition=IssueCondition.UNRESOLVED,
                resulting_issue_condition=IssueCondition.RECOVERY_PENDING_VERIFICATION,
                resulting_revision_number=5,
                actor="technician_dan",
                details="Replaced fluid syringe and cleaned dispense nozzle",
                verification_passed=None,
                created_at=datetime(2026, 9, 14, 10, 15, 0, tzinfo=timezone.utc),
            ),
            LifecycleEventRecord(
                case_id=case_id,
                event_type="RECOVERY_VERIFICATION",
                prior_issue_condition=IssueCondition.RECOVERY_PENDING_VERIFICATION,
                resulting_issue_condition=IssueCondition.RESOLVED,
                resulting_revision_number=6,
                actor="qa_engineer",
                details="100 test shots verified within nominal dot tolerance",
                verification_passed=True,
                created_at=datetime(2026, 9, 14, 10, 20, 0, tzinfo=timezone.utc),
            ),
        ]
    else:
        qas, crs, ccs, lcs = [], [], [], []

    return CaseReportResponse(
        case_id=case_id,
        current_revision=current_revision,
        defect_code="D03_INCONSISTENT_SIZE",
        defect_name="Inconsistent Dot Size",
        description=desc,
        material="solder_paste",
        method="jetting",
        machine_context={"line": "Line A", "temperature_c": 24.5},
        issue_condition=issue_condition,
        created_at=datetime(2026, 9, 14, 10, 0, 0, tzinfo=timezone.utc),
        current_diagnosis=diagnosis,
        diagnosis=diagnosis,
        question_answers=qas,
        question_answer_history=qas,
        check_results=crs,
        troubleshooting_check_history=crs,
        cause_confirmations=ccs,
        cause_confirmation_history=ccs,
        lifecycle_events=lcs,
        issue_lifecycle_history=lcs,
        outcome_summary=outcome_summary,
        current_outcome_summary=outcome_summary,
    )


def test_render_case_report_pdf_valid_bytes_and_structure():
    """Verify that a rich report renders into valid, parseable PDF bytes with expected content."""
    report = _make_sample_report(with_history=True)
    pdf_bytes = render_case_report_pdf(report)

    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-"), "Generated file does not have PDF magic header"
    assert len(pdf_bytes) > 1000

    # Parse with pypdf
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) >= 1

    extracted_text = "\n".join(page.extract_text() or "" for page in reader.pages)

    # Assert major title and headers
    assert "DispenseIQ Diagnostic Case Report" in extracted_text
    assert report.case_id in extracted_text
    assert f"Report Revision: {report.current_revision}" in extracted_text or f"Revision {report.current_revision}" in extracted_text
    assert "1. Case Identity & Process Context" in extracted_text
    assert "2. Current Outcome Summary" in extracted_text
    assert "3. Current Diagnosis Snapshot" in extracted_text
    assert "4. Technician Question-Answer History" in extracted_text
    assert "5. Troubleshooting-Check History" in extracted_text
    assert "6. Cause-Confirmation History" in extracted_text
    assert "7. Issue Lifecycle History" in extracted_text

    # Assert specific content values
    assert "D03_INCONSISTENT_SIZE" in extracted_text
    assert "Inconsistent Dot Size" in extracted_text
    assert "RESOLVED" in extracted_text
    assert "nozzle_restriction" in extracted_text
    assert "Nozzle Restriction / Clog" in extracted_text
    assert "Q01" in extracted_text
    assert "after_prolonged_operation" in extracted_text
    assert "ACT02" in extracted_text
    assert "lead_tech" in extracted_text
    assert "technician_dan" in extracted_text
    assert "qa_engineer" in extracted_text


def test_render_case_report_pdf_empty_history():
    """Verify that an empty history case renders cleanly with neutral 'None recorded' notices."""
    report = _make_sample_report(with_history=False, current_revision=1, issue_condition=IssueCondition.UNRESOLVED)
    pdf_bytes = render_case_report_pdf(report)

    assert pdf_bytes.startswith(b"%PDF-")
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) >= 1

    extracted_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "DispenseIQ Diagnostic Case Report" in extracted_text
    assert "UNRESOLVED" in extracted_text
    # Should display neutral notices for empty tables
    assert "None recorded." in extracted_text


def test_render_case_report_pdf_long_text_wrapping_and_escaping():
    """Verify that long descriptions with special characters wrap properly and do not crash the engine."""
    report = _make_sample_report(long_text=True)
    # Inject special characters that would break unescaped XML/HTML in ReportLab
    report.description = "Critical error <>&\"' with abnormal fluid overflow: " + ("x" * 600)
    pdf_bytes = render_case_report_pdf(report)

    assert pdf_bytes.startswith(b"%PDF-")
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) >= 1
    extracted_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Critical error" in extracted_text


def test_render_case_report_pdf_multi_page_and_page_numbering():
    """Verify multi-page PDF generation and dynamic 'Page X of Y' page numbering."""
    report = _make_sample_report(with_history=True)

    # Multiply history items to force multi-page document
    expanded_qas = list(report.question_answers) * 15
    report.question_answers = expanded_qas
    report.question_answer_history = expanded_qas

    expanded_crs = list(report.check_results) * 15
    report.check_results = expanded_crs
    report.troubleshooting_check_history = expanded_crs

    pdf_bytes = render_case_report_pdf(report)
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))

    # Should span multiple pages
    assert len(reader.pages) > 1, f"Expected > 1 pages, got {len(reader.pages)}"
    total_pages = len(reader.pages)

    # Check that each page has the expected header and footer text
    page1_text = reader.pages[0].extract_text()
    assert f"Page 1 of {total_pages}" in page1_text
    assert "DispenseIQ Diagnostic Automation System" in page1_text

    last_page_text = reader.pages[-1].extract_text()
    assert f"Page {total_pages} of {total_pages}" in last_page_text
