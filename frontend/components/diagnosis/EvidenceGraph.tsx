"use client";

import {
    Bar,
    BarChart,
    CartesianGrid,
    Legend,
    ReferenceLine,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from "recharts";
import { CandidateCause } from "@/types/api";
import { Info } from "lucide-react";

interface EvidenceGraphProps {
    causes?: CandidateCause[];
}

export default function EvidenceGraph({ causes = [] }: EvidenceGraphProps) {
    // Process real candidate causes
    const data = causes.map((c) => {
        // Calculate positive evidence contribution
        const supports = Math.round(
            c.score_breakdown?.positive_evidence ??
            (c.supporting_evidence || []).reduce((sum, item) => sum + (item.score_contribution || 0), 0)
        );

        // Calculate contradiction penalty (represented as negative for the chart layout)
        const contradictionPenalty = Math.round(
            c.score_breakdown?.contradiction_penalty ??
            (c.contradicting_evidence || []).reduce((sum, item) => sum + Math.abs(item.score_contribution || 0), 0)
        );

        const missingPenalty = Math.round(c.score_breakdown?.missing_penalty || 0);
        const base = Math.round(c.score_breakdown?.base || 30);
        const totalScore = Math.round(c.score);

        return {
            cause: c.cause_name,
            causeId: c.cause_id,
            supports,
            contradicts: -contradictionPenalty,
            contradictionPositive: contradictionPenalty,
            net: supports - contradictionPenalty,
            missingPenalty,
            base,
            totalScore,
            supportCount: (c.supporting_evidence || []).length,
            contradictCount: (c.contradicting_evidence || []).length,
        };
    });

    const hasAnyEvidence = data.some((d) => d.supports > 0 || d.contradicts < 0);
    const minVal = Math.min(0, ...data.map((d) => d.contradicts));
    const maxVal = Math.max(20, ...data.map((d) => d.supports));

    const chartHeight = Math.max(300, data.length * 48);

    const CustomTooltip = ({ active, payload }: any) => {
        if (!active || !payload || !payload.length) return null;
        const item = payload[0].payload;

        return (
            <div className="rounded-xl border border-gray-200 bg-white p-3.5 shadow-xl text-xs space-y-1.5 min-w-[220px]">
                <p className="font-bold text-gray-900 border-b border-gray-100 pb-1">
                    {item.cause}
                </p>
                <div className="flex items-center justify-between text-gray-600">
                    <span className="flex items-center gap-1.5">
                        <span className="h-2 w-2 rounded-full bg-[#6d5dfc]" />
                        Supporting Evidence:
                    </span>
                    <span className="font-semibold text-[#6d5dfc]">
                        +{item.supports} ({item.supportCount} {item.supportCount === 1 ? "rule" : "rules"})
                    </span>
                </div>
                <div className="flex items-center justify-between text-gray-600">
                    <span className="flex items-center gap-1.5">
                        <span className="h-2 w-2 rounded-full bg-[#f87171]" />
                        Contradictions:
                    </span>
                    <span className="font-semibold text-[#f87171]">
                        {item.contradicts < 0 ? `${item.contradicts}` : "0"} ({item.contradictCount} {item.contradictCount === 1 ? "rule" : "rules"})
                    </span>
                </div>
                {item.missingPenalty > 0 && (
                    <div className="flex items-center justify-between text-gray-600">
                        <span>Missing Penalty:</span>
                        <span className="font-semibold text-amber-600">-{item.missingPenalty}</span>
                    </div>
                )}
                <div className="flex items-center justify-between text-gray-600">
                    <span>Base Score:</span>
                    <span className="font-medium text-gray-800">{item.base}</span>
                </div>
                <div className="border-t border-gray-100 pt-1.5 flex items-center justify-between font-bold text-gray-900">
                    <span>Total Probability Score:</span>
                    <span className="text-[#5848e8]">{item.totalScore}%</span>
                </div>
            </div>
        );
    };

    return (
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                <div>
                    <h2 className="text-base font-semibold text-gray-900">
                        Evidence Weight Distribution
                    </h2>

                    <p className="mt-1 text-xs text-gray-500">
                        Net evidence contribution per candidate cause based on diagnostic rules
                    </p>
                </div>

                {!hasAnyEvidence && data.length > 0 && (
                    <div className="inline-flex items-center gap-1.5 rounded-lg bg-amber-50 px-2.5 py-1 text-[11px] font-medium text-amber-700">
                        <Info size={13} />
                        Baseline scores (no evidence rules matched yet)
                    </div>
                )}
            </div>

            {data.length === 0 ? (
                <div className="py-16 text-center text-xs text-gray-400">
                    No candidate causes available for this diagnosis.
                </div>
            ) : (
                <div className="mt-6" style={{ height: `${chartHeight}px` }}>
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart
                            data={data}
                            layout="vertical"
                            margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                        >
                            <CartesianGrid
                                horizontal={false}
                                strokeDasharray="3 3"
                                stroke="#f1f5f9"
                            />

                            <XAxis
                                type="number"
                                domain={[minVal, maxVal]}
                                tickLine={false}
                                axisLine={{ stroke: "#e2e8f0" }}
                                fontSize={11}
                            />

                            <YAxis
                                dataKey="cause"
                                type="category"
                                width={140}
                                tickLine={false}
                                axisLine={false}
                                fontSize={11}
                                stroke="#475569"
                            />

                            <ReferenceLine x={0} stroke="#94a3b8" strokeWidth={1.5} />

                            <Tooltip content={<CustomTooltip />} />
                            <Legend
                                wrapperStyle={{ paddingTop: "12px", fontSize: "12px" }}
                            />

                            <Bar
                                dataKey="supports"
                                fill="#6d5dfc"
                                name="Supporting Weight (+)"
                                radius={[0, 4, 4, 0]}
                                barSize={18}
                            />

                            <Bar
                                dataKey="contradicts"
                                fill="#f87171"
                                name="Contradiction Penalty (-)"
                                radius={[4, 0, 0, 4]}
                                barSize={18}
                            />
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            )}
        </div>
    );
}
