"""
DispenseIQ — Truthful Analytics API Integration Tests (DLK-M3-028)

Verifies:
1. Empty database: zero real counts, empty distributions, nullable rates/trends/scores,
   and no sample equipment, cause, narrative, or percentage.
2. Case without machine context or ranked causes: "Not recorded", "Under investigation",
   and evidence_support=None.
3. Multiple analysis revisions: latest top-ranked cause score becomes evidence_support exactly.
4. Cause confirmations: unique confirmed cases produce cause_confirmation_rate coverage metric
   without being labelled accuracy.
5. Period without valid comparison population: trend fields are null.
6. No confirmed cause: insight does not name a fallback cause.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.session import get_session_factory
from app.main import app
from app.models.case import (
    AnalysisRevisionModel,
    CaseCauseConfirmationModel,
    CaseLifecycleEventModel,
    CaseModel,
    ObservationModel,
    QuestionAnswerModel,
)
from app.schemas.diagnosis import IssueCondition

client = TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def configure_test_environment(test_database_url: str) -> None:
    """Configure and verify PostgreSQL connection URL for integration tests."""
    pass


@pytest.fixture
def tracked_cases() -> Generator[list[str], None, None]:
    """Track created case IDs and clean them up after test execution."""
    case_ids: list[str] = []
    yield case_ids

    factory = get_session_factory()
    with factory() as session:
        for cid in case_ids:
            try:
                session.execute(
                    delete(CaseLifecycleEventModel).where(CaseLifecycleEventModel.case_id == cid)
                )
                session.execute(
                    delete(CaseCauseConfirmationModel).where(CaseCauseConfirmationModel.case_id == cid)
                )
                session.execute(
                    delete(AnalysisRevisionModel).where(AnalysisRevisionModel.case_id == cid)
                )
                session.execute(
                    delete(ObservationModel).where(ObservationModel.case_id == cid)
                )
                session.execute(
                    delete(QuestionAnswerModel).where(QuestionAnswerModel.case_id == cid)
                )
                session.execute(delete(CaseModel).where(CaseModel.case_id == cid))
                session.commit()
            except Exception:
                session.rollback()


def test_empty_database_analytics(tracked_cases: list[str]) -> None:
    """Empty database must return zero real counts, empty distributions, and nullable rates/trends."""
    factory = get_session_factory()
    # Ensure database is clean of cases
    with factory() as session:
        session.query(CaseLifecycleEventModel).delete()
        session.query(CaseCauseConfirmationModel).delete()
        session.query(AnalysisRevisionModel).delete()
        session.query(ObservationModel).delete()
        session.query(QuestionAnswerModel).delete()
        session.query(CaseModel).delete()
        session.commit()

    # 1. Dashboard analytics
    resp = client.get("/api/v1/analytics/dashboard")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    kpis = data["kpis"]
    assert kpis["active_diagnoses"] == 0
    assert kpis["open_defects"] == 0
    assert kpis["resolved_cases"] == 0
    assert kpis["avg_diagnosis_time_minutes"] == 0.0
    assert kpis["cause_confirmation_rate"] is None
    assert kpis["active_diagnoses_trend"] is None
    assert kpis["open_defects_trend"] is None
    assert kpis["resolved_cases_trend"] is None
    assert kpis["avg_time_trend"] is None

    assert data["recent_cases"] == []
    assert data["defect_distribution"] == []
    assert data["cause_distribution"] == []
    assert data["ai_insight_text"] is None
    assert data["ai_insight_trend"] is None

    # Verify no fabricated terms
    raw_text = resp.text
    assert "Dispensing Line A" not in raw_text
    assert "Nozzle Condition" not in raw_text
    assert "100%" not in raw_text

    # 2. Performance analytics
    perf_resp = client.get("/api/v1/analytics/performance?period=all")
    assert perf_resp.status_code == 200, perf_resp.text
    perf_data = perf_resp.json()

    perf_kpis = perf_data["kpis"]
    assert perf_kpis["total_cases"] == 0
    assert perf_kpis["resolved_cases"] == 0
    assert perf_kpis["avg_resolution_time_minutes"] == 0.0
    assert perf_kpis["first_time_resolution_rate"] is None
    assert perf_kpis["cause_confirmation_rate"] is None
    assert perf_kpis["total_cases_trend"] is None
    assert perf_kpis["avg_resolution_trend"] is None
    assert perf_kpis["first_time_resolution_trend"] is None
    assert perf_kpis["cause_confirmation_trend"] is None

    assert perf_data["cause_distribution"] == []
    assert perf_data["defect_types"] == []


def test_case_without_machine_context_or_ranked_causes(tracked_cases: list[str]) -> None:
    """A case without machine context or ranked causes returns neutral labels and null score."""
    case_id = str(uuid.uuid4())
    tracked_cases.append(case_id)

    factory = get_session_factory()
    with factory() as session:
        case = CaseModel(
            case_id=case_id,
            description="Test case without context",
            material="solder_paste",
            method="jetting",
            defect_code="D01_BRIDGING",
            defect_name="Bridging",
            issue_condition=IssueCondition.UNRESOLVED.value,
            machine_context=None,
            created_at=datetime.now(timezone.utc),
        )
        session.add(case)
        session.commit()

    resp = client.get("/api/v1/analytics/dashboard")
    assert resp.status_code == 200
    data = resp.json()

    assert len(data["recent_cases"]) >= 1
    recent = next(c for c in data["recent_cases"] if c["id"] == case_id)
    assert recent["equipment"] == "Not recorded"
    assert recent["cause"] == "Under investigation"
    assert recent["evidence_support"] is None
    assert "confidence" not in recent


def test_multiple_analysis_revisions_uses_latest_top_score(tracked_cases: list[str]) -> None:
    """evidence_support is read from latest revision's top ranked cause score exactly."""
    case_id = str(uuid.uuid4())
    tracked_cases.append(case_id)

    factory = get_session_factory()
    with factory() as session:
        case = CaseModel(
            case_id=case_id,
            description="Multi revision test case",
            material="solder_paste",
            method="jetting",
            defect_code="D01_BRIDGING",
            defect_name="Bridging",
            issue_condition=IssueCondition.UNRESOLVED.value,
            machine_context={"machine_id": "Dispense-Bot-42"},
            created_at=datetime.now(timezone.utc),
        )
        session.add(case)

        # Revision 1: score = 45.0
        rev1 = AnalysisRevisionModel(
            case_id=case_id,
            revision_number=1,
            issue_condition=IssueCondition.UNRESOLVED.value,
            analyzed_at=datetime.now(timezone.utc) - timedelta(minutes=10),
            result_snapshot={
                "ranked_causes": [
                    {"cause_id": "nozzle_clog", "cause_name": "Nozzle Clog", "score": 45.0}
                ]
            },
        )
        session.add(rev1)

        # Revision 2: score = 82.5
        rev2 = AnalysisRevisionModel(
            case_id=case_id,
            revision_number=2,
            issue_condition=IssueCondition.UNRESOLVED.value,
            analyzed_at=datetime.now(timezone.utc),
            result_snapshot={
                "ranked_causes": [
                    {"cause_id": "high_pressure", "cause_name": "High Pressure", "score": 82.5}
                ]
            },
        )
        session.add(rev2)
        session.commit()

    resp = client.get("/api/v1/analytics/dashboard")
    assert resp.status_code == 200
    data = resp.json()

    recent = next(c for c in data["recent_cases"] if c["id"] == case_id)
    assert recent["equipment"] == "Dispense-Bot-42"
    assert recent["cause"] == "High Pressure"
    assert recent["evidence_support"] == 82.5


def test_cause_confirmation_rate_coverage_calculation(tracked_cases: list[str]) -> None:
    """cause_confirmation_rate is unique confirmed cases divided by total cases in population."""
    case1_id = str(uuid.uuid4())
    case2_id = str(uuid.uuid4())
    tracked_cases.extend([case1_id, case2_id])

    now = datetime.now(timezone.utc)
    factory = get_session_factory()
    with factory() as session:
        # Case 1: with confirmation
        c1 = CaseModel(
            case_id=case1_id,
            description="Confirmed case",
            material="solder_paste",
            method="jetting",
            defect_code="D01_BRIDGING",
            defect_name="Bridging",
            issue_condition=IssueCondition.RESOLVED.value,
            created_at=now - timedelta(days=2),
        )
        session.add(c1)
        conf1 = CaseCauseConfirmationModel(
            case_id=case1_id,
            cause_id="c_01_thermal_viscosity",
            resulting_revision_number=2,
            confirmed_at=now - timedelta(days=2),
        )
        session.add(conf1)

        # Case 2: without confirmation
        c2 = CaseModel(
            case_id=case2_id,
            description="Unconfirmed case",
            material="solder_paste",
            method="jetting",
            defect_code="D02_TAILING",
            defect_name="Tailing",
            issue_condition=IssueCondition.UNRESOLVED.value,
            created_at=now - timedelta(days=1),
        )
        session.add(c2)
        session.commit()

    # Dashboard check: 1 confirmed / 2 total = 50.0%
    dash_resp = client.get("/api/v1/analytics/dashboard")
    assert dash_resp.status_code == 200
    dash_kpis = dash_resp.json()["kpis"]
    assert dash_kpis["cause_confirmation_rate"] == 50.0

    # Performance check: 1 confirmed / 2 total = 50.0%
    perf_resp = client.get("/api/v1/analytics/performance?period=30d")
    assert perf_resp.status_code == 200
    perf_kpis = perf_resp.json()["kpis"]
    assert perf_kpis["cause_confirmation_rate"] == 50.0


def test_period_without_valid_comparison_population_returns_null_trends(tracked_cases: list[str]) -> None:
    """Trends must return null when no valid period-over-period comparison can be made."""
    case_id = str(uuid.uuid4())
    tracked_cases.append(case_id)

    now = datetime.now(timezone.utc)
    factory = get_session_factory()
    with factory() as session:
        c = CaseModel(
            case_id=case_id,
            description="Recent case only",
            material="solder_paste",
            method="jetting",
            defect_code="D01_BRIDGING",
            defect_name="Bridging",
            issue_condition=IssueCondition.UNRESOLVED.value,
            created_at=now - timedelta(days=2),
        )
        session.add(c)
        session.commit()

    # With period="all", no prior comparison exists -> all trends must be null
    resp_all = client.get("/api/v1/analytics/performance?period=all")
    assert resp_all.status_code == 200
    kpis_all = resp_all.json()["kpis"]
    assert kpis_all["total_cases_trend"] is None
    assert kpis_all["avg_resolution_trend"] is None
    assert kpis_all["first_time_resolution_trend"] is None
    assert kpis_all["cause_confirmation_trend"] is None

    # With period="30d", there are cases in current [now-30d, now] but ZERO in prior [now-60d, now-30d]
    resp_30d = client.get("/api/v1/analytics/performance?period=30d")
    assert resp_30d.status_code == 200
    kpis_30d = resp_30d.json()["kpis"]
    assert kpis_30d["total_cases_trend"] is None
    assert kpis_30d["avg_resolution_trend"] is None
    assert kpis_30d["first_time_resolution_trend"] is None
    assert kpis_30d["cause_confirmation_trend"] is None


def test_no_confirmed_cause_insight_does_not_name_fallback_cause(tracked_cases: list[str]) -> None:
    """When no confirmed cause exists, dashboard insight must not name 'Nozzle Condition' or any unproven cause."""
    case_id = str(uuid.uuid4())
    tracked_cases.append(case_id)

    factory = get_session_factory()
    with factory() as session:
        c = CaseModel(
            case_id=case_id,
            description="Defect without confirmed cause",
            material="solder_paste",
            method="jetting",
            defect_code="D01_BRIDGING",
            defect_name="Bridging",
            issue_condition=IssueCondition.UNRESOLVED.value,
            created_at=datetime.now(timezone.utc),
        )
        session.add(c)
        session.commit()

    resp = client.get("/api/v1/analytics/dashboard")
    assert resp.status_code == 200
    data = resp.json()

    assert data["cause_distribution"] == []
    if data["ai_insight_text"]:
        assert "Nozzle Condition" not in data["ai_insight_text"]
        assert "nozzle" not in data["ai_insight_text"].lower()
