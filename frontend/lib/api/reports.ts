import { apiClient, API_BASE_URL } from "./client";
import { DurableCaseResponse, DiagnosisResult, QuestionAnswerRecord, CheckResultRecord } from "../../types/api";

export interface CaseOutcomeSummary {
    issue_condition: string;
    current_revision: number;
    confirmed_causes: string[];
    is_resolved: boolean;
}

export interface CauseConfirmationRecord {
    cause_id: string;
    confirmed_by: string;
    notes?: string;
    confirmed_at: string;
    resulting_revision_number: number;
}

export interface LifecycleEventRecord {
    id?: number;
    case_id: string;
    event_type: string;
    prior_issue_condition: string;
    resulting_issue_condition: string;
    resulting_revision_number: number;
    actor: string;
    details: string;
    verification_passed?: boolean;
    created_at: string;
}

export interface CaseReportResponse {
    case_id: string;
    current_revision: number;
    defect_code?: string;
    defect_name?: string;
    description: string;
    material?: string;
    method?: string;
    machine_context?: Record<string, any>;
    issue_condition: string;
    created_at: string;
    current_diagnosis: DiagnosisResult;
    question_answers: QuestionAnswerRecord[];
    check_results: CheckResultRecord[];
    cause_confirmations: CauseConfirmationRecord[];
    lifecycle_events: LifecycleEventRecord[];
    outcome_summary: CaseOutcomeSummary;
}

export interface CaseAiSummaryResponse {
    case_id: string;
    summary: string;
    source: "llm" | "deterministic";
    revision: number;
}

// ---------------------------------------------------------------------------
// 8D Quality Report (AIAG / VDA Standard) Types
// ---------------------------------------------------------------------------

export interface EightDTeamMember {
    role: string;
    name: string;
    title: string;
    department: string;
}

export interface SectionD1Team {
    champion: EightDTeamMember;
    team_leader: EightDTeamMember;
    members: EightDTeamMember[];
}

export interface SectionD2ProblemDescription5W2H {
    what: string;
    where: string;
    when: string;
    who: string;
    why: string;
    how: string;
    how_many: string;
    defect_code: string;
    defect_name: string;
    machine_id: string;
    fluid_material: string;
    dispense_method: string;
    operational_context?: Record<string, any>;
}

export interface ContainmentActionItem {
    action_id: string;
    description: string;
    owner: string;
    target_date: string;
    status: string;
    effectivity_percentage: number;
}

export interface SectionD3ContainmentICA {
    containment_status: string;
    quarantine_lot_ids: string[];
    actions: ContainmentActionItem[];
    overall_effectivity: number;
    containment_date: string;
    verified_by: string;
}

export interface FiveWhysStep {
    step: number;
    question: string;
    answer: string;
    category: string;
}

export interface SectionD4RootCauseRCA {
    ishikawa_category: string;
    root_cause_id: string;
    root_cause_name: string;
    mechanism_description: string;
    five_whys: FiveWhysStep[];
    escape_point: string;
    confidence_score: number;
    evidence_summary: string[];
}

export interface CorrectiveActionItem {
    action_id: string;
    title: string;
    description: string;
    risk_assessment: string;
    feasibility: string;
    selected: boolean;
}

export interface SectionD5CorrectiveActionsPCA {
    selected_actions: CorrectiveActionItem[];
    selection_rationale: string;
    fmea_initial_rpn: number;
}

export interface SectionD6ValidationPCA {
    implementation_status: string;
    verification_method: string;
    test_shots_count: number;
    test_shots_passed: number;
    cpk_validation: number;
    target_cpk: number;
    verification_actor: string;
    verified_at: string;
    verification_notes?: string;
}

export interface SectionD7PreventRecurrence {
    sop_references: string[];
    control_plan_updates: string[];
    pfmea_revised_rpn: number;
    preventive_maintenance_action: string;
    systemic_recommendations: string[];
}

export interface SectionD8ClosureSignoff {
    resolution_status: string;
    closure_date?: string;
    quality_manager_signoff: string;
    engineering_lead_signoff: string;
    lessons_learned: string;
    compliance_standard: string;
}

export interface EightDReportResponse {
    case_id: string;
    report_number: string;
    case_ref: string;
    revision: number;
    created_at: string;
    closed_at?: string;
    issue_condition: string;
    is_resolved: boolean;
    d1_team: SectionD1Team;
    d2_problem_description: SectionD2ProblemDescription5W2H;
    d3_containment: SectionD3ContainmentICA;
    d4_root_cause: SectionD4RootCauseRCA;
    d5_corrective_actions: SectionD5CorrectiveActionsPCA;
    d6_validation: SectionD6ValidationPCA;
    d7_prevent_recurrence: SectionD7PreventRecurrence;
    d8_closure: SectionD8ClosureSignoff;
}

export const reportsApi = {
    async listCasesForReports(): Promise<DurableCaseResponse[]> {
        return apiClient.get<DurableCaseResponse[]>("/cases");
    },

    async getCaseReport(caseId: string): Promise<CaseReportResponse> {
        return apiClient.get<CaseReportResponse>(`/cases/${caseId}/report`);
    },

    async get8DReport(caseId: string): Promise<EightDReportResponse> {
        return apiClient.get<EightDReportResponse>(`/cases/${caseId}/8d`);
    },

    async generateAiSummary(caseId: string): Promise<CaseAiSummaryResponse> {
        return apiClient.post<CaseAiSummaryResponse>(`/cases/${caseId}/ai-summary`);
    },

    downloadPdf(caseId: string, filename?: string): void {
        const downloadUrl = `${API_BASE_URL}/cases/${caseId}/report.pdf`;
        const link = document.createElement("a");
        link.href = downloadUrl;
        link.target = "_blank";
        link.download = filename || `dispenselens-case-${caseId}-report.pdf`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    },

    download8DPdf(caseId: string, filename?: string): void {
        const downloadUrl = `${API_BASE_URL}/cases/${caseId}/8d.pdf`;
        const link = document.createElement("a");
        link.href = downloadUrl;
        link.target = "_blank";
        link.download = filename || `dispenselens-8d-${caseId}.pdf`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    },
};
