"use client";

import Link from "next/link";
import { Activity, CheckCircle2, AlertCircle, ArrowUpRight, Cpu } from "lucide-react";

interface LineStatus {
    id: string;
    name: string;
    machine: string;
    status: "nominal" | "warning" | "error";
    yieldRate: string;
    activeDefects: number;
}

const PRODUCTION_LINES: LineStatus[] = [
    {
        id: "Line A",
        name: "Line A",
        machine: "Asymtek 1",
        status: "nominal",
        yieldRate: "99.4%",
        activeDefects: 0,
    },
    {
        id: "Line B",
        name: "Line B",
        machine: "Camalot 2",
        status: "warning",
        yieldRate: "97.1%",
        activeDefects: 1,
    },
    {
        id: "Line C",
        name: "Line C",
        machine: "Nordson 3",
        status: "nominal",
        yieldRate: "98.8%",
        activeDefects: 0,
    },
    {
        id: "Line D",
        name: "Line D",
        machine: "PVA 4",
        status: "nominal",
        yieldRate: "99.1%",
        activeDefects: 0,
    },
];

export default function LineStatusRibbon() {
    return (
        <div className="rounded-2xl border border-gray-200/80 bg-white p-4 shadow-xs">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-3 pb-2.5 border-b border-gray-100">
                <div className="flex items-center gap-2">
                    <Cpu size={16} className="text-[#6d5dfc]" />
                    <h3 className="text-xs font-bold uppercase tracking-wider text-gray-700">
                        Dispensing Lines Status
                    </h3>
                    <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-700 border border-emerald-200">
                        4 Lines Active
                    </span>
                </div>

                <Link
                    href="/cases"
                    className="text-xs font-semibold text-[#6d5dfc] hover:underline inline-flex items-center gap-1 self-start sm:self-auto"
                >
                    View line defect logs <ArrowUpRight size={13} />
                </Link>
            </div>

            <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
                {PRODUCTION_LINES.map((line) => {
                    const isNominal = line.status === "nominal";
                    const isWarning = line.status === "warning";

                    return (
                        <Link
                            key={line.id}
                            href={`/cases?search=${encodeURIComponent(line.id)}`}
                            className="group flex flex-col justify-between rounded-xl border border-gray-100 bg-gray-50/50 p-3 transition hover:border-[#6d5dfc]/40 hover:bg-white hover:shadow-xs"
                        >
                            <div className="flex items-center justify-between">
                                <span className="font-bold text-xs text-gray-900 group-hover:text-[#6d5dfc]">
                                    {line.name}
                                </span>
                                <span
                                    className={`inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-bold ${
                                        isNominal
                                            ? "bg-emerald-50 text-emerald-700"
                                            : "bg-amber-50 text-amber-700"
                                    }`}
                                >
                                    <span
                                        className={`h-1.5 w-1.5 rounded-full ${
                                            isNominal ? "bg-emerald-500 animate-pulse" : "bg-amber-500"
                                        }`}
                                    />
                                    {isNominal ? "Nominal" : "Attention"}
                                </span>
                            </div>

                            <p className="text-[10px] text-gray-400 mt-0.5 font-mono">
                                {line.machine}
                            </p>

                            <div className="mt-2.5 flex items-center justify-between border-t border-gray-100/80 pt-2 text-[11px]">
                                <span className="text-gray-500 font-medium">Yield:</span>
                                <span className="font-bold text-gray-800 font-mono">{line.yieldRate}</span>
                            </div>
                        </Link>
                    );
                })}
            </div>
        </div>
    );
}
