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

const data = [
    { month: "Mar", defects: 18 },
    { month: "Apr", defects: 24 },
    { month: "May", defects: 21 },
    { month: "Jun", defects: 28 },
    { month: "Jul", defects: 22 },
    { month: "Aug", defects: 31 },
    { month: "Sep", defects: 26 },
];

export default function DefectChart() {
    return (
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
            <h2 className="text-base font-semibold text-gray-900">
                Monthly Defect Trend
            </h2>

            <p className="mt-1 text-xs text-gray-500">
                Total defects recorded per month
            </p>

            <div className="mt-6 h-[280px]">
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={data}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                        <XAxis
                            dataKey="month"
                            tickLine={false}
                            axisLine={false}
                            fontSize={11}
                        />
                        <YAxis
                            tickLine={false}
                            axisLine={false}
                            fontSize={11}
                        />
                        <Tooltip />
                        <Line
                            type="monotone"
                            dataKey="defects"
                            stroke="#6d5dfc"
                            strokeWidth={2}
                            dot={{ fill: "#6d5dfc", r: 4 }}
                        />
                    </LineChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}
