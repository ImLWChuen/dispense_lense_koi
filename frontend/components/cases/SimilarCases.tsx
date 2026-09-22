"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
    Sparkles,
    SearchX,
    CheckCircle2,
    Wrench,
    ArrowUpRight,
    RefreshCw,
    AlertCircle,
    ChevronDown,
    ChevronUp,
    Clock,
    Tag,
} from "lucide-react";
import { casesApi, SimilarCaseItem } from "@/lib/api/cases";

interface SimilarCasesProps {
    caseId?: string;
}

export default function SimilarCases({ caseId }: SimilarCasesProps) {
    const [similarCases, setSimilarCases] = useState<SimilarCaseItem[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [expandedCaseId, setExpandedCaseId] = useState<string | null>(null);

    const loadSimilarCases = async () => {
        if (!caseId) {
            setIsLoading(false);
            return;
        }

        try {
            setIsLoading(true);
            setError(null);
            const response = await casesApi.getSimilarCases(caseId, 5, 0.15);
            setSimilarCases(response.similar_cases || []);
        } catch (err: any) {
            console.warn("Failed to retrieve similar cases:", err);
            setError("Could not load similar cases.");
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        loadSimilarCases();
    }, [caseId]);

    const getScoreBadgeColor = (percentage: number) => {
        if (percentage >= 70) {
            return "bg-emerald-50 text-emerald-700 border-emerald-300 dark:bg-emerald-500/20 dark:text-emerald-300 dark:border-emerald-500/40";
        }
        if (percentage >= 40) {
            return "bg-[#eeebff] text-[#5848e8] border-[#d8d1fc] dark:bg-[#6d5dfc]/20 dark:text-[#b4a9ff] dark:border-[#6d5dfc]/40";
        }
        return "bg-amber-50 text-amber-800 border-amber-300 dark:bg-amber-500/20 dark:text-amber-300 dark:border-amber-500/40";
    };

    return (
        <div className="rounded-2xl border border-gray-200/90 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm">
            {/* Component Header */}
            <div className="flex items-center justify-between border-b border-gray-100 dark:border-gray-800 pb-3.5 mb-4">
                <div className="flex items-center gap-2">
                    <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#eeebff] dark:bg-[#5848e8]/25 text-[#6d5dfc] dark:text-[#a59bff]">
                        <Sparkles size={15} />
                    </div>
                    <div>
                        <h2 className="text-sm font-bold text-gray-900 dark:text-white leading-tight">
                            Historical Case Benchmarks
                        </h2>
                        <p className="text-[11px] text-gray-500 dark:text-gray-400">
                            Similar resolved defects & root causes
                        </p>
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    {similarCases.length > 0 && (
                        <span className="rounded-full bg-[#eeebff] dark:bg-[#5848e8]/30 px-2 py-0.5 text-[10px] font-bold text-[#5848e8] dark:text-[#a59bff]">
                            {similarCases.length} {similarCases.length === 1 ? "match" : "matches"}
                        </span>
                    )}
                    <button
                        onClick={loadSimilarCases}
                        disabled={isLoading}
                        title="Re-run similarity match"
                        className="rounded-lg p-1 text-gray-400 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-700 dark:hover:text-white transition disabled:opacity-50"
                    >
                        <RefreshCw size={13} className={isLoading ? "animate-spin text-[#6d5dfc]" : ""} />
                    </button>
                </div>
            </div>

            {/* Loading State */}
            {isLoading && (
                <div className="space-y-3 py-2">
                    {[1, 2].map((i) => (
                        <div key={i} className="animate-pulse rounded-xl border border-gray-100 dark:border-gray-800 p-3.5 space-y-2 dark:bg-[#151d2d]">
                            <div className="flex justify-between">
                                <div className="h-4 w-24 bg-gray-200 dark:bg-gray-800 rounded"></div>
                                <div className="h-4 w-16 bg-gray-200 dark:bg-gray-800 rounded"></div>
                            </div>
                            <div className="h-3 w-40 bg-gray-100 dark:bg-gray-800 rounded"></div>
                            <div className="h-8 w-full bg-gray-100 dark:bg-gray-800 rounded-lg"></div>
                        </div>
                    ))}
                </div>
            )}

            {/* Error State */}
            {!isLoading && error && (
                <div className="flex items-center gap-2 rounded-xl border border-rose-100 dark:border-rose-900/50 bg-rose-50/60 dark:bg-rose-950/40 p-3 text-xs text-rose-700 dark:text-rose-300">
                    <AlertCircle size={15} className="shrink-0" />
                    <span>{error}</span>
                </div>
            )}

            {/* Empty State */}
            {!isLoading && !error && similarCases.length === 0 && (
                <div className="flex flex-col items-center justify-center py-6 text-center text-gray-400">
                    <SearchX size={28} className="text-gray-300 dark:text-gray-600 mb-2" />
                    <p className="text-xs font-semibold text-gray-700 dark:text-gray-200">No Similar Historical Cases Found</p>
                    <p className="mt-1 text-[11px] text-gray-400 dark:text-gray-400 max-w-[240px] leading-relaxed">
                        No previous cases match this defect or material above the similarity threshold.
                    </p>
                </div>
            )}

            {/* Matching Cases List */}
            {!isLoading && !error && similarCases.length > 0 && (
                <div className="space-y-3">
                    {similarCases.map((cand) => {
                        const isExpanded = expandedCaseId === cand.case_id;

                        return (
                            <div
                                key={cand.case_id}
                                className="group rounded-xl border border-gray-200 dark:border-[#26354a] bg-gray-50/80 dark:bg-[#151d2d] p-3.5 text-xs hover:border-[#6d5dfc]/50 dark:hover:border-[#6d5dfc] hover:bg-white dark:hover:bg-[#1a253a] transition shadow-sm"
                            >
                                {/* Card Top Row: Match Score & ID */}
                                <div className="flex items-center justify-between gap-2 mb-2">
                                    <div className="flex items-center gap-1.5">
                                        <span
                                            className={`rounded-md px-1.5 py-0.5 text-[10px] font-bold border ${getScoreBadgeColor(
                                                cand.similarity_percentage
                                            )}`}
                                        >
                                            {cand.similarity_percentage}% Match
                                        </span>
                                        <span className="font-mono text-[11px] font-semibold text-gray-700 dark:text-gray-200">
                                            #{cand.short_id}
                                        </span>
                                    </div>

                                    <span
                                        className={`rounded-full px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider border ${
                                            cand.is_resolved
                                                ? "bg-emerald-50 text-emerald-700 border-emerald-300 dark:bg-emerald-500/20 dark:text-emerald-300 dark:border-emerald-500/40"
                                                : "bg-amber-50 text-amber-800 border-amber-300 dark:bg-amber-500/20 dark:text-amber-300 dark:border-amber-500/40"
                                        }`}
                                    >
                                        {cand.is_resolved ? "RESOLVED" : "IN PROGRESS"}
                                    </span>
                                </div>

                                {/* Defect & Equipment Line */}
                                <p className="font-bold text-gray-900 dark:text-white text-sm leading-snug">
                                    {cand.defect_name || cand.defect_code || "Dispense Defect"}
                                </p>

                                {(cand.material || cand.line_id || cand.method) && (
                                    <p className="mt-1 text-[11px] text-gray-500 dark:text-gray-300 flex items-center gap-1.5 truncate font-medium">
                                        {cand.material && <span>{cand.material}</span>}
                                        {cand.material && cand.line_id && <span>•</span>}
                                        {cand.line_id && <span>{cand.line_id}</span>}
                                        {(cand.material || cand.line_id) && cand.method && <span>•</span>}
                                        {cand.method && <span>{cand.method.replace("_", " ")}</span>}
                                    </p>
                                )}

                                {/* Matching Attribute Tags */}
                                {cand.matching_factors.length > 0 && (
                                    <div className="mt-2.5 flex flex-wrap gap-1.5">
                                        {cand.matching_factors.map((factor, idx) => (
                                            <span
                                                key={idx}
                                                className="inline-flex items-center gap-1 rounded-md bg-gray-100 dark:bg-[#202b3d] px-2 py-0.5 text-[10px] font-medium text-gray-700 dark:text-gray-200 border border-gray-200 dark:border-[#2e3e57]"
                                            >
                                                <Tag size={9} className="text-gray-400 dark:text-gray-400" />
                                                {factor}
                                            </span>
                                        ))}
                                    </div>
                                )}

                                {/* Confirmed Root Cause Callout */}
                                {cand.confirmed_causes.length > 0 && (
                                    <div className="mt-2.5 rounded-lg border border-purple-200 dark:border-purple-600/40 bg-purple-50/80 dark:bg-[#251a3d] p-2.5 text-[11px]">
                                        <div className="flex items-start gap-1.5">
                                            <CheckCircle2 size={13} className="text-purple-600 dark:text-purple-300 shrink-0 mt-0.5" />
                                            <div className="leading-snug">
                                                <strong className="text-purple-900 dark:text-purple-200 font-bold">Confirmed Cause: </strong>
                                                <span className="text-purple-950 dark:text-purple-100 font-medium">
                                                    {cand.confirmed_causes.join(", ")}
                                                </span>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {/* Resolution Action Taken */}
                                {cand.resolution_summary && (
                                    <div className="mt-2 rounded-lg border border-emerald-200 dark:border-emerald-600/40 bg-emerald-50/80 dark:bg-[#092a1e] p-2.5 text-[11px]">
                                        <div className="flex items-start gap-1.5">
                                            <Wrench size={13} className="text-emerald-600 dark:text-emerald-300 shrink-0 mt-0.5" />
                                            <div className="line-clamp-2 leading-snug">
                                                <strong className="text-emerald-900 dark:text-emerald-200 font-bold">Resolution: </strong>
                                                <span className="text-emerald-950 dark:text-emerald-100 font-medium">
                                                    {cand.resolution_summary}
                                                </span>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {/* Collapsible Description Drawer */}
                                {isExpanded && (
                                    <div className="mt-2.5 pt-2.5 border-t border-gray-200 dark:border-gray-800 text-[11px] text-gray-600 dark:text-gray-300 animate-in fade-in space-y-1">
                                        <p>
                                            <strong className="text-gray-900 dark:text-white font-bold">Technician Description:</strong> {cand.description}
                                        </p>
                                        {cand.created_at && (
                                            <div className="flex items-center gap-1 text-[10px] text-gray-500 dark:text-gray-400">
                                                <Clock size={11} />
                                                <span>
                                                    Logged {new Date(cand.created_at).toLocaleDateString()}
                                                </span>
                                            </div>
                                        )}
                                    </div>
                                )}

                                {/* Card Bottom Actions */}
                                <div className="mt-3 pt-2.5 border-t border-gray-200 dark:border-gray-800 flex items-center justify-between text-[11px]">
                                    <button
                                        type="button"
                                        onClick={() => setExpandedCaseId(isExpanded ? null : cand.case_id)}
                                        className="inline-flex items-center gap-1 text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white font-medium transition"
                                    >
                                        {isExpanded ? (
                                            <>
                                                <span>Less details</span>
                                                <ChevronUp size={12} />
                                            </>
                                        ) : (
                                            <>
                                                <span>View details</span>
                                                <ChevronDown size={12} />
                                            </>
                                        )}
                                    </button>

                                    <Link
                                        href={`/cases/${cand.case_id}`}
                                        className="inline-flex items-center gap-1 font-semibold text-[#5848e8] dark:text-[#a59bff] hover:text-[#6d5dfc] dark:hover:text-white transition"
                                    >
                                        <span>Open Case</span>
                                        <ArrowUpRight size={12} />
                                    </Link>
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
