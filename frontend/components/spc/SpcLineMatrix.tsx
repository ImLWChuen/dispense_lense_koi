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
        <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-6 shadow-sm">
            <div className="flex items-center justify-between mb-4">
                <div>
                    <h2 className="text-base font-bold text-gray-900 dark:text-white">
                        Multi-Line Dispensing Capability Matrix
                    </h2>
                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                        Comparing process capability indices (Cp / Cpk) and active control alarms across production bays
                    </p>
                </div>
                <div className="flex items-center gap-1 text-xs text-gray-400 dark:text-gray-400">
                    <Cpu size={14} />
                    <span>Cleanroom SMT Bay 4</span>
                </div>
            </div>

            <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                    <thead>
                        <tr className="border-b border-gray-200 dark:border-gray-800 bg-gray-100 dark:bg-[#1a2436] text-gray-800 dark:text-white font-bold">
                            <th className="py-3.5 px-4 rounded-l-xl bg-gray-100 dark:bg-[#1a2436] text-gray-800 dark:text-white font-bold">Line Identifier</th>
                            <th className="py-3.5 px-3 bg-gray-100 dark:bg-[#1a2436] text-gray-800 dark:text-white font-bold">Dispense Technology</th>
                            <th className="py-3.5 px-3 text-right bg-gray-100 dark:bg-[#1a2436] text-gray-800 dark:text-white font-bold">Samples</th>
                            <th className="py-3.5 px-3 text-right bg-gray-100 dark:bg-[#1a2436] text-gray-800 dark:text-white font-bold">Mean (X̄)</th>
                            <th className="py-3.5 px-3 text-right bg-gray-100 dark:bg-[#1a2436] text-gray-800 dark:text-white font-bold">Std Dev (σ)</th>
                            <th className="py-3.5 px-3 text-right bg-gray-100 dark:bg-[#1a2436] text-gray-800 dark:text-white font-bold">Cp</th>
                            <th className="py-3.5 px-3 text-right bg-gray-100 dark:bg-[#1a2436] text-gray-800 dark:text-white font-bold">Cpk</th>
                            <th className="py-3.5 px-3 text-center bg-gray-100 dark:bg-[#1a2436] text-gray-800 dark:text-white font-bold">Nelson Alarms</th>
                            <th className="py-3.5 px-4 rounded-r-xl text-center bg-gray-100 dark:bg-[#1a2436] text-gray-800 dark:text-white font-bold">Quality Status</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100 dark:divide-gray-800/80">
                        {comparisons.map((c) => {
                            const isSelected = selectedLineId === c.line_id;
                            const isWorldClass = c.cpk >= 1.67;
                            const isCapable = c.cpk >= 1.33 && c.cpk < 1.67;
                            const isMarginal = c.cpk >= 1.0 && c.cpk < 1.33;

                            return (
                                <tr
                                    key={c.line_id}
                                    onClick={() => onSelectLine?.(c.line_id)}
                                    className={`border-b border-gray-100/70 dark:border-gray-800/60 last:border-b-0 transition cursor-pointer hover:bg-gray-50/80 dark:hover:bg-[#253347]/60 ${
                                        isSelected ? "bg-[#6d5dfc]/5 dark:bg-[#6d5dfc]/15 font-medium" : ""
                                    }`}
                                >
                                    <td className="py-3 px-4 font-bold text-gray-900 dark:text-white flex items-center gap-2">
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
                                    <td className="py-3 px-3 text-gray-600 dark:text-gray-300">{c.technology}</td>
                                    <td className="py-3 px-3 text-right font-mono text-gray-600 dark:text-gray-400">
                                        {c.sample_count}
                                    </td>
                                    <td className="py-3 px-3 text-right font-mono text-gray-900 dark:text-white font-semibold">
                                        {c.mean} {unit}
                                    </td>
                                    <td className="py-3 px-3 text-right font-mono text-gray-600 dark:text-gray-400">
                                        ±{c.std_dev} {unit}
                                    </td>
                                    <td className="py-3 px-3 text-right font-mono text-[#6d5dfc] dark:text-[#a59bff] font-semibold">
                                        {c.cp.toFixed(2)}
                                    </td>
                                    <td className="py-3 px-3 text-right font-mono font-bold text-gray-900 dark:text-white">
                                        {c.cpk.toFixed(2)}
                                    </td>
                                    <td className="py-3 px-3 text-center">
                                        {c.violations_count > 0 ? (
                                            <span className="inline-flex items-center gap-1 font-mono font-semibold text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-950/60 px-2 py-0.5 rounded-full border border-rose-200 dark:border-rose-800/60">
                                                <AlertTriangle size={11} />
                                                {c.violations_count}
                                            </span>
                                        ) : (
                                            <span className="inline-flex items-center gap-1 font-mono text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/60 px-2 py-0.5 rounded-full">
                                                0
                                            </span>
                                        )}
                                    </td>
                                    <td className="py-3 px-4 text-center">
                                        {isWorldClass ? (
                                            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 dark:bg-emerald-950/60 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800/60">
                                                <Award size={11} />
                                                World-Class
                                            </span>
                                        ) : isCapable ? (
                                            <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 dark:bg-blue-950/60 px-2.5 py-0.5 text-xs font-semibold text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800/60">
                                                <ShieldCheck size={11} />
                                                Capable
                                            </span>
                                        ) : isMarginal ? (
                                            <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 dark:bg-amber-950/60 px-2.5 py-0.5 text-xs font-semibold text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800/60">
                                                <AlertTriangle size={11} />
                                                Marginal
                                            </span>
                                        ) : (
                                            <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 dark:bg-rose-950/60 px-2.5 py-0.5 text-xs font-semibold text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-800/60">
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
