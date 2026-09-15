import {
    BarChart3,
    Clock3,
    CheckCircle2,
    TrendingUp,
} from "lucide-react";

import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";
import PageContainer from "@/components/layout/PageContainer";
import KpiCard from "@/components/dashboard/KpiCard";
import DefectChart from "@/components/analytics/DefectChart";
import CauseChart from "@/components/analytics/CauseChart";
import ResolutionChart from "@/components/analytics/ResolutionChart";

export default function AnalyticsPage() {
    return (
        <div className="min-h-screen">
            <Sidebar />

            <div className="ml-64">
                <Header />

                <PageContainer>
                    <div>
                        <p className="text-sm font-medium text-[#6d5dfc]">
                            Performance insights
                        </p>

                        <h1 className="mt-1 text-3xl font-bold tracking-tight text-gray-900">
                            Analytics
                        </h1>

                        <p className="mt-2 text-sm text-gray-500">
                            Track defect trends, resolution performance, and
                            root cause patterns across your dispensing
                            operations.
                        </p>
                    </div>

                    {/* Date filter */}
                    <div className="mt-6 flex items-center gap-2">
                        {["7 Days", "30 Days", "90 Days", "Year"].map(
                            (period, i) => (
                                <button
                                    key={period}
                                    className={`rounded-lg px-4 py-2 text-xs font-medium transition ${
                                        i === 1
                                            ? "bg-[#6d5dfc] text-white"
                                            : "border border-gray-200 text-gray-600 hover:bg-gray-50"
                                    }`}
                                >
                                    {period}
                                </button>
                            )
                        )}
                    </div>

                    {/* KPIs */}
                    <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
                        <KpiCard
                            title="Total Cases"
                            value="284"
                            description="this period"
                            trend="+18%"
                            icon={<BarChart3 size={20} />}
                        />

                        <KpiCard
                            title="Avg. Resolution Time"
                            value="8.4 min"
                            description="vs 14.2 min baseline"
                            trend="-41%"
                            icon={<Clock3 size={20} />}
                        />

                        <KpiCard
                            title="First-Time Resolution"
                            value="78%"
                            description="resolved without re-diagnosis"
                            trend="+5%"
                            icon={<CheckCircle2 size={20} />}
                        />

                        <KpiCard
                            title="Diagnostic Accuracy"
                            value="92%"
                            description="confirmed vs suggested cause"
                            trend="+3%"
                            icon={<TrendingUp size={20} />}
                        />
                    </div>

                    {/* Charts */}
                    <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
                        <DefectChart />
                        <CauseChart />
                    </div>

                    <div className="mt-6">
                        <ResolutionChart />
                    </div>

                    {/* Equipment comparison */}
                    <div className="mt-6 rounded-2xl border border-gray-200 bg-white shadow-sm">
                        <div className="border-b border-gray-100 px-6 py-5">
                            <h2 className="text-base font-semibold text-gray-900">
                                Equipment Performance
                            </h2>

                            <p className="mt-1 text-xs text-gray-500">
                                Defect rate comparison across dispensing lines
                            </p>
                        </div>

                        <div className="overflow-x-auto">
                            <table className="w-full min-w-[700px]">
                                <thead>
                                    <tr className="border-b border-gray-100 text-left">
                                        <th className="px-6 py-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                            Equipment
                                        </th>

                                        <th className="px-6 py-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                            Total Cases
                                        </th>

                                        <th className="px-6 py-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                            Resolved
                                        </th>

                                        <th className="px-6 py-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                            Avg. Time
                                        </th>

                                        <th className="px-6 py-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                            Top Cause
                                        </th>
                                    </tr>
                                </thead>

                                <tbody>
                                    {[
                                        {
                                            name: "Dispensing Line A",
                                            total: 89,
                                            resolved: 82,
                                            avgTime: "7.2 min",
                                            topCause: "Nozzle Restriction",
                                        },
                                        {
                                            name: "Dispensing Line B",
                                            total: 72,
                                            resolved: 65,
                                            avgTime: "9.1 min",
                                            topCause: "Pressure Instability",
                                        },
                                        {
                                            name: "Dispensing Line C",
                                            total: 68,
                                            resolved: 63,
                                            avgTime: "8.8 min",
                                            topCause: "Material Condition",
                                        },
                                        {
                                            name: "Dispensing Line D",
                                            total: 55,
                                            resolved: 51,
                                            avgTime: "10.3 min",
                                            topCause: "Valve Issue",
                                        },
                                    ].map((row) => (
                                        <tr
                                            key={row.name}
                                            className="border-b border-gray-50 last:border-0"
                                        >
                                            <td className="px-6 py-4 text-sm font-medium text-gray-900">
                                                {row.name}
                                            </td>

                                            <td className="px-6 py-4 text-sm text-gray-600">
                                                {row.total}
                                            </td>

                                            <td className="px-6 py-4 text-sm text-gray-600">
                                                {row.resolved}
                                            </td>

                                            <td className="px-6 py-4 text-sm text-gray-600">
                                                {row.avgTime}
                                            </td>

                                            <td className="px-6 py-4">
                                                <span className="rounded-md bg-[#eeebff] px-2 py-0.5 text-xs font-medium text-[#5848e8]">
                                                    {row.topCause}
                                                </span>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </PageContainer>
            </div>
        </div>
    );
}
