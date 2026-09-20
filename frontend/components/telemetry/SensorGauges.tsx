"use client";

import { SensorReading, SensorStatus } from "@/lib/api/telemetry";
import {
    Activity,
    AlertTriangle,
    CheckCircle2,
    Gauge,
    Layers,
    Thermometer,
    Wind,
} from "lucide-react";

interface SensorGaugesProps {
    reading: SensorReading;
    iconType?: "pressure" | "vacuum" | "temperature" | "generic";
}

export default function SensorGauges({
    reading,
    iconType = "generic",
}: SensorGaugesProps) {
    const delta = reading.value - reading.target;
    const deltaFormatted = `${delta >= 0 ? "+" : ""}${delta.toFixed(2)}`;

    // SVG Sparkline rendering
    const points = reading.sparkline || [reading.value];
    const minVal = Math.min(...points, reading.lsl);
    const maxVal = Math.max(...points, reading.usl);
    const range = maxVal - minVal || 1.0;

    const width = 160;
    const height = 42;

    const svgPoints = points
        .map((val, idx) => {
            const x = (idx / (points.length - 1 || 1)) * width;
            const y = height - ((val - minVal) / range) * (height - 8) - 4;
            return `${x},${y}`;
        })
        .join(" ");

    const iconNode = () => {
        switch (iconType) {
            case "pressure":
                return <Gauge size={18} className="text-blue-600" />;
            case "vacuum":
                return <Wind size={18} className="text-cyan-600" />;
            case "temperature":
                return <Thermometer size={18} className="text-amber-600" />;
            default:
                return <Layers size={18} className="text-emerald-600" />;
        }
    };

    return (
        <div className="flex flex-col justify-between rounded-2xl border border-gray-200 bg-white p-5 shadow-xs transition hover:shadow-md">
            <div>
                {/* Header: Icon, Name, and Status */}
                <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2.5">
                        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gray-50 border border-gray-100">
                            {iconNode()}
                        </div>
                        <div>
                            <h4 className="text-sm font-semibold text-gray-800">
                                {reading.name}
                            </h4>
                            <span className="text-[11px] font-mono text-gray-400">
                                {reading.sensor_id}
                            </span>
                        </div>
                    </div>

                    <div>
                        {reading.status === "NOMINAL" && (
                            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-bold text-emerald-700 border border-emerald-200">
                                <CheckCircle2 size={11} />
                                NOMINAL
                            </span>
                        )}
                        {reading.status === "WARNING" && (
                            <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-bold text-amber-700 border border-amber-200">
                                <AlertTriangle size={11} />
                                DRIFT
                            </span>
                        )}
                        {reading.status === "CRITICAL" && (
                            <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2 py-0.5 text-[11px] font-bold text-rose-700 border border-rose-200 animate-pulse">
                                <AlertTriangle size={11} />
                                OUT OF SPEC
                            </span>
                        )}
                    </div>
                </div>

                {/* Primary Metric & Target Delta */}
                <div className="my-4 flex items-baseline justify-between">
                    <div className="flex items-baseline gap-1.5">
                        <span className="text-3xl font-black tracking-tight text-gray-900 font-mono">
                            {reading.value.toFixed(1)}
                        </span>
                        <span className="text-sm font-semibold text-gray-500">
                            {reading.unit}
                        </span>
                    </div>

                    <div className="text-right">
                        <span className="text-[11px] font-medium text-gray-400 block">
                            Target Bias
                        </span>
                        <span
                            className={`text-xs font-mono font-bold ${
                                Math.abs(delta) > (reading.usl - reading.target) * 0.5
                                    ? "text-amber-600"
                                    : "text-gray-600"
                            }`}
                        >
                            {deltaFormatted} {reading.unit}
                        </span>
                    </div>
                </div>

                {/* Sparkline Trend Graph */}
                <div className="my-2 rounded-xl bg-gray-50 p-2 border border-gray-100/80">
                    <div className="flex justify-between text-[10px] text-gray-400 mb-1">
                        <span>Trend (Last 25 Samples)</span>
                        <span>Now</span>
                    </div>
                    <svg className="w-full h-11 overflow-visible" viewBox={`0 0 ${width} ${height}`}>
                        <polyline
                            fill="none"
                            stroke={
                                reading.status === "CRITICAL"
                                    ? "#f43f5e"
                                    : reading.status === "WARNING"
                                    ? "#f59e0b"
                                    : "#6366f1"
                            }
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            points={svgPoints}
                        />
                        {/* Current point beacon */}
                        {points.length > 0 && (
                            <circle
                                cx={width}
                                cy={height - ((points[points.length - 1] - minVal) / range) * (height - 8) - 4}
                                r="3.5"
                                fill={
                                    reading.status === "CRITICAL"
                                        ? "#f43f5e"
                                        : reading.status === "WARNING"
                                        ? "#f59e0b"
                                        : "#6366f1"
                                }
                            />
                        )}
                    </svg>
                </div>
            </div>

            {/* Tolerance Band Meter Footer */}
            <div className="mt-2 pt-3 border-t border-gray-100">
                <div className="flex justify-between text-[11px] font-medium text-gray-400 mb-1">
                    <span>LSL: {reading.lsl}</span>
                    <span className="font-semibold text-gray-600">Target: {reading.target}</span>
                    <span>USL: {reading.usl}</span>
                </div>
                {/* Horizontal range bar */}
                <div className="relative h-1.5 w-full rounded-full bg-gray-200 overflow-hidden">
                    <div
                        className="absolute top-0 bottom-0 bg-emerald-500/20"
                        style={{
                            left: "20%",
                            right: "20%",
                        }}
                    />
                    <div
                        className={`absolute top-0 bottom-0 w-2 rounded-full ${
                            reading.status === "CRITICAL"
                                ? "bg-rose-500"
                                : reading.status === "WARNING"
                                ? "bg-amber-500"
                                : "bg-emerald-500"
                        }`}
                        style={{
                            left: `${Math.min(95, Math.max(5, ((reading.value - reading.lsl) / (reading.usl - reading.lsl)) * 100))}%`,
                            transform: "translateX(-50%)",
                        }}
                    />
                </div>
            </div>
        </div>
    );
}
