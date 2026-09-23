"use client";

import Link from "next/link";
import { Lightbulb, Database, ArrowRight, ShieldCheck, Sparkles } from "lucide-react";
import { getLearningInsight } from "@/lib/learning-database";
import { DurableCaseResponse } from "@/types/api";

interface LearningInsightBannerProps {
    caseData?: DurableCaseResponse;
    customDefectCode?: string;
    customDefectName?: string;
}

export default function LearningInsightBanner({
    caseData,
    customDefectCode,
    customDefectName,
}: LearningInsightBannerProps) {
    const diagnosis = caseData?.diagnosis || caseData?.initial_diagnosis;
    const defectCode = customDefectCode || caseData?.defect_code || (diagnosis as any)?.defect_code || "";
    const defectName = customDefectName || diagnosis?.defect_name || diagnosis?.defect || "";

    const insight = getLearningInsight(defectCode, defectName);

    return (
        <div className="relative overflow-hidden rounded-2xl border border-indigo-200 dark:border-indigo-800/80 bg-gradient-to-r from-[#f7f5ff] via-[#faf8ff] to-[#f0edff] dark:from-[#13162b] dark:via-[#161a35] dark:to-[#121630] p-5 shadow-sm">
            {/* Subtle background glow */}
            <div className="pointer-events-none absolute -right-12 -top-12 h-40 w-40 rounded-full bg-[#6d5dfc]/10 dark:bg-[#6d5dfc]/15 blur-2xl" />

            <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex items-start gap-3.5">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white dark:bg-gray-800 text-[#6d5dfc] dark:text-[#a59bff] shadow-sm border border-indigo-100 dark:border-gray-700">
                        <Sparkles size={20} />
                    </div>

                    <div className="space-y-1">
                        <div className="flex items-center gap-1.5">
                            <Database size={13} className="text-[#5848e8] dark:text-[#a59bff]" />
                            <span className="text-xs font-bold uppercase tracking-wider text-[#5848e8] dark:text-[#a59bff]">
                                AI Learning Database Insight
                            </span>
                        </div>

                        {/* Official NSW Wording */}
                        <p className="text-sm font-bold text-gray-900 dark:text-white leading-snug">
                            “{insight.insightText}”
                        </p>

                        <p className="text-xs text-gray-600 dark:text-gray-300 flex items-center gap-1.5 pt-0.5">
                            <ShieldCheck size={14} className="text-emerald-600 dark:text-emerald-400 shrink-0" />
                            <span>
                                <strong className="font-semibold text-gray-700 dark:text-gray-200">Historical Solution: </strong>
                                {insight.successfulSolution}
                            </span>
                        </p>
                    </div>
                </div>

                <div className="shrink-0 flex items-center gap-2 self-start md:self-center pl-13 md:pl-0">
                    <Link
                        href={`/knowledge-base?tab=Learning+Database&search=${encodeURIComponent(insight.problemTitle)}`}
                        className="inline-flex items-center gap-1.5 rounded-xl border border-indigo-200 dark:border-indigo-800 bg-white dark:bg-gray-800 px-3.5 py-2 text-xs font-semibold text-[#5848e8] dark:text-[#a59bff] hover:bg-[#faf9ff] dark:hover:bg-gray-700 shadow-xs transition group"
                    >
                        <span>Explore in Learning Database</span>
                        <ArrowRight
                            size={14}
                            className="transition-transform group-hover:translate-x-0.5"
                        />
                    </Link>
                </div>
            </div>
        </div>
    );
}
