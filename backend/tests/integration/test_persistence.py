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
from typing import Generator

import pytest
from sqlalchemy import delete, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_database_url
from app.db.database import get_engine, reset_engine
from app.db.repository import CaseRepository, StaleRevisionError
from app.db.session import get_session_factory
from app.models.case import (
    AnalysisRevisionModel,
    CaseModel,
    ObservationModel,
    QuestionAnswerModel,
)
from app.schemas.diagnosis import (
    AnalysisRevision,
    AnswerValue,
    DiagnosisResult,
    EvidenceSource,
    IssueCondition,
    Observation,
    ObservationType,
    QuestionAnswer,
    StatementType,
    StructuredCase,
)
from app.services.diagnosis.engine import DiagnosticEngine
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
    obs_q01 = next(o for o in observations if o.value == "after_prolonged_operation")
    assert obs_q01.first_seen_revision == 2

    for obs in observations:
        if obs.value != "after_prolonged_operation":
            assert obs.first_seen_revision == 1

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
            assert len(case_v2.observations) == 2  # "drips_after_dispense" and "after_prolonged_operation"
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
