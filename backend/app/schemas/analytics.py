from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class KpiMetrics(BaseModel):
    active_diagnoses: int
    open_defects: int
    resolved_cases: int
    avg_diagnosis_time_minutes: Optional[float] = None
    active_diagnoses_trend: Optional[str] = None
    open_defects_trend: Optional[str] = None
    resolved_cases_trend: Optional[str] = None
    avg_time_trend: Optional[str] = None
    cause_confirmation_rate: Optional[float] = None

class RecentCaseRecord(BaseModel):
    id: str
    case_number: str
    defect: str
    equipment: str
    cause: str
    status: str
    evidence_support: Optional[float] = None
    time: str

class DefectDistributionItem(BaseModel):
    name: str
    value: float
    count: int = 0

class CauseDistributionItem(BaseModel):
    cause: str
    cases: int

class DashboardAnalyticsResponse(BaseModel):
    kpis: KpiMetrics
    recent_cases: List[RecentCaseRecord]
    defect_distribution: List[DefectDistributionItem]
    cause_distribution: List[CauseDistributionItem]
    ai_insight_text: Optional[str] = None
    ai_insight_trend: Optional[str] = None

class AnalyticsKpiMetrics(BaseModel):
    total_cases: int
    resolved_cases: int
    avg_resolution_time_minutes: Optional[float] = None
    first_time_resolution_rate: Optional[float] = None
    cause_confirmation_rate: Optional[float] = None
    total_cases_trend: Optional[str] = None
    avg_resolution_trend: Optional[str] = None
    first_time_resolution_trend: Optional[str] = None
    cause_confirmation_trend: Optional[str] = None

class DefectTrendItem(BaseModel):
    month: str
    defects: int

class ResolutionDistributionItem(BaseModel):
    range: str
    count: int

class DefectTypeBreakdownItem(BaseModel):
    name: str
    code: Optional[str] = None
    count: int
    percentage: float

class AnalyticsPerformanceResponse(BaseModel):
    kpis: AnalyticsKpiMetrics
    defect_trend: List[DefectTrendItem]
    cause_distribution: List[CauseDistributionItem]
    resolution_time_distribution: List[ResolutionDistributionItem]
    defect_types: List[DefectTypeBreakdownItem]
    period: str
    last_updated: str
