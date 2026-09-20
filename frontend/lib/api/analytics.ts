import { apiClient, API_BASE_URL } from "./client";

export interface AnalyticsKpiMetrics {
    total_cases: number;
    resolved_cases: number;
    avg_resolution_time_minutes: number | null;
    first_time_resolution_rate: number | null;
    cause_confirmation_rate: number | null;
    total_cases_trend: string | null;
    avg_resolution_trend: string | null;
    first_time_resolution_trend: string | null;
    cause_confirmation_trend: string | null;
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
    avg_diagnosis_time_minutes: number | null;
    active_diagnoses_trend: string | null;
    open_defects_trend: string | null;
    resolved_cases_trend: string | null;
    avg_time_trend: string | null;
    cause_confirmation_rate: number | null;
}

export interface RecentCaseRecord {
    id: string;
    case_number: string;
    defect: string;
    equipment: string;
    cause: string;
    status: string;
    evidence_support: number | null;
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

export interface AnalyticsEvent {
    event_type?: string;
    case_id?: string;
    defect_type?: string;
    timestamp?: string;
    [key: string]: unknown;
}

export const analyticsApi = {
    async getPerformanceAnalytics(period: string = "30d"): Promise<AnalyticsPerformanceResponse> {
        return apiClient.get<AnalyticsPerformanceResponse>(`/analytics/performance?period=${period}`);
    },

    async getDashboardAnalytics(): Promise<DashboardAnalyticsResponse> {
        return apiClient.get<DashboardAnalyticsResponse>("/analytics/dashboard");
    },

    subscribeToEvents(onEvent: (event: AnalyticsEvent) => void): () => void {
        try {
            const eventSource = new EventSource(`${API_BASE_URL}/analytics/events`);

            eventSource.onmessage = (event) => {
                try {
                    const parsed = JSON.parse(event.data) as AnalyticsEvent;
                    onEvent(parsed);
                } catch {
                    onEvent({ event_type: "UNKNOWN", raw: event.data });
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
