"use client";

import { SpcLineComparison } from "@/lib/api/spc";
import { Award, ShieldCheck, AlertTriangle, Cpu } from "lucide-react";

interface SpcLineMatrixProps {
    comparisons: SpcLineComparison[];
    unit: string;
    onSelectLine?: (lineId: string) => void;
    selectedLineId?: string;
}

export default function SpcLineMatrix({
    comparisons,
    unit,
    onSelectLine,
    selectedLineId,
}: SpcLineMatrixProps) {
    return (
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
            <div className="flex items-center justify-between mb-4">
                <div>
                    <h2 className="text-base font-bold text-gray-900">
                        Multi-Line Dispensing Capability Matrix
                    </h2>
                    <p className="mt-1 text-xs text-gray-500">
                        Comparing process capability indices (Cp / Cpk) and active control alarms across production bays
                    </p>
                </div>
                <div className="flex items-center gap-1 text-xs text-gray-400">
                    <Cpu size={14} />
                    <span>Cleanroom SMT Bay 4</span>
                </div>
            </div>

            <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                    <thead>
                        <tr className="border-b border-gray-200 bg-gray-50/75 text-gray-600 font-semibold">
                            <th className="py-3 px-4 rounded-l-xl">Line Identifier</th>
                            <th className="py-3 px-3">Dispense Technology</th>
                            <th className="py-3 px-3 text-right">Samples</th>
                            <th className="py-3 px-3 text-right">Mean (X̄)</th>
                            <th className="py-3 px-3 text-right">Std Dev (σ)</th>
                            <th className="py-3 px-3 text-right">Cp</th>
                            <th className="py-3 px-3 text-right">Cpk</th>
                            <th className="py-3 px-3 text-center">Nelson Alarms</th>
                            <th className="py-3 px-4 rounded-r-xl text-center">Quality Status</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                        {comparisons.map((c) => {
                            const isSelected = selectedLineId === c.line_id;
                            const isWorldClass = c.cpk >= 1.67;
                            const isCapable = c.cpk >= 1.33 && c.cpk < 1.67;
                            const isMarginal = c.cpk >= 1.0 && c.cpk < 1.33;

                            return (
                                <tr
                                    key={c.line_id}
                                    onClick={() => onSelectLine?.(c.line_id)}
                                    className={`transition cursor-pointer hover:bg-gray-50/80 ${
                                        isSelected ? "bg-[#6d5dfc]/5 font-medium" : ""
                                    }`}
                                >
                                    <td className="py-3 px-4 font-bold text-gray-900 flex items-center gap-2">
                                        <div
                                            className={`h-2.5 w-2.5 rounded-full ${
                                                isWorldClass
                                                    ? "bg-emerald-500"
                                                    : isCapable
                                                    ? "bg-blue-500"
                                                    : isMarginal
                                                    ? "bg-amber-500"
                                                    : "bg-rose-500"
                                            }`}
                                        />
                                        <span>{c.line_name}</span>
                                    </td>
                                    <td className="py-3 px-3 text-gray-600">{c.technology}</td>
                                    <td className="py-3 px-3 text-right font-mono text-gray-600">
                                        {c.sample_count}
                                    </td>
                                    <td className="py-3 px-3 text-right font-mono text-gray-900 font-semibold">
                                        {c.mean} {unit}
                                    </td>
                                    <td className="py-3 px-3 text-right font-mono text-gray-600">
                                        ±{c.std_dev} {unit}
                                    </td>
                                    <td className="py-3 px-3 text-right font-mono text-[#6d5dfc] font-semibold">
                                        {c.cp.toFixed(2)}
                                    </td>
                                    <td className="py-3 px-3 text-right font-mono font-bold text-gray-900">
                                        {c.cpk.toFixed(2)}
                                    </td>
                                    <td className="py-3 px-3 text-center">
                                        {c.violations_count > 0 ? (
                                            <span className="inline-flex items-center gap-1 font-mono font-semibold text-rose-600 bg-rose-50 px-2 py-0.5 rounded-full border border-rose-200">
                                                <AlertTriangle size={11} />
                                                {c.violations_count}
                                            </span>
                                        ) : (
                                            <span className="inline-flex items-center gap-1 font-mono text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full">
                                                0
                                            </span>
                                        )}
                                    </td>
                                    <td className="py-3 px-4 text-center">
                                        {isWorldClass ? (
                                            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 border border-emerald-200">
                                                <Award size={11} />
                                                World-Class
                                            </span>
                                        ) : isCapable ? (
                                            <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-semibold text-blue-700 border border-blue-200">
                                                <ShieldCheck size={11} />
                                                Capable
                                            </span>
                                        ) : isMarginal ? (
                                            <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-semibold text-amber-700 border border-amber-200">
                                                <AlertTriangle size={11} />
                                                Marginal
                                            </span>
                                        ) : (
                                            <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2.5 py-0.5 text-xs font-semibold text-rose-700 border border-rose-200">
                                                <AlertTriangle size={11} />
                                                Incapable
                                            </span>
                                        )}
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
