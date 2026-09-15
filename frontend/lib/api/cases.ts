import { apiClient } from "./client";
import { CreateCaseRequest, DurableCaseResponse, DiagnosisResult } from "../../types/api";

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

    async submitAnswer(caseId: string, questionId: string, answer: string, expectedRevision: number, answerText?: string) {
        return apiClient.post(`/cases/${caseId}/answers`, {
            question_id: questionId,
            answer,
            expected_revision: expectedRevision,
            answer_text: answerText,
        });
    },

    async submitCheckResult(
        caseId: string,
        checkId: string,
        status: string,
        finding: string,
        expectedRevision: number,
        findingText?: string,
        findingDetails?: string
    ): Promise<DiagnosisResult> {
        return apiClient.post<DiagnosisResult>(`/cases/${caseId}/check-results`, {
            check_id: checkId,
            execution_status: status,
            finding,
            expected_revision: expectedRevision,
            finding_text: findingText,
            finding_details: findingDetails
        });
    },

    async verifyCase(
        caseId: string,
        status: string,
        notes: string,
        expectedRevision: number
    ): Promise<DiagnosisResult> {
        const passed = status === 'RESOLVED';
        return apiClient.post<DiagnosisResult>(`/cases/${caseId}/recovery-verifications`, {
            verification_passed: passed,
            verification_details: notes,
            expected_revision: expectedRevision
        });
    },

    async submitCauseConfirmation(caseId: string, causeId: string, expectedRevision: number, confirmedBy: string = "engineer", notes?: string) {
        return apiClient.post(`/cases/${caseId}/cause-confirmations`, {
            cause_id: causeId,
            expected_revision: expectedRevision,
            confirmed_by: confirmedBy,
            notes,
        });
    },

    async submitRecoveryAction(caseId: string, recoveryDetails: string, expectedRevision: number, performedBy: string = "engineer") {
        return apiClient.post(`/cases/${caseId}/recovery-actions`, {
            recovery_details: recoveryDetails,
            expected_revision: expectedRevision,
            performed_by: performedBy,
        });
    }
};
