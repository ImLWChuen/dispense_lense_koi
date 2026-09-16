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
import threading
import time
import uuid
from typing import Any, Generator

import pytest
from sqlalchemy import delete, event, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.case_snapshot_helper import capture_complete_case_state

from app.core.config import get_database_url
from app.db.database import get_engine, reset_engine
from app.db.repository import CaseRepository, StaleRevisionError
from app.db.session import get_session_factory
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
    AnalysisRevision,
    AnswerValue,
    CauseConclusion,
    CheckExecutionStatus,
    CheckFinding,
    CheckResult,
    DiagnosisResult,
    EvidenceSource,
    IssueCondition,
    Observation,
    ObservationType,
    QuestionAnswer,
    StatementType,
    StructuredCase,
)
from app.services.diagnosis.engine import DiagnosticEngine, StateManager
from tests.unit.test_persistence_safety import assert_safe_test_database


@pytest.fixture(scope="session", autouse=True)
def configure_test_environment() -> None:
    """Configure and verify real PostgreSQL connection URL for tests."""
    if not os.environ.get("DATABASE_URL"):
        os.environ["DATABASE_URL"] = (
            "postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens"
        )
    url = get_database_url()
    assert_safe_test_database(url)
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
    assert "case_question_answers" in tables
    assert "case_check_results" in tables
    assert "case_cause_confirmations" in tables
    assert "case_lifecycle_events" in tables
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

    # Verify unrestricted domain strings are Text in cases
    assert "TEXT" in str(cases_cols["material"]["type"]).upper()
    assert "TEXT" in str(cases_cols["method"]["type"]).upper()
    assert "TEXT" in str(cases_cols["defect_name"]["type"]).upper()
    # Verify enum-backed columns remain bounded
    assert "VARCHAR" in str(cases_cols["defect_code"]["type"]).upper()
    assert "VARCHAR" in str(cases_cols["issue_condition"]["type"]).upper()

    # Check 'case_observations' columns
    obs_cols = {c["name"]: c for c in inspector.get_columns("case_observations")}
    # Verify unrestricted domain observation ID and value are Text
    assert "TEXT" in str(obs_cols["observation_id"]["type"]).upper()
    assert "TEXT" in str(obs_cols["value"]["type"]).upper()
    # Verify enum-backed observation columns remain bounded
    assert "VARCHAR" in str(obs_cols["observation_type"]["type"]).upper()
    assert "VARCHAR" in str(obs_cols["statement_type"]["type"]).upper()
    assert "VARCHAR" in str(obs_cols["source"]["type"]).upper()

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

    # Check 'case_question_answers' columns and constraints
    qa_cols = {c["name"]: c for c in inspector.get_columns("case_question_answers")}
    assert "id" in qa_cols
    assert "case_id" in qa_cols
    assert not qa_cols["case_id"]["nullable"]
    assert "question_id" in qa_cols
    assert "TEXT" in str(qa_cols["question_id"]["type"]).upper()
    assert not qa_cols["question_id"]["nullable"]
    assert "answer_value" in qa_cols
    assert "TEXT" in str(qa_cols["answer_value"]["type"]).upper()
    assert not qa_cols["answer_value"]["nullable"]
    assert "answer_text" in qa_cols
    assert "TEXT" in str(qa_cols["answer_text"]["type"]).upper()
    assert qa_cols["answer_text"]["nullable"]
    assert "source" in qa_cols
    assert "VARCHAR" in str(qa_cols["source"]["type"]).upper()
    assert "answered_at" in qa_cols
    assert not qa_cols["answered_at"]["nullable"]
    assert "resulting_revision_number" in qa_cols
    assert not qa_cols["resulting_revision_number"]["nullable"]

    qa_fks = inspector.get_foreign_keys("case_question_answers")
    assert any(fk["referred_table"] == "cases" for fk in qa_fks)
    qa_uqs = inspector.get_unique_constraints("case_question_answers")
    assert any(
        set(uq["column_names"]) == {"case_id", "resulting_revision_number"} for uq in qa_uqs
    )
    # Ensure no unique constraint on (case_id, question_id)
    assert not any(
        set(uq["column_names"]) == {"case_id", "question_id"} for uq in qa_uqs
    )

    # Check 'case_check_results' columns and constraints
    assert "case_check_results" in tables
    cr_cols = {c["name"]: c for c in inspector.get_columns("case_check_results")}
    assert "id" in cr_cols
    assert "case_id" in cr_cols
    assert not cr_cols["case_id"]["nullable"]
    assert "check_id" in cr_cols
    assert "TEXT" in str(cr_cols["check_id"]["type"]).upper()
    assert not cr_cols["check_id"]["nullable"]
    assert "execution_status" in cr_cols
    assert "VARCHAR" in str(cr_cols["execution_status"]["type"]).upper()
    assert not cr_cols["execution_status"]["nullable"]
    assert "finding" in cr_cols
    assert "VARCHAR" in str(cr_cols["finding"]["type"]).upper()
    assert not cr_cols["finding"]["nullable"]
    assert "finding_details" in cr_cols
    assert "TEXT" in str(cr_cols["finding_details"]["type"]).upper()
    assert cr_cols["finding_details"]["nullable"]
    assert "outcome" in cr_cols
    assert "TEXT" in str(cr_cols["outcome"]["type"]).upper()
    assert cr_cols["outcome"]["nullable"]
    assert "source" in cr_cols
    assert "VARCHAR" in str(cr_cols["source"]["type"]).upper()
    assert not cr_cols["source"]["nullable"]
    assert "checked_at" in cr_cols
    assert not cr_cols["checked_at"]["nullable"]
    assert "resulting_revision_number" in cr_cols
    assert not cr_cols["resulting_revision_number"]["nullable"]

    cr_fks = inspector.get_foreign_keys("case_check_results")
    assert any(fk["referred_table"] == "cases" for fk in cr_fks)
    cr_uqs = inspector.get_unique_constraints("case_check_results")
    assert any(
        set(uq["column_names"]) == {"case_id", "resulting_revision_number"} for uq in cr_uqs
    )
    # Ensure no unique constraint on (case_id, check_id)
    assert not any(
        set(uq["column_names"]) == {"case_id", "check_id"} for uq in cr_uqs
    )


def test_unrestricted_domain_strings_and_confidence_round_trip(case_repo, db_session):
    """Verify that observation IDs > 64 chars, values/material/method > 255 chars,
    and float confidence round-trip through PostgreSQL with exact fidelity."""
    repo, tracked_ids = case_repo
    engine = DiagnosticEngine()

    # Long valid strings exceeding legacy VARCHAR bounds
    long_obs_id = "obs_domain_identifier_with_length_greater_than_sixty_four_characters_test_12345"
    assert len(long_obs_id) > 64

    long_obs_value = "ObsValue_" + "long_value_segment_" * 20
    assert len(long_obs_value) > 255

    long_material = "FluidChemistry_HighPerformanceEpoxy_" + "grade_additive_specifier_" * 15
    assert len(long_material) > 255

    long_method = "DispensingMethod_TimePressureWithPneumaticAssist_" + "custom_valve_profile_" * 15
    assert len(long_method) > 255

    case = StructuredCase(
        defect_code="D03_INCONSISTENT_SIZE",
        defect_name="Inconsistent Dot Size / Line Width",
        description="The dispensing dots become smaller after the machine has been running for around 20 minutes.",
        material=long_material,
        method=long_method,
        observations=[
            Observation(
                id=long_obs_id,
                observation_type=ObservationType.RUNTIME_PATTERN,
                value=long_obs_value,
                original_text="Detailed technician observation text",
                statement_type=StatementType.USER_OBSERVATION,
                source=EvidenceSource.USER,
                confidence=0.925,
            ),
            Observation(
                observation_type=ObservationType.DEPOSIT_SIZE,
                value="smaller",
                source=EvidenceSource.USER,
            ),
        ],
    )
    tracked_ids.append(case.case_id)

    result = engine.diagnose(case)
    assert result.analysis_revision is not None
    assert result.analysis_revision.revision_number == 1

    # Persist atomically
    repo.save_initial_case(case, result)
    db_session.commit()

    # Read back and assert exact parity
    persisted_case = repo.get_case(case.case_id)
    assert persisted_case is not None
    assert persisted_case.material == long_material
    assert persisted_case.method == long_method

    persisted_obs = repo.get_case_observations(case.case_id)
    obs_by_id = {o.observation_id: o for o in persisted_obs}
    assert long_obs_id in obs_by_id
    target_obs = obs_by_id[long_obs_id]
    assert target_obs.observation_id == long_obs_id
    assert target_obs.value == long_obs_value
    assert target_obs.confidence == pytest.approx(0.925, abs=0.0001)

    # Verify stored JSONB snapshot contains the complete diagnosis result
    rev = repo.get_analysis_revision(case.case_id, 1)
    assert rev is not None
    assert rev.result_snapshot["defect"] == result.defect


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
    assert result.analysis_revision is not None
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
    assert result.analysis_revision is not None
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


# ===========================================================================
# DLK-M3-011: Question-Answer Persistence & Analysis Revision Appends
# ===========================================================================

def test_unrestricted_question_answer_strings_round_trip(case_repo, db_session):
    """Verify that question_id > 64 chars, answer_value > 255 chars, and answer_text > 500 chars
    round-trip through PostgreSQL with exact fidelity."""
    repo, tracked_ids = case_repo
    engine = DiagnosticEngine()

    case_id = str(uuid.uuid4())
    tracked_ids.append(case_id)

    # Initial case
    case = engine.prepare_case(
        StructuredCase(
            case_id=case_id,
            defect_code="D03_INCONSISTENT_SIZE",
            defect_name="Inconsistent Dot Size / Line Width",
            description="The dispensing dots become smaller after the machine has been running for around 20 minutes.",
            observations=[
                Observation(
                    observation_type=ObservationType.NOZZLE_CONDITION,
                    value="drips_after_dispense",
                    statement_type=StatementType.USER_OBSERVATION,
                    source=EvidenceSource.USER,
                )
            ],
        )
    )
    result = engine.diagnose(case)
    assert result.analysis_revision is not None
    repo.save_initial_case(case, result)

    # Long unrestricted domain strings
    long_qid = "Q_unrestricted_domain_identifier_with_length_greater_than_sixty_four_chars_test"
    assert len(long_qid) > 64
    long_val = "AnswerValue_" + "extended_token_payload_" * 15
    assert len(long_val) > 255
    long_text = "Technician notes with unicode 🔍 and extended description: " + "verbose_log_details_" * 25
    assert len(long_text) > 500

    qa = QuestionAnswer(
        question_id=long_qid,
        answer_value=long_val,
        answer_text=long_text,
        source=EvidenceSource.USER,
    )

    # Build revision 2 result
    reconstructed = repo.load_structured_case(case_id)
    assert reconstructed is not None
    reconstructed.previous_answers.append(qa)
    result2 = engine.diagnose(reconstructed)
    assert result2.analysis_revision is not None
    assert result2.analysis_revision.revision_number == 2

    repo.append_question_answer_revision(
        case=reconstructed,
        answer=qa,
        result=result2,
        expected_revision=1,
    )

    # Verify direct model query round-trip
    qa_models = repo.get_case_question_answers(case_id)
    assert len(qa_models) == 1
    assert qa_models[0].question_id == long_qid
    assert qa_models[0].answer_value == long_val
    assert qa_models[0].answer_text == long_text
    assert qa_models[0].resulting_revision_number == 2

    # Verify reconstruction round-trip
    reloaded = repo.load_structured_case(case_id)
    assert reloaded is not None
    assert len(reloaded.previous_answers) == 1
    assert reloaded.previous_answers[0].question_id == long_qid
    assert reloaded.previous_answers[0].answer_value == long_val
    assert reloaded.previous_answers[0].answer_text == long_text


def test_load_structured_case_reconstructs_complete_state(case_repo):
    """Verify load_structured_case reconstructs full case context, observations,
    analysis revisions, timestamps, and empty previous_check_results without diagnostic recalculation."""
    repo, tracked_ids = case_repo
    engine = DiagnosticEngine()

    case_id = str(uuid.uuid4())
    tracked_ids.append(case_id)

    case = engine.prepare_case(
        StructuredCase(
            case_id=case_id,
            defect_code="D03_INCONSISTENT_SIZE",
            defect_name="Inconsistent Dot Size / Line Width",
            description="The dispensing dots become smaller after the machine has been running for around 20 minutes.",
            material="UV_Curable_Adhesive_Epoxy",
            method="time_pressure",
            machine_context={"pressure_kpa": 120, "temperature_c": 24.5},
            observations=[
                Observation(
                    observation_type=ObservationType.NOZZLE_CONDITION,
                    value="drips_after_dispense",
                    original_text="Needle dripping fluid",
                    statement_type=StatementType.USER_OBSERVATION,
                    source=EvidenceSource.USER,
                    confidence=0.95,
                )
            ],
        )
    )
    result = engine.diagnose(case)
    assert result.analysis_revision is not None
    repo.save_initial_case(case, result)

    reconstructed = repo.load_structured_case(case_id)
    assert reconstructed is not None
    assert reconstructed.case_id == case_id
    assert reconstructed.description == "The dispensing dots become smaller after the machine has been running for around 20 minutes."
    assert reconstructed.material == "UV_Curable_Adhesive_Epoxy"
    assert reconstructed.method == "time_pressure"
    assert reconstructed.machine_context == {"pressure_kpa": 120, "temperature_c": 24.5}
    assert reconstructed.defect_code == result.defect
    assert reconstructed.issue_condition == IssueCondition.UNRESOLVED
    assert reconstructed.created_at == case.created_at

    # Observations check
    obs_dict = {o.id: o for o in reconstructed.observations}
    for orig_obs in case.observations:
        assert orig_obs.id in obs_dict
        obs = obs_dict[orig_obs.id]
        assert obs.observation_type == orig_obs.observation_type
        assert obs.value == orig_obs.value
        assert obs.statement_type == orig_obs.statement_type
        assert obs.source == orig_obs.source

    # Answers, checks, and revisions
    assert reconstructed.previous_answers == []
    assert reconstructed.previous_check_results == []
    assert len(reconstructed.analysis_revisions) == 1
    assert reconstructed.analysis_revisions[0].revision_number == 1
    assert reconstructed.analysis_revisions[0].defect_code == result.defect
    assert len(reconstructed.analysis_revisions[0].ranked_causes) == len(result.ranked_causes)

    # Non-existent case returns None
    assert repo.load_structured_case(str(uuid.uuid4())) is None


def test_append_question_answer_revision_persists_q01_followup(case_repo):
    """Verify real Q01 answer with submit_question_answer persists as revision 2,
    with new observation first_seen_revision == 2 and revision 1 immutable."""
    repo, tracked_ids = case_repo
    engine = DiagnosticEngine()

    case_id = str(uuid.uuid4())
    tracked_ids.append(case_id)

    # 1. Initial Case & Revision 1
    initial_case = engine.prepare_case(
        StructuredCase(
            case_id=case_id,
            defect_code="D03_INCONSISTENT_SIZE",
            defect_name="Inconsistent Dot Size / Line Width",
            description="The dispensing dots become smaller after the machine has been running for around 20 minutes.",
            observations=[
                Observation(
                    observation_type=ObservationType.NOZZLE_CONDITION,
                    value="drips_after_dispense",
                    statement_type=StatementType.USER_OBSERVATION,
                    source=EvidenceSource.USER,
                )
            ],
        )
    )
    initial_result = engine.diagnose(initial_case)
    assert initial_result.analysis_revision is not None
    repo.save_initial_case(initial_case, initial_result)
    revision_1_observation_ids = {obs.id for obs in initial_case.observations}

    # Capture revision 1 state for immutability verification
    rev1_before = repo.get_analysis_revision(case_id, 1)
    assert rev1_before is not None
    rev1_snapshot_before = copy.deepcopy(rev1_before.result_snapshot)
    rev1_analyzed_at_before = rev1_before.analyzed_at

    # 2. Reconstruct case and submit Q01 follow-up answer
    reconstructed = repo.load_structured_case(case_id)
    assert reconstructed is not None

    answer = QuestionAnswer(
        question_id="Q01",
        answer_value="after_prolonged_operation",
        answer_text="Issue starts after 2 hours of continuous running",
        source=EvidenceSource.USER,
    )
    updated_case, result2 = engine.submit_question_answer(reconstructed, answer)
    assert result2.analysis_revision is not None
    assert result2.analysis_revision.revision_number == 2

    # 3. Append revision 2 via repository
    rev2_model = repo.append_question_answer_revision(
        case=updated_case,
        answer=answer,
        result=result2,
        expected_revision=1,
    )
    assert rev2_model.revision_number == 2

    # 4. Verify question answer persistence
    qa_list = repo.get_case_question_answers(case_id)
    assert len(qa_list) == 1
    assert qa_list[0].question_id == "Q01"
    assert qa_list[0].answer_value == "after_prolonged_operation"
    assert qa_list[0].answer_text == "Issue starts after 2 hours of continuous running"
    assert qa_list[0].resulting_revision_number == 2

    # 5. Verify observation first_seen_revision tracking
    observations = repo.get_case_observations(case_id)
    for obs in observations:
        if obs.observation_id in revision_1_observation_ids:
            assert obs.first_seen_revision == 1
        else:
            assert obs.first_seen_revision == 2

    assert any(o.value == "after_prolonged_operation" for o in observations)
    assert any(o.value == "Q01:after_prolonged_operation" for o in observations)

    # 6. Verify revision 1 remains completely immutable
    rev1_after = repo.get_analysis_revision(case_id, 1)
    assert rev1_after is not None
    assert rev1_after.analyzed_at == rev1_analyzed_at_before
    assert rev1_after.result_snapshot == rev1_snapshot_before

    # 7. Verify revision 2 snapshot parity
    rev2_after = repo.get_analysis_revision(case_id, 2)
    assert rev2_after is not None
    assert rev2_after.revision_number == 2
    assert rev2_after.result_snapshot == result2.model_dump(mode="json")

    # 8. Verify list_case_revisions
    rev_numbers = repo.list_case_revisions(case_id)
    assert rev_numbers == [1, 2]

    # 9. Verify load_structured_case includes all 2 revisions and 1 answer
    final_case = repo.load_structured_case(case_id)
    assert final_case is not None
    assert len(final_case.analysis_revisions) == 2
    assert final_case.analysis_revisions[0].revision_number == 1
    assert final_case.analysis_revisions[1].revision_number == 2
    assert len(final_case.previous_answers) == 1
    assert final_case.previous_answers[0].question_id == "Q01"


def test_append_question_answer_revision_unknown_answer_no_observation(case_repo):
    """Verify UNKNOWN answer produces no new observation but persists answer and advances revision."""
    repo, tracked_ids = case_repo
    engine = DiagnosticEngine()

    case_id = str(uuid.uuid4())
    tracked_ids.append(case_id)

    initial_case = engine.prepare_case(
        StructuredCase(
            case_id=case_id,
            defect_code="D03_INCONSISTENT_SIZE",
            defect_name="Inconsistent Dot Size / Line Width",
            description="The dispensing dots become smaller after the machine has been running for around 20 minutes.",
            observations=[
                Observation(
                    observation_type=ObservationType.NOZZLE_CONDITION,
                    value="drips_after_dispense",
                    statement_type=StatementType.USER_OBSERVATION,
                    source=EvidenceSource.USER,
                )
            ],
        )
    )
    initial_result = engine.diagnose(initial_case)
    assert initial_result.analysis_revision is not None
    repo.save_initial_case(initial_case, initial_result)

    # Reconstruct and submit UNKNOWN answer
    reconstructed = repo.load_structured_case(case_id)
    assert reconstructed is not None
    initial_obs_count = len(reconstructed.observations)

    unknown_answer = QuestionAnswer(
        question_id="Q01",
        answer_value=AnswerValue.UNKNOWN.value,
        answer_text="Technician could not confirm timing",
        source=EvidenceSource.USER,
    )
    updated_case, result2 = engine.submit_question_answer(reconstructed, unknown_answer)
    assert result2.analysis_revision is not None
    assert result2.analysis_revision.revision_number == 2

    # Append revision 2
    repo.append_question_answer_revision(
        case=updated_case,
        answer=unknown_answer,
        result=result2,
        expected_revision=1,
    )

    # Verify no new observation was created in database
    db_obs = repo.get_case_observations(case_id)
    assert len(db_obs) == initial_obs_count

    # Verify answer was persisted
    qa_list = repo.get_case_question_answers(case_id)
    assert len(qa_list) == 1
    assert qa_list[0].question_id == "Q01"
    assert qa_list[0].answer_value == AnswerValue.UNKNOWN.value
    assert qa_list[0].resulting_revision_number == 2

    # Verify reconstruction includes UNKNOWN answer
    reloaded = repo.load_structured_case(case_id)
    assert reloaded is not None
    assert len(reloaded.previous_answers) == 1
    assert reloaded.previous_answers[0].answer_value == AnswerValue.UNKNOWN.value
    assert len(reloaded.analysis_revisions) == 2


def test_stale_expected_revision_rejected_with_no_writes(case_repo, db_session):
    """Verify that expected_revision < latest_revision raises StaleRevisionError
    and creates zero new rows."""
    repo, tracked_ids = case_repo
    engine = DiagnosticEngine()

    case_id = str(uuid.uuid4())
    tracked_ids.append(case_id)

    # 1. Revision 1
    case = engine.prepare_case(
        StructuredCase(
            case_id=case_id,
            defect_code="D03_INCONSISTENT_SIZE",
            defect_name="Inconsistent Dot Size / Line Width",
            description="The dispensing dots become smaller after the machine has been running for around 20 minutes.",
            observations=[
                Observation(
                    observation_type=ObservationType.NOZZLE_CONDITION,
                    value="drips_after_dispense",
                    statement_type=StatementType.USER_OBSERVATION,
                    source=EvidenceSource.USER,
                )
            ],
        )
    )
    res1 = engine.diagnose(case)
    assert res1.analysis_revision is not None
    repo.save_initial_case(case, res1)
    db_session.commit()

    # 2. Append Revision 2
    case_v1 = repo.load_structured_case(case_id)
    ans1 = QuestionAnswer(question_id="Q01", answer_value="after_prolonged_operation")
    case_v2, res2 = engine.submit_question_answer(case_v1, ans1)
    repo.append_question_answer_revision(case_v2, ans1, res2, expected_revision=1)
    db_session.commit()

    # Snapshot database state after revision 2
    revs_before = repo.list_case_revisions(case_id)
    obs_before = repo.get_case_observations(case_id)
    qa_before = repo.get_case_question_answers(case_id)
    assert revs_before == [1, 2]

    # 3. Attempt append with stale expected_revision=1 (latest is 2)
    ans2 = QuestionAnswer(question_id="Q03", answer_value="YES")
    # Simulate someone acting on old revision 1 state
    fake_case, res3 = engine.submit_question_answer(case_v2, ans2)

    with pytest.raises(StaleRevisionError) as exc_info:
        repo.append_question_answer_revision(
            case=fake_case,
            answer=ans2,
            result=res3,
            expected_revision=1,  # STALE: current is 2
        )

    assert exc_info.value.case_id == case_id
    assert exc_info.value.expected_revision == 1
    assert exc_info.value.current_revision == 2

    # 4. Verify zero new rows were created
    assert repo.list_case_revisions(case_id) == revs_before
    assert len(repo.get_case_observations(case_id)) == len(obs_before)
    assert len(repo.get_case_question_answers(case_id)) == len(qa_before)


def test_contract_mismatch_revision_number_rejected(case_repo, db_session):
    """Verify that if result.analysis_revision.revision_number != latest + 1,
    the operation is rejected as a contract mismatch with no writes."""
    repo, tracked_ids = case_repo
    engine = DiagnosticEngine()

    case_id = str(uuid.uuid4())
    tracked_ids.append(case_id)

    case = engine.prepare_case(
        StructuredCase(
            case_id=case_id,
            defect_code="D03_INCONSISTENT_SIZE",
            defect_name="Inconsistent Dot Size / Line Width",
            description="The dispensing dots become smaller after the machine has been running for around 20 minutes.",
        )
    )
    res = engine.diagnose(case)
    assert res.analysis_revision is not None
    repo.save_initial_case(case, res)
    db_session.commit()

    reconstructed = repo.load_structured_case(case_id)
    ans = QuestionAnswer(question_id="Q01", answer_value="after_prolonged_operation")

    # Mismatched revision number (e.g. 5 instead of 2)
    bad_result = DiagnosisResult(
        case_id=case_id,
        analysis_revision=AnalysisRevision(revision_number=5),
    )

    with pytest.raises(ValueError, match="Contract mismatch"):
        repo.append_question_answer_revision(
            case=reconstructed,
            answer=ans,
            result=bad_result,
            expected_revision=1,
        )

    assert repo.list_case_revisions(case_id) == [1]
    assert repo.get_case_question_answers(case_id) == []


def test_duplicate_competing_revision_rejected_by_constraints(case_repo, db_session):
    """Verify that database unique constraints prevent duplicate (case_id, resulting_revision_number)
    for question answers and analysis revisions."""
    repo, tracked_ids = case_repo
    engine = DiagnosticEngine()

    case_id = str(uuid.uuid4())
    tracked_ids.append(case_id)

    case = engine.prepare_case(
        StructuredCase(
            case_id=case_id,
            defect_code="D03_INCONSISTENT_SIZE",
            defect_name="Inconsistent Dot Size / Line Width",
            description="The dispensing dots become smaller after the machine has been running for around 20 minutes.",
        )
    )
    res = engine.diagnose(case)
    assert res.analysis_revision is not None
    repo.save_initial_case(case, res)

    # Append revision 2 successfully
    case_v1 = repo.load_structured_case(case_id)
    ans = QuestionAnswer(question_id="Q01", answer_value="after_prolonged_operation")
    case_v2, res2 = engine.submit_question_answer(case_v1, ans)
    repo.append_question_answer_revision(case_v2, ans, res2, expected_revision=1)

    # Competing write trying to insert another revision 2 directly
    duplicate_qa = QuestionAnswerModel(
        case_id=case_id,
        question_id="Q02",
        answer_value="all_points",
        source="USER",
        answered_at=case.created_at,
        resulting_revision_number=2,  # Already claimed by revision 2!
    )
    db_session.add(duplicate_qa)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()

    duplicate_rev = AnalysisRevisionModel(
        case_id=case_id,
        revision_number=2,  # Already claimed!
        analyzed_at=case.created_at,
        issue_condition="UNRESOLVED",
        result_snapshot={"analysis_revision": {"revision_number": 2}},
    )
    db_session.add(duplicate_rev)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_atomic_rollback_on_append_failure_leaves_no_partial_writes():
    """Verify that if an error occurs after flushing answer and new observations,
    all changes roll back completely and unrelated data survives intact."""
    factory = get_session_factory()
    engine = DiagnosticEngine()

    control_id = str(uuid.uuid4())
    test_id = str(uuid.uuid4())

    try:
        # 1. Control case (persisted completely)
        with factory() as session:
            repo = CaseRepository(session=session)
            control_case = engine.prepare_case(
                StructuredCase(
                    case_id=control_id,
                    defect_code="D03_INCONSISTENT_SIZE",
                    defect_name="Inconsistent Dot Size / Line Width",
                    description="The dispensing dots become smaller after the machine has been running for around 20 minutes.",
                )
            )
            control_res = engine.diagnose(control_case)
            assert control_res.analysis_revision is not None
            repo.save_initial_case(control_case, control_res)
            session.commit()

        # 2. Test case (persisted initially as Revision 1)
        with factory() as session:
            repo = CaseRepository(session=session)
            test_case = engine.prepare_case(
                StructuredCase(
                    case_id=test_id,
                    defect_code="D03_INCONSISTENT_SIZE",
                    defect_name="Inconsistent Dot Size / Line Width",
                    description="The dispensing dots become smaller after the machine has been running for around 20 minutes.",
                    observations=[
                        Observation(
                            observation_type=ObservationType.NOZZLE_CONDITION,
                            value="drips_after_dispense",
                            statement_type=StatementType.USER_OBSERVATION,
                            source=EvidenceSource.USER,
                        )
                    ],
                )
            )
            test_res = engine.diagnose(test_case)
            assert test_res.analysis_revision is not None
            repo.save_initial_case(test_case, test_res)
            session.commit()

        # 3. Attempt append with failure induced after flush
        with factory() as session:
            repo = CaseRepository(session=session)
            reconstructed = repo.load_structured_case(test_id)
            assert reconstructed is not None
            ans = QuestionAnswer(question_id="Q01", answer_value="after_prolonged_operation")
            updated_case, result2 = engine.submit_question_answer(reconstructed, ans)

            # Fault injection: let append execute its internal logic, but inject error
            with pytest.raises(RuntimeError, match="Simulated crash before commit"):
                # We start a transaction, call append, verify rows flushed, then raise
                repo.append_question_answer_revision(
                    case=updated_case,
                    answer=ans,
                    result=result2,
                    expected_revision=1,
                )
                # Verify rows were indeed staged in this active session
                staged_qa = session.scalars(
                    select(QuestionAnswerModel).where(QuestionAnswerModel.case_id == test_id)
                ).all()
                assert len(staged_qa) == 1
                raise RuntimeError("Simulated crash before commit")

        # 4. Verify from fresh independent session
        with factory() as fresh_session:
            fresh_repo = CaseRepository(session=fresh_session)

            # Test case: revision 2 does NOT exist, no QA row exists, no new observation exists
            assert fresh_repo.list_case_revisions(test_id) == [1]
            assert fresh_repo.get_case_question_answers(test_id) == []
            assert len(fresh_repo.get_case_observations(test_id)) == 1

            # Control case: survives completely intact
            assert fresh_repo.list_case_revisions(control_id) == [1]
            assert fresh_repo.get_case(control_id) is not None

    finally:
        with factory() as clean_session:
            clean_session.execute(delete(CaseModel).where(CaseModel.case_id.in_([control_id, test_id])))
            clean_session.commit()


# ---------------------------------------------------------------------------
# DLK-M3-011 Correction: Case Reconstruction Concurrency & Competing Appends
# ---------------------------------------------------------------------------

def test_load_structured_case_consistency_under_interleaved_writes():
    """Verify that case reconstruction in an active session locks the case row,
    preventing an interleaved session from appending revision 2 until reconstruction finishes.
    Verify reconstruction cannot combine revision-1 observations with revision-2 answers/history.
    Verify a later append rejects a diagnosis calculated from an inconsistent/torn mixed state.
    """
    factory = get_session_factory()
    engine = DiagnosticEngine()

    case_id = str(uuid.uuid4())

    try:
        # Setup: Persist initial case (Revision 1)
        with factory() as init_session:
            repo = CaseRepository(session=init_session)
            initial_case = engine.prepare_case(
                StructuredCase(
                    case_id=case_id,
                    defect_code="D03_INCONSISTENT_SIZE",
                    defect_name="Inconsistent Dot Size / Line Width",
                    description="The dispensing dots become smaller after 20 minutes.",
                    observations=[
                        Observation(
                            observation_type=ObservationType.NOZZLE_CONDITION,
                            value="drips_after_dispense",
                            statement_type=StatementType.USER_OBSERVATION,
                            source=EvidenceSource.USER,
                        )
                    ],
                )
            )
            res1 = engine.diagnose(initial_case)
            assert res1.analysis_revision is not None
            repo.save_initial_case(initial_case, res1)
            init_session.commit()

        # Step 1: Begin reconstructing revision 1 in Session 1
        with factory() as session_1:
            repo_1 = CaseRepository(session=session_1)

            # Session 1 acquires row lock via for_update=True and reconstructs case
            case_v1 = repo_1.load_structured_case(case_id, for_update=True)
            assert case_v1 is not None
            assert len(case_v1.observations) == 1
            assert len(case_v1.previous_answers) == 0
            assert len(case_v1.analysis_revisions) == 1

            # Step 2: Interleave another session (Session 2) appending an answer and revision 2
            ans1 = QuestionAnswer(
                question_id="Q01",
                answer_value="after_prolonged_operation",
                answer_text="Issue happens after 2 hours",
                source=EvidenceSource.USER,
            )
            s2_started = threading.Event()
            s2_finished = threading.Event()
            s2_errors: list[Exception] = []

            def session_2_append_worker():
                with factory() as session_2:
                    repo_2 = CaseRepository(session=session_2)
                    c2_copy = copy.deepcopy(case_v1)
                    c2_updated, res2 = engine.submit_question_answer(c2_copy, ans1)
                    s2_started.set()
                    try:
                        # This should block on SELECT ... FOR UPDATE because Session 1 holds FOR SHARE
                        repo_2.append_question_answer_revision(
                            case=c2_updated,
                            answer=ans1,
                            result=res2,
                            expected_revision=1,
                        )
                        session_2.commit()
                    except Exception as e:
                        s2_errors.append(e)
                    finally:
                        s2_finished.set()

            t2 = threading.Thread(target=session_2_append_worker)
            t2.start()

            # Wait for thread 2 to start and attempt append
            assert s2_started.wait(timeout=2.0)
            # Sleep briefly to ensure thread 2 has executed up to the row lock
            time.sleep(0.3)

            # Verify that Session 2 is blocked and has NOT finished
            assert not s2_finished.is_set(), "Session 2 should be blocked by Session 1's lock!"
            assert t2.is_alive()

            # Step 3: Verify reconstruction in Session 1 cannot combine revision-1 observations
            # with revision-2 answers/history.
            # While Session 2 is blocked, re-verifying Session 1 state:
            assert len(case_v1.observations) == 1
            assert len(case_v1.previous_answers) == 0
            assert len(case_v1.analysis_revisions) == 1
            assert case_v1.observations[0].value == "drips_after_dispense"

            # Now release Session 1 lock by committing/closing Session 1
            session_1.commit()

        # Thread 2 should now unblock and complete successfully
        t2.join(timeout=5.0)
        assert not t2.is_alive()
        assert s2_finished.is_set()
        assert len(s2_errors) == 0

        # Verify from fresh session that Revision 2 is now cleanly persisted
        with factory() as session_3:
            repo_3 = CaseRepository(session=session_3)
            case_v2 = repo_3.load_structured_case(case_id)
            assert case_v2 is not None
            assert len(case_v2.observations) == 3
            assert len(case_v2.previous_answers) == 1
            assert len(case_v2.analysis_revisions) == 2

            # Step 4: Verify a later append cannot silently accept a diagnosis
            # calculated from a mixed state.
            ans2 = QuestionAnswer(
                question_id="Q02",
                answer_value="all_points",
                answer_text="Every point is affected",
                source=EvidenceSource.USER,
            )
            # Mixed case: only revision 1 observations, but previous answers and revisions from v2
            mixed_case = copy.deepcopy(case_v2)
            mixed_case.observations = [copy.deepcopy(case_v1.observations[0])]  # MISSING revision 2 observation!

            # Evaluate diagnosis from this mixed state
            updated_mixed, res3 = engine.submit_question_answer(mixed_case, ans2)
            assert res3.analysis_revision is not None
            assert res3.analysis_revision.revision_number == 3

            # Attempt append with expected_revision=2: must be REJECTED!
            with pytest.raises(ValueError, match="Inconsistent case state: case is missing persisted observations"):
                repo_3.append_question_answer_revision(
                    case=updated_mixed,
                    answer=ans2,
                    result=res3,
                    expected_revision=2,
                )

            # Also verify rejection if previous_answers is missing persisted answers
            mixed_case_no_answers = copy.deepcopy(case_v2)
            mixed_case_no_answers.previous_answers = []  # MISSING revision 2 answer!
            updated_mixed_2, res3_b = engine.submit_question_answer(mixed_case_no_answers, ans2)
            assert res3_b.analysis_revision is not None
            res3_b.analysis_revision.revision_number = 3

            with pytest.raises(ValueError, match="Inconsistent case state: case previous_answers"):
                repo_3.append_question_answer_revision(
                    case=updated_mixed_2,
                    answer=ans2,
                    result=res3_b,
                    expected_revision=2,
                )

            # Verify no partial writes occurred and revisions remain strictly [1, 2]
            assert repo_3.list_case_revisions(case_id) == [1, 2]
            assert len(repo_3.get_case_question_answers(case_id)) == 1

    finally:
        with factory() as clean_session:
            clean_session.execute(delete(CaseModel).where(CaseModel.case_id == case_id))
            clean_session.commit()


def test_concurrent_competing_repository_appends_only_one_succeeds():
    """Exercise two actual concurrent competing repository appends on the same case
    at revision 1. Verify exactly one succeeds and the other is rejected with
    StaleRevisionError or IntegrityError without partial writes."""
    factory = get_session_factory()
    engine = DiagnosticEngine()

    case_id = str(uuid.uuid4())

    try:
        # Setup: Persist initial case (Revision 1)
        with factory() as init_session:
            repo = CaseRepository(session=init_session)
            initial_case = engine.prepare_case(
                StructuredCase(
                    case_id=case_id,
                    defect_code="D03_INCONSISTENT_SIZE",
                    defect_name="Inconsistent Dot Size / Line Width",
                    description="The dispensing dots become smaller after 20 minutes.",
                )
            )
            res1 = engine.diagnose(initial_case)
            assert res1.analysis_revision is not None
            repo.save_initial_case(initial_case, res1)
            init_session.commit()

        # Reconstruct base case at revision 1
        with factory() as read_session:
            repo = CaseRepository(session=read_session)
            case_v1 = repo.load_structured_case(case_id)
            assert case_v1 is not None

        # Prepare two competing answers and diagnoses for revision 2
        ans_a = QuestionAnswer(
            question_id="Q01",
            answer_value="after_prolonged_operation",
            answer_text="Competitor A",
            source=EvidenceSource.USER,
        )
        case_a, res_a = engine.submit_question_answer(copy.deepcopy(case_v1), ans_a)

        ans_b = QuestionAnswer(
            question_id="Q02",
            answer_value="all_points",
            answer_text="Competitor B",
            source=EvidenceSource.USER,
        )
        case_b, res_b = engine.submit_question_answer(copy.deepcopy(case_v1), ans_b)

        # Synchronize concurrent execution with a threading barrier
        barrier = threading.Barrier(2)
        results: dict[str, int] = {}
        errors: dict[str, Exception] = {}

        def competitor_worker(worker_id: str, comp_case, comp_ans, comp_res):
            with factory() as session:
                repo = CaseRepository(session=session)
                try:
                    barrier.wait(timeout=5.0)
                    rev_model = repo.append_question_answer_revision(
                        case=comp_case,
                        answer=comp_ans,
                        result=comp_res,
                        expected_revision=1,
                    )
                    session.commit()
                    results[worker_id] = rev_model.revision_number
                except Exception as exc:
                    session.rollback()
                    errors[worker_id] = exc

        thread_a = threading.Thread(target=competitor_worker, args=("A", case_a, ans_a, res_a))
        thread_b = threading.Thread(target=competitor_worker, args=("B", case_b, ans_b, res_b))

        thread_a.start()
        thread_b.start()

        thread_a.join(timeout=10.0)
        thread_b.join(timeout=10.0)

        assert not thread_a.is_alive()
        assert not thread_b.is_alive()

        # Assert exactly one succeeded and one failed
        assert len(results) == 1, f"Expected exactly 1 success, got {len(results)}: {results}"
        assert len(errors) == 1, f"Expected exactly 1 failure, got {len(errors)}: {errors}"

        winner_id = list(results.keys())[0]
        loser_id = list(errors.keys())[0]
        assert results[winner_id] == 2

        loser_exc = errors[loser_id]
        # The competing append is rejected due to optimistic concurrency check (StaleRevisionError)
        # or underlying PostgreSQL unique constraints (IntegrityError)
        assert isinstance(loser_exc, (StaleRevisionError, IntegrityError))
        if isinstance(loser_exc, StaleRevisionError):
            assert loser_exc.expected_revision == 1
            assert loser_exc.current_revision == 2

        # Verify from fresh independent session that state is clean with no partial writes
        with factory() as verify_session:
            verify_repo = CaseRepository(session=verify_session)
            revisions = verify_repo.list_case_revisions(case_id)
            assert revisions == [1, 2]

            qa_list = verify_repo.get_case_question_answers(case_id)
            assert len(qa_list) == 1
            expected_qid = "Q01" if winner_id == "A" else "Q02"
            assert qa_list[0].question_id == expected_qid
            assert qa_list[0].resulting_revision_number == 2

    finally:
        with factory() as clean_session:
            clean_session.execute(delete(CaseModel).where(CaseModel.case_id == case_id))
            clean_session.commit()


def test_concurrent_injected_sessions_load_and_append_flow_avoids_deadlock_and_rejects_stale():
    """Verify that two independent injected sessions performing the complete default
    load -> diagnose -> append workflow avoid shared-lock upgrade deadlocks by design.
    Verify exactly one succeeds and the other receives StaleRevisionError with no partial writes.
    Explicitly assert that neither DeadlockDetected nor generic IntegrityError is returned.
    """
    factory = get_session_factory()
    engine = DiagnosticEngine()

    case_id = str(uuid.uuid4())

    try:
        # Setup: Persist initial case at Revision 1
        with factory() as init_session:
            repo = CaseRepository(session=init_session)
            initial_case = engine.prepare_case(
                StructuredCase(
                    case_id=case_id,
                    defect_code="D03_INCONSISTENT_SIZE",
                    defect_name="Inconsistent Dot Size / Line Width",
                    description="The dispensing dots become smaller after 20 minutes.",
                )
            )
            res1 = engine.diagnose(initial_case)
            assert res1.analysis_revision is not None
            repo.save_initial_case(initial_case, res1)
            init_session.commit()

        # Two concurrent workers using injected sessions performing the complete default flow:
        # load_structured_case() -> diagnose/submit_question_answer -> append_question_answer_revision() -> commit
        barrier = threading.Barrier(2)
        results: dict[str, int] = {}
        errors: dict[str, Exception] = {}

        def complete_workflow_worker(worker_id: str, qid: str, qval: str):
            with factory() as session:
                repo = CaseRepository(session=session)
                try:
                    # 1. Load case using the default workflow (no explicit for_update flag)
                    loaded_case = repo.load_structured_case(case_id)
                    assert loaded_case is not None

                    # 2. Process follow-up question answer
                    ans = QuestionAnswer(
                        question_id=qid,
                        answer_value=qval,
                        source=EvidenceSource.USER,
                    )
                    updated_case, diag_res = engine.submit_question_answer(loaded_case, ans)

                    # Synchronize before competing append
                    barrier.wait(timeout=5.0)

                    # 3. Append revision within the same injected transaction
                    rev_model = repo.append_question_answer_revision(
                        case=updated_case,
                        answer=ans,
                        result=diag_res,
                        expected_revision=1,
                    )
                    session.commit()
                    results[worker_id] = rev_model.revision_number
                except Exception as exc:
                    session.rollback()
                    errors[worker_id] = exc

        thread_1 = threading.Thread(
            target=complete_workflow_worker,
            args=("Worker-1", "Q01", "after_prolonged_operation"),
        )
        thread_2 = threading.Thread(
            target=complete_workflow_worker,
            args=("Worker-2", "Q02", "all_points"),
        )

        thread_1.start()
        thread_2.start()

        thread_1.join(timeout=10.0)
        thread_2.join(timeout=10.0)

        assert not thread_1.is_alive()
        assert not thread_2.is_alive()

        # Exactly one worker succeeded and one failed
        assert len(results) == 1, f"Expected exactly 1 success, got {len(results)}: {results}"
        assert len(errors) == 1, f"Expected exactly 1 error, got {len(errors)}: {errors}"

        winner_id = list(results.keys())[0]
        loser_id = list(errors.keys())[0]
        assert results[winner_id] == 2

        loser_exc = errors[loser_id]

        # Explicitly verify that deadlock was avoided by design
        assert "deadlock" not in str(loser_exc).lower(), f"Deadlock occurred: {loser_exc}"

        # Explicitly verify that the error is NOT a generic IntegrityError
        assert not isinstance(loser_exc, IntegrityError), (
            f"Expected StaleRevisionError, but got generic IntegrityError: {loser_exc}"
        )

        # Explicitly verify the expected error is StaleRevisionError with accurate revision context
        assert isinstance(loser_exc, StaleRevisionError), (
            f"Expected StaleRevisionError, got: {type(loser_exc).__name__}: {loser_exc}"
        )
        assert loser_exc.expected_revision == 1
        assert loser_exc.current_revision == 2

        # Verify from fresh independent session that state is clean with no partial writes
        with factory() as verify_session:
            verify_repo = CaseRepository(session=verify_session)
            revisions = verify_repo.list_case_revisions(case_id)
            assert revisions == [1, 2]

            qa_list = verify_repo.get_case_question_answers(case_id)
            assert len(qa_list) == 1
            expected_qid = "Q01" if winner_id == "Worker-1" else "Q02"
            assert qa_list[0].question_id == expected_qid
            assert qa_list[0].resulting_revision_number == 2

    finally:
        with factory() as clean_session:
            clean_session.execute(delete(CaseModel).where(CaseModel.case_id == case_id))
            clean_session.commit()


def test_load_structured_case_snapshot_boundary_retries_on_interleaved_commit():
    """Verify that load_structured_case via the default loading path detects a commit
    that occurs between reading CaseModel and reading revision history, retries cleanly,
    and returns metadata and history that belong to the exact same revision."""
    factory = get_session_factory()
    engine_db = get_engine()
    diag_engine = DiagnosticEngine()

    case_id = str(uuid.uuid4())

    try:
        # 1. Persist initial case at Revision 1
        with factory() as s:
            repo = CaseRepository(session=s)
            c = diag_engine.prepare_case(
                StructuredCase(
                    case_id=case_id,
                    defect_code="D03_INCONSISTENT_SIZE",
                    defect_name="Inconsistent Dot Size",
                    description="Dots are shrinking",
                    observations=[
                        Observation(
                            observation_type=ObservationType.NOZZLE_CONDITION,
                            value="drips_after_dispense",
                        )
                    ],
                )
            )
            res = diag_engine.diagnose(c)
            repo.save_initial_case(c, res)
            s.commit()

        # 2. Set up deterministic interleave:
        # An independent session commits revision 2 and evolves CaseModel's issue_condition
        # between the reader reading CaseModel and reading observations/revisions on attempt 0.
        interleaved = False

        def interleave_commit_hook(conn, cursor, statement, parameters, context, executemany):
            nonlocal interleaved
            # Trigger hook on the reader's first observation query (right after reading CaseModel)
            if "case_observations" in statement.lower() and not interleaved:
                interleaved = True
                with factory() as ws:
                    w_repo = CaseRepository(session=ws)
                    w_case = w_repo.load_structured_case(case_id)
                    assert w_case is not None
                    ans = QuestionAnswer(
                        question_id="Q01",
                        answer_value="after_prolonged_operation",
                        source=EvidenceSource.USER,
                    )
                    up_case, res2 = diag_engine.submit_question_answer(w_case, ans)
                    res2.issue_condition = IssueCondition.RECOVERY_PENDING_VERIFICATION
                    w_repo.append_question_answer_revision(
                        case=up_case,
                        answer=ans,
                        result=res2,
                        expected_revision=1,
                    )
                    ws.commit()

        event.listen(engine_db, "before_cursor_execute", interleave_commit_hook)

        try:
            # 3. Reader exercises the default loading path (for_update=False)
            with factory() as rs:
                r_repo = CaseRepository(session=rs)
                loaded = r_repo.load_structured_case(case_id)
                assert loaded is not None

                # 4. Verify returned metadata and history belong to the EXACT same revision (Revision 2)
                assert loaded.issue_condition == IssueCondition.RECOVERY_PENDING_VERIFICATION
                assert len(loaded.analysis_revisions) == 2
                assert loaded.analysis_revisions[-1].revision_number == 2
                assert len(loaded.observations) == 3
                assert len(loaded.previous_answers) == 1
                assert loaded.previous_answers[0].question_id == "Q01"
        finally:
            event.remove(engine_db, "before_cursor_execute", interleave_commit_hook)

    finally:
        with factory() as s:
            s.execute(delete(CaseModel).where(CaseModel.case_id == case_id))
            s.commit()


def test_load_structured_case_exhausted_retries_raises_explicit_runtime_error():
    """Verify that if continuous concurrent writes prevent a verified snapshot,
    load_structured_case explicitly fails with RuntimeError rather than returning an unverified attempt."""
    factory = get_session_factory()
    diag_engine = DiagnosticEngine()
    case_id = str(uuid.uuid4())

    try:
        with factory() as s:
            repo = CaseRepository(session=s)
            c = diag_engine.prepare_case(
                StructuredCase(
                    case_id=case_id,
                    defect_code="D03_INCONSISTENT_SIZE",
                    defect_name="Inconsistent Dot Size",
                    description="Dots are shrinking",
                )
            )
            res = diag_engine.diagnose(c)
            repo.save_initial_case(c, res)
            s.commit()

        calls = [0]
        with factory() as rs:
            r_repo = CaseRepository(session=rs)

            # Simulate continuous revision churn across all attempts
            def churning_scalar(stmt, *args, **kwargs):
                calls[0] += 1
                return calls[0]

            rs.scalar = churning_scalar  # type: ignore
            with pytest.raises(RuntimeError, match="Could not obtain a verified consistent snapshot"):
                r_repo.load_structured_case(case_id)
    finally:
        with factory() as s:
            s.execute(delete(CaseModel).where(CaseModel.case_id == case_id))
            s.commit()


# ---------------------------------------------------------------------------
# Check Result Persistence Tests (DLK-M3-013)
# ---------------------------------------------------------------------------

def test_append_check_result_revision_round_trip(case_repo, db_session):
    """Verify check result persistence round-trips:
    - CaseCheckResultModel is persisted with resulting_revision_number == 2
    - Unrestricted text fields (finding_details, outcome) round-trip without truncation
    - Newly introduced observations have first_seen_revision == 2
    - Prior observations and revisions are preserved
    - load_structured_case reconstructs previous_check_results with exact fidelity
    """
    repo, tracked_ids = case_repo
    engine = DiagnosticEngine()
    case_id = str(uuid.uuid4())
    tracked_ids.append(case_id)

    initial_case = engine.prepare_case(
        StructuredCase(
            case_id=case_id,
            defect_code="D03_INCONSISTENT_SIZE",
            defect_name="Inconsistent Dot Size",
            description="Dots shrinking over time",
            observations=[
                Observation(
                    observation_type=ObservationType.NOZZLE_CONDITION,
                    value="drips_after_dispense",
                    statement_type=StatementType.USER_OBSERVATION,
                    source=EvidenceSource.USER,
                )
            ],
        )
    )
    result1 = engine.diagnose(initial_case)
    repo.save_initial_case(initial_case, result1)
    db_session.commit()

    long_finding_details = "Visual inspection under 50x microscope showed no debris or dried material: " + "detail_" * 30
    check = CheckResult(
        check_id="ACT01",
        execution_status=CheckExecutionStatus.COMPLETED,
        finding=CheckFinding.CONTRADICTS,
        finding_details=long_finding_details,
        outcome="no_blockage",
        source=EvidenceSource.USER_CHECK_RESULT,
    )
    loaded_case = repo.load_structured_case(case_id)
    assert loaded_case is not None
    updated_case, result2 = engine.submit_check_result(loaded_case, check)

    rev_model = repo.append_check_result_revision(
        case=updated_case,
        check_result=check,
        result=result2,
        expected_revision=1,
    )
    db_session.commit()
    assert rev_model.revision_number == 2

    # Verify direct query on CaseCheckResultModel
    cr_models = repo.get_case_check_results(case_id)
    assert len(cr_models) == 1
    assert cr_models[0].check_id == "ACT01"
    assert cr_models[0].execution_status == CheckExecutionStatus.COMPLETED.value
    assert cr_models[0].finding == CheckFinding.CONTRADICTS.value
    assert cr_models[0].finding_details == long_finding_details
    assert cr_models[0].outcome == "no_blockage"
    assert cr_models[0].source == EvidenceSource.USER_CHECK_RESULT.value
    assert cr_models[0].resulting_revision_number == 2

    # Verify reconstruction through load_structured_case
    reconstructed = repo.load_structured_case(case_id)
    assert reconstructed is not None
    assert len(reconstructed.analysis_revisions) == 2
    assert reconstructed.analysis_revisions[-1].revision_number == 2
    assert len(reconstructed.previous_check_results) == 1
    rec_check = reconstructed.previous_check_results[0]
    assert rec_check.check_id == "ACT01"
    assert rec_check.execution_status == CheckExecutionStatus.COMPLETED
    assert rec_check.finding == CheckFinding.CONTRADICTS
    assert rec_check.finding_details == long_finding_details
    assert rec_check.outcome == "no_blockage"
    assert rec_check.source == EvidenceSource.USER_CHECK_RESULT

    # Check observations: initial observation has first_seen_revision=1, new ones have first_seen_revision=2
    obs_by_id = {o.observation_id: o for o in repo.get_case_observations(case_id)}
    assert obs_by_id[initial_case.observations[0].id].first_seen_revision == 1
    new_obs_items = [o for o in obs_by_id.values() if o.first_seen_revision == 2]
    assert len(new_obs_items) >= 1


def test_append_check_result_revision_stale_expected_revision(case_repo, db_session):
    """Verify stale expected_revision raises StaleRevisionError without durable mutation."""
    repo, tracked_ids = case_repo
    engine = DiagnosticEngine()
    case_id = str(uuid.uuid4())
    tracked_ids.append(case_id)

    case = engine.prepare_case(
        StructuredCase(
            case_id=case_id,
            defect_code="D03_INCONSISTENT_SIZE",
            defect_name="Inconsistent Dot Size",
            description="Dots shrinking over time",
        )
    )
    result = engine.diagnose(case)
    repo.save_initial_case(case, result)
    db_session.commit()

    # Advance to revision 2 with a check result
    check1 = CheckResult(
        check_id="ACT01",
        execution_status=CheckExecutionStatus.COMPLETED,
        finding=CheckFinding.CONTRADICTS,
        outcome="no_blockage",
        source=EvidenceSource.USER_CHECK_RESULT,
    )
    loaded = repo.load_structured_case(case_id)
    assert loaded is not None
    up_case, res2 = engine.submit_check_result(loaded, check1)
    repo.append_check_result_revision(
        case=up_case,
        check_result=check1,
        result=res2,
        expected_revision=1,
    )
    db_session.commit()

    revs_before = repo.list_case_revisions(case_id)
    assert revs_before == [1, 2]
    cr_before = repo.get_case_check_results(case_id)
    assert len(cr_before) == 1

    # Attempt append with stale expected_revision=1 (latest is 2)
    check2 = CheckResult(
        check_id="ACT02",
        execution_status=CheckExecutionStatus.COMPLETED,
        finding=CheckFinding.SUPPORTS,
        outcome="air_bubbles_found",
        source=EvidenceSource.USER_CHECK_RESULT,
    )
    loaded_v2 = repo.load_structured_case(case_id)
    assert loaded_v2 is not None
    up_case2, res3 = engine.submit_check_result(loaded_v2, check2)

    with pytest.raises(StaleRevisionError) as exc_info:
        repo.append_check_result_revision(
            case=up_case2,
            check_result=check2,
            result=res3,
            expected_revision=1,  # STALE: current is 2
        )

    assert exc_info.value.case_id == case_id
    assert exc_info.value.expected_revision == 1
    assert exc_info.value.current_revision == 2

    # Verify zero new rows were created
    assert repo.list_case_revisions(case_id) == revs_before
    assert len(repo.get_case_check_results(case_id)) == len(cr_before)


def test_append_check_result_revision_rollback_on_failure(case_repo, db_session):
    """Verify that a failure after rows are flushed during append_check_result_revision
    causes the repository's transaction boundary to roll back naturally without manual rollback.
    Asserts:
    1. Both target and control cases have nonempty prior history (advanced to Rev 2).
    2. Expected revision and attempted revision are derived dynamically from baseline.
    3. Target case pending flushed check-result, observations, and revision exist before failure.
    4. Deliberate fault marker and immutable pending evidence are asserted outside the repository call.
    5. Failure raised before commit causes repository to roll back naturally.
    6. Fresh independent session confirms complete prior state is preserved identically
       (target == target_baseline and control == control_baseline).
    """
    repo, tracked_ids = case_repo
    engine = DiagnosticEngine()

    # 1. Create control case (Case A) and advance to Rev 3 with a question answer AND a prior check result
    control_id = str(uuid.uuid4())
    tracked_ids.append(control_id)
    control_case = engine.prepare_case(
        StructuredCase(
            case_id=control_id,
            defect_code="D03_INCONSISTENT_SIZE",
            defect_name="Inconsistent Dot Size",
            description="Control case for rollback isolation",
        )
    )
    control_res = engine.diagnose(control_case)
    repo.save_initial_case(control_case, control_res)

    control_loaded = repo.load_structured_case(control_id)
    assert control_loaded is not None
    control_ans = QuestionAnswer(
        question_id="Q01",
        answer_value="after_prolonged_operation",
        source=EvidenceSource.USER,
    )
    c_ctrl, res_ctrl = engine.submit_question_answer(control_loaded, control_ans)
    repo.append_question_answer_revision(c_ctrl, control_ans, res_ctrl, expected_revision=1)
    db_session.commit()

    control_loaded_rev2 = repo.load_structured_case(control_id)
    assert control_loaded_rev2 is not None
    control_prior_check = CheckResult(
        check_id="ACT02",
        execution_status=CheckExecutionStatus.COMPLETED,
        finding=CheckFinding.SUPPORTS,
        outcome="air_bubbles_found",
        source=EvidenceSource.USER_CHECK_RESULT,
    )
    c_ctrl_check, res_ctrl_check = engine.submit_check_result(control_loaded_rev2, control_prior_check)
    repo.append_check_result_revision(c_ctrl_check, control_prior_check, res_ctrl_check, expected_revision=2)
    db_session.commit()

    # 2. Create target case (Case B) and advance to Rev 3 with an answer AND a prior check result
    target_id = str(uuid.uuid4())
    tracked_ids.append(target_id)
    target_case = engine.prepare_case(
        StructuredCase(
            case_id=target_id,
            defect_code="D03_INCONSISTENT_SIZE",
            defect_name="Inconsistent Dot Size",
            description="Target case for repository post-flush rollback",
        )
    )
    target_res = engine.diagnose(target_case)
    repo.save_initial_case(target_case, target_res)

    target_loaded = repo.load_structured_case(target_id)
    assert target_loaded is not None
    target_ans = QuestionAnswer(
        question_id="Q01",
        answer_value="after_prolonged_operation",
        source=EvidenceSource.USER,
    )
    c_tgt, res_tgt = engine.submit_question_answer(target_loaded, target_ans)
    repo.append_question_answer_revision(c_tgt, target_ans, res_tgt, expected_revision=1)
    db_session.commit()

    target_loaded_rev2 = repo.load_structured_case(target_id)
    assert target_loaded_rev2 is not None
    target_prior_check = CheckResult(
        check_id="ACT02",
        execution_status=CheckExecutionStatus.COMPLETED,
        finding=CheckFinding.SUPPORTS,
        outcome="air_bubbles_found",
        source=EvidenceSource.USER_CHECK_RESULT,
    )
    c_tgt_check, res_tgt_check = engine.submit_check_result(target_loaded_rev2, target_prior_check)
    repo.append_check_result_revision(c_tgt_check, target_prior_check, res_tgt_check, expected_revision=2)
    db_session.commit()

    # Capture complete baselines from an independent session
    factory = get_session_factory()
    with factory() as session:
        target_baseline = capture_complete_case_state(session, target_id)
        control_baseline = capture_complete_case_state(session, control_id)

    # Verify nonempty baselines with both prior question answers AND prior check results
    assert len(target_baseline["analysis_revisions"]) >= 3
    assert len(target_baseline["question_answers"]) >= 1
    assert len(target_baseline["check_results"]) >= 1
    assert len(control_baseline["analysis_revisions"]) >= 3
    assert len(control_baseline["question_answers"]) >= 1
    assert len(control_baseline["check_results"]) >= 1

    baseline_rev = target_baseline["analysis_revisions"][-1]["revision_number"]
    attempted_rev = baseline_rev + 1

    # 3. Create subsequent evidence-producing check result
    check = CheckResult(
        check_id="ACT01",
        execution_status=CheckExecutionStatus.COMPLETED,
        finding=CheckFinding.SUPPORTS,
        outcome="blockage_found",
        source=EvidenceSource.USER_CHECK_RESULT,
    )
    loaded_target = repo.load_structured_case(target_id)
    assert loaded_target is not None
    assert len(loaded_target.previous_check_results) >= 1
    up_case, res_check = engine.submit_check_result(loaded_target, check)

    # 4. Use self-managed repository (session=None) to exercise repository's own rollback handler
    self_managed_repo = CaseRepository()

    fault_reached = False
    captured_pending_evidence: dict[str, Any] = {}

    def fail_after_flush_before_commit(session: Session) -> None:
        nonlocal fault_reached, captured_pending_evidence
        target_crs = session.scalars(
            select(CaseCheckResultModel).where(
                CaseCheckResultModel.case_id == target_id,
                CaseCheckResultModel.resulting_revision_number == attempted_rev,
            )
        ).all()
        if not target_crs:
            return

        cr = target_crs[0]
        cr_data = {
            "check_id": cr.check_id,
            "execution_status": cr.execution_status,
            "finding": cr.finding,
            "outcome": cr.outcome,
            "source": cr.source,
            "resulting_revision_number": cr.resulting_revision_number,
        }

        rev_obs = session.scalars(
            select(ObservationModel).where(
                ObservationModel.case_id == target_id,
                ObservationModel.first_seen_revision == attempted_rev,
            )
        ).all()
        obs_data = [
            {
                "observation_id": o.observation_id,
                "observation_type": o.observation_type,
                "value": o.value,
                "source": o.source,
                "first_seen_revision": o.first_seen_revision,
            }
            for o in rev_obs
        ]

        revs = session.scalars(
            select(AnalysisRevisionModel).where(
                AnalysisRevisionModel.case_id == target_id,
                AnalysisRevisionModel.revision_number == attempted_rev,
            )
        ).all()
        rev_data = (
            {
                "revision_number": revs[0].revision_number,
                "defect_code": revs[0].defect_code if revs[0].defect_code is not None else None,
                "issue_condition": revs[0].issue_condition if revs[0].issue_condition is not None else None,
                "result_snapshot": copy.deepcopy(revs[0].result_snapshot),
            }
            if revs
            else None
        )

        captured_pending_evidence = {
            "check_result": cr_data,
            "observations": obs_data,
            "analysis_revision": rev_data,
        }

        fault_reached = True
        raise RuntimeError("Simulated repository flush boundary fault")

    event.listen(Session, "before_commit", fail_after_flush_before_commit)
    try:
        with pytest.raises(RuntimeError, match="Simulated repository flush boundary fault"):
            self_managed_repo.append_check_result_revision(
                case=up_case,
                check_result=check,
                result=res_check,
                expected_revision=baseline_rev,
            )
    finally:
        event.remove(Session, "before_commit", fail_after_flush_before_commit)

    # Assert outside repository call that fault was reached and evidence was captured
    assert fault_reached, "The deliberate fault was never reached in the commit boundary hook."
    assert captured_pending_evidence.get("check_result") is not None
    assert captured_pending_evidence["check_result"]["check_id"] == "ACT01"
    assert captured_pending_evidence["check_result"]["outcome"] == "blockage_found"
    assert captured_pending_evidence["check_result"]["resulting_revision_number"] == attempted_rev
    assert len(captured_pending_evidence["observations"]) >= 1
    assert captured_pending_evidence.get("analysis_revision") is not None
    assert captured_pending_evidence["analysis_revision"]["revision_number"] == attempted_rev
    pending_snapshot = captured_pending_evidence["analysis_revision"]["result_snapshot"]
    assert isinstance(pending_snapshot, dict)
    assert len(pending_snapshot) > 0
    assert pending_snapshot["defect"] == "D03_INCONSISTENT_SIZE"
    assert "ranked_causes" in pending_snapshot
    assert any(c["cause_id"] == "nozzle_restriction" for c in pending_snapshot["ranked_causes"])

    # 5. Open fresh independent session to verify rollback without manual rollback call
    with factory() as independent_session:
        # Check target case attempted revision artifacts do not exist
        attempted_crs = independent_session.scalars(
            select(CaseCheckResultModel).where(
                CaseCheckResultModel.case_id == target_id,
                CaseCheckResultModel.resulting_revision_number == attempted_rev,
            )
        ).all()
        assert len(attempted_crs) == 0

        attempted_obs = independent_session.scalars(
            select(ObservationModel).where(
                ObservationModel.case_id == target_id,
                ObservationModel.first_seen_revision == attempted_rev,
            )
        ).all()
        assert len(attempted_obs) == 0

        attempted_revs = independent_session.scalars(
            select(AnalysisRevisionModel).where(
                AnalysisRevisionModel.case_id == target_id,
                AnalysisRevisionModel.revision_number == attempted_rev,
            )
        ).all()
        assert len(attempted_revs) == 0

        # Verify complete target and control baselines are preserved identically
        target_after = capture_complete_case_state(independent_session, target_id)
        assert target_after == target_baseline
        assert len(target_after["check_results"]) >= 1
        assert target_after["check_results"][0]["check_id"] == "ACT02"

        control_after = capture_complete_case_state(independent_session, control_id)
        assert control_after == control_baseline


def test_interleaved_mixed_revisions_answer_and_check(case_repo, db_session):
    """Verify mixed revision history:
    Rev 1: Initial diagnosis
    Rev 2: Question answer
    Rev 3: Troubleshooting check result
    Rev 4: Another question answer
    Rev 5: Another troubleshooting check result
    Reconstructed StructuredCase restores all answers, check results, observations, and revisions monotonically.
    """
    repo, tracked_ids = case_repo
    engine = DiagnosticEngine()
    case_id = str(uuid.uuid4())
    tracked_ids.append(case_id)

    # Rev 1: Initial case
    case = engine.prepare_case(
        StructuredCase(
            case_id=case_id,
            defect_code="D03_INCONSISTENT_SIZE",
            defect_name="Inconsistent Dot Size",
            description="Dots shrinking over time",
        )
    )
    res1 = engine.diagnose(case)
    repo.save_initial_case(case, res1)
    db_session.commit()

    # Rev 2: Question Answer (Q01)
    loaded = repo.load_structured_case(case_id)
    assert loaded is not None
    ans1 = QuestionAnswer(
        question_id="Q01",
        answer_value="after_prolonged_operation",
        source=EvidenceSource.USER,
    )
    c2, res2 = engine.submit_question_answer(loaded, ans1)
    repo.append_question_answer_revision(c2, ans1, res2, expected_revision=1)
    db_session.commit()

    # Rev 3: Check Result (ACT01)
    loaded = repo.load_structured_case(case_id)
    assert loaded is not None
    assert len(loaded.previous_answers) == 1
    assert len(loaded.previous_check_results) == 0
    assert len(loaded.analysis_revisions) == 2
    check1 = CheckResult(
        check_id="ACT01",
        execution_status=CheckExecutionStatus.COMPLETED,
        finding=CheckFinding.CONTRADICTS,
        outcome="no_blockage",
        source=EvidenceSource.USER_CHECK_RESULT,
    )
    c3, res3 = engine.submit_check_result(loaded, check1)
    repo.append_check_result_revision(c3, check1, res3, expected_revision=2)
    db_session.commit()

    # Rev 4: Question Answer (Q02)
    loaded = repo.load_structured_case(case_id)
    assert loaded is not None
    assert len(loaded.previous_answers) == 1
    assert len(loaded.previous_check_results) == 1
    assert len(loaded.analysis_revisions) == 3
    ans2 = QuestionAnswer(
        question_id="Q02",
        answer_value="all_points",
        source=EvidenceSource.USER,
    )
    c4, res4 = engine.submit_question_answer(loaded, ans2)
    repo.append_question_answer_revision(c4, ans2, res4, expected_revision=3)
    db_session.commit()

    # Rev 5: Check Result (ACT02)
    loaded = repo.load_structured_case(case_id)
    assert loaded is not None
    assert len(loaded.previous_answers) == 2
    assert len(loaded.previous_check_results) == 1
    assert len(loaded.analysis_revisions) == 4
    check2 = CheckResult(
        check_id="ACT02",
        execution_status=CheckExecutionStatus.COMPLETED,
        finding=CheckFinding.SUPPORTS,
        outcome="air_bubbles_found",
        source=EvidenceSource.USER_CHECK_RESULT,
    )
    c5, res5 = engine.submit_check_result(loaded, check2)
    repo.append_check_result_revision(c5, check2, res5, expected_revision=4)
    db_session.commit()

    # Final reconstruction verification
    final_case = repo.load_structured_case(case_id)
    assert final_case is not None
    assert len(final_case.analysis_revisions) == 5
    assert [r.revision_number for r in final_case.analysis_revisions] == [1, 2, 3, 4, 5]
    assert len(final_case.previous_answers) == 2
    assert [a.question_id for a in final_case.previous_answers] == ["Q01", "Q02"]
    assert len(final_case.previous_check_results) == 2
    assert [c.check_id for c in final_case.previous_check_results] == ["ACT01", "ACT02"]


def test_append_cause_confirmation_revision_rollback_on_failure(case_repo, db_session):
    """Verify that a failure during append_cause_confirmation_revision rolls back
    flushed confirmation and revision rows, preserving prior state intact.
    """
    repo, tracked_ids = case_repo
    engine = DiagnosticEngine()

    # 1. Create control case advanced to Revision 3
    control_id = str(uuid.uuid4())
    tracked_ids.append(control_id)
    ctrl_case = engine.prepare_case(
        StructuredCase(
            case_id=control_id,
            defect_code="D03_INCONSISTENT_SIZE",
            defect_name="Inconsistent Dot Size",
            description="Control case for confirmation rollback",
        )
    )
    ctrl_res1 = engine.diagnose(ctrl_case)
    repo.save_initial_case(ctrl_case, ctrl_res1)
    db_session.commit()

    ctrl_loaded = repo.load_structured_case(control_id)
    assert ctrl_loaded is not None
    ctrl_ans = QuestionAnswer(question_id="Q01", answer_value="after_prolonged_operation", source=EvidenceSource.USER)
    c_case2, c_res2 = engine.submit_question_answer(ctrl_loaded, ctrl_ans)
    repo.append_question_answer_revision(c_case2, ctrl_ans, c_res2, expected_revision=1)
    db_session.commit()

    ctrl_loaded2 = repo.load_structured_case(control_id)
    assert ctrl_loaded2 is not None
    ctrl_chk = CheckResult(
        check_id="ACT02",
        execution_status=CheckExecutionStatus.COMPLETED,
        finding=CheckFinding.SUPPORTS,
        outcome="air_bubbles_found",
        source=EvidenceSource.USER_CHECK_RESULT,
    )
    c_case3, c_res3 = engine.submit_check_result(ctrl_loaded2, ctrl_chk)
    repo.append_check_result_revision(c_case3, ctrl_chk, c_res3, expected_revision=2)
    db_session.commit()

    # 2. Create target case advanced to Revision 3
    target_id = str(uuid.uuid4())
    tracked_ids.append(target_id)
    tgt_case = engine.prepare_case(
        StructuredCase(
            case_id=target_id,
            defect_code="D03_INCONSISTENT_SIZE",
            defect_name="Inconsistent Dot Size",
            description="Target case for confirmation rollback",
        )
    )
    tgt_res1 = engine.diagnose(tgt_case)
    repo.save_initial_case(tgt_case, tgt_res1)
    db_session.commit()

    tgt_loaded = repo.load_structured_case(target_id)
    assert tgt_loaded is not None
    tgt_ans = QuestionAnswer(question_id="Q01", answer_value="after_prolonged_operation", source=EvidenceSource.USER)
    t_case2, t_res2 = engine.submit_question_answer(tgt_loaded, tgt_ans)
    repo.append_question_answer_revision(t_case2, tgt_ans, t_res2, expected_revision=1)
    db_session.commit()

    tgt_loaded2 = repo.load_structured_case(target_id)
    assert tgt_loaded2 is not None
    tgt_chk = CheckResult(
        check_id="ACT02",
        execution_status=CheckExecutionStatus.COMPLETED,
        finding=CheckFinding.SUPPORTS,
        outcome="air_bubbles_found",
        source=EvidenceSource.USER_CHECK_RESULT,
    )
    t_case3, t_res3 = engine.submit_check_result(tgt_loaded2, tgt_chk)
    repo.append_check_result_revision(t_case3, tgt_chk, t_res3, expected_revision=2)
    db_session.commit()

    factory = get_session_factory()
    with factory() as session:
        control_baseline = capture_complete_case_state(session, control_id)
        target_baseline = capture_complete_case_state(session, target_id)

    assert len(target_baseline["question_answers"]) >= 1
    assert len(target_baseline["check_results"]) >= 1
    baseline_rev = target_baseline["analysis_revisions"][-1]["revision_number"]
    attempted_rev = baseline_rev + 1

    # 3. Confirm cause with engine
    tgt_loaded3 = repo.load_structured_case(target_id)
    assert tgt_loaded3 is not None
    confirmed_case, res_conf = engine.confirm_cause(
        tgt_loaded3,
        cause_id="nozzle_restriction",
        confirmed_by="technician",
        confirmation_details="Tested rollback",
    )

    # 4. Use self-managed repository to test repository's own rollback
    self_managed_repo = CaseRepository()
    fault_reached = False

    def fail_after_flush_before_commit(session: Session) -> None:
        nonlocal fault_reached
        target_confs = session.scalars(
            select(CaseCauseConfirmationModel).where(
                CaseCauseConfirmationModel.case_id == target_id,
                CaseCauseConfirmationModel.resulting_revision_number == attempted_rev,
            )
        ).all()
        if not target_confs:
            return

        fault_reached = True
        raise RuntimeError("Simulated repository flush boundary fault during confirmation")

    event.listen(Session, "before_commit", fail_after_flush_before_commit)
    try:
        with pytest.raises(RuntimeError, match="Simulated repository flush boundary fault during confirmation"):
            self_managed_repo.append_cause_confirmation_revision(
                case=confirmed_case,
                cause_id="nozzle_restriction",
                confirmed_by="technician",
                notes="Tested rollback",
                result=res_conf,
                expected_revision=baseline_rev,
            )
    finally:
        event.remove(Session, "before_commit", fail_after_flush_before_commit)

    assert fault_reached

    # 5. Verify fresh session proves baseline preservation and no phantom writes
    with factory() as fresh_session:
        target_after = capture_complete_case_state(fresh_session, target_id)
        control_after = capture_complete_case_state(fresh_session, control_id)

        assert target_after == target_baseline
        assert control_after == control_baseline

        confs = list(fresh_session.scalars(
            select(CaseCauseConfirmationModel).where(CaseCauseConfirmationModel.case_id == target_id)
        ).all())
        assert len(confs) == 0


def test_interleaved_mixed_revisions_answer_check_and_confirmation(case_repo, db_session):
    """Verify mixed revision history:
    Rev 1: Initial diagnosis
    Rev 2: Question answer
    Rev 3: Troubleshooting check result
    Rev 4: Root cause confirmation
    Reconstructed StructuredCase restores all answers, check results, confirmations, and revisions monotonically.
    """
    repo, tracked_ids = case_repo
    engine = DiagnosticEngine()
    case_id = str(uuid.uuid4())
    tracked_ids.append(case_id)

    # Rev 1: Initial case
    case = engine.prepare_case(
        StructuredCase(
            case_id=case_id,
            defect_code="D03_INCONSISTENT_SIZE",
            defect_name="Inconsistent Dot Size",
            description="Dots shrinking over time",
        )
    )
    res1 = engine.diagnose(case)
    repo.save_initial_case(case, res1)
    db_session.commit()

    # Rev 2: Question Answer (Q01)
    loaded = repo.load_structured_case(case_id)
    assert loaded is not None
    ans1 = QuestionAnswer(
        question_id="Q01",
        answer_value="after_prolonged_operation",
        source=EvidenceSource.USER,
    )
    c2, res2 = engine.submit_question_answer(loaded, ans1)
    repo.append_question_answer_revision(c2, ans1, res2, expected_revision=1)
    db_session.commit()

    # Rev 3: Check Result (ACT01)
    loaded = repo.load_structured_case(case_id)
    assert loaded is not None
    check1 = CheckResult(
        check_id="ACT01",
        execution_status=CheckExecutionStatus.COMPLETED,
        finding=CheckFinding.CONTRADICTS,
        outcome="no_blockage",
        source=EvidenceSource.USER_CHECK_RESULT,
    )
    c3, res3 = engine.submit_check_result(loaded, check1)
    repo.append_check_result_revision(c3, check1, res3, expected_revision=2)
    db_session.commit()

    # Rev 4: Cause Confirmation
    loaded = repo.load_structured_case(case_id)
    assert loaded is not None
    c4, res4 = engine.confirm_cause(loaded, cause_id="pressure_instability", confirmed_by="technician", confirmation_details="Confirmed by pressure log")
    repo.append_cause_confirmation_revision(c4, cause_id="pressure_instability", confirmed_by="technician", notes="Confirmed by pressure log", result=res4, expected_revision=3)
    db_session.commit()

    # Final reconstruction verification
    final_case = repo.load_structured_case(case_id)
    assert final_case is not None
    assert len(final_case.analysis_revisions) == 4
    assert [r.revision_number for r in final_case.analysis_revisions] == [1, 2, 3, 4]
    assert len(final_case.previous_answers) == 1
    assert [a.question_id for a in final_case.previous_answers] == ["Q01"]
    assert len(final_case.previous_check_results) == 1
    assert [c.check_id for c in final_case.previous_check_results] == ["ACT01"]
    assert final_case.confirmed_causes == ["pressure_instability"]
    # Check that in the latest revision, pressure_instability is CONFIRMED
    confirmed = next((c for c in final_case.analysis_revisions[-1].ranked_causes if c.cause_id == "pressure_instability"), None)
    assert confirmed is not None
    assert confirmed.conclusion == CauseConclusion.CONFIRMED


def test_append_recovery_action_revision_rollback_on_failure(case_repo, db_session):
    """Verify repository-level atomic rollback when appending recovery action revision fails.

    Proves:
    1. Target case has prior question-answer and check-result history.
    2. Control case is committed and baselined alongside target case.
    3. Injected failure occurs after flush during append_recovery_action_revision when
       CaseLifecycleEventModel is pending.
    4. Exception propagates out and transaction is rolled back.
    5. In fresh independent session, target and control match baseline state exactly.
    6. Case issue condition remains UNRESOLVED, no lifecycle event or revision survives.
    """
    repo, tracked_ids = case_repo
    engine = DiagnosticEngine()

    target_id = str(uuid.uuid4())
    control_id = str(uuid.uuid4())
    tracked_ids.extend([target_id, control_id])

    # 1. Setup control case
    ctrl_case = engine.prepare_case(
        StructuredCase(
            case_id=control_id,
            defect_code="D03_INCONSISTENT_SIZE",
            defect_name="Inconsistent Dot Size",
            description="Control case for recovery action rollback",
        )
    )
    ctrl_res = engine.diagnose(ctrl_case)
    repo.save_initial_case(ctrl_case, ctrl_res)

    # 2. Setup target case up to revision 3 with QA and check result
    tgt_case = engine.prepare_case(
        StructuredCase(
            case_id=target_id,
            defect_code="D03_INCONSISTENT_SIZE",
            defect_name="Inconsistent Dot Size",
            description="Target case for recovery action rollback",
        )
    )
    tgt_res = engine.diagnose(tgt_case)
    repo.save_initial_case(tgt_case, tgt_res)
    db_session.commit()

    tgt_loaded = repo.load_structured_case(target_id)
    assert tgt_loaded is not None
    tgt_ans = QuestionAnswer(question_id="Q01", answer_value="after_prolonged_operation", source=EvidenceSource.USER)
    t_case2, t_res2 = engine.submit_question_answer(tgt_loaded, tgt_ans)
    repo.append_question_answer_revision(t_case2, tgt_ans, t_res2, expected_revision=1)
    db_session.commit()

    tgt_loaded2 = repo.load_structured_case(target_id)
    assert tgt_loaded2 is not None
    tgt_chk = CheckResult(
        check_id="ACT02",
        execution_status=CheckExecutionStatus.COMPLETED,
        finding=CheckFinding.SUPPORTS,
        outcome="air_bubbles_found",
        source=EvidenceSource.USER_CHECK_RESULT,
    )
    t_case3, t_res3 = engine.submit_check_result(tgt_loaded2, tgt_chk)
    repo.append_check_result_revision(t_case3, tgt_chk, t_res3, expected_revision=2)
    db_session.commit()

    tgt_loaded3 = repo.load_structured_case(target_id)
    assert tgt_loaded3 is not None
    t_case4, t_res4 = engine.confirm_cause(
        tgt_loaded3,
        cause_id="nozzle_restriction",
        confirmed_by="technician",
        confirmation_details="Microscope confirmed restriction",
    )
    repo.append_cause_confirmation_revision(
        t_case4,
        cause_id="nozzle_restriction",
        confirmed_by="technician",
        notes="Microscope confirmed restriction",
        result=t_res4,
        expected_revision=3,
    )
    db_session.commit()

    factory = get_session_factory()
    with factory() as session:
        control_baseline = capture_complete_case_state(session, control_id)
        target_baseline = capture_complete_case_state(session, target_id)

    assert len(target_baseline["question_answers"]) == 1
    assert len(target_baseline["check_results"]) == 1
    assert len(target_baseline["cause_confirmations"]) == 1
    assert len(target_baseline["lifecycle_events"]) == 0
    assert target_baseline["case"]["issue_condition"] == "UNRESOLVED"
    baseline_rev = target_baseline["analysis_revisions"][-1]["revision_number"]
    assert baseline_rev == 4
    attempted_rev = baseline_rev + 1

    # 3. Prepare recovery action transition
    tgt_loaded4 = repo.load_structured_case(target_id)
    assert tgt_loaded4 is not None
    new_cond, _ = StateManager.transition_issue_condition(
        current_condition=tgt_loaded4.issue_condition,
        target_condition=IssueCondition.RECOVERY_PENDING_VERIFICATION,
        verification_passed=False,
        verification_details="Replaced fluid syringe",
    )
    tgt_loaded4.issue_condition = new_cond
    res_rec = engine.diagnose(tgt_loaded4)
    res_rec.issue_condition = new_cond

    # 4. Use self-managed repository to test repository's own rollback
    self_managed_repo = CaseRepository()
    fault_reached = False

    def fail_after_flush_before_commit(session: Session) -> None:
        nonlocal fault_reached
        target_events = session.scalars(
            select(CaseLifecycleEventModel).where(
                CaseLifecycleEventModel.case_id == target_id,
                CaseLifecycleEventModel.resulting_revision_number == attempted_rev,
            )
        ).all()
        if not target_events:
            return

        fault_reached = True
        raise RuntimeError("Simulated repository flush boundary fault during recovery action")

    event.listen(Session, "before_commit", fail_after_flush_before_commit)
    try:
        with pytest.raises(RuntimeError, match="Simulated repository flush boundary fault during recovery action"):
            self_managed_repo.append_recovery_action_revision(
                case=tgt_loaded4,
                performed_by="technician",
                recovery_details="Replaced fluid syringe",
                result=res_rec,
                expected_revision=baseline_rev,
            )
    finally:
        event.remove(Session, "before_commit", fail_after_flush_before_commit)

    assert fault_reached

    # 5. Verify fresh session proves baseline preservation and no phantom writes
    with factory() as fresh_session:
        target_after = capture_complete_case_state(fresh_session, target_id)
        control_after = capture_complete_case_state(fresh_session, control_id)

        assert target_after == target_baseline
        assert control_after == control_baseline
        assert len(target_after["cause_confirmations"]) == 1
        assert len(target_after["question_answers"]) == 1
        assert len(target_after["check_results"]) == 1
        assert len(target_after["lifecycle_events"]) == 0
        assert len(target_after["analysis_revisions"]) == 4

        events = list(fresh_session.scalars(
            select(CaseLifecycleEventModel).where(CaseLifecycleEventModel.case_id == target_id)
        ).all())
        assert len(events) == 0
        assert target_after["case"]["issue_condition"] == "UNRESOLVED"


def test_append_recovery_verification_revision_rollback_on_failure(case_repo, db_session):
    """Verify repository-level atomic rollback when appending recovery verification revision fails.

    Proves:
    1. Target case has prior recovery action in RECOVERY_PENDING_VERIFICATION state.
    2. Control case is committed and baselined alongside target case.
    3. Injected failure occurs after flush during append_recovery_verification_revision when
       CaseLifecycleEventModel for verification is pending.
    4. Exception propagates out and transaction is rolled back.
    5. In fresh independent session, target and control match baseline state exactly.
    6. Case issue condition remains RECOVERY_PENDING_VERIFICATION, only the prior action event exists.
    """
    repo, tracked_ids = case_repo
    engine = DiagnosticEngine()

    target_id = str(uuid.uuid4())
    control_id = str(uuid.uuid4())
    tracked_ids.extend([target_id, control_id])

    # 1. Setup control case
    ctrl_case = engine.prepare_case(
        StructuredCase(
            case_id=control_id,
            defect_code="D03_INCONSISTENT_SIZE",
            defect_name="Inconsistent Dot Size",
            description="Control case for verification rollback",
        )
    )
    ctrl_res = engine.diagnose(ctrl_case)
    repo.save_initial_case(ctrl_case, ctrl_res)

    # 2. Setup target case up to recovery action (Rev 5)
    tgt_case = engine.prepare_case(
        StructuredCase(
            case_id=target_id,
            defect_code="D03_INCONSISTENT_SIZE",
            defect_name="Inconsistent Dot Size",
            description="Target case for verification rollback",
        )
    )
    tgt_res = engine.diagnose(tgt_case)
    repo.save_initial_case(tgt_case, tgt_res)
    db_session.commit()

    # Rev 2: QA
    tgt_loaded1 = repo.load_structured_case(target_id)
    assert tgt_loaded1 is not None
    tgt_ans = QuestionAnswer(question_id="Q01", answer_value="after_prolonged_operation", source=EvidenceSource.USER)
    t_case2, t_res2 = engine.submit_question_answer(tgt_loaded1, tgt_ans)
    repo.append_question_answer_revision(t_case2, tgt_ans, t_res2, expected_revision=1)
    db_session.commit()

    # Rev 3: Check
    tgt_loaded2 = repo.load_structured_case(target_id)
    assert tgt_loaded2 is not None
    tgt_chk = CheckResult(
        check_id="ACT02",
        execution_status=CheckExecutionStatus.COMPLETED,
        finding=CheckFinding.SUPPORTS,
        outcome="air_bubbles_found",
        source=EvidenceSource.USER_CHECK_RESULT,
    )
    t_case3, t_res3 = engine.submit_check_result(tgt_loaded2, tgt_chk)
    repo.append_check_result_revision(t_case3, tgt_chk, t_res3, expected_revision=2)
    db_session.commit()

    # Rev 4: Cause Confirmation
    tgt_loaded3 = repo.load_structured_case(target_id)
    assert tgt_loaded3 is not None
    t_case4, t_res4 = engine.confirm_cause(
        tgt_loaded3,
        cause_id="nozzle_restriction",
        confirmed_by="technician",
        confirmation_details="Microscope confirmed restriction",
    )
    repo.append_cause_confirmation_revision(
        t_case4,
        cause_id="nozzle_restriction",
        confirmed_by="technician",
        notes="Microscope confirmed restriction",
        result=t_res4,
        expected_revision=3,
    )
    db_session.commit()

    # Rev 5: Recovery Action
    tgt_loaded4 = repo.load_structured_case(target_id)
    assert tgt_loaded4 is not None
    new_cond, _ = StateManager.transition_issue_condition(
        current_condition=tgt_loaded4.issue_condition,
        target_condition=IssueCondition.RECOVERY_PENDING_VERIFICATION,
        verification_passed=False,
        verification_details="Replaced fluid syringe",
    )
    tgt_loaded4.issue_condition = new_cond
    res_rec = engine.diagnose(tgt_loaded4)
    res_rec.issue_condition = new_cond
    repo.append_recovery_action_revision(
        case=tgt_loaded4,
        performed_by="technician",
        recovery_details="Replaced fluid syringe",
        result=res_rec,
        expected_revision=4,
    )
    db_session.commit()

    factory = get_session_factory()
    with factory() as session:
        control_baseline = capture_complete_case_state(session, control_id)
        target_baseline = capture_complete_case_state(session, target_id)

    assert len(target_baseline["question_answers"]) == 1
    assert len(target_baseline["check_results"]) == 1
    assert len(target_baseline["cause_confirmations"]) == 1
    assert len(target_baseline["lifecycle_events"]) == 1
    assert target_baseline["lifecycle_events"][0]["event_type"] == "RECOVERY_ACTION"
    assert target_baseline["lifecycle_events"][0]["resulting_revision_number"] == 5
    assert target_baseline["case"]["issue_condition"] == "RECOVERY_PENDING_VERIFICATION"
    baseline_rev = target_baseline["analysis_revisions"][-1]["revision_number"]
    assert baseline_rev == 5
    attempted_rev = baseline_rev + 1

    # 3. Prepare recovery verification transition (passed -> RESOLVED)
    tgt_loaded5 = repo.load_structured_case(target_id)
    assert tgt_loaded5 is not None
    resolved_cond, _ = StateManager.transition_issue_condition(
        current_condition=tgt_loaded5.issue_condition,
        target_condition=IssueCondition.RESOLVED,
        verification_passed=True,
        verification_details="Test shots nominal",
    )
    tgt_loaded5.issue_condition = resolved_cond
    res_ver = engine.diagnose(tgt_loaded5)
    res_ver.issue_condition = resolved_cond

    # 4. Use self-managed repository to test repository's own rollback
    self_managed_repo = CaseRepository()
    fault_reached = False

    def fail_after_flush_before_commit(session: Session) -> None:
        nonlocal fault_reached
        target_events = session.scalars(
            select(CaseLifecycleEventModel).where(
                CaseLifecycleEventModel.case_id == target_id,
                CaseLifecycleEventModel.resulting_revision_number == attempted_rev,
            )
        ).all()
        if not target_events:
            return

        fault_reached = True
        raise RuntimeError("Simulated repository flush boundary fault during recovery verification")

    event.listen(Session, "before_commit", fail_after_flush_before_commit)
    try:
        with pytest.raises(RuntimeError, match="Simulated repository flush boundary fault during recovery verification"):
            self_managed_repo.append_recovery_verification_revision(
                case=tgt_loaded5,
                verified_by="qa_engineer",
                verification_passed=True,
                verification_details="Test shots nominal",
                result=res_ver,
                expected_revision=baseline_rev,
            )
    finally:
        event.remove(Session, "before_commit", fail_after_flush_before_commit)

    assert fault_reached

    # 5. Verify fresh session proves baseline preservation and no phantom writes
    with factory() as fresh_session:
        target_after = capture_complete_case_state(fresh_session, target_id)
        control_after = capture_complete_case_state(fresh_session, control_id)

        assert target_after == target_baseline
        assert control_after == control_baseline
        assert len(target_after["cause_confirmations"]) == 1
        assert len(target_after["question_answers"]) == 1
        assert len(target_after["check_results"]) == 1
        assert len(target_after["lifecycle_events"]) == 1
        assert target_after["lifecycle_events"][0]["event_type"] == "RECOVERY_ACTION"
        assert target_after["lifecycle_events"][0]["resulting_revision_number"] == 5
        assert len(target_after["analysis_revisions"]) == 5

        all_events = list(fresh_session.scalars(
            select(CaseLifecycleEventModel).where(CaseLifecycleEventModel.case_id == target_id)
        ).all())
        assert len(all_events) == 1
        assert all_events[0].event_type == "RECOVERY_ACTION"
        assert all_events[0].resulting_revision_number == 5

        rev6_events = list(fresh_session.scalars(
            select(CaseLifecycleEventModel).where(
                CaseLifecycleEventModel.case_id == target_id,
                CaseLifecycleEventModel.resulting_revision_number == attempted_rev,
            )
        ).all())
        assert len(rev6_events) == 0
        assert target_after["case"]["issue_condition"] == "RECOVERY_PENDING_VERIFICATION"


def test_interleaved_mixed_revisions_all_five_event_types(case_repo, db_session):
    """Verify monotonic global revision ordering across all five event types:
    Rev 1: Initial diagnosis (INITIAL)
    Rev 2: Question answer (QUESTION_ANSWER)
    Rev 3: Troubleshooting check result (CHECK_RESULT)
    Rev 4: Root cause confirmation (CAUSE_CONFIRMATION)
    Rev 5: Recovery action applied (RECOVERY_ACTION -> RECOVERY_PENDING_VERIFICATION)
    Rev 6: Recovery verification passed (RECOVERY_VERIFICATION -> RESOLVED)

    Proves:
    - Exactly 6 revisions with monotonic numbers 1..6.
    - Reconstructed StructuredCase preserves all answers, check results, confirmed causes, and final issue condition.
    - Lifecycle event history records both lifecycle transitions with correct prior/resulting states.
    - Cause confirmation state is preserved even after resolution.
    """
    repo, tracked_ids = case_repo
    engine = DiagnosticEngine()
    case_id = str(uuid.uuid4())
    tracked_ids.append(case_id)

    # Rev 1: Initial case
    case = engine.prepare_case(
        StructuredCase(
            case_id=case_id,
            defect_code="D03_INCONSISTENT_SIZE",
            defect_name="Inconsistent Dot Size",
            description="Dots shrinking over time",
        )
    )
    res1 = engine.diagnose(case)
    repo.save_initial_case(case, res1)
    db_session.commit()

    # Rev 2: Question Answer (Q01)
    loaded = repo.load_structured_case(case_id)
    assert loaded is not None
    ans1 = QuestionAnswer(
        question_id="Q01",
        answer_value="after_prolonged_operation",
        source=EvidenceSource.USER,
    )
    c2, res2 = engine.submit_question_answer(loaded, ans1)
    repo.append_question_answer_revision(c2, ans1, res2, expected_revision=1)
    db_session.commit()

    # Rev 3: Check Result (ACT01)
    loaded = repo.load_structured_case(case_id)
    assert loaded is not None
    check1 = CheckResult(
        check_id="ACT01",
        execution_status=CheckExecutionStatus.COMPLETED,
        finding=CheckFinding.CONTRADICTS,
        outcome="no_blockage",
        source=EvidenceSource.USER_CHECK_RESULT,
    )
    c3, res3 = engine.submit_check_result(loaded, check1)
    repo.append_check_result_revision(c3, check1, res3, expected_revision=2)
    db_session.commit()

    # Rev 4: Cause Confirmation
    loaded = repo.load_structured_case(case_id)
    assert loaded is not None
    c4, res4 = engine.confirm_cause(loaded, cause_id="pressure_instability", confirmed_by="technician", confirmation_details="Confirmed by pressure log")
    repo.append_cause_confirmation_revision(c4, cause_id="pressure_instability", confirmed_by="technician", notes="Confirmed by pressure log", result=res4, expected_revision=3)
    db_session.commit()

    # Rev 5: Recovery Action applied
    loaded = repo.load_structured_case(case_id)
    assert loaded is not None
    new_cond, _ = StateManager.transition_issue_condition(
        current_condition=loaded.issue_condition,
        target_condition=IssueCondition.RECOVERY_PENDING_VERIFICATION,
        verification_passed=False,
        verification_details="Replaced pressure regulator valve",
    )
    loaded.issue_condition = new_cond
    res5 = engine.diagnose(loaded)
    res5.issue_condition = new_cond
    repo.append_recovery_action_revision(
        case=loaded,
        performed_by="technician_bob",
        recovery_details="Replaced pressure regulator valve",
        result=res5,
        expected_revision=4,
    )
    db_session.commit()

    # Rev 6: Recovery Verification passed
    loaded = repo.load_structured_case(case_id)
    assert loaded is not None
    resolved_cond, _ = StateManager.transition_issue_condition(
        current_condition=loaded.issue_condition,
        target_condition=IssueCondition.RESOLVED,
        verification_passed=True,
        verification_details="Pressure stability confirmed across 50 continuous cycles",
    )
    loaded.issue_condition = resolved_cond
    res6 = engine.diagnose(loaded)
    res6.issue_condition = resolved_cond
    repo.append_recovery_verification_revision(
        case=loaded,
        verified_by="lead_engineer_alice",
        verification_passed=True,
        verification_details="Pressure stability confirmed across 50 continuous cycles",
        result=res6,
        expected_revision=5,
    )
    db_session.commit()

    # Final reconstruction verification
    final_case = repo.load_structured_case(case_id)
    assert final_case is not None
    assert len(final_case.analysis_revisions) == 6
    assert [r.revision_number for r in final_case.analysis_revisions] == [1, 2, 3, 4, 5, 6]
    assert len(final_case.previous_answers) == 1
    assert [a.question_id for a in final_case.previous_answers] == ["Q01"]
    assert len(final_case.previous_check_results) == 1
    assert [c.check_id for c in final_case.previous_check_results] == ["ACT01"]
    assert final_case.confirmed_causes == ["pressure_instability"]
    assert final_case.issue_condition == IssueCondition.RESOLVED

    # Latest revision preserves confirmed cause
    confirmed = next((c for c in final_case.analysis_revisions[-1].ranked_causes if c.cause_id == "pressure_instability"), None)
    assert confirmed is not None
    assert confirmed.conclusion == CauseConclusion.CONFIRMED

    # Lifecycle event query verification
    lifecycle_events = repo.get_case_lifecycle_events(case_id)
    assert len(lifecycle_events) == 2
    assert lifecycle_events[0].event_type == "RECOVERY_ACTION"
    assert lifecycle_events[0].prior_issue_condition == "UNRESOLVED"
    assert lifecycle_events[0].resulting_issue_condition == "RECOVERY_PENDING_VERIFICATION"
    assert lifecycle_events[0].resulting_revision_number == 5
    assert lifecycle_events[0].actor == "technician_bob"
    assert lifecycle_events[0].verification_passed is None

    assert lifecycle_events[1].event_type == "RECOVERY_VERIFICATION"
    assert lifecycle_events[1].prior_issue_condition == "RECOVERY_PENDING_VERIFICATION"
    assert lifecycle_events[1].resulting_issue_condition == "RESOLVED"
    assert lifecycle_events[1].resulting_revision_number == 6
    assert lifecycle_events[1].actor == "lead_engineer_alice"
    assert lifecycle_events[1].verification_passed is True


def test_append_recurrence_revision_rollback_on_failure(db_session, case_repo):
    """Verify transaction rollback during append_recurrence_revision leaves database intact.

    1. Create control case (unrelated baseline).
    2. Create target case and advance through full lifecycle to RESOLVED (Rev 6):
       Rev 1: initial
       Rev 2: question answer
       Rev 3: check result
       Rev 4: cause confirmation
       Rev 5: recovery action -> RECOVERY_PENDING_VERIFICATION
       Rev 6: recovery verification -> RESOLVED
    3. Capture target_baseline and control_baseline in an independent session.
    4. Inject failure before commit on append_recurrence_revision.
    5. Verify in a fresh independent session that target and control baselines are perfectly preserved.
    """
    repo, tracked_ids = case_repo
    engine = DiagnosticEngine()

    control_id = str(uuid.uuid4())
    target_id = str(uuid.uuid4())
    tracked_ids.extend([control_id, target_id])

    # 1. Setup control case
    ctrl_case = engine.prepare_case(
        StructuredCase(
            case_id=control_id,
            defect_code="D03_INCONSISTENT_SIZE",
            defect_name="Inconsistent Dot Size",
            description="Control baseline case",
        )
    )
    ctrl_res = engine.diagnose(ctrl_case)
    repo.save_initial_case(ctrl_case, ctrl_res)
    db_session.commit()

    # 2. Setup target case up to recovery verification (Rev 6, RESOLVED)
    tgt_case = engine.prepare_case(
        StructuredCase(
            case_id=target_id,
            defect_code="D03_INCONSISTENT_SIZE",
            defect_name="Inconsistent Dot Size",
            description="Target case for recurrence rollback",
        )
    )
    tgt_res = engine.diagnose(tgt_case)
    repo.save_initial_case(tgt_case, tgt_res)
    db_session.commit()

    # Rev 2: QA
    tgt_loaded1 = repo.load_structured_case(target_id)
    assert tgt_loaded1 is not None
    tgt_ans = QuestionAnswer(question_id="Q01", answer_value="after_prolonged_operation", source=EvidenceSource.USER)
    t_case2, t_res2 = engine.submit_question_answer(tgt_loaded1, tgt_ans)
    repo.append_question_answer_revision(t_case2, tgt_ans, t_res2, expected_revision=1)
    db_session.commit()

    # Rev 3: Check
    tgt_loaded2 = repo.load_structured_case(target_id)
    assert tgt_loaded2 is not None
    tgt_chk = CheckResult(
        check_id="ACT02",
        execution_status=CheckExecutionStatus.COMPLETED,
        finding=CheckFinding.SUPPORTS,
        outcome="air_bubbles_found",
        source=EvidenceSource.USER_CHECK_RESULT,
    )
    t_case3, t_res3 = engine.submit_check_result(tgt_loaded2, tgt_chk)
    repo.append_check_result_revision(t_case3, tgt_chk, t_res3, expected_revision=2)
    db_session.commit()

    # Rev 4: Cause Confirmation
    tgt_loaded3 = repo.load_structured_case(target_id)
    assert tgt_loaded3 is not None
    t_case4, t_res4 = engine.confirm_cause(
        tgt_loaded3,
        cause_id="nozzle_restriction",
        confirmed_by="technician",
        confirmation_details="Microscope confirmed restriction",
    )
    repo.append_cause_confirmation_revision(
        t_case4,
        cause_id="nozzle_restriction",
        confirmed_by="technician",
        notes="Microscope confirmed restriction",
        result=t_res4,
        expected_revision=3,
    )
    db_session.commit()

    # Rev 5: Recovery Action
    tgt_loaded4 = repo.load_structured_case(target_id)
    assert tgt_loaded4 is not None
    new_cond, _ = StateManager.transition_issue_condition(
        current_condition=tgt_loaded4.issue_condition,
        target_condition=IssueCondition.RECOVERY_PENDING_VERIFICATION,
        verification_passed=False,
        verification_details="Replaced fluid syringe",
    )
    tgt_loaded4.issue_condition = new_cond
    res_rec = engine.diagnose(tgt_loaded4)
    res_rec.issue_condition = new_cond
    repo.append_recovery_action_revision(
        case=tgt_loaded4,
        performed_by="technician",
        recovery_details="Replaced fluid syringe",
        result=res_rec,
        expected_revision=4,
    )
    db_session.commit()

    # Rev 6: Recovery Verification (passed -> RESOLVED)
    tgt_loaded5 = repo.load_structured_case(target_id)
    assert tgt_loaded5 is not None
    resolved_cond, _ = StateManager.transition_issue_condition(
        current_condition=tgt_loaded5.issue_condition,
        target_condition=IssueCondition.RESOLVED,
        verification_passed=True,
        verification_details="Test shots nominal",
    )
    tgt_loaded5.issue_condition = resolved_cond
    res_ver = engine.diagnose(tgt_loaded5)
    res_ver.issue_condition = resolved_cond
    repo.append_recovery_verification_revision(
        case=tgt_loaded5,
        verified_by="qa_engineer",
        verification_passed=True,
        verification_details="Test shots nominal",
        result=res_ver,
        expected_revision=5,
    )
    db_session.commit()

    factory = get_session_factory()
    with factory() as session:
        control_baseline = capture_complete_case_state(session, control_id)
        target_baseline = capture_complete_case_state(session, target_id)

    assert len(target_baseline["question_answers"]) == 1
    assert len(target_baseline["check_results"]) == 1
    assert len(target_baseline["cause_confirmations"]) == 1
    assert len(target_baseline["lifecycle_events"]) == 2
    assert target_baseline["case"]["issue_condition"] == "RESOLVED"
    baseline_rev = target_baseline["analysis_revisions"][-1]["revision_number"]
    assert baseline_rev == 6
    attempted_rev = baseline_rev + 1

    # 3. Prepare recurrence transition (RESOLVED -> RECURRED)
    tgt_loaded6 = repo.load_structured_case(target_id)
    assert tgt_loaded6 is not None
    recurred_cond, _ = StateManager.transition_issue_condition(
        current_condition=tgt_loaded6.issue_condition,
        target_condition=IssueCondition.RECURRED,
        verification_passed=False,
        verification_details="Defect returned during run",
    )
    tgt_loaded6.issue_condition = recurred_cond
    res_recur = engine.diagnose(tgt_loaded6)
    res_recur.issue_condition = recurred_cond

    # 4. Use self-managed repository to test repository's own rollback
    self_managed_repo = CaseRepository()
    fault_reached = False

    def fail_after_flush_before_commit(session: Session) -> None:
        nonlocal fault_reached
        target_events = session.scalars(
            select(CaseLifecycleEventModel).where(
                CaseLifecycleEventModel.case_id == target_id,
                CaseLifecycleEventModel.resulting_revision_number == attempted_rev,
            )
        ).all()
        if not target_events:
            return

        fault_reached = True
        raise RuntimeError("Simulated repository flush boundary fault during recurrence")

    event.listen(Session, "before_commit", fail_after_flush_before_commit)
    try:
        with pytest.raises(RuntimeError, match="Simulated repository flush boundary fault during recurrence"):
            self_managed_repo.append_recurrence_revision(
                case=tgt_loaded6,
                reported_by="technician",
                recurrence_details="Defect returned during run",
                result=res_recur,
                expected_revision=baseline_rev,
            )
    finally:
        event.remove(Session, "before_commit", fail_after_flush_before_commit)

    assert fault_reached

    # 5. Verify fresh session proves baseline preservation and no phantom writes
    with factory() as fresh_session:
        target_after = capture_complete_case_state(fresh_session, target_id)
        control_after = capture_complete_case_state(fresh_session, control_id)

        assert target_after == target_baseline
        assert control_after == control_baseline
        assert len(target_after["cause_confirmations"]) == 1
        assert len(target_after["question_answers"]) == 1
        assert len(target_after["check_results"]) == 1
        assert len(target_after["lifecycle_events"]) == 2
        assert len(target_after["analysis_revisions"]) == 6

        all_events = list(fresh_session.scalars(
            select(CaseLifecycleEventModel).where(CaseLifecycleEventModel.case_id == target_id)
        ).all())
        assert len(all_events) == 2
        assert all(e.event_type != "RECURRENCE" for e in all_events)

        rev7_events = list(fresh_session.scalars(
            select(CaseLifecycleEventModel).where(
                CaseLifecycleEventModel.case_id == target_id,
                CaseLifecycleEventModel.resulting_revision_number == attempted_rev,
            )
        ).all())
        assert len(rev7_events) == 0
        assert target_after["case"]["issue_condition"] == "RESOLVED"


def test_interleaved_mixed_revisions_all_six_event_types(case_repo, db_session):
    """Verify monotonic global revision ordering across all six event types:
    Rev 1: Initial diagnosis (INITIAL)
    Rev 2: Question answer (QUESTION_ANSWER)
    Rev 3: Troubleshooting check result (CHECK_RESULT)
    Rev 4: Root cause confirmation (CAUSE_CONFIRMATION)
    Rev 5: Recovery action applied (RECOVERY_ACTION -> RECOVERY_PENDING_VERIFICATION)
    Rev 6: Recovery verification passed (RECOVERY_VERIFICATION -> RESOLVED)
    Rev 7: Recurrence reported (RECURRENCE -> RECURRED)

    Proves:
    - Exactly 7 revisions with monotonic numbers 1..7.
    - Reconstructed StructuredCase preserves all answers, check results, confirmed causes, and final issue condition.
    - Lifecycle event history records all three lifecycle transitions with correct prior/resulting states.
    - Cause confirmation state is preserved even after resolution and recurrence.
    """
    repo, tracked_ids = case_repo
    engine = DiagnosticEngine()
    case_id = str(uuid.uuid4())
    tracked_ids.append(case_id)

    # Rev 1: Initial case
    case = engine.prepare_case(
        StructuredCase(
            case_id=case_id,
            defect_code="D03_INCONSISTENT_SIZE",
            defect_name="Inconsistent Dot Size",
            description="Dots shrinking over time",
        )
    )
    res1 = engine.diagnose(case)
    repo.save_initial_case(case, res1)
    db_session.commit()

    # Rev 2: Question Answer (Q01)
    loaded = repo.load_structured_case(case_id)
    assert loaded is not None
    ans1 = QuestionAnswer(
        question_id="Q01",
        answer_value="after_prolonged_operation",
        source=EvidenceSource.USER,
    )
    c2, res2 = engine.submit_question_answer(loaded, ans1)
    repo.append_question_answer_revision(c2, ans1, res2, expected_revision=1)
    db_session.commit()

    # Rev 3: Check Result (ACT01)
    loaded = repo.load_structured_case(case_id)
    assert loaded is not None
    check1 = CheckResult(
        check_id="ACT01",
        execution_status=CheckExecutionStatus.COMPLETED,
        finding=CheckFinding.CONTRADICTS,
        outcome="no_blockage",
        source=EvidenceSource.USER_CHECK_RESULT,
    )
    c3, res3 = engine.submit_check_result(loaded, check1)
    repo.append_check_result_revision(c3, check1, res3, expected_revision=2)
    db_session.commit()

    # Rev 4: Cause Confirmation
    loaded = repo.load_structured_case(case_id)
    assert loaded is not None
    c4, res4 = engine.confirm_cause(loaded, cause_id="pressure_instability", confirmed_by="technician", confirmation_details="Confirmed by pressure log")
    repo.append_cause_confirmation_revision(c4, cause_id="pressure_instability", confirmed_by="technician", notes="Confirmed by pressure log", result=res4, expected_revision=3)
    db_session.commit()

    # Rev 5: Recovery Action applied
    loaded = repo.load_structured_case(case_id)
    assert loaded is not None
    new_cond, _ = StateManager.transition_issue_condition(
        current_condition=loaded.issue_condition,
        target_condition=IssueCondition.RECOVERY_PENDING_VERIFICATION,
        verification_passed=False,
        verification_details="Replaced pressure regulator valve",
    )
    loaded.issue_condition = new_cond
    res5 = engine.diagnose(loaded)
    res5.issue_condition = new_cond
    repo.append_recovery_action_revision(
        case=loaded,
        performed_by="technician_bob",
        recovery_details="Replaced pressure regulator valve",
        result=res5,
        expected_revision=4,
    )
    db_session.commit()

    # Rev 6: Recovery Verification passed
    loaded = repo.load_structured_case(case_id)
    assert loaded is not None
    resolved_cond, _ = StateManager.transition_issue_condition(
        current_condition=loaded.issue_condition,
        target_condition=IssueCondition.RESOLVED,
        verification_passed=True,
        verification_details="Pressure stability confirmed across 50 continuous cycles",
    )
    loaded.issue_condition = resolved_cond
    res6 = engine.diagnose(loaded)
    res6.issue_condition = resolved_cond
    repo.append_recovery_verification_revision(
        case=loaded,
        verified_by="lead_engineer_alice",
        verification_passed=True,
        verification_details="Pressure stability confirmed across 50 continuous cycles",
        result=res6,
        expected_revision=5,
    )
    db_session.commit()

    # Rev 7: Recurrence reported
    loaded = repo.load_structured_case(case_id)
    assert loaded is not None
    recurred_cond, _ = StateManager.transition_issue_condition(
        current_condition=loaded.issue_condition,
        target_condition=IssueCondition.RECURRED,
        verification_passed=False,
        verification_details="Pressure drop recurred on shift start",
    )
    loaded.issue_condition = recurred_cond
    res7 = engine.diagnose(loaded)
    res7.issue_condition = recurred_cond
    repo.append_recurrence_revision(
        case=loaded,
        reported_by="operator_sam",
        recurrence_details="Pressure drop recurred on shift start",
        result=res7,
        expected_revision=6,
    )
    db_session.commit()

    # Final reconstruction verification
    final_case = repo.load_structured_case(case_id)
    assert final_case is not None
    assert len(final_case.analysis_revisions) == 7
    assert [r.revision_number for r in final_case.analysis_revisions] == [1, 2, 3, 4, 5, 6, 7]
    assert len(final_case.previous_answers) == 1
    assert [a.question_id for a in final_case.previous_answers] == ["Q01"]
    assert len(final_case.previous_check_results) == 1
    assert [c.check_id for c in final_case.previous_check_results] == ["ACT01"]
    assert final_case.confirmed_causes == ["pressure_instability"]
    assert final_case.issue_condition == IssueCondition.RECURRED

    # Latest revision preserves confirmed cause
    confirmed = next((c for c in final_case.analysis_revisions[-1].ranked_causes if c.cause_id == "pressure_instability"), None)
    assert confirmed is not None
    assert confirmed.conclusion == CauseConclusion.CONFIRMED

    # Lifecycle event query verification
    lifecycle_events = repo.get_case_lifecycle_events(case_id)
    assert len(lifecycle_events) == 3
    assert lifecycle_events[0].event_type == "RECOVERY_ACTION"
    assert lifecycle_events[0].prior_issue_condition == "UNRESOLVED"
    assert lifecycle_events[0].resulting_issue_condition == "RECOVERY_PENDING_VERIFICATION"
    assert lifecycle_events[0].resulting_revision_number == 5
    assert lifecycle_events[0].actor == "technician_bob"
    assert lifecycle_events[0].verification_passed is None

    assert lifecycle_events[1].event_type == "RECOVERY_VERIFICATION"
    assert lifecycle_events[1].prior_issue_condition == "RECOVERY_PENDING_VERIFICATION"
    assert lifecycle_events[1].resulting_issue_condition == "RESOLVED"
    assert lifecycle_events[1].resulting_revision_number == 6
    assert lifecycle_events[1].actor == "lead_engineer_alice"
    assert lifecycle_events[1].verification_passed is True

    assert lifecycle_events[2].event_type == "RECURRENCE"
    assert lifecycle_events[2].prior_issue_condition == "RESOLVED"
    assert lifecycle_events[2].resulting_issue_condition == "RECURRED"
    assert lifecycle_events[2].resulting_revision_number == 7
    assert lifecycle_events[2].actor == "operator_sam"
    assert lifecycle_events[2].verification_passed is None
