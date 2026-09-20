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
    machine_context?: Record<string, unknown>;
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

export const reportsApi = {
    async listCasesForReports(): Promise<DurableCaseResponse[]> {
        return apiClient.get<DurableCaseResponse[]>("/cases");
    },

    async getCaseReport(caseId: string): Promise<CaseReportResponse> {
        return apiClient.get<CaseReportResponse>(`/cases/${caseId}/report`);
    },

    async generateAiSummary(caseId: string): Promise<CaseAiSummaryResponse> {
        return apiClient.post<CaseAiSummaryResponse>(`/cases/${caseId}/ai-summary`);
    },

    downloadPdf(caseId: string, filename?: string): void {
        const downloadUrl = `${API_BASE_URL}/cases/${caseId}/report.pdf`;
        const link = document.createElement("a");
        link.href = downloadUrl;
        link.target = "_blank";
        link.download = filename || `dispenseiq-case-${caseId}-report.pdf`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    },
};
