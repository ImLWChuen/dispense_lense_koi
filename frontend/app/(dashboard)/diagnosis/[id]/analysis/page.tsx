import Link from "next/link";
import { Clock3 } from "lucide-react";

import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";
import PageContainer from "@/components/layout/PageContainer";
import EvidenceGraph from "@/components/diagnosis/EvidenceGraph";
import ImageAnalysis from "@/components/diagnosis/ImageAnalysis";

const revisions = [
    {
        id: 1,
        timestamp: "10:32 AM",
        trigger: "Initial diagnosis",
        topCause: "Nozzle Restriction",
        topScore: 72,
        changes: "Defect identified as Too Little Material. 5 candidate causes ranked.",
    },
    {
        id: 2,
        timestamp: "10:41 AM",
        trigger: "Q01 answered: after_prolonged_operation",
        topCause: "Nozzle Restriction",
        topScore: 79,
        changes: "Air / Supply Issue score increased. Nozzle Restriction remains top.",
    },
    {
        id: 3,
        timestamp: "10:48 AM",
        trigger: "Q02 answered: specific_nozzle",
        topCause: "Nozzle Restriction",
        topScore: 87,
        changes: "Nozzle Restriction score jumped. System-wide causes (Material, Pressure) reduced.",
    },
];

const scoreBreakdown = [
    { cause: "Nozzle Restriction", base: 35, question: 32, check: 20, total: 87 },
    { cause: "Air / Supply Issue", base: 30, question: 28, check: 14, total: 72 },
    { cause: "Material Condition", base: 25, question: 18, check: 15, total: 58 },
    { cause: "Pressure Instability", base: 20, question: 11, check: 10, total: 41 },
    { cause: "Parameter Issue", base: 15, question: 8, check: 6, total: 29 },
];

export default function AnalysisPage() {
    return (
        <div className="min-h-screen">
            <Sidebar />

            <div className="ml-64">
                <Header />

                <PageContainer>
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-sm font-medium text-[#6d5dfc]">
                                Diagnostic workflow · DSP-2026-0185
                            </p>

                            <h1 className="mt-1 text-3xl font-bold tracking-tight text-gray-900">
                                Analysis Detail
                            </h1>

                            <p className="mt-2 text-sm text-gray-500">
                                Detailed scoring breakdown and revision history
                                for this diagnosis.
                            </p>
                        </div>

                        <Link
                            href="/diagnosis/DSP-2026-0185"
                            className="text-sm font-medium text-[#5848e8] hover:text-[#6d5dfc]"
                        >
                            ← Back to Diagnosis
                        </Link>
                    </div>

                    <div className="mt-8 grid grid-cols-1 gap-8 xl:grid-cols-3">
                        <div className="space-y-6 xl:col-span-2">
                            <EvidenceGraph />

                            {/* Score Breakdown Table */}
                            <div className="rounded-2xl border border-gray-200 bg-white shadow-sm">
                                <div className="border-b border-gray-100 px-6 py-5">
                                    <h2 className="text-base font-semibold text-gray-900">
                                        Score Breakdown
                                    </h2>

                                    <p className="mt-1 text-xs text-gray-500">
                                        Contribution from each evidence source
                                    </p>
                                </div>

                                <div className="overflow-x-auto">
                                    <table className="w-full min-w-[600px]">
                                        <thead>
                                            <tr className="border-b border-gray-100 text-left">
                                                <th className="px-6 py-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                                    Cause
                                                </th>

                                                <th className="px-6 py-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                                    Base
                                                </th>

                                                <th className="px-6 py-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                                    Questions
                                                </th>

                                                <th className="px-6 py-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                                    Checks
                                                </th>

                                                <th className="px-6 py-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                                    Total
                                                </th>
                                            </tr>
                                        </thead>

                                        <tbody>
                                            {scoreBreakdown.map((row) => (
                                                <tr
                                                    key={row.cause}
                                                    className="border-b border-gray-50 last:border-0"
                                                >
                                                    <td className="px-6 py-3 text-sm font-medium text-gray-900">
                                                        {row.cause}
                                                    </td>

                                                    <td className="px-6 py-3 text-sm text-gray-600">
                                                        {row.base}
                                                    </td>

                                                    <td className="px-6 py-3 text-sm text-gray-600">
                                                        +{row.question}
                                                    </td>

                                                    <td className="px-6 py-3 text-sm text-gray-600">
                                                        +{row.check}
                                                    </td>

                                                    <td className="px-6 py-3">
                                                        <span className="text-sm font-bold text-[#5848e8]">
                                                            {row.total}
                                                        </span>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>

                        <div className="space-y-6">
                            {/* Revision Timeline */}
                            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                                <h2 className="text-base font-semibold text-gray-900">
                                    Revision History
                                </h2>

                                <p className="mt-1 text-xs text-gray-500">
                                    How the diagnosis evolved
                                </p>

                                <div className="mt-5 space-y-0">
                                    {revisions.map((rev, index) => (
                                        <div
                                            key={rev.id}
                                            className="relative flex gap-3 pb-6 last:pb-0"
                                        >
                                            {/* Timeline line */}
                                            {index < revisions.length - 1 && (
                                                <div className="absolute left-[11px] top-6 h-full w-px bg-gray-200" />
                                            )}

                                            <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#eeebff]">
                                                <Clock3
                                                    size={12}
                                                    className="text-[#6d5dfc]"
                                                />
                                            </div>

                                            <div>
                                                <div className="flex items-center gap-2">
                                                    <span className="text-xs font-semibold text-gray-900">
                                                        Revision {rev.id}
                                                    </span>

                                                    <span className="text-[10px] text-gray-400">
                                                        {rev.timestamp}
                                                    </span>
                                                </div>

                                                <p className="mt-0.5 text-[10px] font-medium text-[#5848e8]">
                                                    {rev.trigger}
                                                </p>

                                                <p className="mt-1 text-xs leading-5 text-gray-500">
                                                    {rev.changes}
                                                </p>

                                                <div className="mt-1 flex items-center gap-2">
                                                    <span className="text-[10px] text-gray-400">
                                                        Top:
                                                    </span>

                                                    <span className="text-[10px] font-medium text-gray-700">
                                                        {rev.topCause}
                                                    </span>

                                                    <span className="text-[10px] font-bold text-[#5848e8]">
                                                        {rev.topScore}%
                                                    </span>
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            <ImageAnalysis />
                        </div>
                    </div>
                </PageContainer>
            </div>
        </div>
    );
}
