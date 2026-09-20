"use client";

import {
    ComposedChart,
    Bar,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ReferenceLine,
    ResponsiveContainer,
} from "recharts";
import { SpcCapabilityMetrics, SpcHistogramBin, SpcNormalCurvePoint } from "@/lib/api/spc";
import { Layers, CheckCircle2, TrendingUp, Info } from "lucide-react";

interface SpcCapabilityHistogramProps {
    histogram: SpcHistogramBin[];
    normalCurve: SpcNormalCurvePoint[];
    metrics: SpcCapabilityMetrics;
}

export default function SpcCapabilityHistogram({
    histogram,
    normalCurve,
    metrics,
}: SpcCapabilityHistogramProps) {
    // Merge histogram bins and smooth curve for ComposedChart or map histogram with scaled curve
    const maxBinCount = Math.max(...histogram.map((b) => b.count), 1);
    const maxPdf = Math.max(...histogram.map((b) => b.normal_pdf), 0.001);

    // Scale normal PDF to match bar height visually
    const chartData = histogram.map((bin) => {
        const scaledPdf = (bin.normal_pdf / maxPdf) * maxBinCount;
        return {
            bin_center: bin.bin_center,
            bin_range: `${bin.bin_start}–${bin.bin_end}`,
            count: bin.count,
            frequency: bin.frequency,
            normal_fit: Math.round(scaledPdf * 10) / 10,
        };
    });

    const isCentered = Math.abs(metrics.mean_offset) <= 0.5;

    return (
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-gray-100">
                <div>
                    <div className="flex items-center gap-2">
                        <h2 className="text-base font-bold text-gray-900">
                            Process Capability Distribution & Gaussian Fit
                        </h2>
                        <span
                            className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                                isCentered
                                    ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                                    : "bg-amber-50 text-amber-700 border border-amber-200"
                            }`}
                        >
                            <TrendingUp size={12} />
                            {isCentered ? "Process Well-Centered" : "Mean Shift Observed"}
                        </span>
                    </div>
                    <p className="mt-1 text-xs text-gray-500">
                        Measured sample frequencies vs fitted normal Gaussian curve relative to specification limits
                    </p>
                </div>

                {/* Metrics Pill */}
                <div className="flex items-center gap-3 text-xs font-mono">
                    <div className="bg-gray-50 px-3 py-1.5 rounded-xl border border-gray-200">
                        <span className="text-gray-500">Cpk: </span>
                        <span className="font-bold text-gray-900">{metrics.cpk.toFixed(2)}</span>
                    </div>
                    <div className="bg-gray-50 px-3 py-1.5 rounded-xl border border-gray-200">
                        <span className="text-gray-500">Target Bias: </span>
                        <span className="font-bold text-[#6d5dfc]">
                            {metrics.mean_offset >= 0 ? `+${metrics.mean_offset}` : metrics.mean_offset} {metrics.unit}
                        </span>
                    </div>
                </div>
            </div>

            {/* Reference Legend */}
            <div className="mt-4 flex flex-wrap items-center gap-4 text-xs text-gray-600 bg-gray-50/60 p-2.5 rounded-xl border border-gray-100">
                <div className="flex items-center gap-1.5">
                    <div className="h-3 w-3 rounded-sm bg-[#6d5dfc]/40 border border-[#6d5dfc]" />
                    <span>Sample Frequency (Bins)</span>
                </div>
                <div className="flex items-center gap-1.5">
                    <div className="h-0.5 w-4 bg-[#6d5dfc]" />
                    <span>Fitted Gaussian Curve (Normal)</span>
                </div>
                <div className="flex items-center gap-1.5">
                    <div className="h-0.5 w-4 border-t-2 border-dashed border-rose-500" />
                    <span>LSL ({metrics.lsl}) & USL ({metrics.usl})</span>
                </div>
                <div className="flex items-center gap-1.5">
                    <div className="h-0.5 w-4 border-t-2 border-dashed border-emerald-500" />
                    <span>Target ({metrics.target})</span>
                </div>
            </div>

            {/* Chart */}
            <div className="mt-4 h-[300px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={chartData} margin={{ top: 15, right: 30, left: 10, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                        <XAxis
                            dataKey="bin_center"
                            tickLine={false}
                            axisLine={{ stroke: "#e2e8f0" }}
                            fontSize={11}
                            tick={{ fill: "#64748b" }}
                            tickFormatter={(val) => `${val}`}
                            unit={` ${metrics.unit}`}
                        />
                        <YAxis
                            tickLine={false}
                            axisLine={{ stroke: "#e2e8f0" }}
                            fontSize={11}
                            tick={{ fill: "#64748b" }}
                            allowDecimals={false}
                            label={{ value: "Frequency Count", angle: -90, position: "insideLeft", fontSize: 10, fill: "#94a3b8" }}
                        />
                        <Tooltip
                            formatter={(value: any, name: any) => {
                                if (name === "count") return [`${value} samples`, "Observed Samples"];
                                if (name === "normal_fit") return [`${value} (scaled)`, "Fitted Normal Density"];
                                return [value, name];
                            }}
                            labelFormatter={(label: any) => `Bin Center: ${label} ${metrics.unit}`}
                            contentStyle={{
                                backgroundColor: "#ffffff",
                                borderRadius: "12px",
                                border: "1px solid #e2e8f0",
                                boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.05)",
                                fontSize: "12px",
                            }}
                        />

                        {/* Specification Reference Lines */}
                        <ReferenceLine
                            x={metrics.lsl}
                            stroke="#ef4444"
                            strokeDasharray="4 4"
                            strokeWidth={1.5}
                            label={{ value: "LSL", position: "top", fill: "#ef4444", fontSize: 10 }}
                        />
                        <ReferenceLine
                            x={metrics.target}
                            stroke="#10b981"
                            strokeDasharray="3 3"
                            strokeWidth={1.5}
                            label={{ value: "Target", position: "top", fill: "#10b981", fontSize: 10 }}
                        />
                        <ReferenceLine
                            x={metrics.mean}
                            stroke="#6d5dfc"
                            strokeWidth={2}
                            label={{ value: "Mean (X̄)", position: "top", fill: "#6d5dfc", fontSize: 10 }}
                        />
                        <ReferenceLine
                            x={metrics.usl}
                            stroke="#ef4444"
                            strokeDasharray="4 4"
                            strokeWidth={1.5}
                            label={{ value: "USL", position: "top", fill: "#ef4444", fontSize: 10 }}
                        />

                        {/* Histogram Bars */}
                        <Bar
                            dataKey="count"
                            fill="#6d5dfc"
                            opacity={0.35}
                            stroke="#6d5dfc"
                            strokeWidth={1}
                            radius={[4, 4, 0, 0]}
                        />

                        {/* Overlaid Smooth Normal Curve */}
                        <Line
                            type="monotone"
                            dataKey="normal_fit"
                            stroke="#6d5dfc"
                            strokeWidth={2.5}
                            dot={false}
                            isAnimationActive={false}
                        />
                    </ComposedChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}
