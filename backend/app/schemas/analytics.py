from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class KpiMetrics(BaseModel):
    active_diagnoses: int
    open_defects: int
    resolved_cases: int
    avg_diagnosis_time_minutes: float

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

class CauseDistributionItem(BaseModel):
    cause: str
    cases: int

class DashboardAnalyticsResponse(BaseModel):
    kpis: KpiMetrics
    recent_cases: List[RecentCaseRecord]
    defect_distribution: List[DefectDistributionItem]
    cause_distribution: List[CauseDistributionItem]
