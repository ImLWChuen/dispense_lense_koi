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
    {
        cause: "Material",
        cases: 42,
    },
    {
        cause: "Pressure",
        cases: 31,
    },
    {
        cause: "Nozzle",
        cases: 27,
    },
    {
        cause: "Calibration",
        cases: 21,
    },
    {
        cause: "Environment",
        cases: 14,
    },
];

export default function CauseDistribution() {
    return (
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
            <div>
                <h2 className="text-base font-semibold text-gray-900">
                    Top Probable Causes
                </h2>

                <p className="mt-1 text-xs text-gray-500">
                    Most frequently identified root-cause categories
                </p>
            </div>

            <div className="mt-6 h-[310px]">
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                        data={data}
                        layout="vertical"
                        margin={{
                            top: 5,
                            right: 10,
                            left: 10,
                            bottom: 5,
                        }}
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
                            width={80}
                            tickLine={false}
                            axisLine={false}
                            fontSize={11}
                        />

                        <Tooltip />

                        <Bar
                            dataKey="cases"
                            fill="#6d5dfc"
                            radius={[0, 6, 6, 0]}
                            barSize={24}
                        />
                    </BarChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}