"use client";

import { useState } from "react";
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ReferenceLine,
    ResponsiveContainer,
} from "recharts";
import { SpcCapabilityMetrics, SpcDataPoint } from "@/lib/api/spc";
import { AlertTriangle, Info, CheckCircle2 } from "lucide-react";

interface SpcControlChartProps {
    dataPoints: SpcDataPoint[];
    metrics: SpcCapabilityMetrics;
}

interface CustomTooltipProps {
    active?: boolean;
    payload?: Array<{ payload: SpcDataPoint }>;
    unit?: string;
}

function CustomTooltip({ active, payload, unit = "" }: CustomTooltipProps) {
    if (!active || !payload || !payload.length) return null;
    const pt = payload[0].payload;

    return (
        <div className="rounded-xl border border-gray-200 bg-white p-3 shadow-lg text-xs space-y-1.5 min-w-[200px]">
            <div className="flex items-center justify-between border-b border-gray-100 pb-1">
                <span className="font-semibold text-gray-700">Sample #{pt.index}</span>
                <span className="text-gray-400 font-mono">{pt.timestamp}</span>
            </div>
            <div className="flex justify-between items-center font-mono">
                <span className="text-gray-500">Value:</span>
                <span className="font-bold text-gray-900">
                    {pt.value} {unit}
                </span>
            </div>
            {pt.moving_range !== null && pt.moving_range !== undefined && (
                <div className="flex justify-between items-center font-mono">
                    <span className="text-gray-500">Moving Range (MR):</span>
                    <span className="text-gray-700">
                        {pt.moving_range} {unit}
                    </span>
                </div>
            )}
            <div className="flex justify-between items-center">
                <span className="text-gray-500">Subgroup:</span>
                <span className="font-semibold text-[#6d5dfc]">{pt.subgroup_id}</span>
            </div>

            {pt.is_out_of_control && (
                <div className="mt-1 pt-1.5 border-t border-rose-100 bg-rose-50 -mx-3 -mb-3 p-2 rounded-b-xl">
                    <div className="flex items-center gap-1 text-rose-700 font-bold">
                        <AlertTriangle size={12} />
                        <span>Out of Control Violation:</span>
                    </div>
                    <ul className="list-disc list-inside text-[11px] text-rose-600 mt-0.5 space-y-0.5">
                        {pt.violations.map((v, i) => (
                            <li key={i}>{v.replace(/_/g, " ")}</li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    );
}

export default function SpcControlChart({ dataPoints, metrics }: SpcControlChartProps) {
    const [chartMode, setChartMode] = useState<"individuals" | "moving_range">("individuals");

    const violationCount = dataPoints.filter((d) => d.is_out_of_control).length;

    // Custom Dot Renderer
    const renderCustomDot = (props: any) => {
        const { cx, cy, payload } = props;
        if (!cx || !cy) return null;

        if (payload.is_out_of_control) {
            return (
                <g key={`dot-ooc-${payload.index}`}>
                    <circle cx={cx} cy={cy} r={6} fill="#ef4444" stroke="#ffffff" strokeWidth={2} />
                    <circle cx={cx} cy={cy} r={9} fill="none" stroke="#ef4444" strokeWidth={1.5} opacity={0.6} />
                </g>
            );
        }

        return (
            <circle
                key={`dot-${payload.index}`}
                cx={cx}
                cy={cy}
                r={3}
                fill="#6d5dfc"
                stroke="#ffffff"
                strokeWidth={1.5}
            />
        );
    };

    return (
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
            {/* Header with Mode Toggle and Legend */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-gray-100">
                <div>
                    <div className="flex items-center gap-2">
                        <h2 className="text-base font-bold text-gray-900">
                            {chartMode === "individuals"
                                ? `Individuals (X) Control Chart - ${metrics.parameter_label}`
                                : `Moving Range (MR) Control Chart - ${metrics.parameter_label}`}
                        </h2>
                        {violationCount > 0 ? (
                            <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2.5 py-0.5 text-xs font-semibold text-rose-700 border border-rose-200">
                                <AlertTriangle size={12} />
                                {violationCount} Alarm{violationCount > 1 ? "s" : ""}
                            </span>
                        ) : (
                            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 border border-emerald-200">
                                <CheckCircle2 size={12} />
                                In Statistical Control
                            </span>
                        )}
                    </div>
                    <p className="mt-1 text-xs text-gray-500">
                        Evaluated against Nelson / Western Electric statistical process control rules
                    </p>
                </div>

                {/* Chart Toggle */}
                <div className="flex items-center gap-1 bg-gray-100 p-1 rounded-xl">
                    <button
                        onClick={() => setChartMode("individuals")}
                        className={`rounded-lg px-3 py-1 text-xs font-medium transition ${
                            chartMode === "individuals"
                                ? "bg-white text-gray-900 shadow-sm font-semibold"
                                : "text-gray-500 hover:text-gray-900"
                        }`}
                    >
                        Individuals (X)
                    </button>
                    <button
                        onClick={() => setChartMode("moving_range")}
                        className={`rounded-lg px-3 py-1 text-xs font-medium transition ${
                            chartMode === "moving_range"
                                ? "bg-white text-gray-900 shadow-sm font-semibold"
                                : "text-gray-500 hover:text-gray-900"
                        }`}
                    >
                        Moving Range (MR)
                    </button>
                </div>
            </div>

            {/* Reference Legend */}
            <div className="mt-4 flex flex-wrap items-center gap-4 text-xs text-gray-600 bg-gray-50/60 p-2.5 rounded-xl border border-gray-100">
                {chartMode === "individuals" ? (
                    <>
                        <div className="flex items-center gap-1.5">
                            <div className="h-0.5 w-4 border-t-2 border-dashed border-rose-500" />
                            <span>USL ({metrics.usl})</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                            <div className="h-0.5 w-4 border-t-2 border-dashed border-amber-500" />
                            <span>UCL ({metrics.ucl})</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                            <div className="h-0.5 w-4 bg-[#6d5dfc]" />
                            <span className="font-semibold text-gray-800">CL ({metrics.cl})</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                            <div className="h-0.5 w-4 border-t-2 border-dashed border-amber-500" />
                            <span>LCL ({metrics.lcl})</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                            <div className="h-0.5 w-4 border-t-2 border-dashed border-rose-500" />
                            <span>LSL ({metrics.lsl})</span>
                        </div>
                    </>
                ) : (
                    <>
                        <div className="flex items-center gap-1.5">
                            <div className="h-0.5 w-4 border-t-2 border-dashed border-amber-500" />
                            <span>UCL(MR) ({metrics.ucl_mr})</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                            <div className="h-0.5 w-4 bg-[#6d5dfc]" />
                            <span className="font-semibold text-gray-800">CL(MR) ({metrics.cl_mr})</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                            <div className="h-0.5 w-4 bg-gray-300" />
                            <span>LCL(MR) (0.0)</span>
                        </div>
                    </>
                )}

                <div className="ml-auto flex items-center gap-1 text-gray-400 text-[11px]">
                    <Info size={13} />
                    <span>Red halo marks Nelson rule violation</span>
                </div>
            </div>

            {/* Recharts Container */}
            <div className="mt-4 h-[320px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={dataPoints} margin={{ top: 10, right: 30, left: 10, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                        <XAxis
                            dataKey="index"
                            tickLine={false}
                            axisLine={{ stroke: "#e2e8f0" }}
                            fontSize={11}
                            tick={{ fill: "#64748b" }}
                            tickFormatter={(idx) => `#${idx}`}
                        />
                        <YAxis
                            tickLine={false}
                            axisLine={{ stroke: "#e2e8f0" }}
                            fontSize={11}
                            tick={{ fill: "#64748b" }}
                            domain={
                                chartMode === "individuals"
                                    ? [
                                          Math.floor(metrics.lsl - (metrics.usl - metrics.lsl) * 0.1),
                                          Math.ceil(metrics.usl + (metrics.usl - metrics.lsl) * 0.1),
                                      ]
                                    : [0, Math.ceil(metrics.ucl_mr * 1.25)]
                            }
                            unit={` ${metrics.unit}`}
                        />
                        <Tooltip content={<CustomTooltip unit={metrics.unit} />} />

                        {chartMode === "individuals" ? (
                            <>
                                {/* Specification limits */}
                                <ReferenceLine
                                    y={metrics.usl}
                                    stroke="#ef4444"
                                    strokeDasharray="4 4"
                                    strokeWidth={1.5}
                                    label={{ value: "USL", position: "right", fill: "#ef4444", fontSize: 10 }}
                                />
                                <ReferenceLine
                                    y={metrics.lsl}
                                    stroke="#ef4444"
                                    strokeDasharray="4 4"
                                    strokeWidth={1.5}
                                    label={{ value: "LSL", position: "right", fill: "#ef4444", fontSize: 10 }}
                                />

                                {/* Control limits */}
                                <ReferenceLine
                                    y={metrics.ucl}
                                    stroke="#f59e0b"
                                    strokeDasharray="3 3"
                                    strokeWidth={1.5}
                                    label={{ value: "UCL", position: "right", fill: "#f59e0b", fontSize: 10 }}
                                />
                                <ReferenceLine
                                    y={metrics.cl}
                                    stroke="#6d5dfc"
                                    strokeWidth={2}
                                    label={{ value: "CL (X̄)", position: "right", fill: "#6d5dfc", fontSize: 10 }}
                                />
                                <ReferenceLine
                                    y={metrics.lcl}
                                    stroke="#f59e0b"
                                    strokeDasharray="3 3"
                                    strokeWidth={1.5}
                                    label={{ value: "LCL", position: "right", fill: "#f59e0b", fontSize: 10 }}
                                />

                                {/* Data Line */}
                                <Line
                                    type="monotone"
                                    dataKey="value"
                                    stroke="#6d5dfc"
                                    strokeWidth={2}
                                    dot={renderCustomDot}
                                    activeDot={{ r: 7, fill: "#5848e8" }}
                                    isAnimationActive={false}
                                />
                            </>
                        ) : (
                            <>
                                <ReferenceLine
                                    y={metrics.ucl_mr}
                                    stroke="#f59e0b"
                                    strokeDasharray="3 3"
                                    strokeWidth={1.5}
                                    label={{ value: "UCL(MR)", position: "right", fill: "#f59e0b", fontSize: 10 }}
                                />
                                <ReferenceLine
                                    y={metrics.cl_mr}
                                    stroke="#6d5dfc"
                                    strokeWidth={2}
                                    label={{ value: "MR̄", position: "right", fill: "#6d5dfc", fontSize: 10 }}
                                />

                                <Line
                                    type="monotone"
                                    dataKey="moving_range"
                                    stroke="#0284c7"
                                    strokeWidth={2}
                                    dot={{ r: 3, fill: "#0284c7" }}
                                    isAnimationActive={false}
                                />
                            </>
                        )}
                    </LineChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}
