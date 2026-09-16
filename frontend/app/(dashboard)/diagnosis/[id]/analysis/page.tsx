"use client";

import { useState, useEffect, useCallback, use } from "react";
import Link from "next/link";
import { Clock3 } from "lucide-react";

import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";
import PageContainer from "@/components/layout/PageContainer";
import EvidenceGraph from "@/components/diagnosis/EvidenceGraph";
import ImageAnalysis from "@/components/diagnosis/ImageAnalysis";
import { casesApi } from "@/lib/api/cases";
import { DurableCaseResponse } from "@/types/api";

export default function AnalysisPage({ params }: { params: Promise<{ id: string }> }) {
    const resolvedParams = use(params);
    const [caseData, setCaseData] = useState<DurableCaseResponse | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchCase = useCallback(async () => {
        try {
            const data = await casesApi.getCase(resolvedParams.id);
            setCaseData(data);
        } catch (err: any) {
            console.error("Failed to fetch case", err);
            setError(err.message || "Failed to load case data.");
        } finally {
            setIsLoading(false);
        }
    }, [resolvedParams.id]);

    useEffect(() => {
        fetchCase();
    }, [fetchCase]);

    if (isLoading && !caseData) {
        return (
            <div className="min-h-screen">
                <Sidebar />
                <div className="ml-64">
                    <Header />
                    <PageContainer>
                        <div className="flex h-64 items-center justify-center">
                            <p className="text-gray-500">Loading analysis data...</p>
                        </div>
                    </PageContainer>
                </div>
            </div>
        );
    }

    const diagnosis = caseData?.diagnosis || caseData?.initial_diagnosis;
    const revisions = caseData?.analysis_revisions || [];
    
    const scoreBreakdown = diagnosis?.ranked_causes?.map(cause => {
        return {
            cause: cause.cause_name,
            base: cause.score_breakdown?.base || 0,
            question: cause.score_breakdown?.question || 0,
            check: cause.score_breakdown?.check || 0,
            total: Math.round(cause.score)
        };
    }) || [];

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
                            href={`/diagnosis/${resolvedParams.id}`}
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
                                    {revisions.map((rev, index) => {
                                        const topCause = rev.ranked_causes?.[0];
                                        return (
                                        <div
                                            key={rev.revision_number}
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
                                                        Revision {rev.revision_number}
                                                    </span>

                                                    <span className="text-[10px] text-gray-400">
                                                        {new Date(rev.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                                    </span>
                                                </div>

                                                <p className="mt-0.5 text-[10px] font-medium text-[#5848e8]">
                                                    {rev.new_evidence_summary || "Initial diagnosis"}
                                                </p>

                                                <p className="mt-1 text-xs leading-5 text-gray-500">
                                                    {rev.changes_from_previous?.join(" ") || "Defect identified. Candidate causes ranked."}
                                                </p>

                                                <div className="mt-1 flex items-center gap-2">
                                                    <span className="text-[10px] text-gray-400">
                                                        Top:
                                                    </span>

                                                    <span className="text-[10px] font-medium text-gray-700">
                                                        {topCause?.cause_name || "N/A"}
                                                    </span>

                                                    <span className="text-[10px] font-bold text-[#5848e8]">
                                                        {Math.round(topCause?.score || 0)}%
                                                    </span>
                                                </div>
                                            </div>
                                        </div>
                                    )})}
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
