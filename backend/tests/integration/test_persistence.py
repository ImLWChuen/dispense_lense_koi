"""
DispenseIQ — PostgreSQL Persistence Foundation Integration Tests

Tests minimal atomic persistence for:
1. Diagnostic cases;
2. Structured observations with provenance;
3. Append-oriented analysis revisions;
4. The full immutable initial DiagnosisResult snapshot.

Executes strictly against real PostgreSQL (SQLite is prohibited).
"""

from __future__ import annotations

import copy
import os
import uuid
from typing import Generator

import pytest
from sqlalchemy import delete, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_database_url
from app.db.database import get_engine, reset_engine
from app.db.repository import CaseRepository
from app.db.session import get_session_factory
from app.models.case import AnalysisRevisionModel, CaseModel, ObservationModel
from app.schemas.diagnosis import (
    AnalysisRevision,
    DiagnosisResult,
    EvidenceSource,
    IssueCondition,
    Observation,
    ObservationType,
    StatementType,
    StructuredCase,
)
from app.services.diagnosis.engine import DiagnosticEngine


def _assert_safe_test_database(url: str) -> None:
    """Ensure tests run only against clearly local/test PostgreSQL instances."""
    lower = url.lower()
    is_local = any(
        host in lower
        for host in ("localhost", "127.0.0.1", "postgres", "dispenselens-postgres")
    )
    is_test_db = any(
        db in lower for db in ("dispenselens", "test")
    )
    if not (is_local and is_test_db):
        raise RuntimeError(
            f"Safety check failed: database URL '{url}' is not a local test database. "
            "Destructive testing operations are restricted to verified local test databases."
        )


@pytest.fixture(scope="session", autouse=True)
def configure_test_environment() -> None:
    """Configure and verify real PostgreSQL connection URL for tests."""
    if not os.environ.get("DATABASE_URL"):
        os.environ["DATABASE_URL"] = (
            "postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens"
        )
    url = get_database_url()
    _assert_safe_test_database(url)
    reset_engine()


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide a database session for test execution."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def case_repo(db_session: Session) -> Generator[tuple[CaseRepository, list[str]], None, None]:
    """Provide a CaseRepository with tracked case cleanup for test isolation."""
    created_ids: list[str] = []
    repo = CaseRepository(session=db_session)
    yield repo, created_ids

    # Cleanup created cases
    if created_ids:
        for cid in created_ids:
            db_session.execute(delete(CaseModel).where(CaseModel.case_id == cid))
        db_session.commit()


# ---------------------------------------------------------------------------
# Test 1: Alembic Schema Inspection
# ---------------------------------------------------------------------------

def test_alembic_schema_structure_and_constraints():
    """Verify that Alembic has established cases, observations, and revisions tables."""
    engine = get_engine()
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    assert "cases" in tables
    assert "case_observations" in tables
    assert "analysis_revisions" in tables
    assert "alembic_version" in tables

    # Check 'cases' columns
    cases_cols = {c["name"]: c for c in inspector.get_columns("cases")}
    assert "case_id" in cases_cols
    assert not cases_cols["case_id"]["nullable"]
    assert "description" in cases_cols
    assert not cases_cols["description"]["nullable"]
    assert "issue_condition" in cases_cols
    assert not cases_cols["issue_condition"]["nullable"]
    assert "created_at" in cases_cols
    assert not cases_cols["created_at"]["nullable"]

    # Check 'case_observations' constraints
    obs_fks = inspector.get_foreign_keys("case_observations")
    assert any(fk["referred_table"] == "cases" for fk in obs_fks)
    obs_uqs = inspector.get_unique_constraints("case_observations")
    assert any(
        set(uq["column_names"]) == {"case_id", "observation_id"} for uq in obs_uqs
    )

    # Check 'analysis_revisions' constraints
    rev_fks = inspector.get_foreign_keys("analysis_revisions")
    assert any(fk["referred_table"] == "cases" for fk in rev_fks)
    rev_uqs = inspector.get_unique_constraints("analysis_revisions")
    assert any(
        set(uq["column_names"]) == {"case_id", "revision_number"} for uq in rev_uqs
    )


# ---------------------------------------------------------------------------
# Test 2 & 3: Real Engine Case + Extracted Observations Persistence
# ---------------------------------------------------------------------------

def test_save_and_reconstruct_initial_case_with_extracted_observations(case_repo, db_session):
    """Execute real diagnostic engine, persist mutated case + result, and assert semantic parity."""
    repo, tracked_ids = case_repo
    engine = DiagnosticEngine()

    # Create StructuredCase with description that triggers deterministic extraction
    case = StructuredCase(
        description="The dispensing dots become smaller after the machine has been running for around 20 minutes.",
        material="Epoxy-300",
        method="time_pressure",
        machine_context={"machine_id": "M-101", "pressure_psi": 25.0},
    )
    tracked_ids.append(case.case_id)

    # Run real diagnosis: mutates case.observations and appends revision 1
    result = engine.diagnose(case)

    # Assert preconditions from domain engine
    assert len(case.observations) > 0, "Engine must extract observations from description"
    assert result.analysis_revision is not None
    assert result.analysis_revision.revision_number == 1
    assert result.defect == "D03_INCONSISTENT_SIZE"

    # Persist atomically
    saved_model = repo.save_initial_case(case, result)
    db_session.commit()

    assert saved_model.case_id == case.case_id

    # 1. Read back case and verify semantic parity
    persisted_case = repo.get_case(case.case_id)
    assert persisted_case is not None
    assert persisted_case.case_id == case.case_id
    assert persisted_case.description == case.description
    assert persisted_case.material == "Epoxy-300"
    assert persisted_case.method == "time_pressure"
    assert persisted_case.machine_context == {"machine_id": "M-101", "pressure_psi": 25.0}
    assert persisted_case.defect_code == "D03_INCONSISTENT_SIZE"
    assert persisted_case.defect_name == result.defect_name
    assert persisted_case.issue_condition == IssueCondition.UNRESOLVED.value
    assert persisted_case.created_at.timestamp() == pytest.approx(case.created_at.timestamp(), abs=0.001)

    # 2. Read back observations and verify provenance retention
    persisted_obs = repo.get_case_observations(case.case_id)
    assert len(persisted_obs) == len(case.observations)

    domain_obs_map = {o.id: o for o in case.observations}
    for p_obs in persisted_obs:
        assert p_obs.observation_id in domain_obs_map
        d_obs = domain_obs_map[p_obs.observation_id]

        assert p_obs.case_id == case.case_id
        assert p_obs.observation_type == (
            d_obs.observation_type.value
            if hasattr(d_obs.observation_type, "value")
            else str(d_obs.observation_type)
        )
        assert p_obs.value == d_obs.value
        assert p_obs.original_text == d_obs.original_text
        assert p_obs.statement_type == (
            d_obs.statement_type.value
            if hasattr(d_obs.statement_type, "value")
            else str(d_obs.statement_type)
        )
        assert p_obs.source == (
            d_obs.source.value
            if hasattr(d_obs.source, "value")
            else str(d_obs.source)
        )
        assert p_obs.first_seen_revision == 1
        assert p_obs.created_at.timestamp() == pytest.approx(d_obs.timestamp.timestamp(), abs=0.001)

    # Specific check: proves extracted observations (not just raw text) are retained
    obs_types = {o.observation_type for o in persisted_obs}
    assert ObservationType.RUNTIME_PATTERN.value in obs_types
    assert ObservationType.DEPOSIT_SIZE.value in obs_types


# ---------------------------------------------------------------------------
# Test 4: Complete Immutable Result Snapshot Parity
# ---------------------------------------------------------------------------

def test_immutable_revision_snapshot_semantic_match(case_repo, db_session):
    """Prove that the stored JSONB snapshot semantically matches DiagnosisResult serialization."""
    repo, tracked_ids = case_repo
    engine = DiagnosticEngine()

    case = StructuredCase(
        description="The dispensing dots become smaller after the machine has been running for around 20 minutes.",
        material="Epoxy-300",
        method="time_pressure",
    )
    tracked_ids.append(case.case_id)

    result = engine.diagnose(case)
    repo.save_initial_case(case, result)
    db_session.commit()

    # Read revision 1
    rev_model = repo.get_analysis_revision(case.case_id, 1)
    assert rev_model is not None
    assert rev_model.case_id == case.case_id
    assert rev_model.revision_number == 1
    assert rev_model.defect_code == "D03_INCONSISTENT_SIZE"
    assert rev_model.issue_condition == IssueCondition.UNRESOLVED.value
    assert rev_model.analyzed_at.timestamp() == pytest.approx(
        result.analysis_revision.timestamp.timestamp(), abs=0.001
    )

    # Compare stored JSONB snapshot with result.model_dump(mode="json")
    expected_snapshot = result.model_dump(mode="json")
    assert rev_model.result_snapshot == expected_snapshot

    # Explicit assertions covering key diagnostic sections
    snapshot = rev_model.result_snapshot
    assert snapshot["case_id"] == case.case_id
    assert snapshot["defect"] == "D03_INCONSISTENT_SIZE"
    assert len(snapshot["ranked_causes"]) > 0

    top_cause = snapshot["ranked_causes"][0]
    assert "cause_id" in top_cause
    assert "score" in top_cause
    assert "conclusion" in top_cause
    assert "supporting_evidence" in top_cause
    assert "contradicting_evidence" in top_cause
    assert "neutral_evidence" in top_cause
    assert "missing_evidence" in top_cause
    assert "score_breakdown" in top_cause

    # Evidence details preserved
    assert len(top_cause["supporting_evidence"]) > 0
    ev = top_cause["supporting_evidence"][0]
    assert "observation_id" in ev
    assert "relation" in ev
    assert "strength" in ev
    assert "source" in ev
    assert "explanation" in ev
    assert "score_contribution" in ev

    # Next steps and explanation preserved
    assert snapshot["explanation"] != ""
    assert snapshot["analysis_revision"]["revision_number"] == 1
    assert snapshot["issue_condition"] == "UNRESOLVED"
    assert isinstance(snapshot["warnings"], list)


# ---------------------------------------------------------------------------
# Test 5: Duplicate Revision Insertion Protection
# ---------------------------------------------------------------------------

def test_duplicate_revision_insertion_fails_and_does_not_overwrite(case_repo, db_session):
    """Prove that revision 1 cannot be overwritten by a duplicate write."""
    repo, tracked_ids = case_repo
    engine = DiagnosticEngine()

    case = StructuredCase(
        description="The dispensing dots become smaller after the machine has been running for around 20 minutes.",
    )
    tracked_ids.append(case.case_id)

    result = engine.diagnose(case)
    repo.save_initial_case(case, result)
    db_session.commit()

    # Attempt to insert a duplicate revision 1 for the same case_id
    duplicate_rev = AnalysisRevisionModel(
        case_id=case.case_id,
        revision_number=1,
        analyzed_at=result.analysis_revision.timestamp,
        defect_code="TAMPERED_CODE",
        issue_condition="RESOLVED",
        result_snapshot={"tampered": True},
    )
    db_session.add(duplicate_rev)

    with pytest.raises(IntegrityError):
        db_session.flush()

    db_session.rollback()

    # Verify original revision 1 is completely untouched
    rev_model = repo.get_analysis_revision(case.case_id, 1)
    assert rev_model is not None
    assert rev_model.defect_code == "D03_INCONSISTENT_SIZE"
    assert rev_model.result_snapshot["defect"] == "D03_INCONSISTENT_SIZE"
    assert "tampered" not in rev_model.result_snapshot


# ---------------------------------------------------------------------------
# Test 6: Atomic Rollback on Failure
# ---------------------------------------------------------------------------

def test_initial_save_rolls_back_atomically_on_failure(case_repo, db_session):
    """Ensure that if any part of the initial save fails, no partial case is stored."""
    repo, tracked_ids = case_repo
    engine = DiagnosticEngine()

    case = StructuredCase(
        description="The dispensing dots become smaller after the machine has been running for around 20 minutes.",
    )
    tracked_ids.append(case.case_id)
    result = engine.diagnose(case)

    # Intentionally corrupt observations to cause a unique constraint violation
    # by duplicating observation_id
    dup_obs = copy.deepcopy(case.observations[0])
    case.observations.append(dup_obs)

    with pytest.raises(IntegrityError):
        repo.save_initial_case(case, result)

    db_session.rollback()

    # Assert no partial case, observations, or revisions exist
    assert repo.get_case(case.case_id) is None
    assert repo.get_case_observations(case.case_id) == []
    assert repo.get_analysis_revision(case.case_id, 1) is None


# ---------------------------------------------------------------------------
# Test 7: Independent Cases Stored Without Leakage
# ---------------------------------------------------------------------------

def test_independent_cases_persisted_without_leakage(case_repo, db_session):
    """Verify that two distinct cases do not leak observations, revisions, or IDs."""
    repo, tracked_ids = case_repo
    engine = DiagnosticEngine()

    case_1 = StructuredCase(
        description="The dispensing dots become smaller after the machine has been running for around 20 minutes.",
        material="Epoxy-A",
    )
    case_2 = StructuredCase(
        description="Fluid spreading excessively onto adjacent copper pads after dispensing.",
        material="Adhesive-B",
    )
    tracked_ids.extend([case_1.case_id, case_2.case_id])

    result_1 = engine.diagnose(case_1)
    result_2 = engine.diagnose(case_2)

    repo.save_initial_case(case_1, result_1)
    repo.save_initial_case(case_2, result_2)
    db_session.commit()

    # Query Case 1
    c1 = repo.get_case(case_1.case_id)
    obs1 = repo.get_case_observations(case_1.case_id)
    rev1 = repo.get_analysis_revision(case_1.case_id, 1)

    # Query Case 2
    c2 = repo.get_case(case_2.case_id)
    obs2 = repo.get_case_observations(case_2.case_id)
    rev2 = repo.get_analysis_revision(case_2.case_id, 1)

    assert c1.case_id != c2.case_id
    assert c1.defect_code == "D03_INCONSISTENT_SIZE"
    assert c2.defect_code == "D05_SPREADING"

    obs1_ids = {o.observation_id for o in obs1}
    obs2_ids = {o.observation_id for o in obs2}
    assert obs1_ids.isdisjoint(obs2_ids)

    assert rev1.result_snapshot["defect"] == "D03_INCONSISTENT_SIZE"
    assert rev2.result_snapshot["defect"] == "D05_SPREADING"


# ---------------------------------------------------------------------------
# Test 8 & 9: Repository Precondition Validation
# ---------------------------------------------------------------------------

def test_repository_rejects_mismatched_ids(case_repo):
    """Reject save_initial_case when case_id and result.case_id differ."""
    repo, _ = case_repo
    case = StructuredCase(case_id=str(uuid.uuid4()), description="Test problem")
    result = DiagnosisResult(
        case_id=str(uuid.uuid4()),  # Different ID
        analysis_revision=AnalysisRevision(revision_number=1),
    )

    with pytest.raises(ValueError, match="Mismatched case IDs"):
        repo.save_initial_case(case, result)


def test_repository_rejects_missing_or_non_1_revision(case_repo):
    """Reject save_initial_case when analysis_revision is absent or not revision 1."""
    repo, _ = case_repo
    case_id = str(uuid.uuid4())
    case = StructuredCase(case_id=case_id, description="Test problem")

    # Missing revision
    res_no_rev = DiagnosisResult(case_id=case_id, analysis_revision=None)
    with pytest.raises(ValueError, match="must include an analysis_revision"):
        repo.save_initial_case(case, res_no_rev)

    # Revision number != 1
    res_rev_2 = DiagnosisResult(
        case_id=case_id,
        analysis_revision=AnalysisRevision(revision_number=2),
    )
    with pytest.raises(ValueError, match="requires analysis_revision.revision_number == 1"):
        repo.save_initial_case(case, res_rev_2)


# ---------------------------------------------------------------------------
# Test 10: Configuration and Database Scheme Safety
# ---------------------------------------------------------------------------

def test_configuration_prohibits_sqlite(monkeypatch):
    """Explicitly test that SQLite is rejected with a clear ValueError."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")
    with pytest.raises(ValueError, match="Only PostgreSQL is authorized"):
        get_database_url()


def test_configuration_requires_database_url_when_called(monkeypatch):
    """Explicitly test that empty DATABASE_URL raises a clear RuntimeError."""
    monkeypatch.setenv("DATABASE_URL", "")
    with pytest.raises(RuntimeError, match="DATABASE_URL environment variable is not set"):
        get_database_url()
