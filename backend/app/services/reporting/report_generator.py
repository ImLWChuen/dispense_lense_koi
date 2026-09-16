"""
DispenseIQ — Deterministic Durable Case Report Assembler

Assembles a deterministic read-only report for a durable case from persisted state
and audit history without recalculating diagnosis, mutating workflow state, or
creating database records.
"""

from __future__ import annotations

import logging
from typing import Any

from app.db.repository import CaseRepository
from app.models.case import (
    CaseCauseConfirmationModel,
    CaseCheckResultModel,
    CaseLifecycleEventModel,
    QuestionAnswerModel,
)
from app.schemas.case import (
    CaseOutcomeSummary,
    CaseReportResponse,
    CauseConfirmationRecord,
    CheckResultRecord,
    LifecycleEventRecord,
    QuestionAnswerRecord,
)
from app.schemas.diagnosis import (
    CauseConclusion,
    CheckExecutionStatus,
    CheckFinding,
    DiagnosisResult,
    EvidenceSource,
    IssueCondition,
)

logger = logging.getLogger(__name__)


def _map_question_answer(model: QuestionAnswerModel) -> QuestionAnswerRecord:
    """Map a QuestionAnswerModel to its canonical QuestionAnswerRecord schema."""
    source_val = (
        EvidenceSource(model.source)
        if model.source in EvidenceSource._value2member_map_
        else model.source
    )
    return QuestionAnswerRecord(
        question_id=model.question_id,
        answer_value=model.answer_value,
        answer_text=model.answer_text,
        source=source_val,
        answered_at=model.answered_at,
        resulting_revision_number=model.resulting_revision_number,
    )


def _map_check_result(model: CaseCheckResultModel) -> CheckResultRecord:
    """Map a CaseCheckResultModel to its canonical CheckResultRecord schema."""
    exec_status = (
        CheckExecutionStatus(model.execution_status)
        if model.execution_status in CheckExecutionStatus._value2member_map_
        else model.execution_status
    )
    finding = (
        CheckFinding(model.finding)
        if model.finding in CheckFinding._value2member_map_
        else model.finding
    )
    source_val = (
        EvidenceSource(model.source)
        if model.source in EvidenceSource._value2member_map_
        else model.source
    )
    return CheckResultRecord(
        check_id=model.check_id,
        execution_status=exec_status,
        finding=finding,
        finding_details=model.finding_details,
        outcome=model.outcome,
        source=source_val,
        checked_at=model.checked_at,
        resulting_revision_number=model.resulting_revision_number,
    )


def _map_cause_confirmation(model: CaseCauseConfirmationModel) -> CauseConfirmationRecord:
    """Map a CaseCauseConfirmationModel to its canonical CauseConfirmationRecord schema."""
    return CauseConfirmationRecord(
        cause_id=model.cause_id,
        confirmed_by=model.confirmed_by or "technician",
        notes=model.notes,
        confirmed_at=model.confirmed_at,
        resulting_revision_number=model.resulting_revision_number,
    )


def _map_lifecycle_event(model: CaseLifecycleEventModel) -> LifecycleEventRecord:
    """Map a CaseLifecycleEventModel to its canonical LifecycleEventRecord schema."""
    prior_cond = (
        IssueCondition(model.prior_issue_condition)
        if model.prior_issue_condition in IssueCondition._value2member_map_
        else model.prior_issue_condition
    )
    resulting_cond = (
        IssueCondition(model.resulting_issue_condition)
        if model.resulting_issue_condition in IssueCondition._value2member_map_
        else model.resulting_issue_condition
    )
    return LifecycleEventRecord(
        id=model.id,
        case_id=model.case_id,
        event_type=model.event_type,
        prior_issue_condition=prior_cond,
        resulting_issue_condition=resulting_cond,
        resulting_revision_number=model.resulting_revision_number,
        actor=model.actor or "technician",
        details=model.details or "",
        verification_passed=model.verification_passed,
        created_at=model.created_at,
    )


def build_case_report(
    case_id: str,
    repository: CaseRepository,
    pinned_revision: int | None = None,
) -> CaseReportResponse | None:
    """Assemble a deterministic read-only report for a durable case from persistent storage.

    Reads persisted case details, latest analysis revision snapshot, and full audit histories
    (answers, checks, confirmations, lifecycle events). Performs no diagnostic recalculation,
    writes no audit rows, and introduces no mutations.

    Args:
        case_id: Canonical UUID string identifying the case.
        repository: CaseRepository instance for storage access.
        pinned_revision: Optional revision number to pin the report basis to. If None,
            the latest available analysis revision is used as the pinned basis.

    Returns:
        CaseReportResponse if case and revisions exist, None if case is not found.
    """
    case_model = repository.get_case(case_id)
    if case_model is None:
        return None

    if pinned_revision is not None:
        target_rev = repository.get_analysis_revision(case_id, revision_number=pinned_revision)
        if target_rev is None:
            return None
    else:
        target_rev = repository.get_latest_analysis_revision(case_id)
        if target_rev is None:
            target_rev = repository.get_analysis_revision(case_id, revision_number=1)
            if target_rev is None:
                return None

    effective_revision = target_rev.revision_number
    latest_diagnosis = DiagnosisResult.model_validate(target_rev.result_snapshot)

    # Resolve issue condition strictly from the pinned revision basis, not from potentially mutable case_model
    pinned_condition_raw = target_rev.issue_condition or latest_diagnosis.issue_condition
    if pinned_condition_raw in IssueCondition._value2member_map_:
        pinned_condition = IssueCondition(pinned_condition_raw)
    elif isinstance(pinned_condition_raw, IssueCondition):
        pinned_condition = pinned_condition_raw
    else:
        try:
            pinned_condition = IssueCondition(pinned_condition_raw)
        except ValueError:
            pinned_condition = pinned_condition_raw

    # 1. Question-answer history (scoped to pinned revision; sorted by revision asc, answered_at asc, question_id asc)
    raw_qa = repository.get_case_question_answers(case_id, max_revision=effective_revision)
    mapped_qa = [_map_question_answer(m) for m in raw_qa]
    sorted_qa = sorted(
        mapped_qa,
        key=lambda r: (r.resulting_revision_number, r.answered_at, r.question_id),
    )

    # 2. Troubleshooting-check history (scoped to pinned revision; sorted by revision asc, checked_at asc, check_id asc)
    raw_cr = repository.get_case_check_results(case_id, max_revision=effective_revision)
    mapped_cr = [_map_check_result(m) for m in raw_cr]
    sorted_cr = sorted(
        mapped_cr,
        key=lambda r: (r.resulting_revision_number, r.checked_at, r.check_id),
    )

    # 3. Cause-confirmation history (scoped to pinned revision; sorted by revision asc, confirmed_at asc, cause_id asc)
    raw_conf = repository.get_case_cause_confirmations(case_id, max_revision=effective_revision)
    mapped_conf = [_map_cause_confirmation(m) for m in raw_conf]
    sorted_conf = sorted(
        mapped_conf,
        key=lambda r: (r.resulting_revision_number, r.confirmed_at, r.cause_id),
    )

    # 4. Issue-lifecycle history (scoped to pinned revision; sorted by revision asc, created_at asc, id asc)
    raw_lc = repository.get_case_lifecycle_events(case_id, max_revision=effective_revision)
    mapped_lc = [_map_lifecycle_event(m) for m in raw_lc]
    sorted_lc = sorted(
        mapped_lc,
        key=lambda r: (r.resulting_revision_number, r.created_at, r.id or 0),
    )

    # 5. Outcome summary projection scoped strictly to pinned revision basis
    confirmed_cause_ids: list[str] = [
        c.cause_id
        for c in latest_diagnosis.ranked_causes
        if getattr(c, "conclusion", None) in (CauseConclusion.CONFIRMED, "CONFIRMED", "confirmed")
    ]
    # Fallback/merge with explicit cause confirmation records if not yet reflected in ranked_causes
    for conf in sorted_conf:
        if conf.cause_id not in confirmed_cause_ids:
            confirmed_cause_ids.append(conf.cause_id)

    is_resolved = (
        pinned_condition == IssueCondition.RESOLVED
        or str(pinned_condition).upper() == "RESOLVED"
    )

    outcome_summary = CaseOutcomeSummary(
        issue_condition=pinned_condition,
        current_revision=effective_revision,
        confirmed_causes=confirmed_cause_ids,
        currently_confirmed_causes=confirmed_cause_ids,
        is_resolved=is_resolved,
        resolved=is_resolved,
    )

    defect_code = target_rev.defect_code or latest_diagnosis.defect or case_model.defect_code
    defect_name = latest_diagnosis.defect_name or case_model.defect_name

    return CaseReportResponse(
        case_id=case_model.case_id,
        current_revision=effective_revision,
        defect_code=defect_code,
        defect_name=defect_name,
        description=case_model.description or "",
        material=case_model.material,
        method=case_model.method,
        machine_context=case_model.machine_context,
        issue_condition=pinned_condition,
        created_at=case_model.created_at,
        current_diagnosis=latest_diagnosis,
        diagnosis=latest_diagnosis,
        question_answers=sorted_qa,
        question_answer_history=sorted_qa,
        check_results=sorted_cr,
        troubleshooting_check_history=sorted_cr,
        cause_confirmations=sorted_conf,
        cause_confirmation_history=sorted_conf,
        lifecycle_events=sorted_lc,
        issue_lifecycle_history=sorted_lc,
        outcome_summary=outcome_summary,
        current_outcome_summary=outcome_summary,
    )
