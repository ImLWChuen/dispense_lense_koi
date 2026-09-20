import { apiClient } from "./client";

export interface SpcDataPoint {
    index: number;
    timestamp: string;
    value: number;
    moving_range?: number | null;
    subgroup_id: string;
    line_id: string;
    is_out_of_control: boolean;
    violations: string[];
}

export interface SpcCapabilityMetrics {
    parameter: string;
    parameter_label: string;
    unit: string;
    sample_count: number;
    target: number;
    usl: number;
    lsl: number;
    mean: number;
    mean_offset: number;
    std_dev_overall: number;
    std_dev_within: number;
    ucl: number;
    cl: number;
    lcl: number;
    ucl_mr: number;
    cl_mr: number;
    cp: number;
    cpk: number;
    pp: number;
    ppk: number;
    cpm: number;
    ppm_total: number;
    capability_status: "WORLD_CLASS" | "CAPABLE" | "MARGINAL" | "INCAPABLE";
    status_description: string;
}

export interface SpcHistogramBin {
    bin_start: number;
    bin_end: number;
    bin_center: number;
    count: number;
    frequency: number;
    normal_pdf: number;
}

export interface SpcNormalCurvePoint {
    x: number;
    y: number;
}

export interface SpcLineComparison {
    line_id: string;
    line_name: string;
    technology: string;
    sample_count: number;
    mean: number;
    std_dev: number;
    cp: number;
    cpk: number;
    violations_count: number;
    status: string;
}

export interface SpcAnalysisResponse {
    parameter: string;
    line_id: string;
    sample_size: number;
    metrics: SpcCapabilityMetrics;
    data_points: SpcDataPoint[];
    histogram: SpcHistogramBin[];
    normal_curve: SpcNormalCurvePoint[];
    line_comparisons: SpcLineComparison[];
    rules_violated_summary: Record<string, number>;
    generated_at: string;
}

export const spcApi = {
    async getSpcAnalytics(params?: {
        parameter?: string;
        line_id?: string;
        sample_size?: number;
    }): Promise<SpcAnalysisResponse> {
        const query = new URLSearchParams();
        if (params?.parameter) query.set("parameter", params.parameter);
        if (params?.line_id) query.set("line_id", params.line_id);
        if (params?.sample_size) query.set("sample_size", String(params.sample_size));

        const qs = query.toString();
        const endpoint = `/analytics/spc${qs ? `?${qs}` : ""}`;
        return apiClient.get<SpcAnalysisResponse>(endpoint);
    },
};
