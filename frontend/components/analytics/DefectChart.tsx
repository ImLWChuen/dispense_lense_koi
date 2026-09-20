"use client";

import {
    Line,
    LineChart,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
    CartesianGrid,
} from "recharts";
import { DefectTrendItem } from "@/lib/api/analytics";
import { AlertCircle } from "lucide-react";

interface DefectChartProps {
    data?: DefectTrendItem[];
}

export default function DefectChart({ data }: DefectChartProps) {
    const chartData = data ?? [];
    const hasData = chartData.length > 0 && chartData.some((d) => d.defects > 0);

    return (
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
            <h2 className="text-base font-semibold text-gray-900">
                Monthly Defect Trend
            </h2>

            <p className="mt-1 text-xs text-gray-500">
                Total defects recorded per month
            </p>

            <div className="mt-6 h-[280px]">
                {hasData ? (
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={chartData}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                            <XAxis
                                dataKey="month"
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
                                formatter={(val: unknown) => [`${val} defects`, "Defects"]}
                                contentStyle={{
                                    backgroundColor: "#ffffff",
                                    borderRadius: "12px",
                                    border: "1px solid #e2e8f0",
                                    boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.05)",
                                    fontSize: "12px",
                                }}
                            />
                            <Line
                                type="monotone"
                                dataKey="defects"
                                stroke="#6d5dfc"
                                strokeWidth={2.5}
                                dot={{ fill: "#6d5dfc", r: 4 }}
                                activeDot={{ r: 6, fill: "#5848e8" }}
                            />
                        </LineChart>
                    </ResponsiveContainer>
                ) : (
                    <div className="flex h-full flex-col items-center justify-center text-center">
                        <AlertCircle className="h-7 w-7 text-gray-300 mb-2" />
                        <p className="text-xs font-medium text-gray-500">No defect trend data available</p>
                    </div>
                )}
            </div>
        </div>
    );
}
