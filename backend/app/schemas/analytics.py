from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class KpiMetrics(BaseModel):
    active_diagnoses: int
    open_defects: int
    resolved_cases: int
    avg_diagnosis_time_minutes: float
    active_diagnoses_trend: str = "0%"
    open_defects_trend: str = "0%"
    resolved_cases_trend: str = "0%"
    avg_time_trend: str = "0%"
    ai_accuracy_rate: float = 100.0

class RecentCaseRecord(BaseModel):
    id: str
    case_number: str
    defect: str
    equipment: str
    cause: str
    status: str
    confidence: int
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
    avg_resolution_time_minutes: float
    first_time_resolution_rate: float
    diagnostic_accuracy_rate: float
    total_cases_trend: str = "+18%"
    avg_resolution_trend: str = "-41%"
    first_time_resolution_trend: str = "+5%"
    diagnostic_accuracy_trend: str = "+3%"

class DefectTrendItem(BaseModel):
    month: str
    defects: int

class ResolutionDistributionItem(BaseModel):
    range: str
    count: int

class DefectTypeBreakdownItem(BaseModel):
    name: str
    code: str
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
