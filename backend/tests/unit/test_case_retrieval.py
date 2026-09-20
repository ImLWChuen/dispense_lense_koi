"""
Unit tests for multi-attribute case similarity and CaseRetriever.
"""

from datetime import datetime, timezone
import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.case import (
    CaseCauseConfirmationModel,
    CaseLifecycleEventModel,
    CaseModel,
    ObservationModel,
)
from app.services.retrieval.case_retriever import CaseRetriever
from app.services.retrieval.similarity import calculate_case_similarity


from unittest.mock import MagicMock


def test_calculate_case_similarity_identical_defects():
    target = CaseModel(
        case_id=str(uuid.uuid4()),
        defect_code="D03_INCONSISTENT_SIZE",
        defect_name="Inconsistent Size",
        material="UV Acrylic",
        method="jetting",
        description="Dispensed dots vary significantly in volume",
        issue_condition="UNRESOLVED",
        created_at=datetime.now(timezone.utc),
        machine_context={"line_id": "Line A"},
    )

    candidate = CaseModel(
        case_id=str(uuid.uuid4()),
        defect_code="D03_INCONSISTENT_SIZE",
        defect_name="Inconsistent Size",
        material="UV Acrylic",
        method="jetting",
        description="Inconsistent dot volume on substrate",
        issue_condition="RESOLVED",
        created_at=datetime.now(timezone.utc),
        machine_context={"line_id": "Line A"},
    )

    score, factors = calculate_case_similarity(target, candidate)
    assert score > 0.60
    assert any("Same Defect" in f for f in factors)
    assert any("Same Material" in f for f in factors)
    assert any("Same Method" in f for f in factors)
    assert any("Same Line" in f for f in factors)
    assert any("Verified Resolution Available" in f for f in factors)


def test_calculate_case_similarity_different_defects():
    target = CaseModel(
        case_id=str(uuid.uuid4()),
        defect_code="D01_TOO_LITTLE",
        defect_name="Too Little Material",
        material="Epoxy",
        method="time_pressure",
        description="Undersized dots",
        issue_condition="UNRESOLVED",
        created_at=datetime.now(timezone.utc),
    )

    candidate = CaseModel(
        case_id=str(uuid.uuid4()),
        defect_code="D05_SPREADING",
        defect_name="Spreading",
        material="Silicone",
        method="auger",
        description="Excessive wetting on board",
        issue_condition="UNRESOLVED",
        created_at=datetime.now(timezone.utc),
    )

    score, factors = calculate_case_similarity(target, candidate)
    assert score < 0.10


def test_case_retriever_finds_and_sorts_cases():
    target_id = str(uuid.uuid4())
    cand1_id = str(uuid.uuid4())
    cand2_id = str(uuid.uuid4())

    now = datetime.now(timezone.utc)

    target = CaseModel(
        case_id=target_id,
        defect_code="D03_INCONSISTENT_SIZE",
        material="UV Acrylic",
        method="jetting",
        description="Dots fluctuating in diameter",
        issue_condition="UNRESOLVED",
        created_at=now,
    )

    # High match, resolved with confirmation
    cand1 = CaseModel(
        case_id=cand1_id,
        defect_code="D03_INCONSISTENT_SIZE",
        defect_name="Inconsistent Size",
        material="UV Acrylic",
        method="jetting",
        description="Fluctuating diameter dots",
        issue_condition="RESOLVED",
        created_at=now,
    )
    conf = CaseCauseConfirmationModel(
        case_id=cand1_id,
        cause_id="air_supply_issue",
        confirmed_by="tech-1",
        notes="Purged air pocket from feed line",
        confirmed_at=now,
        resulting_revision_number=2,
    )
    lifecycle = CaseLifecycleEventModel(
        case_id=cand1_id,
        event_type="RECOVERY_VERIFICATION",
        prior_issue_condition="RECOVERY_PENDING_VERIFICATION",
        resulting_issue_condition="RESOLVED",
        resulting_revision_number=3,
        actor="engineer-1",
        details="50 test shots within 2% weight tolerance. Verified resolved.",
        verification_passed=True,
        created_at=now,
    )
    cand1.cause_confirmations = [conf]
    cand1.lifecycle_events = [lifecycle]

    # Low match, unresolved
    cand2 = CaseModel(
        case_id=cand2_id,
        defect_code="D05_SPREADING",
        material="Silicone",
        method="time_pressure",
        description="Fluid running together",
        issue_condition="UNRESOLVED",
        created_at=now,
    )
    cand2.cause_confirmations = []
    cand2.lifecycle_events = []

    mock_db = MagicMock()
    mock_db.scalar.return_value = target
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [cand1, cand2]
    mock_db.scalars.return_value = mock_scalars

    retriever = CaseRetriever(mock_db)
    response = retriever.find_similar_cases(target_id, limit=5, min_score=0.15)

    assert response.count >= 1
    top_match = response.similar_cases[0]
    assert top_match.case_id == cand1_id
    assert top_match.is_resolved is True
    assert "Air / Supply Issue" in top_match.confirmed_causes
    assert "50 test shots" in (top_match.resolution_summary or "")
