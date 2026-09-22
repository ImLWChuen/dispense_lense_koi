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
    code: string | null;
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

// Shared singleton SSE connection state
let sharedEventSource: EventSource | null = null;
const sseListeners = new Set<(event: AnalyticsEvent) => void>();
let consecutiveFailures = 0;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

function cleanupSharedEventSource() {
    if (sharedEventSource) {
        sharedEventSource.onmessage = null;
        sharedEventSource.onerror = null;
        sharedEventSource.close();
        sharedEventSource = null;
    }
}

function initSharedEventSource() {
    if (typeof window === "undefined" || sseListeners.size === 0) return;
    if (sharedEventSource && sharedEventSource.readyState !== EventSource.CLOSED) return;

    if (consecutiveFailures >= 3) {
        if (!reconnectTimer) {
            reconnectTimer = setTimeout(() => {
                reconnectTimer = null;
                consecutiveFailures = 0;
                initSharedEventSource();
            }, 30000);
        }
        return;
    }

    try {
        const es = new EventSource(`${API_BASE_URL}/analytics/events`);
        sharedEventSource = es;

        es.onopen = () => {
            consecutiveFailures = 0;
        };

        es.onmessage = (event) => {
            let parsed: AnalyticsEvent;
            try {
                parsed = JSON.parse(event.data) as AnalyticsEvent;
            } catch {
                parsed = { event_type: "UNKNOWN", raw: event.data };
            }
            sseListeners.forEach((listener) => {
                try {
                    listener(parsed);
                } catch {
                    // Ignore listener errors
                }
            });
        };

        es.onerror = () => {
            consecutiveFailures++;
            if (consecutiveFailures === 1) {
                console.warn("[Analytics SSE] Connection unavailable; will retry with backoff.");
            }
            cleanupSharedEventSource();
            if (sseListeners.size > 0 && consecutiveFailures < 3 && !reconnectTimer) {
                const delay = consecutiveFailures * 3000;
                reconnectTimer = setTimeout(() => {
                    reconnectTimer = null;
                    initSharedEventSource();
                }, delay);
            }
        };
    } catch {
        // SSE not supported
    }
}

export const analyticsApi = {
    async getPerformanceAnalytics(period: string = "30d"): Promise<AnalyticsPerformanceResponse> {
        return apiClient.get<AnalyticsPerformanceResponse>(`/analytics/performance?period=${period}`);
    },

    async getDashboardAnalytics(): Promise<DashboardAnalyticsResponse> {
        return apiClient.get<DashboardAnalyticsResponse>("/analytics/dashboard");
    },

    subscribeToEvents(onEvent: (event: AnalyticsEvent) => void): () => void {
        sseListeners.add(onEvent);
        initSharedEventSource();

        return () => {
            sseListeners.delete(onEvent);
            if (sseListeners.size === 0) {
                if (reconnectTimer) {
                    clearTimeout(reconnectTimer);
                    reconnectTimer = null;
                }
                consecutiveFailures = 0;
                cleanupSharedEventSource();
            }
        };
    },
};
