"use client";

import { SpcCapabilityMetrics } from "@/lib/api/spc";
import { Award, Target, TrendingUp, AlertTriangle, ShieldCheck, Activity } from "lucide-react";

interface SpcMetricCardsProps {
    metrics?: SpcCapabilityMetrics;
    isLoading?: boolean;
}

export default function SpcMetricCards({ metrics, isLoading }: SpcMetricCardsProps) {
    if (isLoading || !metrics) {
        return (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
                {[1, 2, 3, 4].map((i) => (
                    <div
                        key={i}
                        className="h-32 rounded-2xl border border-gray-200 bg-white p-6 shadow-sm animate-pulse flex flex-col justify-between"
                    >
                        <div className="h-4 w-24 bg-gray-200 rounded" />
                        <div className="h-8 w-16 bg-gray-200 rounded" />
                        <div className="h-3 w-32 bg-gray-100 rounded" />
                    </div>
                ))}
            </div>
        );
    }

    const isWorldClass = metrics.capability_status === "WORLD_CLASS";
    const isCapable = metrics.capability_status === "CAPABLE";
    const isMarginal = metrics.capability_status === "MARGINAL";

    const statusBadge = isWorldClass ? (
        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-700 border border-emerald-200">
            <Award size={12} />
            Six-Sigma World-Class
        </span>
    ) : isCapable ? (
        <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-xs font-semibold text-blue-700 border border-blue-200">
            <ShieldCheck size={12} />
            Capable (Meets Spec)
        </span>
    ) : isMarginal ? (
        <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-xs font-semibold text-amber-700 border border-amber-200">
            <AlertTriangle size={12} />
            Marginal Attention
        </span>
    ) : (
        <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2 py-0.5 text-xs font-semibold text-rose-700 border border-rose-200">
            <AlertTriangle size={12} />
            Incapable (Action Req)
        </span>
    );

    return (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
            {/* Cpk Card */}
            <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm hover:shadow-md transition">
                <div className="flex items-center justify-between">
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                        Process Capability (Cpk)
                    </p>
                    {statusBadge}
                </div>
                <div className="mt-3 flex items-baseline gap-2">
                    <span className="text-3xl font-bold font-mono text-gray-900">
                        {metrics.cpk.toFixed(2)}
                    </span>
                    <span className="text-xs text-gray-400 font-medium">Target ≥ 1.67</span>
                </div>
                <p className="mt-2 text-xs text-gray-500 line-clamp-1">
                    {metrics.status_description}
                </p>
            </div>

            {/* Cp (Potential Capability) Card */}
            <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm hover:shadow-md transition">
                <div className="flex items-center justify-between">
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                        Potential Index (Cp)
                    </p>
                    <span className="text-xs font-mono text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">
                        Pp = {metrics.pp.toFixed(2)}
                    </span>
                </div>
                <div className="mt-3 flex items-baseline gap-2">
                    <span className="text-3xl font-bold font-mono text-[#6d5dfc]">
                        {metrics.cp.toFixed(2)}
                    </span>
                    <span className="text-xs text-gray-400 font-medium">Spread Ratio</span>
                </div>
                <p className="mt-2 text-xs text-gray-500">
                    Tolerance width / (6 × σ) with zero mean offset
                </p>
            </div>

            {/* Mean & Target Bias */}
            <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm hover:shadow-md transition">
                <div className="flex items-center justify-between">
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                        Mean (X̄) vs Target (T)
                    </p>
                    <span
                        className={`text-xs font-mono px-2 py-0.5 rounded-full font-semibold ${
                            Math.abs(metrics.mean_offset) <= 0.5
                                ? "text-emerald-700 bg-emerald-50"
                                : "text-amber-700 bg-amber-50"
                        }`}
                    >
                        {metrics.mean_offset >= 0 ? `+${metrics.mean_offset}` : metrics.mean_offset}{" "}
                        {metrics.unit}
                    </span>
                </div>
                <div className="mt-3 flex items-baseline gap-2">
                    <span className="text-3xl font-bold font-mono text-gray-900">
                        {metrics.mean}
                    </span>
                    <span className="text-xs text-gray-500 font-medium">
                        {metrics.unit} (T = {metrics.target})
                    </span>
                </div>
                <p className="mt-2 text-xs text-gray-500">
                    USL: {metrics.usl} {metrics.unit} &nbsp;|&nbsp; LSL: {metrics.lsl} {metrics.unit}
                </p>
            </div>

            {/* Dispersion & Defect PPM */}
            <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm hover:shadow-md transition">
                <div className="flex items-center justify-between">
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                        Dispersion (σ) & PPM
                    </p>
                    <span className="text-xs font-mono text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full font-semibold">
                        {metrics.ppm_total < 1 ? "< 1.0 PPM" : `${metrics.ppm_total} PPM`}
                    </span>
                </div>
                <div className="mt-3 flex items-baseline gap-2">
                    <span className="text-3xl font-bold font-mono text-gray-900">
                        ±{metrics.std_dev_within}
                    </span>
                    <span className="text-xs text-gray-500 font-medium">{metrics.unit} (within)</span>
                </div>
                <p className="mt-2 text-xs text-gray-500">
                    s(overall) = {metrics.std_dev_overall} {metrics.unit} across {metrics.sample_count} samples
                </p>
            </div>
        </div>
    );
}
