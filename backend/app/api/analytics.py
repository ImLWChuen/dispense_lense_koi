from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone, timedelta
import logging

from app.db.session import get_db
from app.schemas.analytics import DashboardAnalyticsResponse, KpiMetrics, RecentCaseRecord, DefectDistributionItem, CauseDistributionItem
from app.models.case import CaseModel, CaseCauseConfirmationModel, CaseLifecycleEventModel
from app.schemas.diagnosis import IssueCondition

logger = logging.getLogger(__name__)

router = APIRouter()

def time_ago(dt: datetime) -> str:
    now = datetime.now(timezone.utc)
    diff = now - dt
    minutes = int(diff.total_seconds() / 60)
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
def get_dashboard_analytics(session: Session = Depends(get_db)):
    """Retrieve aggregated data for the dashboard."""
    
    # 1. KPIs
    # Active Diagnoses: Not resolved
    active_diagnoses = session.query(CaseModel).filter(CaseModel.issue_condition != IssueCondition.RESOLVED.value).count()
    
    # Open Defects: Same as active diagnoses or where defect_code is present and not resolved
    open_defects = session.query(CaseModel).filter(
        CaseModel.issue_condition != IssueCondition.RESOLVED.value,
        CaseModel.defect_code.isnot(None)
    ).count()
    
    # Resolved Cases this month
    now = datetime.now(timezone.utc)
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    resolved_cases = session.query(CaseModel).filter(
        CaseModel.issue_condition == IssueCondition.RESOLVED.value,
        CaseModel.created_at >= start_of_month
    ).count()
    
    # Avg Diagnosis Time (time to resolution)
    resolved_case_models = session.query(CaseModel).filter(CaseModel.issue_condition == IssueCondition.RESOLVED.value).all()
    total_minutes = 0
    resolved_count = 0
    
    for case in resolved_case_models:
        # Find the earliest RESOLVED lifecycle event
        resolve_event = session.query(CaseLifecycleEventModel).filter(
            CaseLifecycleEventModel.case_id == case.case_id,
            CaseLifecycleEventModel.resulting_issue_condition == IssueCondition.RESOLVED.value
        ).order_by(CaseLifecycleEventModel.created_at.asc()).first()
        
        if resolve_event:
            diff = resolve_event.created_at - case.created_at
            total_minutes += diff.total_seconds() / 60
            resolved_count += 1
            
    avg_time = round(total_minutes / resolved_count, 1) if resolved_count > 0 else 0.0

    kpis = KpiMetrics(
        active_diagnoses=active_diagnoses,
        open_defects=open_defects,
        resolved_cases=resolved_cases,
        avg_diagnosis_time_minutes=avg_time
    )
    
    # 2. Recent Cases
    recent_case_models = session.query(CaseModel).order_by(CaseModel.created_at.desc()).limit(5).all()
    recent_cases = []
    for c in recent_case_models:
        # Map status to UI labels
        status_map = {
            IssueCondition.UNRESOLVED.value: "In Progress",
            IssueCondition.RECOVERY_PENDING_VERIFICATION.value: "Needs Review",
            IssueCondition.RESOLVED.value: "Resolved"
        }
        ui_status = status_map.get(c.issue_condition, "In Progress")
        
        cause_name = "Unknown"
        conf = session.query(CaseCauseConfirmationModel).filter(CaseCauseConfirmationModel.case_id == c.case_id).order_by(CaseCauseConfirmationModel.confirmed_at.desc()).first()
        if conf:
            # We would ideally map cause_id to a human readable name, but we can just use the ID for now
            # or extract from analysis revision.
            cause_name = conf.cause_id.replace("_", " ").title()
            
        recent_cases.append(RecentCaseRecord(
            id=c.case_id,
            case_number=f"DSP-{c.case_id[:8]}", # Using short UUID as case number
            defect=c.defect_name or "Unknown Defect",
            equipment=c.machine_context.get("equipment_id", "Dispensing Line") if c.machine_context else "Dispensing Line",
            cause=cause_name,
            status=ui_status,
            confidence=90, # Hardcoded confidence for now
            time=time_ago(c.created_at)
        ))
        
    # 3. Defect Distribution
    defect_counts = session.query(
        CaseModel.defect_name, 
        func.count(CaseModel.case_id)
    ).filter(CaseModel.defect_name.isnot(None)).group_by(CaseModel.defect_name).all()
    
    total_defects = sum([count for _, count in defect_counts])
    defect_distribution = []
    for d_name, d_count in defect_counts:
        pct = round((d_count / total_defects) * 100, 1) if total_defects > 0 else 0
        defect_distribution.append(DefectDistributionItem(name=d_name, value=pct))
        
    if not defect_distribution:
        # Mock data if none exists
        defect_distribution = [
            DefectDistributionItem(name="Stringing", value=32),
            DefectDistributionItem(name="Under-dispensing", value=24),
            DefectDistributionItem(name="Inconsistent bead", value=18)
        ]
        
    # 4. Cause Distribution
    cause_counts = session.query(
        CaseCauseConfirmationModel.cause_id,
        func.count(CaseCauseConfirmationModel.id)
    ).group_by(CaseCauseConfirmationModel.cause_id).order_by(func.count(CaseCauseConfirmationModel.id).desc()).limit(5).all()
    
    cause_distribution = []
    for c_id, c_count in cause_counts:
        cause_distribution.append(CauseDistributionItem(cause=c_id.replace("_", " ").title(), cases=c_count))
        
    if not cause_distribution:
         cause_distribution = [
            CauseDistributionItem(cause="Material", cases=42),
            CauseDistributionItem(cause="Pressure", cases=31),
            CauseDistributionItem(cause="Nozzle", cases=27)
        ]

    return DashboardAnalyticsResponse(
        kpis=kpis,
        recent_cases=recent_cases,
        defect_distribution=defect_distribution,
        cause_distribution=cause_distribution
    )
