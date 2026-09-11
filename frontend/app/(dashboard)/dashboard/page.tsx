import {
    AlertTriangle,
    CheckCircle2,
    Clock3,
    Stethoscope,
} from "lucide-react";

import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";
import PageContainer from "@/components/layout/PageContainer";
import KpiCard from "@/components/dashboard/KpiCard";
import RecentCases from "@/components/dashboard/RecentCases";
import DefectDistribution from "@/components/dashboard/DefectDistribution";
import CauseDistribution from "@/components/dashboard/CauseDistribution";
import AiInsights from "@/components/dashboard/AiInsights";

export default function DashboardPage() {
    return (
        <div className="min-h-screen">
            <Sidebar />

            <div className="ml-64">
                <Header />

                <PageContainer>
                    <div>
                        <p className="text-sm font-medium text-[#6d5dfc]">
                            Operations overview
                        </p>

                        <h1 className="mt-1 text-3xl font-bold tracking-tight text-gray-900">
                            Good morning, Sarah
                        </h1>

                        <p className="mt-2 text-sm text-gray-500">
                            Monitor dispensing defects, active diagnoses and
                            troubleshooting performance.
                        </p>
                    </div>
                    <div className="mt-8 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
                        <KpiCard
                            title="Active Diagnoses"
                            value="12"
                            description="currently in progress"
                            trend="+3"
                            icon={<Stethoscope size={20} />}
                        />

                        <KpiCard
                            title="Open Defects"
                            value="7"
                            description="awaiting resolution"
                            trend="-2"
                            icon={<AlertTriangle size={20} />}
                        />

                        <KpiCard
                            title="Resolved Cases"
                            value="184"
                            description="this month"
                            trend="+12%"
                            icon={<CheckCircle2 size={20} />}
                        />

                        <KpiCard
                            title="Avg. Diagnosis Time"
                            value="8.4 min"
                            description="vs 14.2 min baseline"
                            trend="-41%"
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

                                <a
                                    href="/diagnosis/new"
                                    className="mt-6 inline-flex items-center rounded-xl bg-[#6d5dfc] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#5848e8]"
                                >
                                    Start new diagnosis
                                </a>
                            </div>

                            <div className="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-[#6d5dfc]/20 blur-3xl" />
                        </div>

                        <div className="rounded-2xl border border-gray-200 bg-white p-6">
                            <p className="text-sm font-semibold text-gray-900">
                                AI Diagnostic Status
                            </p>

                            <p className="mt-1 text-xs text-gray-500">
                                Current system performance
                            </p>

                            <div className="mt-6">
                                <div className="flex items-end justify-between">
                                    <span className="text-3xl font-bold text-gray-900">
                                         92%
                                    </span>

                                    <span className="text-xs font-medium text-green-600">
                                        Good
                                    </span>
                                </div>

                                <div className="mt-3 h-2 overflow-hidden rounded-full bg-gray-100">
                                    <div className="h-full w-[92%] rounded-full bg-[#6d5dfc]" />
                                </div>

                                <p className="mt-3 text-xs leading-5 text-gray-500">
                                    Based on recent benchmark scenarios and verified
                                    engineer outcomes.
                                </p>
                            </div>
                        </div>
                    </div>
                    <RecentCases />
                    <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
                        <DefectDistribution />
                        <CauseDistribution />
                    </div>
                    <div className="mt-6">
                        <AiInsights />
                    </div>
                </PageContainer>
            </div>
        </div>
    );
}