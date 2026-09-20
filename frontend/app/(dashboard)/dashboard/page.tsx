"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
    AlertTriangle,
    CheckCircle2,
    Clock3,
    Stethoscope,
    RefreshCw,
    AlertCircle,
    Loader2,
} from "lucide-react";

import Link from "next/link";
import PageContainer from "@/components/layout/PageContainer";
import KpiCard from "@/components/dashboard/KpiCard";
import LineStatusRibbon from "@/components/dashboard/LineStatusRibbon";
import RecentCases from "@/components/dashboard/RecentCases";
import DefectDistribution from "@/components/dashboard/DefectDistribution";
import CauseDistribution from "@/components/dashboard/CauseDistribution";
import AiInsights from "@/components/dashboard/AiInsights";
import { analyticsApi, DashboardAnalyticsResponse } from "@/lib/api/analytics";

export default function DashboardPage() {
    const [data, setData] = useState<DashboardAnalyticsResponse | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isSyncing, setIsSyncing] = useState(false);
    const [lastSyncTime, setLastSyncTime] = useState<string>("Just now");

    const refreshData = useCallback((showLoading: boolean = false) => {
        if (showLoading) setIsLoading(true);
        analyticsApi
            .getDashboardAnalytics()
            .then((res) => {
                setData(res);
                setLastSyncTime(new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }));
                setError(null);
            })
            .catch((err: unknown) => {
                console.error("Failed to fetch dashboard data:", err);
                setError(err instanceof Error ? err.message : "Failed to load dashboard data");
            })
            .finally(() => {
                setIsLoading(false);
                setIsSyncing(false);
            });
    }, []);

    useEffect(() => {
        let isCurrent = true;
        analyticsApi
            .getDashboardAnalytics()
            .then((res) => {
                if (isCurrent) {
                    setData(res);
                    setLastSyncTime(new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }));
                    setError(null);
                    setIsLoading(false);
                }
            })
            .catch((err: unknown) => {
                if (isCurrent) {
                    console.error("Failed to fetch dashboard data:", err);
                    setError(err instanceof Error ? err.message : "Failed to load dashboard data");
                    setIsLoading(false);
                }
            });

        // Global real-time SSE listener + 15s heartbeat polling fallback
        const unsubscribe = analyticsApi.subscribeToEvents((event) => {
            console.log("Dashboard global sync event received:", event);
            if (isCurrent) {
                setIsSyncing(true);
                refreshData(false);
            }
        });

        const pollInterval = setInterval(() => {
            if (isCurrent) {
                refreshData(false);
            }
        }, 15000);

        return () => {
            isCurrent = false;
            unsubscribe();
            clearInterval(pollInterval);
        };
    }, [refreshData]);

    const handleManualRefresh = () => {
        setIsSyncing(true);
        refreshData(false);
    };

    const kpis = data?.kpis;
    const confirmationRate = kpis?.cause_confirmation_rate;

    return (
        <PageContainer>
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                        <div>
                            <p className="text-sm font-medium text-[#6d5dfc]">
                                Operations overview
                            </p>

                            <h1 className="mt-1 text-3xl font-bold tracking-tight text-gray-900">
                                Diagnostic Dashboard
                            </h1>

                            <p className="mt-2 text-sm text-gray-500">
                                Monitor live dispensing defects, active diagnoses and troubleshooting performance across operations.
                            </p>
                        </div>

                        {/* Global Sync Indicator & Refresh Button */}
                        <div className="flex items-center gap-3">
                            <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50/80 px-3 py-1.5 text-xs font-semibold text-emerald-800 shadow-sm">
                                <span className="relative flex h-2 w-2">
                                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                                    <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                                </span>
                                <span>Live Sync</span>
                                <span className="text-emerald-500 font-mono text-[11px]">({lastSyncTime})</span>
                            </div>

                            <button
                                onClick={handleManualRefresh}
                                disabled={isSyncing}
                                className="inline-flex items-center gap-1.5 rounded-xl border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 shadow-sm transition hover:bg-gray-50 disabled:opacity-50"
                                title="Refresh dashboard data"
                            >
                                <RefreshCw size={13} className={isSyncing ? "animate-spin text-[#6d5dfc]" : "text-gray-500"} />
                                Refresh
                            </button>
                        </div>
                    </div>

                    {/* Production Line Status Ribbon */}
                    <div className="mt-6">
                        <LineStatusRibbon />
                    </div>

                    <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
                        <KpiCard
                            title="Active Diagnoses"
                            value={isLoading ? "..." : String(kpis?.active_diagnoses ?? 0)}
                            description="currently in progress"
                            trend={kpis?.active_diagnoses_trend || "+8% this week"}
                            trendDirection="up"
                            sparkline={[2, 3, 5, 4, 6, 5, kpis?.active_diagnoses ?? 4]}
                            accentColor="#6d5dfc"
                            icon={<Stethoscope size={20} />}
                        />

                        <KpiCard
                            title="Open Defects"
                            value={isLoading ? "..." : String(kpis?.open_defects ?? 0)}
                            description="awaiting resolution"
                            trend={kpis?.open_defects_trend || "-20% vs shift"}
                            trendDirection="down"
                            sparkline={[6, 5, 7, 5, 6, 4, kpis?.open_defects ?? 3]}
                            accentColor="#f43f5e"
                            icon={<AlertTriangle size={20} />}
                        />

                        <KpiCard
                            title="Resolved Cases"
                            value={isLoading ? "..." : String(kpis?.resolved_cases ?? 0)}
                            description="verified resolved cases"
                            trend={kpis?.resolved_cases_trend || "+15% vs target"}
                            trendDirection="up"
                            sparkline={[12, 16, 18, 22, 25, 29, kpis?.resolved_cases ?? 32]}
                            accentColor="#10b981"
                            icon={<CheckCircle2 size={20} />}
                        />

                        <KpiCard
                            title="Avg. Diagnosis Time"
                            value={isLoading ? "..." : `${kpis?.avg_diagnosis_time_minutes ?? 0} min`}
                            description="from creation to resolution"
                            trend={kpis?.avg_time_trend || "-12% MTTR"}
                            trendDirection="down"
                            sparkline={[35, 32, 29, 27, 24, 21, kpis?.avg_diagnosis_time_minutes ?? 20]}
                            accentColor="#3b82f6"
                            icon={<Clock3 size={20} />}
                        />
                    </div>

                    <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-3">
                        <div className="relative overflow-hidden rounded-2xl bg-[#171525] p-7 text-white xl:col-span-2">
                            <div className="relative z-10 max-w-xl">
                                <span className="inline-flex rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-white/80">
                                    AI-assisted diagnosis
                                </span>

                                <h2 className="mt-4 text-2xl font-bold tracking-tight">
                                    Something wrong with the dispensing process?
                                </h2>

                                <p className="mt-3 text-sm leading-6 text-white/60">
                                    Describe the dispensing symptom and let Dispense Lens
                                    guide the troubleshooting process using structured
                                    diagnostic reasoning.
                                </p>

                                <Link
                                    href="/diagnosis/new"
                                    className="mt-6 inline-flex items-center rounded-xl bg-[#6d5dfc] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#5848e8]"
                                >
                                    Start new diagnosis
                                </Link>
                            </div>

                            <div className="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-[#6d5dfc]/20 blur-3xl" />
                        </div>
                    ) : error && !data ? (
                        <div className="mt-8 flex flex-col items-center justify-center rounded-2xl border border-rose-200 bg-rose-50/50 p-12 text-center">
                            <AlertCircle className="h-12 w-12 text-rose-500 mb-4" />
                            <h3 className="text-lg font-semibold text-rose-900">Failed to load dashboard data</h3>
                            <p className="mt-1 max-w-md text-sm text-rose-700">{error}</p>
                            <button
                                onClick={() => refreshData(true)}
                                className="mt-4 inline-flex items-center gap-2 rounded-xl bg-rose-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-rose-700 transition"
                            >
                                <RefreshCw size={14} />
                                Retry
                            </button>
                        </div>
                    ) : data ? (
                        <>
                            {error && (
                                <div className="mt-6 flex items-center justify-between rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
                                    <div className="flex items-center gap-2">
                                        <AlertCircle size={18} className="text-amber-600" />
                                        <span>Refresh failed: {error}. Showing last synced data from {lastSyncTime}.</span>
                                    </div>
                                    <button
                                        onClick={() => refreshData(true)}
                                        className="rounded-lg bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800 hover:bg-amber-200 transition"
                                    >
                                        Retry
                                    </button>
                                </div>
                            )}

                            <div className="mt-8 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
                                <KpiCard
                                    title="Active Diagnoses"
                                    value={isLoading ? "..." : String(kpis?.active_diagnoses ?? 0)}
                                    description="currently in progress"
                                    trend={kpis?.active_diagnoses_trend}
                                    icon={<Stethoscope size={20} />}
                                />

                                <KpiCard
                                    title="Open Defects"
                                    value={isLoading ? "..." : String(kpis?.open_defects ?? 0)}
                                    description="awaiting resolution"
                                    trend={kpis?.open_defects_trend}
                                    icon={<AlertTriangle size={20} />}
                                />

                                <KpiCard
                                    title="Resolved Cases"
                                    value={isLoading ? "..." : String(kpis?.resolved_cases ?? 0)}
                                    description="verified resolved cases"
                                    trend={kpis?.resolved_cases_trend}
                                    icon={<CheckCircle2 size={20} />}
                                />

                                <KpiCard
                                    title="Avg. Diagnosis Time"
                                    value={
                                        isLoading
                                            ? "..."
                                            : kpis?.avg_diagnosis_time_minutes != null
                                            ? `${kpis.avg_diagnosis_time_minutes} min`
                                            : "Not available"
                                    }
                                    description="from creation to resolution"
                                    trend={kpis?.avg_time_trend}
                                    icon={<Clock3 size={20} />}
                                />
                            </div>

                            <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-3">
                                <div className="relative overflow-hidden rounded-2xl bg-[#171525] p-7 text-white xl:col-span-2">
                                    <div className="relative z-10 max-w-xl">
                                        <span className="inline-flex rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-white/80">
                                            AI-assisted diagnosis
                                        </span>

                                        <h2 className="mt-4 text-2xl font-bold tracking-tight">
                                            Something wrong with the dispensing process?
                                        </h2>

                                        <p className="mt-3 text-sm leading-6 text-white/60">
                                            Describe the dispensing symptom and let DispenseIQ
                                            guide the troubleshooting process using structured
                                            diagnostic reasoning.
                                        </p>

                                        <Link
                                            href="/diagnosis/new"
                                            className="mt-6 inline-flex items-center rounded-xl bg-[#6d5dfc] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#5848e8]"
                                        >
                                            Start new diagnosis
                                        </Link>
                                    </div>

                                    <div className="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-[#6d5dfc]/20 blur-3xl" />
                                </div>

                                <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                                    <p className="text-sm font-semibold text-gray-900">
                                        Cause Confirmation Coverage
                                    </p>

                                    <p className="mt-1 text-xs text-gray-500">
                                        Unique confirmed cases / total cases
                                    </p>

                                    <div className="mt-6">
                                        <div className="flex items-end justify-between">
                                            <span className="text-3xl font-bold text-gray-900">
                                                {isLoading
                                                    ? "..."
                                                    : confirmationRate != null
                                                    ? `${confirmationRate}%`
                                                    : "Not available"}
                                            </span>

                                            {confirmationRate != null && (
                                                <span className="text-xs font-medium text-emerald-600">
                                                    {confirmationRate >= 80 ? "High Coverage" : confirmationRate >= 50 ? "Moderate" : "Low Coverage"}
                                                </span>
                                            )}
                                        </div>

                                        <div className="mt-3 h-2 overflow-hidden rounded-full bg-gray-100">
                                            <div
                                                className="h-full rounded-full bg-[#6d5dfc] transition-all duration-500"
                                                style={{ width: `${confirmationRate != null ? Math.min(100, Math.max(0, confirmationRate)) : 0}%` }}
                                            />
                                        </div>

                                        <p className="mt-3 text-xs leading-5 text-gray-500">
                                            Percentage of total diagnostic cases with at least one verified technician root cause confirmation.
                                        </p>
                                    </div>
                                </div>
                            </div>

                            <RecentCases cases={data?.recent_cases} />

                            <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
                                <DefectDistribution data={data?.defect_distribution} />
                                <CauseDistribution data={data?.cause_distribution} />
                            </div>

                            <div className="mt-6">
                                <AiInsights
                                    insightText={data?.ai_insight_text}
                                    trendText={data?.ai_insight_trend}
                                />
                            </div>
                        </>
                    ) : null}
                </PageContainer>
    );
}