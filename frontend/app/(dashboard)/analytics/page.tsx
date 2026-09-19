"use client";

import { useEffect, useState, useRef } from "react";
import {
    BarChart3,
    Clock3,
    CheckCircle2,
    TrendingUp,
    RefreshCw,
    Radio,
    ShieldCheck,
    Layers,
    Loader2,
} from "lucide-react";

import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";
import PageContainer from "@/components/layout/PageContainer";
import KpiCard from "@/components/dashboard/KpiCard";
import DefectChart from "@/components/analytics/DefectChart";
import CauseChart from "@/components/analytics/CauseChart";
import ResolutionChart from "@/components/analytics/ResolutionChart";
import { analyticsApi, AnalyticsPerformanceResponse } from "@/lib/api/analytics";

const periods = [
    { label: "7 Days", value: "7d" },
    { label: "30 Days", value: "30d" },
    { label: "90 Days", value: "90d" },
    { label: "Year", value: "year" },
    { label: "All Time", value: "all" },
];

export default function AnalyticsPage() {
    const [selectedPeriod, setSelectedPeriod] = useState("30d");
    const [analytics, setAnalytics] = useState<AnalyticsPerformanceResponse | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isSyncing, setIsSyncing] = useState(false);
    const [lastSyncTime, setLastSyncTime] = useState<string>("Just now");

    const periodRef = useRef(selectedPeriod);
    periodRef.current = selectedPeriod;

    const fetchAnalytics = async (period: string, showLoading: boolean = true) => {
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
    };

    useEffect(() => {
        fetchAnalytics(selectedPeriod, true);
    }, [selectedPeriod]);

    // Global real-time SSE listener + 15s heartbeat fallback sync
    useEffect(() => {
        const unsubscribe = analyticsApi.subscribeToEvents((event) => {
            console.log("Global real-time sync event received:", event);
            setIsSyncing(true);
            fetchAnalytics(periodRef.current, false);
            setTimeout(() => setIsSyncing(false), 1500);
        });

        // 15-second heartbeat poll to ensure guaranteed multi-account global sync
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
        fetchAnalytics(selectedPeriod, false).finally(() => {
            setTimeout(() => setIsSyncing(false), 800);
        });
    };

    const kpis = analytics?.kpis;

    return (
        <div className="min-h-screen bg-[#f8fafc]">
            <Sidebar />

            <div className="ml-64">
                <Header />

                <PageContainer>
                    {/* Header with Global Sync Indicator */}
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                        <div>
                            <p className="text-sm font-semibold tracking-wide text-[#6d5dfc]">
                                Performance Insights
                            </p>

                            <h1 className="mt-1 text-3xl font-bold tracking-tight text-gray-900">
                                Diagnostic Analytics
                            </h1>

                            <p className="mt-1 text-sm text-gray-500">
                                Track defect trends, resolution performance, and root cause distributions across all cases in real time.
                            </p>
                        </div>

                        {/* Real-time Global Sync Badge */}
                        <div className="flex items-center gap-3">
                            <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50/80 px-3 py-1.5 text-xs font-semibold text-emerald-800 shadow-sm">
                                <span className="relative flex h-2 w-2">
                                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                                    <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                                </span>
                                <span>Global Sync Active</span>
                                <span className="text-emerald-500 font-mono text-[11px]">({lastSyncTime})</span>
                            </div>

                            <button
                                onClick={handleManualRefresh}
                                disabled={isSyncing}
                                className="inline-flex items-center gap-1.5 rounded-xl border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 shadow-sm transition hover:bg-gray-50 disabled:opacity-50"
                                title="Refresh data"
                            >
                                <RefreshCw size={13} className={isSyncing ? "animate-spin text-[#6d5dfc]" : "text-gray-500"} />
                                Refresh
                            </button>
                        </div>
                    </div>

                    {/* Interactive Date Filter Bar */}
                    <div className="mt-6 flex flex-wrap items-center justify-between gap-4">
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
                    <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
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
                    <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
                        <DefectChart data={analytics?.defect_trend} />
                        <CauseChart data={analytics?.cause_distribution} />
                    </div>

                    {/* Resolution Distribution & Defect Breakdown */}
                    <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-3">
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
                                <span>Synced across all users</span>
                            </div>
                        </div>
                    </div>
                </PageContainer>
            </div>
        </div>
    );
}
