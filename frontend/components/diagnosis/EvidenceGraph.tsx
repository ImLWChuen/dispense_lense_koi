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

const data = [
    {
        cause: "Nozzle Restriction",
        supports: 72,
        contradicts: -15,
    },
    {
        cause: "Air / Supply",
        supports: 54,
        contradicts: -22,
    },
    {
        cause: "Material Condition",
        supports: 38,
        contradicts: -18,
    },
    {
        cause: "Pressure Instability",
        supports: 22,
        contradicts: -31,
    },
    {
        cause: "Parameter Issue",
        supports: 15,
        contradicts: -12,
    },
];

export default function EvidenceGraph() {
    return (
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
            <div>
                <h2 className="text-base font-semibold text-gray-900">
                    Evidence Weight Distribution
                </h2>

                <p className="mt-1 text-xs text-gray-500">
                    Net evidence contribution per candidate cause
                </p>
            </div>

            <div className="mt-6 h-[350px]">
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                        data={data}
                        layout="vertical"
                        margin={{ top: 5, right: 20, left: 10, bottom: 5 }}
                    >
                        <CartesianGrid
                            horizontal={false}
                            strokeDasharray="3 3"
                        />

                        <XAxis
                            type="number"
                            tickLine={false}
                            axisLine={false}
                            fontSize={11}
                        />

                        <YAxis
                            dataKey="cause"
                            type="category"
                            width={120}
                            tickLine={false}
                            axisLine={false}
                            fontSize={11}
                        />

                        <Tooltip />
                        <Legend />

                        <Bar
                            dataKey="supports"
                            fill="#6d5dfc"
                            name="Supporting"
                            radius={[0, 4, 4, 0]}
                            barSize={18}
                        />

                        <Bar
                            dataKey="contradicts"
                            fill="#f87171"
                            name="Contradicting"
                            radius={[4, 0, 0, 4]}
                            barSize={18}
                        />
                    </BarChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}
