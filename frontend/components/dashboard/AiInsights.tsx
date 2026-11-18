/**
 * AiInsights Component
 *
 * Displays high-level diagnostic intelligence summaries on the executive/line dashboard.
 * Highlights observed failure patterns, emergent defect clustering, and shifts
 * in verification confidence across active dispensing lines.
 */

import Link from "next/link";
import {
    ArrowRight,
    Lightbulb,
    TrendingUp,
} from "lucide-react";

/**
 * Props for the AiInsights component.
 */
interface AiInsightsProps {
    /** Summary text of observed diagnostic patterns or recommendations */
    insightText?: string | null;
    /** Trend description string (e.g. "+14% needle clog occurrences") */
    trendText?: string | null;
}

export default function AiInsights({ insightText, trendText }: AiInsightsProps) {
    // Fallback default message when no active anomaly pattern has crossed threshold
    const text = insightText || "Diagnostic monitoring active. Verified patterns and confirmed root-cause aggregates will populate automatically as cases progress.";
    const hasActiveInsight = Boolean(insightText);

    return (
        <div className="rounded-2xl border border-[#ded9ff] bg-[#faf9ff] p-6">
            <div className="flex items-start gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#eeebff] text-[#6d5dfc]">
                    <Lightbulb size={20} />
                </div>

                <div className="flex-1">
                    <div className="flex items-center gap-2">
                        <h2 className="text-base font-semibold text-gray-900">
                            Diagnostic Insight
                        </h2>

                        {hasActiveInsight ? (
                            <span className="rounded-full bg-[#eeebff] px-2 py-0.5 text-[10px] font-semibold text-[#5848e8]">
                                OBSERVED PATTERN
                            </span>
                        ) : (
                            <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-semibold text-gray-500">
                                MONITORING ACTIVE
                            </span>
                        )}
                    </div>

                    <p className="mt-2 text-sm leading-6 text-gray-600">
                        {text}
                    </p>

                    {trendText && (
                        <div className="mt-4 flex items-center gap-3">
                            <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-600">
                                <TrendingUp size={14} />
                                {trendText}
                            </div>

                            <span className="text-xs text-gray-400">
                                computed from active cases
                            </span>
                        </div>
                    )}

                    <Link
                        href="/cases"
                        className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-[#5848e8] hover:text-[#6d5dfc]"
                    >
                        View related cases
                        <ArrowRight size={15} />
                    </Link>
                </div>
            </div>
        </div>
    );
}