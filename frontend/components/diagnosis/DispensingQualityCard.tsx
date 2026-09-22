"use client";

import { Award, CheckCircle2, AlertTriangle, ShieldAlert, Sparkles } from "lucide-react";
import { computeDispensingQuality, DispensingQualityAssessment } from "@/lib/quality-assessment";
import { DurableCaseResponse } from "@/types/api";

interface DispensingQualityCardProps {
    caseData?: DurableCaseResponse;
    customAssessment?: DispensingQualityAssessment;
}

export default function DispensingQualityCard({
    caseData,
    customAssessment,
}: DispensingQualityCardProps) {
    const diagnosis = caseData?.diagnosis || caseData?.initial_diagnosis;
    const defectCode = caseData?.defect_code || (diagnosis as any)?.defect_code || "";
    const defectName = diagnosis?.defect_name || diagnosis?.defect || "";

    const assessment =
        customAssessment ||
        computeDispensingQuality({
            defectCode,
            defectName,
            observations: caseData?.observations as any,
        });

    const { overallScore, metrics, summary } = assessment;

    // Color theme based on overall score
    const getScoreBadgeStyles = (score: number) => {
        if (score >= 80) {
            return {
                bg: "bg-emerald-50 dark:bg-emerald-950/30",
                text: "text-emerald-700 dark:text-emerald-300",
                border: "border-emerald-200 dark:border-emerald-800",
                bar: "bg-emerald-500",
            };
        }
        if (score >= 65) {
            return {
                bg: "bg-blue-50 dark:bg-blue-950/30",
                text: "text-blue-700 dark:text-blue-300",
                border: "border-blue-200 dark:border-blue-800",
                bar: "bg-blue-600",
            };
        }
        if (score >= 50) {
            return {
                bg: "bg-amber-50 dark:bg-amber-950/30",
                text: "text-amber-700 dark:text-amber-300",
                border: "border-amber-200 dark:border-amber-800",
                bar: "bg-amber-500",
            };
        }
        return {
            bg: "bg-rose-50 dark:bg-rose-950/30",
            text: "text-rose-700 dark:text-rose-300",
            border: "border-rose-200 dark:border-rose-800",
            bar: "bg-rose-500",
        };
    };

    const overallStyles = getScoreBadgeStyles(overallScore);

    const metricItems = [
        {
            item: metrics.shape,
            color: "text-amber-400 dark:text-amber-300",
            barColor: "bg-indigo-500",
        },
        {
            item: metrics.size,
            color: "text-amber-400 dark:text-amber-300",
            barColor: "bg-blue-500",
        },
        {
            item: metrics.position,
            color: "text-amber-400 dark:text-amber-300",
            barColor: "bg-emerald-500",
        },
        {
            item: metrics.defectRisk,
            color: "text-amber-400 dark:text-amber-300",
            barColor: "bg-rose-500",
            isRisk: true,
        },
    ];

    return (
        <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm overflow-hidden">
            {/* Header */}
            <div className="border-b border-gray-100 dark:border-gray-800 px-6 py-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-purple-50 dark:bg-[#5848e8]/25 text-[#6d5dfc] dark:text-[#a59bff]">
                        <Award size={19} />
                    </div>
                    <div>
                        <div className="flex items-center gap-2">
                            <h3 className="text-sm font-bold text-gray-900 dark:text-white">
                                Dispensing Quality Assessment
                            </h3>
                            <span className="rounded bg-purple-50 dark:bg-[#5848e8]/20 text-[#5848e8] dark:text-[#a59bff] border border-purple-200 dark:border-[#5848e8]/40 px-1.5 py-0.2 text-[9px] font-bold uppercase tracking-wider">
                                Bonus Challenge 2
                            </span>
                        </div>
                        <p className="text-[11px] text-gray-500 dark:text-gray-400">
                            Multi-parameter fluid deposition quality scoring
                        </p>
                    </div>
                </div>

                {/* Overall Score Callout */}
                <div className="text-right flex items-center gap-2">
                    <div className="text-right">
                        <span className="text-[10px] uppercase font-bold text-gray-400 dark:text-gray-400 block leading-tight">
                            Overall Quality
                        </span>
                        <div className="flex items-baseline justify-end gap-1">
                            <span className="text-2xl font-black text-gray-900 dark:text-white tracking-tight">
                                {overallScore}
                            </span>
                            <span className="text-xs font-semibold text-gray-400 dark:text-gray-500">
                                / 100
                            </span>
                        </div>
                    </div>
                    <div
                        className={`flex h-11 w-11 items-center justify-center rounded-xl border ${overallStyles.border} ${overallStyles.bg}`}
                    >
                        <span className={`text-base font-black ${overallStyles.text}`}>
                            {overallScore}
                        </span>
                    </div>
                </div>
            </div>

            {/* Metrics Breakdown Grid */}
            <div className="p-6 space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                    {metricItems.map(({ item, color, barColor, isRisk }) => (
                        <div
                            key={item.key}
                            className="rounded-xl border border-gray-100 dark:border-gray-800 bg-gray-50/70 dark:bg-[#151d2d] p-3.5 flex flex-col justify-between"
                        >
                            <div className="flex items-center justify-between">
                                <span className="text-xs font-semibold text-gray-800 dark:text-gray-200">
                                    {item.name}
                                </span>
                                <span
                                    className={`text-sm tracking-wider font-mono select-none ${color}`}
                                    title={`${item.stars} out of 5 stars`}
                                >
                                    {item.starDisplay}
                                </span>
                            </div>

                            <p className="mt-1 text-[11px] text-gray-500 dark:text-gray-400 line-clamp-2 leading-relaxed">
                                {item.description}
                            </p>

                            <div className="mt-3 flex items-center justify-between text-[11px]">
                                <span className="text-gray-500 dark:text-gray-400 font-medium">
                                    {item.label}
                                </span>
                                <span className="font-bold text-gray-700 dark:text-gray-300">
                                    {item.score}%
                                </span>
                            </div>

                            {/* Progress bar */}
                            <div className="mt-1.5 h-1.5 w-full rounded-full bg-gray-200 dark:bg-gray-700/60 overflow-hidden">
                                <div
                                    className={`h-full rounded-full transition-all duration-500 ${barColor}`}
                                    style={{ width: `${item.score}%` }}
                                />
                            </div>
                        </div>
                    ))}
                </div>

                {/* Synthesis summary */}
                <div className="rounded-xl bg-[#faf9ff] dark:bg-[#191d38] border border-indigo-100 dark:border-indigo-900/40 p-3 flex items-start gap-2.5">
                    <Sparkles size={16} className="text-[#6d5dfc] dark:text-[#a59bff] shrink-0 mt-0.5" />
                    <p className="text-xs text-gray-700 dark:text-gray-300 leading-relaxed">
                        <strong className="text-gray-900 dark:text-white font-semibold">Quality Assessment Rationale: </strong>
                        {summary}
                    </p>
                </div>
            </div>
        </div>
    );
}
