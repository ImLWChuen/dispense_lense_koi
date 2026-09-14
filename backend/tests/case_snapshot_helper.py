"""Test-only snapshot helper for capturing and verifying complete persistent case state.

Used to verify that transaction rollback and rejected API requests leave
prior database state, snapshots, and histories strictly unchanged.
"""

from __future__ import annotations

import copy
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import (
    AnalysisRevisionModel,
    CaseCheckResultModel,
    CaseModel,
    ObservationModel,
    QuestionAnswerModel,
)


def capture_complete_case_state(session: Session, case_id: str) -> dict[str, Any]:
    """Query and return an immutable, detached dictionary of all stored state for a case.

    Includes:
    - Case row scalar fields
    - All observations (sorted deterministically by observation_id)
    - All question answers (sorted by resulting_revision_number, question_id)
    - All check results (sorted by resulting_revision_number, check_id)
    - All analysis revisions and their full result_snapshot JSON payloads
    """
    case_row = session.scalar(
        select(CaseModel)
        .where(CaseModel.case_id == case_id)
        .execution_options(populate_existing=True)
    )
    if case_row is None:
        return {}

    case_data = {
        "case_id": str(case_row.case_id),
        "description": str(case_row.description or ""),
        "material": str(case_row.material) if case_row.material else None,
        "method": str(case_row.method) if case_row.method else None,
        "machine_context": copy.deepcopy(case_row.machine_context),
        "defect_code": str(case_row.defect_code) if case_row.defect_code else None,
        "defect_name": str(case_row.defect_name) if case_row.defect_name else None,
        "issue_condition": str(case_row.issue_condition),
        "created_at": case_row.created_at.isoformat() if case_row.created_at else None,
    }

    obs_rows = session.scalars(
        select(ObservationModel)
        .where(ObservationModel.case_id == case_id)
        .order_by(ObservationModel.observation_id.asc())
        .execution_options(populate_existing=True)
    ).all()
    obs_data = [
        {
            "observation_id": str(o.observation_id),
            "observation_type": str(o.observation_type),
            "value": str(o.value),
            "original_text": str(o.original_text) if o.original_text else None,
            "statement_type": str(o.statement_type),
            "source": str(o.source),
            "confidence": float(o.confidence) if o.confidence is not None else None,
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "first_seen_revision": int(o.first_seen_revision),
        }
        for o in obs_rows
    ]

    qa_rows = session.scalars(
        select(QuestionAnswerModel)
        .where(QuestionAnswerModel.case_id == case_id)
        .order_by(
            QuestionAnswerModel.resulting_revision_number.asc(),
            QuestionAnswerModel.question_id.asc(),
        )
        .execution_options(populate_existing=True)
    ).all()
    qa_data = [
        {
            "question_id": str(q.question_id),
            "answer_value": str(q.answer_value),
            "answer_text": str(q.answer_text) if q.answer_text else None,
            "source": str(q.source),
            "answered_at": q.answered_at.isoformat() if q.answered_at else None,
            "resulting_revision_number": int(q.resulting_revision_number),
        }
        for q in qa_rows
    ]

    cr_rows = session.scalars(
        select(CaseCheckResultModel)
        .where(CaseCheckResultModel.case_id == case_id)
        .order_by(
            CaseCheckResultModel.resulting_revision_number.asc(),
            CaseCheckResultModel.check_id.asc(),
        )
        .execution_options(populate_existing=True)
    ).all()
    cr_data = [
        {
            "check_id": str(c.check_id),
            "execution_status": str(c.execution_status),
            "finding": str(c.finding),
            "finding_details": str(c.finding_details) if c.finding_details else None,
            "outcome": str(c.outcome) if c.outcome else None,
            "source": str(c.source),
            "checked_at": c.checked_at.isoformat() if c.checked_at else None,
            "resulting_revision_number": int(c.resulting_revision_number),
        }
        for c in cr_rows
    ]

    rev_rows = session.scalars(
        select(AnalysisRevisionModel)
        .where(AnalysisRevisionModel.case_id == case_id)
        .order_by(AnalysisRevisionModel.revision_number.asc())
        .execution_options(populate_existing=True)
    ).all()
    rev_data = [
        {
            "revision_number": int(r.revision_number),
            "analyzed_at": r.analyzed_at.isoformat() if r.analyzed_at else None,
            "defect_code": str(r.defect_code) if r.defect_code else None,
            "issue_condition": str(r.issue_condition),
            "result_snapshot": copy.deepcopy(r.result_snapshot),
        }
        for r in rev_rows
    ]

    return {
        "case": case_data,
        "observations": obs_data,
        "question_answers": qa_data,
        "check_results": cr_data,
        "analysis_revisions": rev_data,
    }
