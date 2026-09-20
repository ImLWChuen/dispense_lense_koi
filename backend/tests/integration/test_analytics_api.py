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
    assert kpis["avg_diagnosis_time_minutes"] is None
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
    assert perf_kpis["avg_resolution_time_minutes"] is None
    assert perf_kpis["first_time_resolution_rate"] is None
    assert perf_kpis["cause_confirmation_rate"] is None
    assert perf_kpis["total_cases_trend"] is None
    assert perf_kpis["avg_resolution_trend"] is None
    assert perf_kpis["first_time_resolution_trend"] is None
    assert perf_kpis["cause_confirmation_trend"] is None

    assert perf_data["cause_distribution"] == []
    assert perf_data["defect_types"] == []
    assert perf_data["defect_trend"] == []
    assert perf_data["resolution_time_distribution"] == []


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


def test_dashboard_trends_return_none_for_mismatched_cohorts(tracked_cases: list[str]) -> None:
    """R1: Dashboard KPIs represent all-time states and must return None for trends rather than comparing against 30d creation cohorts."""
    case_old_id = str(uuid.uuid4())
    case_prior_id = str(uuid.uuid4())
    case_curr_id = str(uuid.uuid4())
    tracked_cases.extend([case_old_id, case_prior_id, case_curr_id])

    now = datetime.now(timezone.utc)
    factory = get_session_factory()
    with factory() as session:
        # Older case (> 60 days)
        c_old = CaseModel(
            case_id=case_old_id,
            description="Older case",
            material="solder_paste",
            method="jetting",
            defect_code="D01_BRIDGING",
            defect_name="Bridging",
            issue_condition=IssueCondition.UNRESOLVED.value,
            created_at=now - timedelta(days=90),
        )
        session.add(c_old)

        # Prior-window case (30-60 days)
        c_prior = CaseModel(
            case_id=case_prior_id,
            description="Prior window case",
            material="solder_paste",
            method="jetting",
            defect_code="D01_BRIDGING",
            defect_name="Bridging",
            issue_condition=IssueCondition.UNRESOLVED.value,
            created_at=now - timedelta(days=45),
        )
        session.add(c_prior)

        # Current-window case (< 30 days)
        c_curr = CaseModel(
            case_id=case_curr_id,
            description="Current window case",
            material="solder_paste",
            method="jetting",
            defect_code="D02_TAILING",
            defect_name="Tailing",
            issue_condition=IssueCondition.RESOLVED.value,
            created_at=now - timedelta(days=10),
        )
        session.add(c_curr)
        session.commit()

    resp = client.get("/api/v1/analytics/dashboard")
    assert resp.status_code == 200
    kpis = resp.json()["kpis"]
    assert kpis["active_diagnoses_trend"] is None
    assert kpis["open_defects_trend"] is None
    assert kpis["resolved_cases_trend"] is None
    assert kpis["avg_time_trend"] is None


def test_first_time_resolution_requires_persisted_verification_evidence_and_ignores_revisions(
    tracked_cases: list[str],
) -> None:
    """R2: First-time resolution requires explicit verification lifecycle evidence and is not penalized by analysis revisions."""
    case_no_verif_id = str(uuid.uuid4())
    case_multi_rev_id = str(uuid.uuid4())
    case_failed_then_passed_id = str(uuid.uuid4())
    tracked_cases.extend([case_no_verif_id, case_multi_rev_id, case_failed_then_passed_id])

    now = datetime.now(timezone.utc)
    factory = get_session_factory()
    with factory() as session:
        # Case A: resolved but has NO verification lifecycle event
        cA = CaseModel(
            case_id=case_no_verif_id,
            description="Resolved without lifecycle event",
            material="solder_paste",
            method="jetting",
            defect_code="D01_BRIDGING",
            defect_name="Bridging",
            issue_condition=IssueCondition.RESOLVED.value,
            created_at=now - timedelta(days=5),
        )
        session.add(cA)
        session.commit()

    # When a resolved case has no verification lifecycle events, evidence is unsupported -> None
    resp_unsupported = client.get("/api/v1/analytics/performance?period=30d")
    assert resp_unsupported.status_code == 200
    assert resp_unsupported.json()["kpis"]["first_time_resolution_rate"] is None

    # Clean up Case A so we can test cases with full verification lifecycle evidence
    with factory() as session:
        session.query(CaseModel).filter(CaseModel.case_id == case_no_verif_id).delete()
        session.commit()

    with factory() as session:
        # Case B: 4 analysis revisions, 1 recovery action, 1 passed verification (0 failed, 0 recurred)
        cB = CaseModel(
            case_id=case_multi_rev_id,
            description="Multi revision first-time resolved",
            material="solder_paste",
            method="jetting",
            defect_code="D01_BRIDGING",
            defect_name="Bridging",
            issue_condition=IssueCondition.RESOLVED.value,
            created_at=now - timedelta(days=5),
        )
        session.add(cB)
        # Add 4 revisions (questions, checks, etc.)
        for r in range(1, 5):
            session.add(
                AnalysisRevisionModel(
                    case_id=case_multi_rev_id,
                    revision_number=r,
                    issue_condition=IssueCondition.UNRESOLVED.value if r < 4 else IssueCondition.RESOLVED.value,
                    analyzed_at=now - timedelta(days=5) + timedelta(minutes=r * 2),
                    result_snapshot={},
                )
            )
        # Passed verification lifecycle event
        ev_pass = CaseLifecycleEventModel(
            case_id=case_multi_rev_id,
            event_type="RECOVERY_VERIFICATION",
            prior_issue_condition="RECOVERY_PENDING_VERIFICATION",
            resulting_issue_condition=IssueCondition.RESOLVED.value,
            resulting_revision_number=4,
            actor="technician",
            details="Passed on first verification attempt",
            verification_passed=True,
            created_at=now - timedelta(days=5) + timedelta(minutes=15),
        )
        session.add(ev_pass)
        session.commit()

    # Case B alone with 4 revisions must still be 100% first-time resolved!
    resp_b = client.get("/api/v1/analytics/performance?period=30d")
    assert resp_b.status_code == 200
    assert resp_b.json()["kpis"]["first_time_resolution_rate"] == 100.0

    # Now add Case C: had a failed verification before succeeding
    with factory() as session:
        cC = CaseModel(
            case_id=case_failed_then_passed_id,
            description="Failed verification first attempt",
            material="solder_paste",
            method="jetting",
            defect_code="D02_TAILING",
            defect_name="Tailing",
            issue_condition=IssueCondition.RESOLVED.value,
            created_at=now - timedelta(days=4),
        )
        session.add(cC)
        # Failed verification
        ev_fail = CaseLifecycleEventModel(
            case_id=case_failed_then_passed_id,
            event_type="RECOVERY_VERIFICATION",
            prior_issue_condition="RECOVERY_PENDING_VERIFICATION",
            resulting_issue_condition=IssueCondition.UNRESOLVED.value,
            resulting_revision_number=2,
            actor="technician",
            details="Verification check failed",
            verification_passed=False,
            created_at=now - timedelta(days=4) + timedelta(minutes=10),
        )
        session.add(ev_fail)
        # Subsequent passed verification
        ev_pass2 = CaseLifecycleEventModel(
            case_id=case_failed_then_passed_id,
            event_type="RECOVERY_VERIFICATION",
            prior_issue_condition="RECOVERY_PENDING_VERIFICATION",
            resulting_issue_condition=IssueCondition.RESOLVED.value,
            resulting_revision_number=3,
            actor="technician",
            details="Second verification check passed",
            verification_passed=True,
            created_at=now - timedelta(days=4) + timedelta(minutes=25),
        )
        session.add(ev_pass2)
        session.commit()

    # With 1 first-time resolved and 1 retry-resolved: 1/2 = 50.0%
    resp_bc = client.get("/api/v1/analytics/performance?period=30d")
    assert resp_bc.status_code == 200
    assert resp_bc.json()["kpis"]["first_time_resolution_rate"] == 50.0


def test_resolved_case_without_resolution_event_excluded_from_duration(
    tracked_cases: list[str],
) -> None:
    """R3: Cases resolved without an explicit resolution lifecycle event are excluded from averages and duration buckets."""
    case_no_ev_id = str(uuid.uuid4())
    case_measured_id = str(uuid.uuid4())
    tracked_cases.extend([case_no_ev_id, case_measured_id])

    now = datetime.now(timezone.utc)
    factory = get_session_factory()
    with factory() as session:
        # Case without lifecycle event
        c1 = CaseModel(
            case_id=case_no_ev_id,
            description="Resolved without event",
            material="solder_paste",
            method="jetting",
            defect_code="D01_BRIDGING",
            defect_name="Bridging",
            issue_condition=IssueCondition.RESOLVED.value,
            created_at=now - timedelta(days=2),
        )
        session.add(c1)
        session.commit()

    # Dashboard: avg_diagnosis_time_minutes must be None (not 0.0)
    dash_resp = client.get("/api/v1/analytics/dashboard")
    assert dash_resp.status_code == 200
    assert dash_resp.json()["kpis"]["avg_diagnosis_time_minutes"] is None

    # Performance: avg_resolution_time_minutes must be None and 0-5 min bucket must be 0
    perf_resp = client.get("/api/v1/analytics/performance?period=all")
    assert perf_resp.status_code == 200
    perf_data = perf_resp.json()
    assert perf_data["kpis"]["avg_resolution_time_minutes"] is None
    assert perf_data["resolution_time_distribution"] == []

    # Now add measured case with 12-minute duration
    with factory() as session:
        c2 = CaseModel(
            case_id=case_measured_id,
            description="Measured case",
            material="solder_paste",
            method="jetting",
            defect_code="D01_BRIDGING",
            defect_name="Bridging",
            issue_condition=IssueCondition.RESOLVED.value,
            created_at=now - timedelta(minutes=15),
        )
        session.add(c2)
        ev = CaseLifecycleEventModel(
            case_id=case_measured_id,
            event_type="RECOVERY_VERIFICATION",
            prior_issue_condition="RECOVERY_PENDING_VERIFICATION",
            resulting_issue_condition=IssueCondition.RESOLVED.value,
            resulting_revision_number=2,
            actor="technician",
            details="Resolved and verified",
            verification_passed=True,
            created_at=now - timedelta(minutes=3),  # 15 - 3 = 12 minutes
        )
        session.add(ev)
        session.commit()

    perf_resp2 = client.get("/api/v1/analytics/performance?period=all")
    assert perf_resp2.status_code == 200
    perf_data2 = perf_resp2.json()
    assert perf_data2["kpis"]["avg_resolution_time_minutes"] == 12.0
    assert len(perf_data2["resolution_time_distribution"]) == 6

    bucket_0_5_after = next(b for b in perf_data2["resolution_time_distribution"] if b["range"] == "0-5 min")
    bucket_10_15_after = next(b for b in perf_data2["resolution_time_distribution"] if b["range"] == "10-15 min")
    assert bucket_0_5_after["count"] == 0
    assert bucket_10_15_after["count"] == 1


def test_canonical_equipment_key_read_in_recent_cases(tracked_cases: list[str]) -> None:
    """R5: machine_context.equipment is read as canonical equipment key."""
    case_id = str(uuid.uuid4())
    tracked_cases.append(case_id)

    factory = get_session_factory()
    with factory() as session:
        c = CaseModel(
            case_id=case_id,
            description="Case with canonical equipment",
            material="solder_paste",
            method="jetting",
            defect_code="D01_BRIDGING",
            defect_name="Bridging",
            issue_condition=IssueCondition.UNRESOLVED.value,
            machine_context={"equipment": "Dispenser Alpha-9"},
            created_at=datetime.now(timezone.utc),
        )
        session.add(c)
        session.commit()

    resp = client.get("/api/v1/analytics/dashboard")
    assert resp.status_code == 200
    recent = next(c for c in resp.json()["recent_cases"] if c["id"] == case_id)
    assert recent["equipment"] == "Dispenser Alpha-9"


def test_cause_distribution_counts_distinct_cases_with_repeated_confirmations(
    tracked_cases: list[str],
) -> None:
    """R6: Repeated cause confirmation revisions for one case must count as only 1 case."""
    case_id = str(uuid.uuid4())
    tracked_cases.append(case_id)

    now = datetime.now(timezone.utc)
    factory = get_session_factory()
    with factory() as session:
        c = CaseModel(
            case_id=case_id,
            description="Case with multiple confirmation revisions",
            material="solder_paste",
            method="jetting",
            defect_code="D01_BRIDGING",
            defect_name="Bridging",
            issue_condition=IssueCondition.RESOLVED.value,
            created_at=now - timedelta(days=2),
        )
        session.add(c)
        # Rev 2 confirmation
        conf1 = CaseCauseConfirmationModel(
            case_id=case_id,
            cause_id="c_01_thermal_viscosity",
            resulting_revision_number=2,
            confirmed_at=now - timedelta(days=2),
        )
        session.add(conf1)
        # Rev 3 re-confirmation of same cause
        conf2 = CaseCauseConfirmationModel(
            case_id=case_id,
            cause_id="c_01_thermal_viscosity",
            resulting_revision_number=3,
            confirmed_at=now - timedelta(days=1),
        )
        session.add(conf2)
        session.commit()

    # Dashboard cause distribution: cases must be 1
    dash_resp = client.get("/api/v1/analytics/dashboard")
    assert dash_resp.status_code == 200
    dash_causes = dash_resp.json()["cause_distribution"]
    assert len(dash_causes) >= 1
    top_cause = dash_causes[0]
    assert top_cause["cases"] == 1

    # Performance cause distribution: cases must be 1
    perf_resp = client.get("/api/v1/analytics/performance?period=all")
    assert perf_resp.status_code == 200
    perf_causes = perf_resp.json()["cause_distribution"]
    assert len(perf_causes) >= 1
    assert perf_causes[0]["cases"] == 1


def test_insight_population_label_and_defect_trend(tracked_cases: list[str]) -> None:
    """R7: Insight label describes defect-recorded cases, and monthly defect trend queries defect-classified cases."""
    case1_id = str(uuid.uuid4())
    case2_id = str(uuid.uuid4())
    tracked_cases.extend([case1_id, case2_id])

    now = datetime.now(timezone.utc)
    factory = get_session_factory()
    with factory() as session:
        # Case 1 with defect
        c1 = CaseModel(
            case_id=case1_id,
            description="Case with defect",
            material="solder_paste",
            method="jetting",
            defect_code="D01_BRIDGING",
            defect_name="Bridging",
            issue_condition=IssueCondition.UNRESOLVED.value,
            created_at=now,
        )
        session.add(c1)

        # Case 2 without defect
        c2 = CaseModel(
            case_id=case2_id,
            description="Case without defect",
            material="solder_paste",
            method="jetting",
            defect_code=None,
            defect_name=None,
            issue_condition=IssueCondition.UNRESOLVED.value,
            created_at=now,
        )
        session.add(c2)
        session.commit()

    dash_resp = client.get("/api/v1/analytics/dashboard")
    assert dash_resp.status_code == 200
    dash_data = dash_resp.json()
    assert dash_data["ai_insight_trend"] == "100.0% of defect-recorded cases"

    perf_resp = client.get("/api/v1/analytics/performance?period=all")
    assert perf_resp.status_code == 200
    trend = perf_resp.json()["defect_trend"]
    assert len(trend) == 6
    # Current month should have exactly 1 defect (from case 1, case 2 excluded)
    current_month_name = now.strftime("%b")
    cur_trend = next(t for t in trend if t["month"] == current_month_name)
    assert cur_trend["defects"] == 1


def test_deterministic_defect_order_and_unrelated_cause_insight(
    tracked_cases: list[str],
) -> None:
    """R9: Defect distribution is sorted deterministically by count desc, and insight presents separate scoped facts."""
    case_stringing_id = str(uuid.uuid4())
    case_bridging_1_id = str(uuid.uuid4())
    case_bridging_2_id = str(uuid.uuid4())
    tracked_cases.extend([case_stringing_id, case_bridging_1_id, case_bridging_2_id])

    now = datetime.now(timezone.utc)
    factory = get_session_factory()
    with factory() as session:
        # Insert Stringing FIRST (1 case). If unsorted, PostgreSQL might return Stringing first.
        c_str = CaseModel(
            case_id=case_stringing_id,
            description="Stringing defect",
            material="solder_paste",
            method="jetting",
            defect_code="D03_STRINGING",
            defect_name="Stringing",
            issue_condition=IssueCondition.RESOLVED.value,
            created_at=now - timedelta(hours=3),
        )
        session.add(c_str)

        # Confirmed cause for Stringing case
        conf = CaseCauseConfirmationModel(
            case_id=case_stringing_id,
            cause_id="nozzle_restriction",
            resulting_revision_number=2,
            confirmed_by="technician",
            notes="Confirmed nozzle restriction",
            confirmed_at=now - timedelta(hours=2),
        )
        session.add(conf)

        # Insert Bridging SECOND and THIRD (2 cases). Bridging must be top defect by count.
        c_br1 = CaseModel(
            case_id=case_bridging_1_id,
            description="Bridging defect 1",
            material="solder_paste",
            method="jetting",
            defect_code="D01_BRIDGING",
            defect_name="Bridging",
            issue_condition=IssueCondition.UNRESOLVED.value,
            created_at=now - timedelta(hours=1),
        )
        session.add(c_br1)

        c_br2 = CaseModel(
            case_id=case_bridging_2_id,
            description="Bridging defect 2",
            material="solder_paste",
            method="jetting",
            defect_code="D01_BRIDGING",
            defect_name="Bridging",
            issue_condition=IssueCondition.UNRESOLVED.value,
            created_at=now,
        )
        session.add(c_br2)
        session.commit()

    resp = client.get("/api/v1/analytics/dashboard")
    assert resp.status_code == 200
    data = resp.json()

    # 1. Defect distribution must have Bridging first (2 cases = 66.7%), Stringing second (1 case = 33.3%)
    defects = data["defect_distribution"]
    assert len(defects) == 2
    assert defects[0]["name"] == "Bridging"
    assert defects[0]["count"] == 2
    assert defects[0]["value"] == 66.7
    assert defects[1]["name"] == "Stringing"
    assert defects[1]["count"] == 1
    assert defects[1]["value"] == 33.3

    # 2. Insight must present separate scoped facts and never link Bridging causally to Nozzle Restriction
    insight_text = data["ai_insight_text"]
    assert insight_text is not None
    assert "Most recorded defect category: Bridging." in insight_text
    assert "Most commonly confirmed cause across all confirmed cases: Nozzle Restriction." in insight_text
    # Prohibit unsupported causal link or recency
    assert "recent" not in insight_text.lower()
    assert "primary contributing factor" not in insight_text.lower()
    assert data["ai_insight_trend"] == "66.7% of defect-recorded cases"


def test_defect_breakdown_with_missing_defect_code(
    tracked_cases: list[str],
) -> None:
    """R10: Defect type breakdown preserves null defect_code without inventing D00."""
    case_id = str(uuid.uuid4())
    tracked_cases.append(case_id)

    now = datetime.now(timezone.utc)
    factory = get_session_factory()
    with factory() as session:
        c = CaseModel(
            case_id=case_id,
            description="Satellite defect without code",
            material="solder_paste",
            method="jetting",
            defect_code=None,  # No defect code recorded
            defect_name="Satellite Droplets",
            issue_condition=IssueCondition.UNRESOLVED.value,
            created_at=now,
        )
        session.add(c)
        session.commit()

    resp = client.get("/api/v1/analytics/performance?period=all")
    assert resp.status_code == 200
    data = resp.json()

    defect_types = data["defect_types"]
    assert len(defect_types) >= 1
    target = next((d for d in defect_types if d["name"] == "Satellite Droplets"), None)
    assert target is not None
    assert target["code"] is None  # Must remain None, not "D00"
    assert target["count"] == 1
    assert "D00" not in [d["code"] for d in defect_types if d.get("code") is not None]
