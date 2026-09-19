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

interface EvidenceGraphProps {
    rankedCauses?: CandidateCause[];
}

export default function EvidenceGraph({ rankedCauses = [] }: EvidenceGraphProps) {
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

    const chartData = rankedCauses.map((cause) => {
        let support = 0;
        let contradict = 0;

        if (cause.score_breakdown) {
            if (typeof cause.score_breakdown.positive_evidence === "number") {
                support = cause.score_breakdown.positive_evidence;
            } else if (typeof cause.score_breakdown.support === "number") {
                support = cause.score_breakdown.support;
            }

            if (typeof cause.score_breakdown.contradiction_penalty === "number") {
                contradict = cause.score_breakdown.contradiction_penalty;
            } else if (typeof cause.score_breakdown.contradict === "number") {
                contradict = cause.score_breakdown.contradict;
            }
        }

        // Fallback: derive directly from score_contribution of evaluated evidence
        if (support === 0 && Array.isArray(cause.supporting_evidence)) {
            cause.supporting_evidence.forEach((ev) => {
                if (typeof ev.score_contribution === "number") {
                    support += ev.score_contribution;
                }
            });
        }

        if (contradict === 0 && Array.isArray(cause.contradicting_evidence)) {
            cause.contradicting_evidence.forEach((ev) => {
                if (typeof ev.score_contribution === "number") {
                    contradict += ev.score_contribution;
                }
            });
        }

        return {
            cause: cause.cause_name,
            supports: Number(support.toFixed(2)),
            contradicts: Number(contradict.toFixed(2)),
            finalScore: Number(cause.score.toFixed(1)),
        };
    });

    return (
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
            <div>
                <h2 className="text-base font-semibold text-gray-900">
                    Evidence Weight Distribution
                </h2>

                <p className="mt-1 text-xs text-gray-500">
                    Net score contribution per candidate cause derived from evaluated observations
                </p>
            </div>

            <div className="mt-6 h-[350px]">
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                        data={chartData}
                        layout="vertical"
                        margin={{ top: 5, right: 20, left: 20, bottom: 5 }}
                    >
                        <CartesianGrid horizontal={false} strokeDasharray="3 3" />

                        <XAxis
                            type="number"
                            tickLine={false}
                            axisLine={false}
                            fontSize={11}
                        />

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

                        <Bar
                            dataKey="supports"
                            fill="#6d5dfc"
                            name="Supporting Contribution"
                            radius={[0, 4, 4, 0]}
                            barSize={18}
                        />

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
