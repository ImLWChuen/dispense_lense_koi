"use client";

import {
    Bar,
    BarChart,
    CartesianGrid,
    Legend,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from "recharts";
import { CandidateCause } from "@/types/api";

/**
 * Props for the EvidenceGraph component.
 */
interface EvidenceGraphProps {
    /** Ranked candidate causes with their underlying supporting and contradicting evidence contributions */
    rankedCauses?: CandidateCause[];
}

/**
 * EvidenceGraph
 * 
 * Horizontal diverging bar chart illustrating the positive (supporting) and negative
 * (contradicting) Bayesian score contributions for each root cause hypothesis.
 * Enables production engineers to visually inspect why certain causes scored higher or lower.
 */
export default function EvidenceGraph({ rankedCauses = [] }: EvidenceGraphProps) {
    // Empty state fallback when no candidate causes exist yet
    if (!rankedCauses || rankedCauses.length === 0) {
        return (
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                <h2 className="text-base font-semibold text-gray-900">
                    Evidence Weight Distribution
                </h2>
                <p className="mt-1 text-xs text-gray-500">
                    Net evidence contribution per candidate cause
                </p>
                <div className="mt-6 flex h-48 items-center justify-center rounded-xl border border-dashed border-gray-200 bg-gray-50/50">
                    <p className="text-xs text-gray-500 italic">
                        No candidate causes available for evidence charting.
                    </p>
                </div>
            </div>
        );
    }

    // Aggregate numeric score contributions per cause
    const chartData = rankedCauses.map((cause) => {
        let supports = 0;
        let contradicts = 0;

        // Sum supporting evidence deltas
        if (Array.isArray(cause.supporting_evidence)) {
            for (const ev of cause.supporting_evidence) {
                if (typeof ev.score_contribution === "number" && Number.isFinite(ev.score_contribution)) {
                    supports += ev.score_contribution;
                }
            }
        }

        // Sum contradicting evidence deltas
        if (Array.isArray(cause.contradicting_evidence)) {
            for (const ev of cause.contradicting_evidence) {
                if (typeof ev.score_contribution === "number" && Number.isFinite(ev.score_contribution)) {
                    contradicts += ev.score_contribution;
                }
            }
        }

        return {
            cause: cause.cause_name || cause.name || cause.cause_id,
            supports: Number(supports.toFixed(2)),
            contradicts: Number(contradicts.toFixed(2)),
            finalScore: Number(cause.score.toFixed(1)),
        };
    });

    return (
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
            {/* Header: Title and explanation */}
            <div>
                <h2 className="text-base font-semibold text-gray-900">
                    Evidence Weight Distribution
                </h2>

                <p className="mt-1 text-xs text-gray-500">
                    Net score contribution per candidate cause derived from evaluated observations
                </p>
            </div>

            {/* Recharts Bar Visualization */}
            <div className="mt-6 h-[350px]">
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                        data={chartData}
                        layout="vertical"
                        margin={{ top: 5, right: 20, left: 20, bottom: 5 }}
                    >
                        <CartesianGrid horizontal={false} strokeDasharray="3 3" />

                        {/* X-Axis: Magnitude of evidence score delta */}
                        <XAxis
                            type="number"
                            tickLine={false}
                            axisLine={false}
                            fontSize={11}
                        />

                        {/* Y-Axis: Cause names */}
                        <YAxis
                            dataKey="cause"
                            type="category"
                            width={140}
                            tickLine={false}
                            axisLine={false}
                            fontSize={11}
                        />

                        <Tooltip />
                        <Legend />

                        {/* Positive Supporting Bar */}
                        <Bar
                            dataKey="supports"
                            fill="#6d5dfc"
                            name="Supporting Contribution"
                            radius={[0, 4, 4, 0]}
                            barSize={18}
                        />

                        {/* Negative Contradicting Bar */}
                        <Bar
                            dataKey="contradicts"
                            fill="#f87171"
                            name="Contradicting Contribution"
                            radius={[4, 0, 0, 4]}
                            barSize={18}
                        />
                    </BarChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}
