import Link from "next/link";
import {
    ArrowRight,
    Lightbulb,
    TrendingUp,
} from "lucide-react";

interface AiInsightsProps {
    insightText?: string | null;
    trendText?: string | null;
}

export default function AiInsights({ insightText, trendText }: AiInsightsProps) {
    const text = insightText || "Continuous diagnostic monitoring active across all equipment. AI patterns and root-cause trends will populate automatically as cases progress.";
    const trend = trendText || "Real-time analysis";

    return (
        <div className="rounded-2xl border border-[#ded9ff] bg-[#faf9ff] p-6">
            <div className="flex items-start gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#eeebff] text-[#6d5dfc]">
                    <Lightbulb size={20} />
                </div>

                <div className="flex-1">
                    <div className="flex items-center gap-2">
                        <h2 className="text-base font-semibold text-gray-900">
                            AI Insight
                        </h2>

                        <span className="rounded-full bg-[#eeebff] px-2 py-0.5 text-[10px] font-semibold text-[#5848e8]">
                            PATTERN DETECTED
                        </span>
                    </div>

                    <p className="mt-2 text-sm leading-6 text-gray-600">
                        {text}
                    </p>

                    <div className="mt-4 flex items-center gap-3">
                        <div className="flex items-center gap-1.5 text-xs font-semibold text-green-600">
                            <TrendingUp size={14} />
                            {trend}
                        </div>

                        <span className="text-xs text-gray-400">
                            computed from active cases
                        </span>
                    </div>

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