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
    { cause: "Material", cases: 42 },
    { cause: "Pressure", cases: 31 },
    { cause: "Nozzle", cases: 27 },
    { cause: "Calibration", cases: 21 },
    { cause: "Environment", cases: 14 },
    { cause: "Valve", cases: 11 },
    { cause: "Substrate", cases: 8 },
];

export default function CauseChart() {
    return (
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
            <h2 className="text-base font-semibold text-gray-900">
                Root Cause Distribution
            </h2>

            <p className="mt-1 text-xs text-gray-500">
                Most frequently confirmed root causes
            </p>

            <div className="mt-6 h-[280px]">
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={data}>
                        <CartesianGrid
                            strokeDasharray="3 3"
                            vertical={false}
                        />

                        <XAxis
                            dataKey="cause"
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
                            dataKey="cases"
                            fill="#6d5dfc"
                            radius={[6, 6, 0, 0]}
                            barSize={32}
                        />
                    </BarChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}
