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
import { CauseDistributionItem } from "@/lib/api/analytics";
import { AlertCircle } from "lucide-react";

interface CauseDistributionProps {
    data?: CauseDistributionItem[];
}

export default function CauseDistribution({ data = [] }: CauseDistributionProps) {
    const hasData = data && data.length > 0;

    return (
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
            <div>
                <h2 className="text-base font-semibold text-gray-900">
                    Top Confirmed Causes
                </h2>

                <p className="mt-1 text-xs text-gray-500">
                    Confirmed root causes across cases
                </p>
            </div>

            <div className="mt-6 h-[310px]">
                {hasData ? (
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart
                            data={data}
                            layout="vertical"
                            margin={{
                                top: 5,
                                right: 20,
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
                                allowDecimals={false}
                            />

                            <YAxis
                                dataKey="cause"
                                type="category"
                                width={120}
                                tickLine={false}
                                axisLine={false}
                                fontSize={11}
                            />

                            <Tooltip
                                formatter={(value: unknown) => [`${value} cases`, "Cases"]}
                                contentStyle={{
                                    backgroundColor: "#ffffff",
                                    borderRadius: "12px",
                                    border: "1px solid #e2e8f0",
                                    boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.05)",
                                    fontSize: "12px",
                                }}
                            />

                            <Bar
                                dataKey="cases"
                                fill="#6d5dfc"
                                radius={[0, 6, 6, 0]}
                                barSize={24}
                            />
                        </BarChart>
                    </ResponsiveContainer>
                ) : (
                    <div className="flex h-full flex-col items-center justify-center text-center">
                        <AlertCircle className="h-7 w-7 text-gray-300 mb-2" />
                        <p className="text-xs font-medium text-gray-500">No confirmed root causes recorded yet</p>
                    </div>
                )}
            </div>
        </div>
    );
}