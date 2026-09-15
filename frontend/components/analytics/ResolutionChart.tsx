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

const data = [
    { range: "0-5 min", count: 18 },
    { range: "5-10 min", count: 34 },
    { range: "10-15 min", count: 28 },
    { range: "15-20 min", count: 15 },
    { range: "20-30 min", count: 9 },
    { range: "30+ min", count: 4 },
];

export default function ResolutionChart() {
    return (
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
            <h2 className="text-base font-semibold text-gray-900">
                Resolution Time Distribution
            </h2>

            <p className="mt-1 text-xs text-gray-500">
                Time from case creation to resolution
            </p>

            <div className="mt-6 h-[280px]">
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={data}>
                        <CartesianGrid
                            strokeDasharray="3 3"
                            vertical={false}
                        />

                        <XAxis
                            dataKey="range"
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

                        <Bar
                            dataKey="count"
                            fill="#8b7ff7"
                            radius={[6, 6, 0, 0]}
                            barSize={32}
                        />
                    </BarChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}
