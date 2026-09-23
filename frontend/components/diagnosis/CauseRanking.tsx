"use client";

import { useState } from "react";
import CauseCard from "./CauseCard";
import { StarRating } from "./ConfidenceScore";
import { CandidateCause } from "@/types/api";
import { Sparkles, Table as TableIcon, LayoutList, HelpCircle } from "lucide-react";

interface CauseRankingProps {
    causes?: CandidateCause[];
    revision?: number;
}

export default function CauseRanking({ causes = [], revision = 1 }: CauseRankingProps) {
    const [viewMode, setViewMode] = useState<"table" | "cards">("table");

    if (causes.length === 0) {
        return (
            <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-6 shadow-sm">
                <p className="text-sm text-gray-500 dark:text-gray-400">No causes identified yet.</p>
            </div>
        );
    }

    const topCause = causes[0];

    // Derive deterministic causal "WHY" reasoning from supporting evidence (Step 4 - NSW Automation)
    let whyReasoning = "";
    if (topCause) {
        const topEv = topCause.supporting_evidence?.[0];
        if (topEv?.explanation) {
            whyReasoning = topEv.explanation;
        } else {
            // Contextual fallback based on cause category
            const lowerId = topCause.cause_id.toLowerCase();
            if (lowerId.includes("air")) {
                whyReasoning = "the dispensing volume changes occasionally rather than continuously, pointing toward air pocket entrapment.";
            } else if (lowerId.includes("nozzle")) {
                whyReasoning = "the flow restriction is localized to specific dispensing cycles or points.";
            } else if (lowerId.includes("material")) {
                whyReasoning = "material viscosity or pot-life aging is shifting fluid delivery rates.";
            } else if (lowerId.includes("parameter")) {
                whyReasoning = "dispense pressure and pulse duration settings are deviating from nominal process limits.";
            } else {
                whyReasoning = "equipment telemetry and inspection patterns correlate with mechanical variation.";
            }
        }
    }

    return (
        <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-6 shadow-sm">
            {/* Header with View Toggle */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-4 border-b border-gray-100 dark:border-gray-800">
                <div>
                    <h2 className="text-base font-bold text-gray-900 dark:text-white">
                        AI Cause Analysis & Troubleshooting Score
                    </h2>

                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                        Candidate causes evaluated and ranked by multi-source evidence likelihood
                    </p>
                </div>

                <div className="flex items-center gap-2">
                    <span className="rounded-full bg-[#eeebff] dark:bg-[#5848e8]/30 px-2.5 py-1 text-[10px] font-semibold text-[#5848e8] dark:text-[#a59bff]">
                        REVISION {revision}
                    </span>

                    <div className="flex items-center rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 p-0.5 text-xs">
                        <button
                            onClick={() => setViewMode("table")}
                            className={`flex items-center gap-1 rounded-md px-2 py-1 transition ${
                                viewMode === "table"
                                    ? "bg-white dark:bg-gray-900 text-gray-900 dark:text-white font-semibold shadow-2xs"
                                    : "text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
                            }`}
                            title="Score Table"
                        >
                            <TableIcon size={13} />
                            <span>Score Table</span>
                        </button>
                        <button
                            onClick={() => setViewMode("cards")}
                            className={`flex items-center gap-1 rounded-md px-2 py-1 transition ${
                                viewMode === "cards"
                                    ? "bg-white dark:bg-gray-900 text-gray-900 dark:text-white font-semibold shadow-2xs"
                                    : "text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
                            }`}
                            title="Detailed Cause Cards"
                        >
                            <LayoutList size={13} />
                            <span>Cards</span>
                        </button>
                    </div>
                </div>
            </div>

            {/* AI Logical Reasoning Callout ("WHY It Provides the Recommendation") */}
            {topCause && (
                <div className="mt-5 rounded-xl border border-indigo-100 dark:border-indigo-900/50 bg-[#faf9ff] dark:bg-indigo-950/20 p-4 text-xs">
                    <div className="flex items-center gap-1.5 mb-1 text-[#5848e8] dark:text-[#a59bff]">
                        <Sparkles size={14} className="shrink-0" />
                        <span className="font-bold uppercase tracking-wider text-[10px]">
                            AI Logical Reasoning
                        </span>
                    </div>
                    <p className="text-gray-800 dark:text-gray-200 leading-relaxed">
                        <span className="font-bold text-gray-900 dark:text-white">“{topCause.cause_name}</span> is ranked as the highest possible cause ({Math.round(topCause.score)}% likelihood) because {whyReasoning}”
                    </p>
                    <p className="mt-1 text-[11px] text-gray-500 dark:text-gray-400 italic">
                        Provides explainable engineering rationale rather than generic automated answers.
                    </p>
                </div>
            )}

            {/* NSW Step 4 Table View */}
            {viewMode === "table" ? (
                <div className="mt-5 overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-800">
                    <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-800 text-left text-xs">
                        <thead className="bg-gray-50/80 dark:bg-gray-800/80 text-[11px] font-semibold text-gray-600 dark:text-gray-300 uppercase tracking-wider">
                            <tr>
                                <th scope="col" className="py-3 pl-4 pr-3">Rank</th>
                                <th scope="col" className="px-3 py-3 font-bold text-gray-800 dark:text-gray-200">Possible Cause</th>
                                <th scope="col" className="px-3 py-3">AI Likelihood Score</th>
                                <th scope="col" className="px-3 py-3">Confidence Level</th>
                                <th scope="col" className="px-3 py-3">Conclusion Status</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100 dark:divide-gray-800 bg-white dark:bg-gray-900">
                            {causes.map((cause, index) => {
                                const score = Math.round(cause.score);
                                const isTop = index === 0;

                                return (
                                    <tr
                                        key={cause.cause_id}
                                        className={isTop ? "bg-indigo-50/30 dark:bg-indigo-950/20 font-medium" : "hover:bg-gray-50/50 dark:hover:bg-gray-800/50"}
                                    >
                                        <td className="py-3 pl-4 pr-3 whitespace-nowrap">
                                            <span className={`inline-flex h-6 w-6 items-center justify-center rounded-md text-[11px] font-bold ${
                                                isTop ? "bg-[#6d5dfc] text-white" : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400"
                                            }`}>
                                                {index + 1}
                                            </span>
                                        </td>
                                        <td className="px-3 py-3 whitespace-nowrap">
                                            <div className="flex flex-col">
                                                <span className="font-semibold text-gray-900 dark:text-white">
                                                    {cause.cause_name}
                                                </span>
                                                <span className="text-[10px] text-gray-400 dark:text-gray-500 font-mono">
                                                    {cause.cause_id}
                                                </span>
                                            </div>
                                        </td>
                                        <td className="px-3 py-3 whitespace-nowrap">
                                            <div className="flex items-center gap-2.5">
                                                <div className="h-2 w-16 overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
                                                    <div
                                                        className={`h-full rounded-full ${
                                                            score >= 70 ? "bg-[#6d5dfc]" : score >= 50 ? "bg-amber-500" : "bg-gray-400"
                                                        }`}
                                                        style={{ width: `${score}%` }}
                                                    />
                                                </div>
                                                <span className="font-bold text-gray-900 dark:text-white text-sm">{score}%</span>
                                            </div>
                                        </td>
                                        <td className="px-3 py-3 whitespace-nowrap">
                                            <StarRating score={score} />
                                        </td>
                                        <td className="px-3 py-3 whitespace-nowrap">
                                            <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                                                cause.conclusion === "CONFIRMED"
                                                    ? "bg-green-100 dark:bg-green-950/40 text-green-800 dark:text-green-300"
                                                    : cause.conclusion === "SUSPECTED"
                                                    ? "bg-amber-100 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300"
                                                    : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400"
                                            }`}>
                                                {cause.conclusion}
                                            </span>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            ) : (
                /* Cards View */
                <div className="mt-5 space-y-3">
                    {causes.map((cause, index) => {
                        const cardData = {
                            id: cause.cause_id,
                            name: cause.cause_name,
                            description: cause.description || "",
                            score: Math.round(cause.score),
                            conclusion: cause.conclusion,
                            evidenceCount: (cause.supporting_evidence?.length || 0) + (cause.contradicting_evidence?.length || 0) + (cause.neutral_evidence?.length || 0),
                            supportCount: cause.supporting_evidence?.length || 0,
                            contradictCount: cause.contradicting_evidence?.length || 0,
                        };
                        return (
                            <CauseCard
                                key={cause.cause_id}
                                cause={cardData}
                                rank={index + 1}
                            />
                        );
                    })}
                </div>
            )}
        </div>
    );
}
