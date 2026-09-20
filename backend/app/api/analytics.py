from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.knowledge import get_cause_by_id
from app.models.case import (
    AnalysisRevisionModel,
    CaseCauseConfirmationModel,
    CaseLifecycleEventModel,
    CaseModel,
)
from app.schemas.analytics import (
    AnalyticsKpiMetrics,
    AnalyticsPerformanceResponse,
    CauseDistributionItem,
    DashboardAnalyticsResponse,
    DefectDistributionItem,
    DefectTrendItem,
    DefectTypeBreakdownItem,
    KpiMetrics,
    RecentCaseRecord,
    ResolutionDistributionItem,
)
from app.schemas.diagnosis import IssueCondition
from app.schemas.spc import SpcAnalysisResponse
from app.services.spc.spc_service import generate_spc_analysis

logger = logging.getLogger(__name__)

router = APIRouter()

# Global subscriber list for real-time SSE event broadcast
_sse_subscribers: list[asyncio.Queue] = []


def broadcast_analytics_update(event_type: str = "CASE_COMPLETED", payload: dict[str, Any] | None = None) -> None:
    """Broadcast an event to all connected clients globally."""
    message = {
        "event": event_type,
        "payload": payload or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    for queue in list(_sse_subscribers):
        try:
            queue.put_nowait(message)
        except Exception:
            pass


@router.get(
    "/events",
    summary="Server-Sent Events stream for global real-time analytics updates",
    description="Maintains an open SSE connection to broadcast case updates to all accounts in real time.",
)
async def sse_events(request: Request) -> StreamingResponse:
    """Server-Sent Events endpoint streaming real-time case and analytics events."""
    queue: asyncio.Queue = asyncio.Queue()
    _sse_subscribers.append(queue)

    async def event_generator():
        try:
            # Send initial connected event
            init_msg = json.dumps({"event": "CONNECTED", "timestamp": datetime.now(timezone.utc).isoformat()})
            yield f"data: {init_msg}\n\n"

            while True:
                if await request.is_disconnected():
                    break
                # Wait for broadcasted message or send periodic keepalive
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(data)}\n\n"
                except asyncio.TimeoutError:
                    if await request.is_disconnected():
                        break
                    # Send keepalive ping to prevent connection drop
                    ping = json.dumps({"event": "PING", "timestamp": datetime.now(timezone.utc).isoformat()})
                    yield f"data: {ping}\n\n"
        except (asyncio.CancelledError, GeneratorExit):
            pass
        finally:
            if queue in _sse_subscribers:
                _sse_subscribers.remove(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def time_ago(dt: datetime) -> str:
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    diff = now - dt
    minutes = max(0, int(diff.total_seconds() / 60))
    if minutes < 60:
        return f"{minutes} min ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hr{'s' if hours > 1 else ''} ago"
    days = hours // 24
    return f"{days} day{'s' if days > 1 else ''} ago"


@router.get(
    "/dashboard",
    response_model=DashboardAnalyticsResponse,
    summary="Get dashboard analytics",
)
def get_dashboard_analytics(session: Session = Depends(get_db)) -> DashboardAnalyticsResponse:
    """Retrieve aggregated data for the main dashboard overview directly from database records."""
    now = datetime.now(timezone.utc)

    active_diagnoses = session.query(CaseModel).filter(
        CaseModel.issue_condition != IssueCondition.RESOLVED.value
    ).count()

    open_defects = session.query(CaseModel).filter(
        CaseModel.issue_condition != IssueCondition.RESOLVED.value,
        CaseModel.defect_code.isnot(None),
    ).count()

    resolved_cases = session.query(CaseModel).filter(
        CaseModel.issue_condition == IssueCondition.RESOLVED.value,
    ).count()

    resolved_case_models = session.query(CaseModel).filter(
        CaseModel.issue_condition == IssueCondition.RESOLVED.value
    ).all()
    total_minutes = 0.0
    resolved_count = 0

    for case in resolved_case_models:
        resolve_event = session.query(CaseLifecycleEventModel).filter(
            CaseLifecycleEventModel.case_id == case.case_id,
            CaseLifecycleEventModel.resulting_issue_condition == IssueCondition.RESOLVED.value,
        ).order_by(CaseLifecycleEventModel.created_at.asc()).first()

        if resolve_event:
            diff = resolve_event.created_at - case.created_at
            total_minutes += max(0.1, round(diff.total_seconds() / 60, 1))
            resolved_count += 1

    avg_time: Optional[float] = round(total_minutes / resolved_count, 1) if resolved_count > 0 else None

    total_cases = session.query(CaseModel).count()
    if total_cases > 0:
        confirmed_cases_count = session.query(
            func.count(func.distinct(CaseCauseConfirmationModel.case_id))
        ).scalar() or 0
        cause_confirmation_rate = round((confirmed_cases_count / total_cases) * 100, 1)
    else:
        cause_confirmation_rate = None

    # Operational state trends (active_diagnoses, open_defects, resolved_cases)
    # cannot be reconstructed truthfully from historical creation cohorts without
    # point-in-time state snapshots; set to None per contract.
    active_diagnoses_trend: Optional[str] = None
    open_defects_trend: Optional[str] = None
    resolved_cases_trend: Optional[str] = None
    avg_time_trend: Optional[str] = None

    kpis = KpiMetrics(
        active_diagnoses=active_diagnoses,
        open_defects=open_defects,
        resolved_cases=resolved_cases,
        avg_diagnosis_time_minutes=avg_time,
        active_diagnoses_trend=active_diagnoses_trend,
        open_defects_trend=open_defects_trend,
        resolved_cases_trend=resolved_cases_trend,
        avg_time_trend=avg_time_trend,
        cause_confirmation_rate=cause_confirmation_rate,
    )

    recent_cases_query = session.query(CaseModel).order_by(CaseModel.created_at.desc()).limit(5).all()
    recent_cases: list[RecentCaseRecord] = []
    for c in recent_cases_query:
        conf = session.query(CaseCauseConfirmationModel).filter(
            CaseCauseConfirmationModel.case_id == c.case_id
        ).order_by(CaseCauseConfirmationModel.resulting_revision_number.desc()).first()

        if conf:
            c_def = get_cause_by_id(conf.cause_id)
            cause_name = c_def.name if c_def else conf.cause_id.replace("_", " ").title()
        else:
            rev = session.query(AnalysisRevisionModel).filter(
                AnalysisRevisionModel.case_id == c.case_id
            ).order_by(AnalysisRevisionModel.revision_number.desc()).first()
            if rev and rev.result_snapshot and rev.result_snapshot.get("ranked_causes"):
                top_cause = rev.result_snapshot["ranked_causes"][0]
                c_def = get_cause_by_id(top_cause.get("cause_id")) if top_cause.get("cause_id") else None
                cause_name = (
                    top_cause.get("cause_name")
                    or (c_def.name if c_def else None)
                    or "Under investigation"
                )
            else:
                cause_name = "Under investigation"

        status = (
            "Resolved"
            if c.issue_condition in (IssueCondition.RESOLVED.value, "RESOLVED")
            else "Needs Review"
            if c.issue_condition in (IssueCondition.RECOVERY_PENDING_VERIFICATION.value, "RECOVERY_PENDING_VERIFICATION")
            else "In Progress"
        )

        eq = "Not recorded"
        if c.machine_context and isinstance(c.machine_context, dict):
            eq = (
                c.machine_context.get("equipment")
                or c.machine_context.get("machine_id")
                or c.machine_context.get("equipment_id")
                or "Not recorded"
            )

        # Read evidence_support from latest persisted analysis revision's top-ranked cause score
        latest_rev = session.query(AnalysisRevisionModel).filter(
            AnalysisRevisionModel.case_id == c.case_id,
        ).order_by(AnalysisRevisionModel.revision_number.desc()).first()

        evidence_support: Optional[float] = None
        if latest_rev and latest_rev.result_snapshot and latest_rev.result_snapshot.get("ranked_causes"):
            top_ranked = latest_rev.result_snapshot["ranked_causes"][0]
            if "score" in top_ranked and top_ranked["score"] is not None:
                evidence_support = round(float(top_ranked["score"]), 1)

        recent_cases.append(
            RecentCaseRecord(
                id=c.case_id,
                case_number=f"DSP-{c.case_id[:8].upper()}",
                defect=c.defect_name or "Unknown Defect",
                equipment=eq,
                cause=cause_name,
                status=status,
                evidence_support=evidence_support,
                time=time_ago(c.created_at),
            )
        )

    defect_counts = (
        session.query(
            CaseModel.defect_name,
            func.count(CaseModel.case_id),
        )
        .filter(CaseModel.defect_name.isnot(None))
        .group_by(CaseModel.defect_name)
        .order_by(
            func.count(CaseModel.case_id).desc(),
            CaseModel.defect_name.asc(),
        )
        .all()
    )

    total_defects = sum([count for _, count in defect_counts])
    defect_distribution: list[DefectDistributionItem] = []
    if total_defects > 0:
        defect_distribution = [
            DefectDistributionItem(
                name=name,
                value=round((count / total_defects) * 100, 1),
                count=count,
            )
            for name, count in defect_counts
        ]

    cause_counts = session.query(
        CaseCauseConfirmationModel.cause_id,
        func.count(func.distinct(CaseCauseConfirmationModel.case_id)),
    ).group_by(CaseCauseConfirmationModel.cause_id).order_by(
        func.count(func.distinct(CaseCauseConfirmationModel.case_id)).desc()
    ).limit(5).all()

    cause_distribution: list[CauseDistributionItem] = []
    for c_id, c_count in cause_counts:
        cause_def = get_cause_by_id(c_id)
        cause_name = cause_def.name if cause_def else c_id.replace("_", " ").title()
        cause_distribution.append(CauseDistributionItem(cause=cause_name, cases=c_count))

    # Truthful AI Insight based strictly on verified data
    ai_insight_text = None
    ai_insight_trend = None
    if defect_distribution:
        top_defect = defect_distribution[0]
        if cause_distribution:
            top_cause = cause_distribution[0].cause
            ai_insight_text = (
                f"Most recorded defect category: {top_defect.name}. "
                f"Most commonly confirmed cause across all confirmed cases: {top_cause}."
            )
        else:
            ai_insight_text = (
                f"Most recorded defect category: {top_defect.name}. "
                "Root cause investigations are currently in progress."
            )
        ai_insight_trend = f"{top_defect.value}% of defect-recorded cases"

    return DashboardAnalyticsResponse(
        kpis=kpis,
        recent_cases=recent_cases,
        defect_distribution=defect_distribution,
        cause_distribution=cause_distribution,
        ai_insight_text=ai_insight_text,
        ai_insight_trend=ai_insight_trend,
    )


@router.get(
    "/performance",
    response_model=AnalyticsPerformanceResponse,
    summary="Get dedicated performance analytics with dynamic period filtering",
)
def get_performance_analytics(
    period: str = Query("30d", enum=["7d", "30d", "90d", "year", "all"]),
    session: Session = Depends(get_db),
) -> AnalyticsPerformanceResponse:
    """Retrieve accurate performance analytics and chart distributions directly from database records."""
    now = datetime.now(timezone.utc)

    # Date filter window
    cutoff: datetime | None = None
    prev_cutoff: datetime | None = None
    if period == "7d":
        cutoff = now - timedelta(days=7)
        prev_cutoff = now - timedelta(days=14)
    elif period == "30d":
        cutoff = now - timedelta(days=30)
        prev_cutoff = now - timedelta(days=60)
    elif period == "90d":
        cutoff = now - timedelta(days=90)
        prev_cutoff = now - timedelta(days=180)
    elif period == "year":
        cutoff = now - timedelta(days=365)
        prev_cutoff = now - timedelta(days=730)
    elif period == "all":
        cutoff = None
        prev_cutoff = None

    cases_query = session.query(CaseModel)
    if cutoff:
        cases_query = cases_query.filter(CaseModel.created_at >= cutoff)
    cases = cases_query.all()

    total_cases = len(cases)
    resolved_cases = [c for c in cases if c.issue_condition in (IssueCondition.RESOLVED.value, "RESOLVED")]
    resolved_count = len(resolved_cases)

    # 1. Average Resolution Time
    total_res_minutes = 0.0
    measured_res_count = 0
    res_times_minutes: list[float] = []

    for c in resolved_cases:
        res_event = session.query(CaseLifecycleEventModel).filter(
            CaseLifecycleEventModel.case_id == c.case_id,
            CaseLifecycleEventModel.resulting_issue_condition.in_([IssueCondition.RESOLVED.value, "RESOLVED"]),
        ).order_by(CaseLifecycleEventModel.created_at.asc()).first()

        if res_event:
            diff = (res_event.created_at - c.created_at).total_seconds() / 60
            minutes = max(0.1, round(diff, 1))
            total_res_minutes += minutes
            measured_res_count += 1
            res_times_minutes.append(minutes)

    avg_res_time: Optional[float] = (
        round(total_res_minutes / measured_res_count, 1)
        if measured_res_count > 0
        else None
    )

    # 2. First-Time Resolution Rate
    # Derived strictly from explicit persisted lifecycle evidence:
    # A resolved case is first-time resolved if it has at least one passed verification (RECOVERY_VERIFICATION with verification_passed=True),
    # 0 failed verifications, and 0 recurrences.
    # If verification lifecycle evidence is missing/unsupported for any resolved case in the cohort, return None.
    first_time_rate: Optional[float] = None
    if resolved_count > 0:
        first_time_resolved_count = 0
        has_unsupported_evidence = False
        for c in resolved_cases:
            events = session.query(CaseLifecycleEventModel).filter(
                CaseLifecycleEventModel.case_id == c.case_id
            ).all()
            verifs = [
                e for e in events
                if e.event_type in ("RECOVERY_VERIFICATION", "VERIFICATION")
            ]
            if not verifs:
                has_unsupported_evidence = True
                break

            has_recurrence = any(
                e.resulting_issue_condition in (IssueCondition.RECURRED.value, "RECURRED")
                or e.event_type == "RECURRENCE"
                for e in events
            )
            has_passed = any(e.verification_passed is True for e in verifs)
            has_failed = any(e.verification_passed is False for e in verifs)

            if has_passed and not has_failed and not has_recurrence:
                first_time_resolved_count += 1

        if not has_unsupported_evidence:
            first_time_rate = round((first_time_resolved_count / resolved_count) * 100, 1)

    # 3. Cause Confirmation Rate: unique cases with at least one confirmation / total cases
    cause_confirmation_rate: Optional[float] = None
    if total_cases > 0:
        case_ids = [c.case_id for c in cases]
        confirmed_cases_count = session.query(
            func.count(func.distinct(CaseCauseConfirmationModel.case_id))
        ).filter(CaseCauseConfirmationModel.case_id.in_(case_ids)).scalar() or 0
        cause_confirmation_rate = round((confirmed_cases_count / total_cases) * 100, 1)

    # Trend calculation: only when comparable prior population exists
    total_cases_trend: Optional[str] = None
    avg_resolution_trend: Optional[str] = None
    first_time_resolution_trend: Optional[str] = None
    cause_confirmation_trend: Optional[str] = None

    if cutoff and prev_cutoff:
        prev_cases = session.query(CaseModel).filter(
            CaseModel.created_at >= prev_cutoff,
            CaseModel.created_at < cutoff,
        ).all()
        prev_total_cases = len(prev_cases)

        if prev_total_cases > 0:
            diff_pct = round(((total_cases - prev_total_cases) / prev_total_cases) * 100)
            total_cases_trend = f"{'+' if diff_pct >= 0 else ''}{diff_pct}%"

            # Prior confirmation rate
            prev_case_ids = [c.case_id for c in prev_cases]
            prev_confirmed = session.query(
                func.count(func.distinct(CaseCauseConfirmationModel.case_id))
            ).filter(CaseCauseConfirmationModel.case_id.in_(prev_case_ids)).scalar() or 0
            prev_conf_rate = round((prev_confirmed / prev_total_cases) * 100, 1)
            if cause_confirmation_rate is not None and prev_conf_rate > 0:
                diff_conf = round(((cause_confirmation_rate - prev_conf_rate) / prev_conf_rate) * 100)
                cause_confirmation_trend = f"{'+' if diff_conf >= 0 else ''}{diff_conf}%"

            # Prior resolution time and first-time resolution
            prev_resolved = [c for c in prev_cases if c.issue_condition in (IssueCondition.RESOLVED.value, "RESOLVED")]
            if prev_resolved and measured_res_count > 0 and avg_res_time is not None:
                prev_res_minutes = 0.0
                prev_measured = 0
                for c in prev_resolved:
                    ev = session.query(CaseLifecycleEventModel).filter(
                        CaseLifecycleEventModel.case_id == c.case_id,
                        CaseLifecycleEventModel.resulting_issue_condition.in_([IssueCondition.RESOLVED.value, "RESOLVED"]),
                    ).order_by(CaseLifecycleEventModel.created_at.asc()).first()
                    if ev:
                        diff = (ev.created_at - c.created_at).total_seconds() / 60
                        prev_res_minutes += max(0.1, round(diff, 1))
                        prev_measured += 1
                if prev_measured > 0:
                    prev_avg_res = round(prev_res_minutes / prev_measured, 1)
                    if prev_avg_res > 0:
                        diff_avg = round(((avg_res_time - prev_avg_res) / prev_avg_res) * 100)
                        avg_resolution_trend = f"{'+' if diff_avg >= 0 else ''}{diff_avg}%"

    kpis = AnalyticsKpiMetrics(
        total_cases=total_cases,
        resolved_cases=resolved_count,
        avg_resolution_time_minutes=avg_res_time,
        first_time_resolution_rate=first_time_rate,
        cause_confirmation_rate=cause_confirmation_rate,
        total_cases_trend=total_cases_trend,
        avg_resolution_trend=avg_resolution_trend,
        first_time_resolution_trend=first_time_resolution_trend,
        cause_confirmation_trend=cause_confirmation_trend,
    )

    # 4. Monthly Defect Trend (Chronological last 6 calendar months up to current month)
    cur_year = now.year
    cur_month = now.month
    month_slots: list[tuple[int, int, str]] = []
    for i in range(5, -1, -1):
        m = cur_month - i
        y = cur_year
        while m <= 0:
            m += 12
            y -= 1
        dt = datetime(y, m, 1, tzinfo=timezone.utc)
        month_slots.append((y, m, dt.strftime("%b")))

    defect_trend = []
    for y, m, m_name in month_slots:
        month_count = session.query(CaseModel).filter(
            or_(CaseModel.defect_code.isnot(None), CaseModel.defect_name.isnot(None)),
            func.extract("year", CaseModel.created_at) == y,
            func.extract("month", CaseModel.created_at) == m,
        ).count()
        defect_trend.append(DefectTrendItem(month=m_name, defects=month_count))

    if not any(d.defects > 0 for d in defect_trend):
        defect_trend = []

    # 5. Root Cause Distribution (Actual confirmed root causes)
    cause_counts_query = (
        session.query(
            CaseCauseConfirmationModel.cause_id,
            func.count(func.distinct(CaseCauseConfirmationModel.case_id)),
        )
        .join(CaseModel, CaseCauseConfirmationModel.case_id == CaseModel.case_id)
    )
    if cutoff:
        cause_counts_query = cause_counts_query.filter(CaseModel.created_at >= cutoff)

    cause_counts = (
        cause_counts_query
        .group_by(CaseCauseConfirmationModel.cause_id)
        .order_by(func.count(func.distinct(CaseCauseConfirmationModel.case_id)).desc())
        .all()
    )

    cause_distribution: list[CauseDistributionItem] = []
    for c_id, count in cause_counts:
        cause_def = get_cause_by_id(c_id)
        cause_name = cause_def.name if cause_def else c_id.replace("_", " ").title()
        cause_distribution.append(CauseDistributionItem(cause=cause_name, cases=count))

    # 6. Resolution Time Distribution (Actual resolved case duration buckets)
    if not res_times_minutes:
        resolution_time_distribution = []
    else:
        buckets = {
            "0-5 min": 0,
            "5-10 min": 0,
            "10-15 min": 0,
            "15-20 min": 0,
            "20-30 min": 0,
            "30+ min": 0,
        }
        for m in res_times_minutes:
            if m <= 5:
                buckets["0-5 min"] += 1
            elif m <= 10:
                buckets["5-10 min"] += 1
            elif m <= 15:
                buckets["10-15 min"] += 1
            elif m <= 20:
                buckets["15-20 min"] += 1
            elif m <= 30:
                buckets["20-30 min"] += 1
            else:
                buckets["30+ min"] += 1

        resolution_time_distribution = [
            ResolutionDistributionItem(range=r, count=c) for r, c in buckets.items()
        ]

    # 7. Defect Type Breakdown (Actual defects in current period)
    defect_counts_query = (
        session.query(
            CaseModel.defect_name,
            CaseModel.defect_code,
            func.count(CaseModel.case_id),
        )
        .filter(CaseModel.defect_name.isnot(None))
    )
    if cutoff:
        defect_counts_query = defect_counts_query.filter(CaseModel.created_at >= cutoff)

    defect_counts = (
        defect_counts_query
        .group_by(CaseModel.defect_name, CaseModel.defect_code)
        .order_by(func.count(CaseModel.case_id).desc())
        .all()
    )

    defect_types: list[DefectTypeBreakdownItem] = []
    total_dt = sum([count for _, _, count in defect_counts])
    if total_dt > 0:
        for d_name, d_code, count in defect_counts:
            pct = round((count / total_dt) * 100, 1)
            defect_types.append(
                DefectTypeBreakdownItem(
                    name=d_name or "Unknown",
                    code=d_code,
                    count=count,
                    percentage=pct,
                )
            )

    return AnalyticsPerformanceResponse(
        kpis=kpis,
        defect_trend=defect_trend,
        cause_distribution=cause_distribution,
        resolution_time_distribution=resolution_time_distribution,
        defect_types=defect_types,
        period=period,
        last_updated=now.strftime("%Y-%m-%d %H:%M:%S UTC"),
    )


@router.get(
    "/spc",
    response_model=SpcAnalysisResponse,
    summary="Get Statistical Process Control (SPC) process capability metrics and charts",
    description="Returns Cp, Cpk, Pp, Ppk, I-MR control chart data, frequency histogram, and Nelson out-of-control rules.",
)
def get_spc_analytics(
    parameter: str = Query("dot_diameter", enum=["dot_diameter", "dispense_weight", "line_width", "fluid_pressure"]),
    line_id: str = Query("all", enum=["all", "line-a", "line-b", "line-c", "line-d"]),
    sample_size: int = Query(50, ge=20, le=200),
) -> SpcAnalysisResponse:
    """Retrieve statistical process control metrics, capability indices, and control charts."""
    return generate_spc_analysis(parameter=parameter, line_id=line_id, sample_size=sample_size)
