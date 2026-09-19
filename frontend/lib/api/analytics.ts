import { apiClient, API_BASE_URL } from "./client";

export interface AnalyticsKpiMetrics {
    total_cases: number;
    resolved_cases: number;
    avg_resolution_time_minutes: number;
    first_time_resolution_rate: number;
    diagnostic_accuracy_rate: number;
    total_cases_trend: string;
    avg_resolution_trend: string;
    first_time_resolution_trend: string;
    diagnostic_accuracy_trend: string;
}

export interface DefectTrendItem {
    month: string;
    defects: number;
}

export interface CauseDistributionItem {
    cause: string;
    cases: number;
}

export interface ResolutionDistributionItem {
    range: string;
    count: number;
}

export interface DefectTypeBreakdownItem {
    name: string;
    code: string;
    count: number;
    percentage: number;
}

export interface AnalyticsPerformanceResponse {
    kpis: AnalyticsKpiMetrics;
    defect_trend: DefectTrendItem[];
    cause_distribution: CauseDistributionItem[];
    resolution_time_distribution: ResolutionDistributionItem[];
    defect_types: DefectTypeBreakdownItem[];
    period: string;
    last_updated: string;
}

export interface DashboardKpiMetrics {
    active_diagnoses: number;
    open_defects: number;
    resolved_cases: number;
    avg_diagnosis_time_minutes: number;
    active_diagnoses_trend: string;
    open_defects_trend: string;
    resolved_cases_trend: string;
    avg_time_trend: string;
    ai_accuracy_rate: number;
}

export interface RecentCaseRecord {
    id: string;
    case_number: string;
    defect: string;
    equipment: string;
    cause: string;
    status: string;
    confidence: number;
    time: string;
}

export interface DashboardDefectItem {
    name: string;
    value: number;
    count?: number;
}

export interface DashboardAnalyticsResponse {
    kpis: DashboardKpiMetrics;
    recent_cases: RecentCaseRecord[];
    defect_distribution: DashboardDefectItem[];
    cause_distribution: CauseDistributionItem[];
    ai_insight_text?: string | null;
    ai_insight_trend?: string | null;
}

export const analyticsApi = {
    async getPerformanceAnalytics(period: string = "30d"): Promise<AnalyticsPerformanceResponse> {
        return apiClient.get<AnalyticsPerformanceResponse>(`/analytics/performance?period=${period}`);
    },

    async getDashboardAnalytics(): Promise<DashboardAnalyticsResponse> {
        return apiClient.get<DashboardAnalyticsResponse>("/analytics/dashboard");
    },

    subscribeToEvents(onEvent: (event: any) => void): () => void {
        try {
            const eventSource = new EventSource(`${API_BASE_URL}/analytics/events`);

            eventSource.onmessage = (event) => {
                try {
                    const parsed = JSON.parse(event.data);
                    onEvent(parsed);
                } catch {
                    onEvent(event.data);
                }
            };

            eventSource.onerror = (err) => {
                console.warn("Analytics SSE connection warning / reconnecting...", err);
            };

            return () => {
                eventSource.close();
            };
        } catch (e) {
            console.warn("SSE not supported in this environment, falling back to polling.", e);
            return () => {};
        }
    },
};
