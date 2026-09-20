"use client";

import {
    Bar,
    BarChart,
    CartesianGrid,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from "recharts";
import { ResolutionDistributionItem } from "@/lib/api/analytics";
import { AlertCircle } from "lucide-react";

interface ResolutionChartProps {
    data?: ResolutionDistributionItem[];
}

export default function ResolutionChart({ data }: ResolutionChartProps) {
    const chartData = data ?? [];
    const hasData = chartData.length > 0 && chartData.some((d) => d.count > 0);

    return (
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
            <h2 className="text-base font-semibold text-gray-900">
                Resolution Time Distribution
            </h2>

            <p className="mt-1 text-xs text-gray-500">
                Time from case creation to resolution
            </p>

            <div className="mt-6 h-[280px]">
                {hasData ? (
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={chartData}>
                            <CartesianGrid
                                strokeDasharray="3 3"
                                vertical={false}
                                stroke="#f1f5f9"
                            />

                            <XAxis
                                dataKey="range"
                                tickLine={false}
                                axisLine={false}
                                fontSize={11}
                                tick={{ fill: "#64748b" }}
                            />

                            <YAxis
                                tickLine={false}
                                axisLine={false}
                                fontSize={11}
                                tick={{ fill: "#64748b" }}
                                allowDecimals={false}
                                domain={[0, "auto"]}
                            />

                            <Tooltip
                                formatter={(val: unknown) => [`${val} cases`, "Resolved Cases"]}
                                contentStyle={{
                                    backgroundColor: "#ffffff",
                                    borderRadius: "12px",
                                    border: "1px solid #e2e8f0",
                                    boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.05)",
                                    fontSize: "12px",
                                }}
                            />

                            <Bar
                                dataKey="count"
                                fill="#8b7ff7"
                                radius={[6, 6, 0, 0]}
                                barSize={32}
                            />
                        </BarChart>
                    </ResponsiveContainer>
                ) : (
                    <div className="flex h-full flex-col items-center justify-center text-center">
                        <AlertCircle className="h-7 w-7 text-gray-300 mb-2" />
                        <p className="text-xs font-medium text-gray-500">No resolution duration data available</p>
                    </div>
                )}
            </div>
        </div>
    );
}
