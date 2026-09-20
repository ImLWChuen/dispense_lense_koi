import { apiClient } from "./client";
import {
    CreateCaseRequest,
    DurableCaseResponse,
    CaseAnswerResponse,
    CaseCheckResultResponse,
    CaseCauseConfirmationResponse,
    CaseRecoveryActionResponse,
    CaseRecoveryVerificationResponse,
    CaseRecurrenceResponse,
    SubmitAnswerPayload,
    SubmitCheckResultPayload,
    SubmitCauseConfirmationPayload,
    SubmitRecoveryActionPayload,
    SubmitRecoveryVerificationPayload,
    SubmitRecurrencePayload,
} from "../../types/api";

export const casesApi = {
    async listCases(): Promise<DurableCaseResponse[]> {
        return apiClient.get<DurableCaseResponse[]>("/cases");
    },

    async createCase(data: CreateCaseRequest): Promise<DurableCaseResponse> {
        return apiClient.post<DurableCaseResponse>("/cases", data);
    },

    async getCase(caseId: string): Promise<DurableCaseResponse> {
        return apiClient.get<DurableCaseResponse>(`/cases/${caseId}`);
    },

    async submitAnswer(
        caseId: string,
        payloadOrQuestionId: SubmitAnswerPayload | string,
        answer?: string,
        expectedRevision?: number,
        answerText?: string
    ): Promise<CaseAnswerResponse> {
        const body: SubmitAnswerPayload =
            typeof payloadOrQuestionId === "string"
                ? {
                      question_id: payloadOrQuestionId,
                      answer: answer!,
                      expected_revision: expectedRevision!,
                      answer_text: answerText,
                  }
                : payloadOrQuestionId;
        return apiClient.post<CaseAnswerResponse>(`/cases/${caseId}/answers`, body);
    },

    async submitCheckResult(
        caseId: string,
        payloadOrCheckId: SubmitCheckResultPayload | string,
        executionStatus?: string,
        finding?: string,
        expectedRevision?: number,
        outcome?: string | null,
        findingDetails?: string | null
    ): Promise<CaseCheckResultResponse> {
        const body: SubmitCheckResultPayload =
            typeof payloadOrCheckId === "string"
                ? {
                      check_id: payloadOrCheckId,
                      execution_status: executionStatus!,
                      finding: finding!,
                      expected_revision: expectedRevision!,
                      outcome: outcome !== undefined ? outcome : null,
                      finding_details: findingDetails !== undefined ? findingDetails : null,
                  }
                : payloadOrCheckId;
        return apiClient.post<CaseCheckResultResponse>(
            `/cases/${caseId}/check-results`,
            body
        );
    },

    async verifyCase(
        caseId: string,
        payloadOrPassed: SubmitRecoveryVerificationPayload | boolean | string,
        verificationDetails?: string,
        expectedRevision?: number,
        verifiedBy: string = "technician"
    ): Promise<CaseRecoveryVerificationResponse> {
        let body: SubmitRecoveryVerificationPayload;
        if (typeof payloadOrPassed === "object" && payloadOrPassed !== null) {
            body = {
                verified_by: "technician",
                ...payloadOrPassed,
            };
        } else {
            const passed =
                typeof payloadOrPassed === "boolean"
                    ? payloadOrPassed
                    : payloadOrPassed === "RESOLVED";
            body = {
                verification_passed: passed,
                verification_details: verificationDetails || "",
                expected_revision: expectedRevision!,
                verified_by: verifiedBy,
            };
        }
        return apiClient.post<CaseRecoveryVerificationResponse>(
            `/cases/${caseId}/recovery-verifications`,
            body
        );
    },

    async submitCauseConfirmation(
        caseId: string,
        payloadOrCauseId: SubmitCauseConfirmationPayload | string,
        expectedRevision?: number,
        confirmedBy: string = "technician",
        notes?: string
    ): Promise<CaseCauseConfirmationResponse> {
        const body: SubmitCauseConfirmationPayload =
            typeof payloadOrCauseId === "string"
                ? {
                      cause_id: payloadOrCauseId,
                      expected_revision: expectedRevision!,
                      confirmed_by: confirmedBy,
                      notes,
                  }
                : {
                      confirmed_by: "technician",
                      ...payloadOrCauseId,
                  };
        return apiClient.post<CaseCauseConfirmationResponse>(
            `/cases/${caseId}/cause-confirmations`,
            body
        );
    },

    async submitRecoveryAction(caseId: string, recoveryDetails: string, expectedRevision: number, performedBy: string = "engineer") {
        return apiClient.post(`/cases/${caseId}/recovery-actions`, {
            recovery_details: recoveryDetails,
            expected_revision: expectedRevision,
            performed_by: performedBy,
        });
    },

    async getSimilarCases(caseId: string, limit: number = 5, minScore: number = 0.20): Promise<SimilarCasesResponse> {
        return apiClient.get<SimilarCasesResponse>(`/cases/${caseId}/similar?limit=${limit}&min_score=${minScore}`);
    }
};

export interface SimilarCaseItem {
    case_id: string;
    short_id: string;
    defect_code?: string;
    defect_name?: string;
    description: string;
    material?: string;
    method?: string;
    line_id?: string;
    issue_condition: string;
    is_resolved: boolean;
    similarity_score: number;
    similarity_percentage: number;
    matching_factors: string[];
    confirmed_causes: string[];
    resolution_summary?: string;
    created_at: string;
    resolved_at?: string;
}

export interface SimilarCasesResponse {
    target_case_id: string;
    count: number;
    similar_cases: SimilarCaseItem[];
}
