import {
    ArrowRight,
    Lightbulb,
    TrendingUp,
} from "lucide-react";

export default function AiInsights() {
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
                        Stringing defects have increased across Dispensing
                        Line A over the last 7 days. Recent verified cases
                        show material viscosity as the most common
                        contributing factor.
                    </p>

                    <div className="mt-4 flex items-center gap-3">
                        <div className="flex items-center gap-1.5 text-xs font-semibold text-green-600">
                            <TrendingUp size={14} />
                            18% increase
                        </div>

                        <span className="text-xs text-gray-400">
              compared with previous period
            </span>
                    </div>

                    <button className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-[#5848e8] hover:text-[#6d5dfc]">
                        View related cases
                        <ArrowRight size={15} />
                    </button>
                </div>
            </div>
        </div>
    );
}