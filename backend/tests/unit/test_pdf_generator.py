"""Unit tests for deterministic downloadable PDF case report generator."""

from __future__ import annotations

import copy
import io
from datetime import datetime, timezone
from typing import Any
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
    CauseEvidence,
    CheckExecutionStatus,
    CheckFinding,
    DiagnosisResult,
    EvidenceRelation,
    EvidenceSource,
    EvidenceStrength,
    IssueCondition,
    Question,
    TroubleshootingCheck,
)
from app.services.reporting.pdf_generator import render_case_report_pdf


def _make_sample_report(
    case_id: str = "33333333-3333-4333-8333-333333333333",
    current_revision: int = 12,
    issue_condition: IssueCondition = IssueCondition.RECURRED,
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
            supporting_evidence=[
                CauseEvidence(
                    observation_id="obs_001",
                    cause_id="nozzle_restriction",
                    relation=EvidenceRelation.SUPPORTS,
                    strength=EvidenceStrength.STRONG,
                    source=EvidenceSource.USER,
                    explanation="Restricted orifice directly causes undersized deposits.",
                    score_contribution=20.0,
                )
            ] if with_history else [],
            neutral_evidence=[
                CauseEvidence(
                    observation_id="obs_002",
                    cause_id="nozzle_restriction",
                    relation=EvidenceRelation.NEUTRAL,
                    strength=EvidenceStrength.WEAK,
                    source=EvidenceSource.USER,
                    explanation="Material color is nominal.",
                    score_contribution=0.0,
                )
            ] if with_history else [],
        ),
        CandidateCause(
            cause_id="air_entrapment",
            cause_name="Air Entrapment in Fluid Line",
            score=12.0,
            conclusion=CauseConclusion.SUSPECTED,
            contradicting_evidence=[
                CauseEvidence(
                    observation_id="obs_003",
                    cause_id="air_entrapment",
                    relation=EvidenceRelation.CONTRADICTS,
                    strength=EvidenceStrength.MODERATE,
                    source=EvidenceSource.USER_CHECK_RESULT,
                    explanation="No bubbles observed in syringe barrel.",
                    score_contribution=-8.0,
                )
            ] if with_history else [],
        ),
    ]

    next_q = (
        Question(
            question_id="Q01",
            text="Does the defect worsen over prolonged continuous run?",
            options=["YES", "NO", "UNKNOWN"],
            purpose="Differentiates thermal/viscosity drift from static clog.",
        )
        if with_history
        else None
    )

    next_c = (
        TroubleshootingCheck(
            check_id="ACT04",
            name="Inspect Syringe Pressure Gauge",
            description="Verify actual manifold pressure matches setpoint.",
            procedure="Read analog gauge and log values.",
        )
        if with_history
        else None
    )

    diagnosis = DiagnosisResult(
        case_id=case_id,
        defect="D03_INCONSISTENT_SIZE",
        defect_name="Inconsistent Dot Size",
        ranked_causes=ranked_causes,
        issue_condition=issue_condition,
        explanation="Nozzle restriction is confirmed as primary root cause." if with_history else "",
        next_question=next_q,
        next_check=next_c,
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
                answer_text="Dots shrink after 30 min",
                source=EvidenceSource.USER,
                answered_at=datetime(2026, 9, 14, 10, 5, 0, tzinfo=timezone.utc),
                resulting_revision_number=2,
            ),
            QuestionAnswerRecord(
                question_id="Q01",
                answer_value="immediately",
                answer_text="Clarified: shrinking starts immediately on cold startup",
                source=EvidenceSource.USER,
                answered_at=datetime(2026, 9, 14, 10, 8, 0, tzinfo=timezone.utc),
                resulting_revision_number=3,
            ),
        ]
        crs = [
            CheckResultRecord(
                check_id="ACT02",
                execution_status=CheckExecutionStatus.COMPLETED,
                finding=CheckFinding.SUPPORTS,
                finding_details="Trapped air bubbles observed in syringe barrel",
                outcome="air_bubbles_found",
                source=EvidenceSource.USER_CHECK_RESULT,
                checked_at=datetime(2026, 9, 14, 10, 10, 0, tzinfo=timezone.utc),
                resulting_revision_number=4,
            ),
            CheckResultRecord(
                check_id="ACT02",
                execution_status=CheckExecutionStatus.COMPLETED,
                finding=CheckFinding.CONTRADICTS,
                finding_details="After fluid purge, syringe material inspected normal",
                outcome="material_normal",
                source=EvidenceSource.USER_CHECK_RESULT,
                checked_at=datetime(2026, 9, 14, 10, 12, 0, tzinfo=timezone.utc),
                resulting_revision_number=5,
            ),
        ]
        ccs = [
            CauseConfirmationRecord(
                cause_id="nozzle_restriction",
                confirmed_by="lead_tech",
                notes="Initial optical microscope inspection confirmed blockage",
                confirmed_at=datetime(2026, 9, 14, 10, 14, 0, tzinfo=timezone.utc),
                resulting_revision_number=6,
            ),
            CauseConfirmationRecord(
                cause_id="nozzle_restriction",
                confirmed_by="senior_tech",
                notes="Secondary confirmation via flow meter differential pressure",
                confirmed_at=datetime(2026, 9, 14, 10, 16, 0, tzinfo=timezone.utc),
                resulting_revision_number=7,
            ),
        ]
        lcs = [
            LifecycleEventRecord(
                case_id=case_id,
                event_type="RECOVERY_ACTION",
                prior_issue_condition=IssueCondition.UNRESOLVED,
                resulting_issue_condition=IssueCondition.RECOVERY_PENDING_VERIFICATION,
                resulting_revision_number=8,
                actor="tech_dan",
                details="Cleaned nozzle orifice with ultrasonic bath",
                verification_passed=None,
                created_at=datetime(2026, 9, 14, 10, 18, 0, tzinfo=timezone.utc),
            ),
            LifecycleEventRecord(
                case_id=case_id,
                event_type="RECOVERY_VERIFICATION",
                prior_issue_condition=IssueCondition.RECOVERY_PENDING_VERIFICATION,
                resulting_issue_condition=IssueCondition.UNRESOLVED,
                resulting_revision_number=9,
                actor="qa_sarah",
                details="50 test shots showed persistent dot shrinkage",
                verification_passed=False,
                created_at=datetime(2026, 9, 14, 10, 20, 0, tzinfo=timezone.utc),
            ),
            LifecycleEventRecord(
                case_id=case_id,
                event_type="RECOVERY_ACTION",
                prior_issue_condition=IssueCondition.UNRESOLVED,
                resulting_issue_condition=IssueCondition.RECOVERY_PENDING_VERIFICATION,
                resulting_revision_number=10,
                actor="tech_alex",
                details="Replaced entire nozzle assembly and syringe barrel",
                verification_passed=None,
                created_at=datetime(2026, 9, 14, 10, 22, 0, tzinfo=timezone.utc),
            ),
            LifecycleEventRecord(
                case_id=case_id,
                event_type="RECOVERY_VERIFICATION",
                prior_issue_condition=IssueCondition.RECOVERY_PENDING_VERIFICATION,
                resulting_issue_condition=IssueCondition.RESOLVED,
                resulting_revision_number=11,
                actor="qa_sarah",
                details="100 test shots verified within nominal dot tolerance",
                verification_passed=True,
                created_at=datetime(2026, 9, 14, 10, 24, 0, tzinfo=timezone.utc),
            ),
            LifecycleEventRecord(
                case_id=case_id,
                event_type="RECURRENCE",
                prior_issue_condition=IssueCondition.RESOLVED,
                resulting_issue_condition=IssueCondition.RECURRED,
                resulting_revision_number=12,
                actor="operator_bob",
                details="Dot size shrinking re-observed on shift 3 after continuous run",
                verification_passed=None,
                created_at=datetime(2026, 9, 14, 10, 26, 0, tzinfo=timezone.utc),
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


def extract_pdf_history_sections(pdf_bytes: bytes) -> dict[str, str]:
    """Extract and isolate text strictly scoped to each history section."""
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    full_text = "\n".join(page.extract_text() or "" for page in reader.pages)

    sec4_marker = "4. Technician Question-Answer History"
    sec5_marker = "5. Troubleshooting-Check History"
    sec6_marker = "6. Cause-Confirmation History"
    sec7_marker = "7. Issue Lifecycle History"

    p4 = full_text.find(sec4_marker)
    p5 = full_text.find(sec5_marker)
    p6 = full_text.find(sec6_marker)
    p7 = full_text.find(sec7_marker)

    assert p4 != -1, f"Section 4 marker '{sec4_marker}' not found in PDF"
    assert p5 != -1, f"Section 5 marker '{sec5_marker}' not found in PDF"
    assert p6 != -1, f"Section 6 marker '{sec6_marker}' not found in PDF"
    assert p7 != -1, f"Section 7 marker '{sec7_marker}' not found in PDF"
    assert p4 < p5 < p6 < p7, f"Section headings not sequential: {p4} < {p5} < {p6} < {p7}"

    return {
        "question_answers": full_text[p4:p5],
        "check_results": full_text[p5:p6],
        "cause_confirmations": full_text[p6:p7],
        "lifecycle_events": full_text[p7:],
    }


def verify_question_answers_section(section_text: str, qas: list[Any]) -> None:
    """Verify complete row values and order against question_answers report array."""
    norm_text = " ".join(section_text.split())
    expected_header = f"Question Answers ({len(qas)})"
    if expected_header not in norm_text:
        raise AssertionError(f"Expected count header '{expected_header}' not found in section text")

    last_pos = -1
    for idx, qa in enumerate(qas, start=1):
        qid = qa["question_id"] if isinstance(qa, dict) else qa.question_id
        ans = qa["answer_value"] if isinstance(qa, dict) else qa.answer_value
        src = qa["source"] if isinstance(qa, dict) else (qa.source.value if hasattr(qa.source, "value") else str(qa.source))
        rev = str(qa["resulting_revision_number"] if isinstance(qa, dict) else qa.resulting_revision_number)

        pos_qid = norm_text.find(qid, last_pos + 1)
        if pos_qid == -1:
            raise AssertionError(f"Row {idx} ({qid}): question_id not found after pos {last_pos}")
        pos_ans = norm_text.find(ans, pos_qid)
        if pos_ans == -1:
            raise AssertionError(f"Row {idx} ({qid}): answer_value '{ans}' not found after pos {pos_qid}")
        pos_src = norm_text.find(src, pos_ans)
        if pos_src == -1:
            raise AssertionError(f"Row {idx} ({qid}): source '{src}' not found after pos {pos_ans}")
        pos_rev = norm_text.find(rev, pos_src)
        if pos_rev == -1:
            raise AssertionError(f"Row {idx} ({qid}): rev '{rev}' not found after pos {pos_src}")

        ans_txt = qa.get("answer_text") if isinstance(qa, dict) else getattr(qa, "answer_text", None)
        if ans_txt and ans_txt != ans:
            key_phrase = ans_txt.split()[0]
            if key_phrase not in norm_text[pos_qid:pos_src]:
                raise AssertionError(f"Row {idx} ({qid}): answer_text token '{key_phrase}' not found in row text")

        last_pos = pos_qid


def verify_check_results_section(section_text: str, crs: list[Any]) -> None:
    """Verify complete row values and order against check_results report array."""
    norm_text = " ".join(section_text.split())
    expected_header = f"Troubleshooting Checks ({len(crs)})"
    if expected_header not in norm_text:
        raise AssertionError(f"Expected count header '{expected_header}' not found in section text")

    last_pos = -1
    for idx, cr in enumerate(crs, start=1):
        cid = cr["check_id"] if isinstance(cr, dict) else cr.check_id
        status_val = cr["execution_status"] if isinstance(cr, dict) else (cr.execution_status.value if hasattr(cr.execution_status, "value") else str(cr.execution_status))
        finding = cr["finding"] if isinstance(cr, dict) else (cr.finding.value if hasattr(cr.finding, "value") else str(cr.finding))
        rev = str(cr["resulting_revision_number"] if isinstance(cr, dict) else cr.resulting_revision_number)
        outcome = cr.get("outcome") if isinstance(cr, dict) else getattr(cr, "outcome", None)
        details = cr.get("finding_details") if isinstance(cr, dict) else getattr(cr, "finding_details", None)

        pos_cid = norm_text.find(cid, last_pos + 1)
        if pos_cid == -1:
            raise AssertionError(f"Row {idx} ({cid}): check_id not found after pos {last_pos}")
        pos_status = norm_text.find(status_val, pos_cid)
        if pos_status == -1:
            raise AssertionError(f"Row {idx} ({cid}): execution_status '{status_val}' not found after pos {pos_cid}")
        pos_finding = norm_text.find(finding, pos_status)
        if pos_finding == -1:
            raise AssertionError(f"Row {idx} ({cid}): finding '{finding}' not found after pos {pos_status}")
        if outcome:
            pos_out = norm_text.find(outcome, pos_finding)
            if pos_out == -1:
                raise AssertionError(f"Row {idx} ({cid}): outcome '{outcome}' not found after pos {pos_finding}")
        if details:
            key_phrase = details.split()[0]
            pos_det = norm_text.find(key_phrase, pos_finding)
            if pos_det == -1:
                raise AssertionError(f"Row {idx} ({cid}): finding_details token '{key_phrase}' not found after pos {pos_finding}")
        pos_rev = norm_text.find(rev, pos_finding)
        if pos_rev == -1:
            raise AssertionError(f"Row {idx} ({cid}): rev '{rev}' not found after pos {pos_finding}")

        last_pos = pos_cid


def verify_cause_confirmations_section(section_text: str, ccs: list[Any]) -> None:
    """Verify complete row values and order against cause_confirmations report array."""
    norm_text = " ".join(section_text.split())
    expected_header = f"Cause Confirmations ({len(ccs)})"
    if expected_header not in norm_text:
        raise AssertionError(f"Expected count header '{expected_header}' not found in section text")

    last_pos = -1
    for idx, cc in enumerate(ccs, start=1):
        cause_id = cc["cause_id"] if isinstance(cc, dict) else cc.cause_id
        conf_by = cc["confirmed_by"] if isinstance(cc, dict) else cc.confirmed_by
        rev = str(cc["resulting_revision_number"] if isinstance(cc, dict) else cc.resulting_revision_number)
        notes = cc.get("notes") if isinstance(cc, dict) else getattr(cc, "notes", None)

        pos_cause = norm_text.find(cause_id, last_pos + 1)
        if pos_cause == -1:
            raise AssertionError(f"Row {idx} ({cause_id}): cause_id not found after pos {last_pos}")
        pos_by = norm_text.find(conf_by, pos_cause)
        if pos_by == -1:
            raise AssertionError(f"Row {idx} ({cause_id}): confirmed_by '{conf_by}' not found after pos {pos_cause}")
        if notes:
            key_phrase = notes.split()[0]
            pos_notes = norm_text.find(key_phrase, pos_by)
            if pos_notes == -1:
                raise AssertionError(f"Row {idx} ({cause_id}): notes token '{key_phrase}' not found after pos {pos_by}")
        pos_rev = norm_text.find(rev, pos_by)
        if pos_rev == -1:
            raise AssertionError(f"Row {idx} ({cause_id}): rev '{rev}' not found after pos {pos_by}")

        last_pos = pos_cause


def verify_lifecycle_events_section(section_text: str, lcs: list[Any]) -> None:
    """Verify complete row values and order against lifecycle_events report array."""
    norm_text = " ".join(section_text.split())
    expected_header = f"Lifecycle Events ({len(lcs)})"
    if expected_header not in norm_text:
        raise AssertionError(f"Expected count header '{expected_header}' not found in section text")

    last_pos = -1
    for idx, lc in enumerate(lcs, start=1):
        ev_type = lc["event_type"] if isinstance(lc, dict) else lc.event_type
        prior = lc["prior_issue_condition"] if isinstance(lc, dict) else (lc.prior_issue_condition.value if hasattr(lc.prior_issue_condition, "value") else str(lc.prior_issue_condition))
        res = lc["resulting_issue_condition"] if isinstance(lc, dict) else (lc.resulting_issue_condition.value if hasattr(lc.resulting_issue_condition, "value") else str(lc.resulting_issue_condition))
        actor = lc["actor"] if isinstance(lc, dict) else lc.actor
        rev = str(lc["resulting_revision_number"] if isinstance(lc, dict) else lc.resulting_revision_number)
        details = lc.get("details") if isinstance(lc, dict) else getattr(lc, "details", None)
        ver_pass = lc.get("verification_passed") if isinstance(lc, dict) else getattr(lc, "verification_passed", None)

        pos_ev = norm_text.find(ev_type, last_pos + 1)
        if pos_ev == -1:
            raise AssertionError(f"Row {idx} ({ev_type}): event_type not found after pos {last_pos}")
        pos_prior = norm_text.find(prior, pos_ev)
        if pos_prior == -1:
            raise AssertionError(f"Row {idx} ({ev_type}): prior '{prior}' not found after pos {pos_ev}")
        pos_res = norm_text.find(res, pos_prior)
        if pos_res == -1:
            raise AssertionError(f"Row {idx} ({ev_type}): resulting '{res}' not found after pos {pos_prior}")
        pos_rev = norm_text.find(rev, pos_res)
        if pos_rev == -1:
            raise AssertionError(f"Row {idx} ({ev_type}): rev '{rev}' not found after pos {pos_res}")
        pos_actor = norm_text.find(actor, pos_rev)
        if pos_actor == -1:
            raise AssertionError(f"Row {idx} ({ev_type}): actor '{actor}' not found after pos {pos_rev}")
        if ver_pass is True:
            if "[PASSED]" not in norm_text[pos_actor:pos_actor + 200]:
                raise AssertionError(f"Row {idx} ({ev_type}): '[PASSED]' indicator not found after actor {actor}")
        elif ver_pass is False:
            if "[FAILED]" not in norm_text[pos_actor:pos_actor + 200]:
                raise AssertionError(f"Row {idx} ({ev_type}): '[FAILED]' indicator not found after actor {actor}")
        if details:
            key_phrase = details.split()[0]
            if key_phrase not in norm_text[pos_actor:pos_actor + 200]:
                raise AssertionError(f"Row {idx} ({ev_type}): details token '{key_phrase}' not found near actor {actor}")

        last_pos = pos_ev


def test_render_case_report_pdf_valid_bytes_and_structure():
    """Verify that a rich report renders into valid, parseable PDF bytes with expected content and ordering."""
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
    assert f"Question Answers ({len(report.question_answers)})" in extracted_text
    assert "5. Troubleshooting-Check History" in extracted_text
    assert f"Troubleshooting Checks ({len(report.check_results)})" in extracted_text
    assert "6. Cause-Confirmation History" in extracted_text
    assert f"Cause Confirmations ({len(report.cause_confirmations)})" in extracted_text
    assert "7. Issue Lifecycle History" in extracted_text
    assert f"Lifecycle Events ({len(report.lifecycle_events)})" in extracted_text

    # Assert specific content values
    assert "D03_INCONSISTENT_SIZE" in extracted_text
    assert "Inconsistent Dot Size" in extracted_text
    assert report.issue_condition in extracted_text
    assert "nozzle_restriction" in extracted_text
    assert "Nozzle Restriction / Clog" in extracted_text
    assert "Q01" in extracted_text
    assert "after_prolonged_operation" in extracted_text
    assert "ACT02" in extracted_text
    assert "lead_tech" in extracted_text
    assert "tech_dan" in extracted_text
    assert "qa_sarah" in extracted_text

    # Section-scoped isolation and order verification
    sections = extract_pdf_history_sections(pdf_bytes)

    # Positive: Verify complete row values and order against report arrays
    verify_question_answers_section(sections["question_answers"], report.question_answers)
    verify_check_results_section(sections["check_results"], report.check_results)
    verify_cause_confirmations_section(sections["cause_confirmations"], report.cause_confirmations)
    verify_lifecycle_events_section(sections["lifecycle_events"], report.lifecycle_events)

    # Negative: Ensure reversed rows fail for all history sections
    with pytest.raises(AssertionError):
        verify_question_answers_section(sections["question_answers"], list(reversed(report.question_answers)))
    with pytest.raises(AssertionError):
        verify_check_results_section(sections["check_results"], list(reversed(report.check_results)))
    with pytest.raises(AssertionError):
        verify_cause_confirmations_section(sections["cause_confirmations"], list(reversed(report.cause_confirmations)))
    with pytest.raises(AssertionError):
        verify_lifecycle_events_section(sections["lifecycle_events"], list(reversed(report.lifecycle_events)))

    # Negative: Ensure mismatched row values fail for all history sections
    mismatched_qa = copy.deepcopy(report.question_answers)
    mismatched_qa[0].answer_value = "BOGUS_ANSWER_VALUE"
    with pytest.raises(AssertionError):
        verify_question_answers_section(sections["question_answers"], mismatched_qa)

    mismatched_cr = copy.deepcopy(report.check_results)
    mismatched_cr[0].finding = CheckFinding.CONTRADICTS
    with pytest.raises(AssertionError):
        verify_check_results_section(sections["check_results"], mismatched_cr)

    mismatched_cc = copy.deepcopy(report.cause_confirmations)
    mismatched_cc[0].confirmed_by = "bogus_technician"
    with pytest.raises(AssertionError):
        verify_cause_confirmations_section(sections["cause_confirmations"], mismatched_cc)

    mismatched_lc = copy.deepcopy(report.lifecycle_events)
    mismatched_lc[0].actor = "bogus_actor"
    with pytest.raises(AssertionError):
        verify_lifecycle_events_section(sections["lifecycle_events"], mismatched_lc)

    # Assert diagnosis explanation and evidence
    assert "Nozzle restriction is confirmed as primary root cause." in extracted_text
    assert "Restricted orifice directly causes undersized deposits." in extracted_text
    assert "obs_001" in extracted_text
    assert "SUPPORTS" in extracted_text
    assert "STRONG" in extracted_text
    assert "No bubbles observed in syringe barrel." in extracted_text
    assert "obs_003" in extracted_text
    assert "CONTRADICTS" in extracted_text
    assert "Does the defect worsen over prolonged continuous run?" in extracted_text
    assert "Inspect Syringe Pressure Gauge" in extracted_text

    # Assert provenance notice and absence of unsupported confidentiality label
    assert "Generated from persisted diagnostic records" in extracted_text
    assert "Confidential" not in extracted_text

    # Assert persisted timestamp and absence of live generation clock
    assert "Case Created:" in extracted_text
    assert "Generated:" not in extracted_text


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
    assert "Diagnostic Explanation: None recorded." in extracted_text
    assert "Recommended Next Question: None recorded." in extracted_text
    assert "Recommended Next Troubleshooting Check: None recorded." in extracted_text
    assert "Question Answers (0)" in extracted_text
    assert "Troubleshooting Checks (0)" in extracted_text
    assert "Cause Confirmations (0)" in extracted_text
    assert "Lifecycle Events (0)" in extracted_text


def test_render_case_report_pdf_logical_repeatability():
    """Verify rendering the same unchanged report twice yields identical extracted logical text and order."""
    report = _make_sample_report(with_history=True)

    pdf1 = render_case_report_pdf(report)
    pdf2 = render_case_report_pdf(report)

    reader1 = pypdf.PdfReader(io.BytesIO(pdf1))
    reader2 = pypdf.PdfReader(io.BytesIO(pdf2))

    assert len(reader1.pages) == len(reader2.pages)
    text1 = [page.extract_text() for page in reader1.pages]
    text2 = [page.extract_text() for page in reader2.pages]

    assert text1 == text2, "Logical text and order differ across repeated renderings of unchanged report!"


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
