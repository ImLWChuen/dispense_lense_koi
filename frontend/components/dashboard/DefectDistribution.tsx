"use client";

import {
    Cell,
    Pie,
    PieChart,
    ResponsiveContainer,
    Tooltip,
} from "recharts";

const data = [
    {
        name: "Stringing",
        value: 32,
    },
    {
        name: "Under-dispensing",
        value: 24,
    },
    {
        name: "Inconsistent bead",
        value: 18,
    },
    {
        name: "Excess material",
        value: 15,
    },
    {
        name: "Other",
        value: 11,
    },
];

const COLORS = [
    "#6d5dfc",
    "#8b7ff7",
    "#a79ff9",
    "#c2bcfb",
    "#ddd9fd",
];

export default function DefectDistribution() {
    return (
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
            <div>
                <h2 className="text-base font-semibold text-gray-900">
                    Defect Distribution
                </h2>

                <p className="mt-1 text-xs text-gray-500">
                    Defects recorded this month
                </p>
            </div>

            <div className="mt-6 h-[260px]">
                <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                        <Pie
                            data={data}
                            dataKey="value"
                            nameKey="name"
                            cx="50%"
                            cy="50%"
                            innerRadius={70}
                            outerRadius={100}
                            paddingAngle={2}
                        >
                            {data.map((_, index) => (
                                <Cell
                                    key={`cell-${index}`}
                                    fill={COLORS[index]}
                                />
                            ))}
                        </Pie>

                        <Tooltip
                            formatter={(value) => [`${value}%`, "Cases"]}
                        />
                    </PieChart>
                </ResponsiveContainer>
            </div>

            <div className="mt-2 grid grid-cols-2 gap-3">
                {data.map((item, index) => (
                    <div
                        key={item.name}
                        className="flex items-center gap-2"
                    >
            <span
                className="h-2.5 w-2.5 rounded-full"
                style={{
                    backgroundColor: COLORS[index],
                }}
            />

                        <span className="text-xs text-gray-600">
              {item.name}
            </span>

                        <span className="ml-auto text-xs font-semibold text-gray-800">
              {item.value}%
            </span>
                    </div>
                ))}
            </div>
        </div>
    );
}