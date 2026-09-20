"""
Dispense Lens - Standardized 8D Quality Report Schemas (AIAG / VDA Compliant)

Defines the data contract for standard Eight Disciplines (8D) Problem Solving,
the manufacturing industry standard for root cause containment, corrective
action, and process verification.
"""

from __future__ import annotations

from typing import Any, List, Optional
from pydantic import BaseModel, Field


class EightDTeamMember(BaseModel):
    """Member of the cross-functional 8D problem-solving team (D1)."""
    role: str = Field(..., description="Role in 8D investigation, e.g., Champion, QA Lead, Process Eng, Operator")
    name: str = Field(..., description="Full name of the team member")
    title: str = Field(..., description="Job title / qualification")
    department: str = Field(..., description="Assigned department or production line")


class SectionD1Team(BaseModel):
    """D1: Use Team Approach - Cross-functional problem solving team."""
    champion: EightDTeamMember
    team_leader: EightDTeamMember
    members: List[EightDTeamMember] = Field(default_factory=list)


class SectionD2ProblemDescription5W2H(BaseModel):
    """D2: Describe the Problem using 5W2H framework."""
    what: str = Field(..., description="What is the defect symptom?")
    where: str = Field(..., description="Where on the substrate / dispensing cell?")
    when: str = Field(..., description="When did the defect first appear?")
    who: str = Field(..., description="Who discovered / reported the defect?")
    why: str = Field(..., description="Why is this considered a defect? (Quality/Yield impact)")
    how: str = Field(..., description="How was the defect observed or measured?")
    how_many: str = Field(..., description="Defect rate, scrap count, or lot volume affected")

    defect_code: str = Field(..., description="Standard defect taxonomy code (e.g., D01)")
    defect_name: str = Field(..., description="Human-readable defect title")
    machine_id: str = Field(..., description="Equipment or line identifier")
    fluid_material: str = Field(..., description="Adhesive / dispensing fluid specification")
    dispense_method: str = Field(..., description="Dispense technology (jetting, time_pressure, auger)")
    operational_context: dict[str, Any] = Field(default_factory=dict)


class ContainmentActionItem(BaseModel):
    """Specific interim containment action (ICA) taken."""
    action_id: str
    description: str
    owner: str
    target_date: str
    status: str = Field("COMPLETED", description="COMPLETED, IN_PROGRESS, or PENDING")
    effectivity_percentage: float = Field(100.0, description="Measured containment effectivity %")


class SectionD3ContainmentICA(BaseModel):
    """D3: Develop Interim Containment Actions (ICA)."""
    containment_status: str = Field(..., description="Status: CONTAINED, PARTIAL, PENDING")
    quarantine_lot_ids: List[str] = Field(default_factory=list)
    actions: List[ContainmentActionItem] = Field(default_factory=list)
    overall_effectivity: float = Field(100.0, description="Measured containment efficiency %")
    containment_date: str = Field(...)
    verified_by: str = Field(...)


class FiveWhysStep(BaseModel):
    """A single step in the 5-Whys root cause analysis."""
    step: int = Field(..., ge=1, le=5)
    question: str = Field(...)
    answer: str = Field(...)
    category: str = Field("Machine", description="Ishikawa 6M: Machine, Method, Material, Measurement, Man, Milieu")


class SectionD4RootCauseRCA(BaseModel):
    """D4: Determine Root Cause and Escape Point."""
    ishikawa_category: str = Field(..., description="Primary 6M cause category")
    root_cause_id: str = Field(...)
    root_cause_name: str = Field(...)
    mechanism_description: str = Field(...)
    five_whys: List[FiveWhysStep] = Field(default_factory=list)
    escape_point: str = Field(..., description="Why did the defect escape in-line detection?")
    confidence_score: float = Field(..., description="Diagnostic engine confidence (0.0 - 1.0)")
    evidence_summary: List[str] = Field(default_factory=list)


class CorrectiveActionItem(BaseModel):
    """Specific permanent corrective action (PCA) proposed/selected."""
    action_id: str
    title: str
    description: str
    risk_assessment: str
    feasibility: str
    selected: bool = True


class SectionD5CorrectiveActionsPCA(BaseModel):
    """D5: Choose and Verify Permanent Corrective Actions (PCAs)."""
    selected_actions: List[CorrectiveActionItem] = Field(default_factory=list)
    selection_rationale: str = Field(...)
    fmea_initial_rpn: int = Field(240, description="Failure Mode Effects Analysis initial RPN")


class SectionD6ValidationPCA(BaseModel):
    """D6: Implement and Validate Permanent Corrective Actions (PCAs)."""
    implementation_status: str = Field(..., description="VERIFIED_PASS, PENDING_VERIFICATION, FAILED")
    verification_method: str = Field(...)
    test_shots_count: int = Field(30, description="Cleanroom verification test shots performed")
    test_shots_passed: int = Field(30, description="Cleanroom test shots meeting specs")
    cpk_validation: float = Field(..., description="Post-PCA process capability Cpk")
    target_cpk: float = Field(1.67, description="Target cleanroom Cpk threshold")
    verification_actor: str = Field(...)
    verified_at: str = Field(...)
    verification_notes: Optional[str] = None


class SectionD7PreventRecurrence(BaseModel):
    """D7: Prevent Recurrence & Systemic Improvements."""
    sop_references: List[str] = Field(default_factory=list, description="Updated standard operating procedures")
    control_plan_updates: List[str] = Field(default_factory=list, description="Control plan revisions")
    pfmea_revised_rpn: int = Field(48, description="Revised post-action RPN")
    preventive_maintenance_action: str = Field(...)
    systemic_recommendations: List[str] = Field(default_factory=list)


class SectionD8ClosureSignoff(BaseModel):
    """D8: Congratulate Team & Formal Management Sign-Off."""
    resolution_status: str = Field(..., description="RESOLVED or IN_PROGRESS")
    closure_date: Optional[str] = None
    quality_manager_signoff: str = Field(...)
    engineering_lead_signoff: str = Field(...)
    lessons_learned: str = Field(...)
    compliance_standard: str = Field("AIAG / VDA 8D Quality Standard (ISO/TS 16949 Compliant)")


class EightDReportResponse(BaseModel):
    """Standardized 8D Quality Report complete response."""
    case_id: str
    report_number: str = Field(..., description="8D-RPT-XXXXXXXX formatted identifier")
    case_ref: str = Field(..., description="DSP-XXXXXXXX formatted reference")
    revision: int
    created_at: str
    closed_at: Optional[str] = None
    issue_condition: str
    is_resolved: bool

    # 8 Disciplines
    d1_team: SectionD1Team
    d2_problem_description: SectionD2ProblemDescription5W2H
    d3_containment: SectionD3ContainmentICA
    d4_root_cause: SectionD4RootCauseRCA
    d5_corrective_actions: SectionD5CorrectiveActionsPCA
    d6_validation: SectionD6ValidationPCA
    d7_prevent_recurrence: SectionD7PreventRecurrence
    d8_closure: SectionD8ClosureSignoff
