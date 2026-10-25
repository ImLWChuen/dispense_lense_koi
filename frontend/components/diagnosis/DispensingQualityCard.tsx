"use client";

import { Award, CheckCircle2, AlertTriangle, ShieldAlert, Sparkles, Star } from "lucide-react";
import { computeDispensingQuality, DispensingQualityAssessment } from "@/lib/quality-assessment";
import { DurableCaseResponse } from "@/types/api";

/**
 * Props for DispensingQualityCard component.
 */
interface DispensingQualityCardProps {
    /** Case payload containing defect code and computer vision observations */
    caseData?: DurableCaseResponse;
    /** Optional pre-computed assessment override (e.g. from local image ROI editor) */
    customAssessment?: DispensingQualityAssessment;
}

/**
 * DispensingQualityCard
 * 
 * Multi-dimensional quality breakdown evaluating four essential fluid dispensing criteria:
 * 1. Shape Regularity (Circularity and aspect ratio)
 * 2. Size Accuracy (Volume and area deviation vs nominal recipe)
 * 3. Position Repeatability (XY centroid offset vs coordinate target)
 * 4. Defect Risk (Satellite droplet, void, or bridging likelihood)
 * 
 * Integrates visual star ratings, colored progress bars, and an AI rationale summary.
 */
export default function DispensingQualityCard({
    caseData,
    customAssessment,
}: DispensingQualityCardProps) {
    // Extract defect classifications to parameterize the quality computation
    const diagnosis = caseData?.diagnosis || caseData?.initial_diagnosis;
    const defectCode = caseData?.defect_code || (diagnosis as any)?.defect_code || "";
    const defectName = diagnosis?.defect_name || diagnosis?.defect || "";

    // Compute or adopt passed assessment
    const assessment =
        customAssessment ||
        computeDispensingQuality({
            defectCode,
            defectName,
            observations: caseData?.observations as any,
        });

    const { overallScore, metrics, summary } = assessment;

    // Ordered metrics list with specific brand accent colors
    const metricItems = [
        {
            item: metrics.shape,
            barColor: "bg-indigo-500",
        },
        {
            item: metrics.size,
            barColor: "bg-blue-500",
        },
        {
            item: metrics.position,
            barColor: "bg-emerald-500",
        },
        {
            item: metrics.defectRisk,
            barColor: "bg-rose-500",
            isRisk: true,
        },
    ];

    return (
        <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm overflow-hidden">
            {/* Header: Title, Description, and Aggregate Score Badge */}
            <div className="border-b border-gray-100 dark:border-gray-800 px-5 py-4 flex items-center justify-between gap-3">
                <div className="flex items-center gap-3 min-w-0">
                    <div 
                        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-purple-50 dark:bg-[#5848e8]/25 text-[#6d5dfc] dark:text-[#a59bff]"
                        aria-hidden="true"
                    >
                        <Award size={20} />
                    </div>
                    <div className="min-w-0">
                        <h3 className="text-sm font-bold text-gray-900 dark:text-white leading-tight truncate">
                            Dispensing Quality Assessment
                        </h3>
                        <p className="text-[11px] text-gray-500 dark:text-gray-400 mt-0.5 truncate">
                            Multi-parameter fluid deposition quality scoring
                        </p>
                    </div>
                </div>

                {/* Overall Score Callout */}
                <div className="text-right shrink-0 pl-2">
                    <span className="text-[10px] uppercase font-bold text-gray-400 dark:text-gray-400 block tracking-wider leading-none">
                        Overall Quality
                    </span>
                    <div className="flex items-baseline justify-end gap-1 mt-1">
                        <span className="text-2xl font-black text-gray-900 dark:text-white tracking-tight font-mono">
                            {overallScore}
                        </span>
                        <span className="text-xs font-semibold text-gray-400 dark:text-gray-500">
                            / 100
                        </span>
                    </div>
                </div>
            </div>

            {/* Metrics Breakdown Grid: 2x2 grid for Shape, Size, Position, Defect Risk */}
            <div className="p-5 space-y-4">
                <div className="grid grid-cols-2 gap-3">
                    {metricItems.map(({ item, barColor }) => (
                        <div
                            key={item.key}
                            className="rounded-xl border border-gray-100 dark:border-gray-800 bg-gray-50/70 dark:bg-[#151d2d] p-3 flex flex-col justify-between"
                        >
                            <div>
                                <div className="flex items-start justify-between gap-1">
                                    <h4 className="text-xs font-bold text-gray-900 dark:text-gray-100 leading-snug">
                                        {item.name}
                                    </h4>
                                    <span className="text-xs font-bold font-mono text-gray-700 dark:text-gray-300 shrink-0">
                                        {item.score}%
                                    </span>
                                </div>

                                {/* 5-Star Rating Indicators */}
                                <div
                                    className="mt-1 flex items-center gap-0.5"
                                    title={`${item.stars} out of 5 stars`}
                                    aria-label={`${item.name} score: ${item.stars} out of 5 stars`}
                                >
                                    {[1, 2, 3, 4, 5].map((star) => (
                                        <Star
                                            key={star}
                                            size={12}
                                            aria-hidden="true"
                                            className={
                                                star <= item.stars
                                                    ? "fill-amber-400 text-amber-400 dark:fill-amber-400 dark:text-amber-400 shrink-0"
                                                    : "fill-gray-200 text-gray-200 dark:fill-gray-700 dark:text-gray-700 shrink-0"
                                            }
                                        />
                                    ))}
                                </div>

                                <p className="mt-2 text-[11px] text-gray-500 dark:text-gray-400 line-clamp-2 leading-relaxed">
                                    {item.description}
                                </p>
                            </div>

                            {/* Score progress bar */}
                            <div className="mt-3">
                                <div className="flex items-center justify-between text-[11px] mb-1">
                                    <span className="text-gray-600 dark:text-gray-300 font-medium truncate">
                                        {item.label}
                                    </span>
                                </div>

                                <div 
                                    className="h-1.5 w-full rounded-full bg-gray-200 dark:bg-gray-700/60 overflow-hidden"
                                    role="progressbar"
                                    aria-valuenow={item.score}
                                    aria-valuemin={0}
                                    aria-valuemax={100}
                                >
                                    <div
                                        className={`h-full rounded-full transition-all duration-500 ${barColor}`}
                                        style={{ width: `${item.score}%` }}
                                    />
                                </div>
                            </div>
                        </div>
                    ))}
                </div>

                {/* Synthesis Summary: Engineering rationale callout */}
                <div className="rounded-xl bg-[#faf9ff] dark:bg-[#191d38] border border-indigo-100 dark:border-indigo-900/40 p-3 flex items-start gap-2.5">
                    <Sparkles size={16} className="text-[#6d5dfc] dark:text-[#a59bff] shrink-0 mt-0.5" aria-hidden="true" />
                    <p className="text-xs text-gray-700 dark:text-gray-300 leading-relaxed">
                        <strong className="text-gray-900 dark:text-white font-semibold">Quality Assessment Rationale: </strong>
                        {summary}
                    </p>
                </div>
            </div>
        </div>
    );
}
