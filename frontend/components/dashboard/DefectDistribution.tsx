"use client";

import {
    Cell,
    Pie,
    PieChart,
    ResponsiveContainer,
    Tooltip,
} from "recharts";
import { DashboardDefectItem } from "@/lib/api/analytics";
import { AlertCircle } from "lucide-react";

const COLORS = [
    "#6d5dfc",
    "#8b7ff7",
    "#a79ff9",
    "#c2bcfb",
    "#ddd9fd",
];

interface DefectDistributionProps {
    data?: DashboardDefectItem[];
}

export default function DefectDistribution({ data = [] }: DefectDistributionProps) {
    const hasData = data && data.length > 0;

    return (
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
            <div>
                <h2 className="text-base font-semibold text-gray-900">
                    Defect Distribution
                </h2>

                <p className="mt-1 text-xs text-gray-500">
                    Defects recorded across cases
                </p>
            </div>

            <div className="mt-6 h-[260px]">
                {hasData ? (
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
                                        fill={COLORS[index % COLORS.length]}
                                    />
                                ))}
                            </Pie>

                            <Tooltip
                                formatter={(value: unknown, name: unknown, item: { payload?: { count?: number } }) => [
                                    `${String(value)}% (${item?.payload?.count ?? 1} cases)`,
                                    String(name),
                                ]}
                                contentStyle={{
                                    backgroundColor: "#ffffff",
                                    borderRadius: "12px",
                                    border: "1px solid #e2e8f0",
                                    boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.05)",
                                    fontSize: "12px",
                                }}
                            />
                        </PieChart>
                    </ResponsiveContainer>
                ) : (
                    <div className="flex h-full flex-col items-center justify-center text-center">
                        <AlertCircle className="h-7 w-7 text-gray-300 mb-2" />
                        <p className="text-xs font-medium text-gray-500">No defect distribution data</p>
                    </div>
                )}
            </div>

            {hasData && (
                <div className="mt-2 grid grid-cols-2 gap-3">
                    {data.map((item, index) => (
                        <div
                            key={item.name}
                            className="flex items-center gap-2"
                        >
                            <span
                                className="h-2.5 w-2.5 rounded-full shrink-0"
                                style={{
                                    backgroundColor: COLORS[index % COLORS.length],
                                }}
                            />

                            <span className="text-xs text-gray-600 truncate" title={item.name}>
                                {item.name}
                            </span>

                            <span className="ml-auto text-xs font-semibold text-gray-800">
                                {item.value}%
                            </span>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}