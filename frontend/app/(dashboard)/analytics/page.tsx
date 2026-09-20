"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import {
    BarChart3,
    Clock3,
    CheckCircle2,
    TrendingUp,
    RefreshCw,
    ShieldCheck,
    Layers,
    Loader2,
    Activity,
    Download,
} from "lucide-react";

import PageContainer from "@/components/layout/PageContainer";
import KpiCard from "@/components/dashboard/KpiCard";
import DefectChart from "@/components/analytics/DefectChart";
import CauseChart from "@/components/analytics/CauseChart";
import ResolutionChart from "@/components/analytics/ResolutionChart";
import SpcMetricCards from "@/components/spc/SpcMetricCards";
import SpcControlChart from "@/components/spc/SpcControlChart";
import SpcCapabilityHistogram from "@/components/spc/SpcCapabilityHistogram";
import SpcLineMatrix from "@/components/spc/SpcLineMatrix";
import { analyticsApi, AnalyticsPerformanceResponse } from "@/lib/api/analytics";
import { spcApi, SpcAnalysisResponse } from "@/lib/api/spc";

const periods = [
    { label: "7 Days", value: "7d" },
    { label: "30 Days", value: "30d" },
    { label: "90 Days", value: "90d" },
    { label: "Year", value: "year" },
    { label: "All Time", value: "all" },
];

const spcParameters = [
    { key: "dot_diameter", label: "Dot Diameter", spec: "850 ± 100 µm" },
    { key: "dispense_weight", label: "Deposit Weight", spec: "12.5 ± 1.5 mg" },
    { key: "line_width", label: "Bead Width", spec: "320 ± 40 µm" },
    { key: "fluid_pressure", label: "Fluid Pressure", spec: "240 ± 20 kPa" },
];

const spcLines = [
    { key: "all", label: "All Lines Combined" },
    { key: "line-a", label: "Line A (Jetting)" },
    { key: "line-b", label: "Line B (Auger)" },
    { key: "line-c", label: "Line C (Pneumatic)" },
    { key: "line-d", label: "Line D (Piston)" },
];

export default function AnalyticsPage() {
    // Mode: Diagnostic Analytics vs SPC Capability
    const [viewMode, setViewMode] = useState<"performance" | "spc">("performance");

    // Performance Analytics state
    const [selectedPeriod, setSelectedPeriod] = useState("30d");
    const [analytics, setAnalytics] = useState<AnalyticsPerformanceResponse | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isSyncing, setIsSyncing] = useState(false);
    const [lastSyncTime, setLastSyncTime] = useState<string>("Just now");

    const periodRef = useRef(selectedPeriod);
    useEffect(() => {
        periodRef.current = selectedPeriod;
    }, [selectedPeriod]);

    // SPC State
    const [spcParam, setSpcParam] = useState("dot_diameter");
    const [spcLine, setSpcLine] = useState("all");
    const [spcSampleSize, setSpcSampleSize] = useState(50);
    const [spcData, setSpcData] = useState<SpcAnalysisResponse | null>(null);
    const [isSpcLoading, setIsSpcLoading] = useState(false);

    // Fetch Performance Analytics
    const fetchAnalytics = useCallback(async (period: string, showLoading: boolean = true) => {
        try {
            if (showLoading) setIsLoading(true);
            const data = await analyticsApi.getPerformanceAnalytics(period);
            setAnalytics(data);
            setLastSyncTime(new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }));
        } catch (err) {
            console.error("Failed to fetch performance analytics:", err);
        } finally {
            if (showLoading) setIsLoading(false);
        }
    }, []);

    // Fetch SPC Data
    const fetchSpcData = useCallback(async () => {
        try {
            setIsSpcLoading(true);
            const data = await spcApi.getSpcAnalytics({
                parameter: spcParam,
                line_id: spcLine,
                sample_size: spcSampleSize,
            });
            setSpcData(data);
        } catch (err) {
            console.error("Failed to fetch SPC analytics:", err);
        } finally {
            setIsSpcLoading(false);
        }
    }, [spcParam, spcLine, spcSampleSize]);

    useEffect(() => {
        fetchAnalytics(selectedPeriod, true);
    }, [selectedPeriod, fetchAnalytics]);

    useEffect(() => {
        if (viewMode === "spc") {
            fetchSpcData();
        }
    }, [viewMode, fetchSpcData]);

    // Global real-time SSE listener + 15s heartbeat fallback sync
    useEffect(() => {
        const unsubscribe = analyticsApi.subscribeToEvents((event) => {
            console.log("Global real-time sync event received:", event);
            setIsSyncing(true);
            fetchAnalytics(periodRef.current, false);
            setTimeout(() => setIsSyncing(false), 1500);
        });

        const pollInterval = setInterval(() => {
            fetchAnalytics(periodRef.current, false);
        }, 15000);

        return () => {
            unsubscribe();
            clearInterval(pollInterval);
        };
    }, []);

    const handleManualRefresh = () => {
        setIsSyncing(true);
        if (viewMode === "spc") {
            fetchSpcData().finally(() => {
                setTimeout(() => setIsSyncing(false), 800);
            });
        } else {
            fetchAnalytics(selectedPeriod, false).finally(() => {
                setTimeout(() => setIsSyncing(false), 800);
            });
        }
    };

    const handleExportSpcCsv = () => {
        if (!spcData) return;
        const headers = ["Index", "Timestamp", "Value", "Unit", "MovingRange", "Subgroup", "Line", "OutOfControl", "Violations"];
        const rows = spcData.data_points.map((pt) => [
            pt.index,
            `"${pt.timestamp}"`,
            pt.value,
            `"${spcData.metrics.unit}"`,
            pt.moving_range ?? "",
            `"${pt.subgroup_id}"`,
            `"${pt.line_id}"`,
            pt.is_out_of_control ? "YES" : "NO",
            `"${pt.violations.join("; ")}"`,
        ]);
        const csvContent = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
        const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `dispenselens-spc-${spcParam}-${spcLine}-${new Date().toISOString().slice(0, 10)}.csv`;
        link.click();
        URL.revokeObjectURL(url);
    };

    const kpis = analytics?.kpis;

    return (
        <PageContainer>
            {/* Header with View Mode Switcher and Global Sync Indicator */}
            <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 pb-6 border-b border-gray-200">
                <div>
                    <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold uppercase tracking-wider text-[#6d5dfc]">
                            Cleanroom Quality & Yield Intelligence
                        </span>
                    </div>

                    <h1 className="mt-1 text-3xl font-bold tracking-tight text-gray-900">
                        {viewMode === "performance" ? "Diagnostic Performance Analytics" : "Statistical Process Control (SPC) Capability"}
                    </h1>

                    <p className="mt-1 text-sm text-gray-500">
                        {viewMode === "performance"
                            ? "Track defect trends, resolution cycle times, and root cause distributions across all cases in real time."
                            : "Monitor process capability indices (Cp, Cpk, Pp, Ppk), I-MR control charts, and Nelson out-of-control rules."}
                    </p>
                </div>

                <div className="flex flex-wrap items-center gap-3">
                    {/* View Switcher Tabs */}
                    <div className="flex items-center gap-1 bg-gray-100 p-1.5 rounded-2xl border border-gray-200">
                        <button
                            onClick={() => setViewMode("performance")}
                            className={`flex items-center gap-1.5 rounded-xl px-3.5 py-1.5 text-xs font-semibold transition ${
                                viewMode === "performance"
                                    ? "bg-white text-gray-900 shadow-sm"
                                    : "text-gray-600 hover:text-gray-900"
                            }`}
                        >
                            <BarChart3 size={14} className={viewMode === "performance" ? "text-[#6d5dfc]" : ""} />
                            Diagnostic Analytics
                        </button>
                        <button
                            onClick={() => setViewMode("spc")}
                            className={`flex items-center gap-1.5 rounded-xl px-3.5 py-1.5 text-xs font-semibold transition ${
                                viewMode === "spc"
                                    ? "bg-white text-gray-900 shadow-sm"
                                    : "text-gray-600 hover:text-gray-900"
                            }`}
                        >
                            <Activity size={14} className={viewMode === "spc" ? "text-[#6d5dfc]" : ""} />
                            SPC Process Capability
                        </button>
                    </div>

                    {/* Sync Badge */}
                    <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50/80 px-3 py-2 text-xs font-semibold text-emerald-800 shadow-sm">
                        <span className="relative flex h-2 w-2">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                        </span>
                        <span className="hidden sm:inline">Global Sync</span>
                        <span className="text-emerald-600 font-mono text-[11px]">({lastSyncTime})</span>
                    </div>

                    {/* Manual Refresh Button */}
                    <button
                        onClick={handleManualRefresh}
                        disabled={isSyncing}
                        className="inline-flex items-center gap-1.5 rounded-xl border border-gray-200 bg-white px-3 py-2 text-xs font-medium text-gray-700 shadow-sm transition hover:bg-gray-50 disabled:opacity-50"
                        title="Refresh data"
                    >
                        <RefreshCw size={13} className={isSyncing ? "animate-spin text-[#6d5dfc]" : "text-gray-500"} />
                        Refresh
                    </button>
                </div>
            </div>

            {/* ========================================================= */}
            {/* VIEW MODE 1: DIAGNOSTIC PERFORMANCE ANALYTICS */}
            {/* ========================================================= */}
            {viewMode === "performance" && (
                <div className="space-y-6 mt-6">
                    {/* Interactive Date Filter Bar */}
                    <div className="flex flex-wrap items-center justify-between gap-4">
                        <div className="flex items-center gap-1.5 bg-white p-1 rounded-xl border border-gray-200 shadow-sm">
                            {periods.map((p) => (
                                <button
                                    key={p.value}
                                    onClick={() => setSelectedPeriod(p.value)}
                                    className={`rounded-lg px-3.5 py-1.5 text-xs font-medium transition ${
                                        selectedPeriod === p.value
                                            ? "bg-[#6d5dfc] text-white shadow-sm font-semibold"
                                            : "text-gray-600 hover:text-gray-900 hover:bg-gray-50"
                                    }`}
                                >
                                    {p.label}
                                </button>
                            ))}
                        </div>

                        {isSyncing && (
                            <div className="flex items-center gap-1.5 text-xs text-[#6d5dfc] font-medium animate-pulse">
                                <Loader2 size={13} className="animate-spin" />
                                Syncing global updates...
                            </div>
                        )}
                    </div>

                    {/* KPIs Grid */}
                    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
                        <KpiCard
                            title="Total Cases"
                            value={isLoading ? "..." : String(kpis?.total_cases ?? 0)}
                            description={`${kpis?.resolved_cases ?? 0} resolved in this period`}
                            trend={kpis?.total_cases_trend || "0%"}
                            icon={<BarChart3 size={20} />}
                        />

                        <KpiCard
                            title="Avg. Resolution Time"
                            value={isLoading ? "..." : `${kpis?.avg_resolution_time_minutes ?? 0} min`}
                            description="from issue detection to closure"
                            trend={kpis?.avg_resolution_trend || "0%"}
                            icon={<Clock3 size={20} />}
                        />

                        <KpiCard
                            title="First-Time Resolution"
                            value={isLoading ? "..." : `${kpis?.first_time_resolution_rate ?? 0}%`}
                            description="resolved without re-diagnosis"
                            trend={kpis?.first_time_resolution_trend || "0%"}
                            icon={<CheckCircle2 size={20} />}
                        />

                        <KpiCard
                            title="Diagnostic Accuracy"
                            value={isLoading ? "..." : `${kpis?.diagnostic_accuracy_rate ?? 0}%`}
                            description="confirmed vs engine hypothesis"
                            trend={kpis?.diagnostic_accuracy_trend || "0%"}
                            icon={<TrendingUp size={20} />}
                        />
                    </div>

                    {/* Charts Grid */}
                    <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
                        <DefectChart data={analytics?.defect_trend} />
                        <CauseChart data={analytics?.cause_distribution} />
                    </div>

                    {/* Resolution Distribution & Defect Breakdown */}
                    <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
                        <div className="xl:col-span-2">
                            <ResolutionChart data={analytics?.resolution_time_distribution} />
                        </div>

                        {/* Defect Categories Breakdown Card */}
                        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm flex flex-col justify-between">
                            <div>
                                <div className="flex items-center justify-between mb-2">
                                    <h2 className="text-base font-semibold text-gray-900">
                                        Defect Type Breakdown
                                    </h2>
                                    <Layers size={18} className="text-gray-400" />
                                </div>
                                <p className="text-xs text-gray-500 mb-5">
                                    Observed defect categories and percentage share
                                </p>

                                <div className="space-y-4">
                                    {analytics?.defect_types && analytics.defect_types.length > 0 ? (
                                        analytics.defect_types.map((dt) => (
                                            <div key={dt.code} className="space-y-1.5">
                                                <div className="flex items-center justify-between text-xs font-medium">
                                                    <span className="text-gray-800 font-semibold">{dt.name}</span>
                                                    <span className="text-gray-500 font-mono">{dt.percentage}% ({dt.count})</span>
                                                </div>
                                                <div className="h-2 w-full rounded-full bg-gray-100 overflow-hidden">
                                                    <div
                                                        className="h-full rounded-full bg-[#6d5dfc] transition-all duration-500"
                                                        style={{ width: `${Math.min(100, dt.percentage)}%` }}
                                                    />
                                                </div>
                                            </div>
                                        ))
                                    ) : (
                                        <div className="py-8 text-center text-xs text-gray-400">
                                            No defect categories recorded in this period.
                                        </div>
                                    )}
                                </div>
                            </div>

                            <div className="mt-6 pt-4 border-t border-gray-100 flex items-center justify-between text-xs text-gray-500">
                                <div className="flex items-center gap-1.5 text-emerald-700 font-medium">
                                    <ShieldCheck size={14} />
                                    Continuous Monitoring
                                </div>
                                <span>Synced across all cleanroom accounts</span>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* ========================================================= */}
            {/* VIEW MODE 2: SPC PROCESS CAPABILITY (CP / CPK) */}
            {/* ========================================================= */}
            {viewMode === "spc" && (
                <div className="space-y-6 mt-6">
                    {/* SPC Controls Bar */}
                    <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 bg-white p-4 rounded-2xl border border-gray-200 shadow-sm">
                        {/* Parameter Selector */}
                        <div className="flex flex-wrap items-center gap-2">
                            <span className="text-xs font-bold text-gray-400 uppercase tracking-wider mr-1">
                                Parameter:
                            </span>
                            {spcParameters.map((param) => {
                                const isSelected = spcParam === param.key;
                                return (
                                    <button
                                        key={param.key}
                                        onClick={() => setSpcParam(param.key)}
                                        className={`rounded-xl px-3 py-1.5 text-xs transition flex items-center gap-2 ${
                                            isSelected
                                                ? "bg-[#6d5dfc] text-white font-semibold shadow-sm"
                                                : "bg-gray-50 text-gray-700 hover:bg-gray-100 border border-gray-200"
                                        }`}
                                    >
                                        <span>{param.label}</span>
                                        <span className={`text-[10px] font-mono opacity-80 ${isSelected ? "text-white" : "text-gray-500"}`}>
                                            ({param.spec})
                                        </span>
                                    </button>
                                );
                            })}
                        </div>

                        {/* Line & Sample Controls & Export */}
                        <div className="flex flex-wrap items-center gap-3">
                            {/* Line Filter */}
                            <div className="flex items-center gap-1.5">
                                <span className="text-xs text-gray-500 font-medium">Line:</span>
                                <select
                                    value={spcLine}
                                    onChange={(e) => setSpcLine(e.target.value)}
                                    className="rounded-xl border border-gray-200 bg-gray-50 px-2.5 py-1.5 text-xs font-semibold text-gray-800 focus:outline-none focus:ring-2 focus:ring-[#6d5dfc]"
                                >
                                    {spcLines.map((l) => (
                                        <option key={l.key} value={l.key}>
                                            {l.label}
                                        </option>
                                    ))}
                                </select>
                            </div>

                            {/* Sample Size Toggle */}
                            <div className="flex items-center gap-1 bg-gray-100 p-1 rounded-xl">
                                {[30, 50, 100].map((size) => (
                                    <button
                                        key={size}
                                        onClick={() => setSpcSampleSize(size)}
                                        className={`rounded-lg px-2.5 py-1 text-xs font-medium transition ${
                                            spcSampleSize === size
                                                ? "bg-white text-gray-900 shadow-sm font-semibold"
                                                : "text-gray-500 hover:text-gray-900"
                                        }`}
                                    >
                                        {size} Shots
                                    </button>
                                ))}
                            </div>

                            {/* Export CSV */}
                            <button
                                onClick={handleExportSpcCsv}
                                disabled={!spcData}
                                className="inline-flex items-center gap-1.5 rounded-xl border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 shadow-sm hover:bg-gray-50 transition"
                            >
                                <Download size={13} />
                                Export CSV
                            </button>
                        </div>
                    </div>

                    {/* SPC Metric Cards */}
                    <SpcMetricCards metrics={spcData?.metrics} isLoading={isSpcLoading} />

                    {/* Charts Grid: Control Chart & Capability Histogram */}
                    {spcData && (
                        <>
                            <SpcControlChart
                                dataPoints={spcData.data_points}
                                metrics={spcData.metrics}
                            />

                            <div className="grid grid-cols-1 gap-6">
                                <SpcCapabilityHistogram
                                    histogram={spcData.histogram}
                                    normalCurve={spcData.normal_curve}
                                    metrics={spcData.metrics}
                                />
                            </div>

                            {/* Multi-Line Capability Comparison */}
                            <SpcLineMatrix
                                comparisons={spcData.line_comparisons}
                                unit={spcData.metrics.unit}
                                selectedLineId={spcLine}
                                onSelectLine={(lineId) => setSpcLine(lineId)}
                            />
                        </>
                    )}
                </div>
            )}
        </PageContainer>
    );
}
