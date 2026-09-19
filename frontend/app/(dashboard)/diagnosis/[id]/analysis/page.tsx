"use client";

import { useState, useEffect, useCallback, use } from "react";
import Link from "next/link";
import { Clock3, AlertCircle, ArrowLeft, RefreshCw, Loader2 } from "lucide-react";

import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";
import PageContainer from "@/components/layout/PageContainer";
import EvidenceGraph from "@/components/diagnosis/EvidenceGraph";
import ImageAnalysis from "@/components/diagnosis/ImageAnalysis";
import { casesApi } from "@/lib/api/cases";
import { DurableCaseResponse } from "@/types/api";

function formatBreakdownKey(key: string): string {
    return key
        .replace(/_/g, " ")
        .replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function AnalysisPage({ params }: { params: Promise<{ id: string }> }) {
    const resolvedParams = use(params);
    const [caseData, setCaseData] = useState<DurableCaseResponse | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const handleRetry = useCallback(() => {
        setIsLoading(true);
        setError(null);
        casesApi
            .getCase(resolvedParams.id)
            .then((data) => {
                setCaseData(data);
                setError(null);
            })
            .catch((err: unknown) => {
                const msg = err instanceof Error ? err.message : "Failed to load case data.";
                setError(msg);
            })
            .finally(() => {
                setIsLoading(false);
            });
    }, [resolvedParams.id]);

    useEffect(() => {
        let isCurrent = true;
        casesApi
            .getCase(resolvedParams.id)
            .then((data) => {
                if (isCurrent) {
                    setCaseData(data);
                    setError(null);
                    setIsLoading(false);
                }
            })
            .catch((err: unknown) => {
                if (isCurrent) {
                    const msg = err instanceof Error ? err.message : "Failed to load case data.";
                    setError(msg);
                    setIsLoading(false);
                }
            });
        return () => {
            isCurrent = false;
        };
    }, [resolvedParams.id]);

    // Loading State
    if (isLoading && !caseData) {
        return (
            <div className="min-h-screen">
                <Sidebar />
                <div className="ml-64">
                    <Header />
                    <PageContainer>
                        <div className="flex h-72 flex-col items-center justify-center gap-3">
                            <Loader2 size={24} className="animate-spin text-[#6d5dfc]" />
                            <p className="text-sm text-gray-500">Loading analysis data...</p>
                        </div>
                    </PageContainer>
                </div>
            </div>
        );
    }

    // API Error State
    if (error && !caseData) {
        return (
            <div className="min-h-screen">
                <Sidebar />
                <div className="ml-64">
                    <Header />
                    <PageContainer>
                        <div className="flex flex-col items-center justify-center rounded-2xl border border-red-200 bg-red-50/50 p-10 text-center">
                            <AlertCircle size={36} className="text-red-500" />
                            <h2 className="mt-3 text-lg font-semibold text-gray-900">
                                Failed to Load Case Analysis
                            </h2>
                            <p className="mt-1 max-w-md text-xs text-red-700">{error}</p>
                            <div className="mt-5 flex gap-3">
                                <button
                                    type="button"
                                    onClick={handleRetry}
                                    className="inline-flex items-center gap-1.5 rounded-xl bg-[#6d5dfc] px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-[#5848e8]"
                                >
                                    <RefreshCw size={13} />
                                    Retry
                                </button>
                                <Link
                                    href="/cases"
                                    className="inline-flex items-center gap-1 rounded-xl border border-gray-200 bg-white px-4 py-2 text-xs font-semibold text-gray-700 hover:bg-gray-50"
                                >
                                    View All Cases
                                </Link>
                            </div>
                        </div>
                    </PageContainer>
                </div>
            </div>
        );
    }

    // No Case Data State
    if (!caseData) {
        return (
            <div className="min-h-screen">
                <Sidebar />
                <div className="ml-64">
                    <Header />
                    <PageContainer>
                        <div className="flex flex-col items-center justify-center rounded-2xl border border-gray-200 bg-white p-10 text-center">
                            <p className="text-sm font-medium text-gray-700">
                                Case not found ({resolvedParams.id})
                            </p>
                            <Link
                                href="/cases"
                                className="mt-4 text-xs font-semibold text-[#5848e8] hover:underline"
                            >
                                &larr; Return to Cases
                            </Link>
                        </div>
                    </PageContainer>
                </div>
            </div>
        );
    }

    const diagnosis = caseData.diagnosis || caseData.initial_diagnosis;
    const revisions = caseData.analysis_revisions || [];
    const rankedCauses = diagnosis?.ranked_causes || [];

    // Dynamically extract all score breakdown keys across ranked causes
    const allBreakdownKeys = Array.from(
        new Set(
            rankedCauses.flatMap((c) => (c.score_breakdown ? Object.keys(c.score_breakdown) : []))
        )
    );

    return (
        <div className="min-h-screen">
            <Sidebar />

            <div className="ml-64">
                <Header />

                <PageContainer>
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-sm font-medium text-[#6d5dfc]">
                                Diagnostic workflow &middot; Case {caseData.case_id}
                            </p>

                            <h1 className="mt-1 text-3xl font-bold tracking-tight text-gray-900">
                                Analysis Detail
                            </h1>

                            <p className="mt-2 text-sm text-gray-500">
                                Detailed scoring breakdown and revision history for this diagnosis.
                            </p>
                        </div>

                        <Link
                            href={`/diagnosis/${caseData.case_id}`}
                            className="inline-flex items-center gap-1.5 rounded-xl border border-gray-200 bg-white px-3.5 py-2 text-xs font-semibold text-gray-700 shadow-sm transition hover:bg-gray-50"
                        >
                            <ArrowLeft size={14} />
                            Back to Diagnosis
                        </Link>
                    </div>

                    <div className="mt-8 grid grid-cols-1 gap-8 xl:grid-cols-3">
                        <div className="space-y-6 xl:col-span-2">
                            {/* Real Evidence Weight Distribution */}
                            <EvidenceGraph rankedCauses={rankedCauses} />

                            {/* Dynamic Score Breakdown Table */}
                            <div className="rounded-2xl border border-gray-200 bg-white shadow-sm">
                                <div className="border-b border-gray-100 px-6 py-5">
                                    <h2 className="text-base font-semibold text-gray-900">
                                        Score Breakdown
                                    </h2>

                                    <p className="mt-1 text-xs text-gray-500">
                                        Component contributions from diagnostic evaluation
                                    </p>
                                </div>

                                {rankedCauses.length === 0 ? (
                                    <div className="p-6 text-center text-xs text-gray-500 italic">
                                        No ranked candidate causes available for this diagnosis.
                                    </div>
                                ) : (
                                    <div className="overflow-x-auto">
                                        <table className="w-full min-w-[600px]">
                                            <thead>
                                                <tr className="border-b border-gray-100 text-left">
                                                    <th className="px-6 py-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                                        Candidate Cause
                                                    </th>

                                                    {allBreakdownKeys.map((key) => (
                                                        <th
                                                            key={key}
                                                            className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-gray-400"
                                                        >
                                                            {formatBreakdownKey(key)}
                                                        </th>
                                                    ))}

                                                    <th className="px-6 py-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                                        Final Score
                                                    </th>
                                                </tr>
                                            </thead>

                                            <tbody>
                                                {rankedCauses.map((cause) => (
                                                    <tr
                                                        key={cause.cause_id}
                                                        className="border-b border-gray-50 last:border-0"
                                                    >
                                                        <td className="px-6 py-3 text-sm font-medium text-gray-900">
                                                            {cause.cause_name}
                                                        </td>

                                                        {allBreakdownKeys.map((key) => {
                                                            const val = cause.score_breakdown?.[key];
                                                            return (
                                                                <td
                                                                    key={key}
                                                                    className="px-4 py-3 text-sm text-gray-600"
                                                                >
                                                                    {typeof val === "number"
                                                                        ? val >= 0
                                                                            ? `+${val.toFixed(2)}`
                                                                            : val.toFixed(2)
                                                                        : "—"}
                                                                </td>
                                                            );
                                                        })}

                                                        <td className="px-6 py-3">
                                                            <span className="text-sm font-bold text-[#5848e8]">
                                                                {cause.score.toFixed(1)}
                                                            </span>
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                )}
                            </div>
                        </div>

                        <div className="space-y-6">
                            {/* Revision Timeline */}
                            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                                <h2 className="text-base font-semibold text-gray-900">
                                    Revision History
                                </h2>

                                <p className="mt-1 text-xs text-gray-500">
                                    How the diagnosis evolved across revisions
                                </p>

                                {revisions.length === 0 ? (
                                    <p className="mt-5 text-xs text-gray-400 italic">
                                        No revision history recorded.
                                    </p>
                                ) : (
                                    <div className="mt-5 space-y-0">
                                        {revisions.map((rev, index) => {
                                            const topCause = rev.ranked_causes?.[0];
                                            return (
                                                <div
                                                    key={rev.revision_number}
                                                    className="relative flex gap-3 pb-6 last:pb-0"
                                                >
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
                                                                {new Date(rev.timestamp).toLocaleTimeString([], {
                                                                    hour: "2-digit",
                                                                    minute: "2-digit",
                                                                })}
                                                            </span>
                                                        </div>

                                                        <p className="mt-0.5 text-[10px] font-medium text-[#5848e8]">
                                                            {rev.new_evidence_summary || "Initial diagnosis"}
                                                        </p>

                                                        {rev.changes_from_previous &&
                                                            rev.changes_from_previous.length > 0 && (
                                                                <p className="mt-1 text-xs leading-5 text-gray-500">
                                                                    {rev.changes_from_previous.join(" ")}
                                                                </p>
                                                            )}

                                                        <div className="mt-1 flex items-center gap-2">
                                                            <span className="text-[10px] text-gray-400">
                                                                Top Cause:
                                                            </span>

                                                            <span className="text-[10px] font-medium text-gray-700">
                                                                {topCause?.cause_name || "N/A"}
                                                            </span>

                                                            {topCause && (
                                                                <span className="text-[10px] font-bold text-[#5848e8]">
                                                                    {topCause.score.toFixed(1)}
                                                                </span>
                                                            )}
                                                        </div>
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                )}
                            </div>

                            {/* Persisted Image Evidence */}
                            <ImageAnalysis observations={caseData.observations || []} />
                        </div>
                    </div>
                </PageContainer>
            </div>
        </div>
    );
}
