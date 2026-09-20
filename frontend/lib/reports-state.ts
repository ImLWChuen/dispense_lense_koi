/**
 * Pure state reducer and helpers for Diagnostic Reports view (DLK-M3-028).
 */

import type { DurableCaseResponse } from "@/types/api";

export interface ReportItem {
    id: string;
    displayId: string;
    caseRef: string;
    title: string;
    date: string;
    type: string;
    status: string;
    isResolved: boolean;
}

export interface ReportsPageState {
    isLoading: boolean;
    error: string | null;
    reports: ReportItem[];
}

export interface ReportsViewDerived {
    showInitialLoading: boolean;
    showDedicatedError: boolean;
    showStaleBanner: boolean;
    showTable: boolean;
    showEmpty: boolean;
}

export function createInitialReportsState(): ReportsPageState {
    return {
        isLoading: true,
        error: null,
        reports: [],
    };
}

export function startReportsLoading(state: ReportsPageState): ReportsPageState {
    return {
        ...state,
        isLoading: true,
        error: null,
    };
}

export function reportsLoadSuccess(
    _state: ReportsPageState,
    reports: ReportItem[]
): ReportsPageState {
    return {
        isLoading: false,
        error: null,
        reports,
    };
}

export function reportsLoadFailure(
    state: ReportsPageState,
    errorMessage: string
): ReportsPageState {
    return {
        isLoading: false,
        error: errorMessage,
        // Retain previously loaded reports on refresh failure; do NOT wipe them
        reports: state.reports,
    };
}

export function deriveReportsView(state: ReportsPageState): ReportsViewDerived {
    const hasReports = state.reports.length > 0;
    const hasError = state.error !== null;

    return {
        showInitialLoading: state.isLoading && !hasReports && !hasError,
        showDedicatedError: !state.isLoading && hasError && !hasReports,
        showStaleBanner: hasError && hasReports,
        showTable: hasReports,
        showEmpty: !state.isLoading && !hasError && !hasReports,
    };
}

export function mapCasesToReports(cases: DurableCaseResponse[]): ReportItem[] {
    if (!cases || cases.length === 0) return [];
    return cases.map((c) => {
        const shortId = c.case_id.substring(0, 8).toUpperCase();
        const isResolved =
            c.issue_condition === "RESOLVED" ||
            c.issue_condition === "IssueCondition.RESOLVED";
        const cleanStatus = isResolved
            ? "Complete"
            : c.issue_condition.replace("IssueCondition.", "").replace(/_/g, " ");

        const dateStr = c.created_at
            ? new Date(c.created_at).toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                  year: "numeric",
              })
            : "Recent";

        return {
            id: c.case_id,
            displayId: `RPT-${shortId}`,
            caseRef: `DSP-${shortId}`,
            title: c.defect_name || c.description || "Dispensing Diagnostic Report",
            date: dateStr,
            type: "Diagnostic Report",
            status: cleanStatus,
            isResolved,
        };
    });
}
