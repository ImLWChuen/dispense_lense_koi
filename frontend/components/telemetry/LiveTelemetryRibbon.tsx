"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
    ChevronDown,
    ChevronUp,
    Clock,
    ExternalLink,
    Gauge,
    Layers,
    Radio,
    Thermometer,
    Wind,
} from "lucide-react";
import {
    telemetryApi,
    TelemetryOverviewResponse,
    LineTelemetrySnapshot,
    ConsumableItem,
    PotLifeStatus,
} from "@/lib/api/telemetry";

function formatSecondsToHms(totalSeconds: number): string {
    if (totalSeconds <= 0) return "EXPIRED";
    const h = Math.floor(totalSeconds / 3600);
    const m = Math.floor((totalSeconds % 3600) / 60);
    const s = totalSeconds % 60;
    return `${h.toString().padStart(2, "0")}h ${m.toString().padStart(2, "0")}m ${s.toString().padStart(2, "0")}s`;
}

export default function LiveTelemetryRibbon() {
    const [overview, setOverview] = useState<TelemetryOverviewResponse | null>(null);
    const [selectedLineId, setSelectedLineId] = useState<string>("line-a");
    const [isExpanded, setIsExpanded] = useState<boolean>(() => {
        if (typeof window !== "undefined") {
            try {
                const saved = localStorage.getItem("dispenselens_telemetry_ribbon_expanded");
                if (saved !== null) return saved === "true";
            } catch {
                // Ignore storage errors
            }
        }
        return true;
    });
    const [currentTime, setCurrentTime] = useState<number>(() => Date.now());

    const toggleExpanded = () => {
        setIsExpanded((prev) => {
            const next = !prev;
            try {
                localStorage.setItem("dispenselens_telemetry_ribbon_expanded", String(next));
            } catch {
                // Ignore
            }
            return next;
        });
    };

    // Poll overview every 6 seconds
    useEffect(() => {
        let isMounted = true;
        const fetchOverview = async () => {
            try {
                const data = await telemetryApi.getOverview();
                if (isMounted) {
                    setOverview(data);
                }
            } catch (err) {
                console.warn("Failed to fetch telemetry overview:", err);
            }
        };

        fetchOverview();
        const interval = setInterval(fetchOverview, 6000);
        return () => {
            isMounted = false;
            clearInterval(interval);
        };
    }, []);

    // 1-second local tick for smooth countdown
    useEffect(() => {
        const timer = setInterval(() => {
            setCurrentTime(Date.now());
        }, 1000);
        return () => clearInterval(timer);
    }, []);

    if (!overview) {
        return null; // Silent until loaded
    }

    const currentLine: LineTelemetrySnapshot | undefined =
        overview.lines.find((l) => l.line_id === selectedLineId) || overview.lines[0];

    const mountedSyringe: ConsumableItem | undefined = overview.active_syringes.find(
        (s) => s.line_id === selectedLineId
    );

    // Compute live ticking pot life seconds
    let liveRemainingSeconds = 0;
    let potStatus: PotLifeStatus = "OPTIMAL";
    if (mountedSyringe) {
        if (mountedSyringe.pot_life_expiry_time) {
            const expiry = new Date(mountedSyringe.pot_life_expiry_time).getTime();
            liveRemainingSeconds = Math.max(0, Math.floor((expiry - currentTime) / 1000));
            if (liveRemainingSeconds <= 0) {
                potStatus = "EXPIRED";
            } else if (liveRemainingSeconds < 1800) {
                potStatus = "CRITICAL";
            } else if (liveRemainingSeconds < 7200) {
                potStatus = "WARNING";
            } else {
                potStatus = "OPTIMAL";
            }
        } else {
            liveRemainingSeconds = mountedSyringe.remaining_pot_life_seconds;
            potStatus = mountedSyringe.pot_life_status;
        }
    }

    return (
        <div className="border-b border-gray-200 bg-white/95 backdrop-blur-sm transition-all duration-200">
            {/* Main Bar / Compact Bar */}
            <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-2 sm:px-6">
                {/* Left: Cleanroom Facility & Active Line Selector */}
                <div className="flex flex-wrap items-center gap-2 sm:gap-4">
                    {/* Cleanroom ISO 5 status chip */}
                    <div className="flex items-center gap-2 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700 border border-emerald-200 shadow-2xs">
                        <span className="relative flex h-2 w-2">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                        </span>
                        <span className="font-bold">ISO 5</span>
                        <span className="hidden md:inline text-emerald-600 font-normal">
                            • {overview.environment.ambient_temp_c.toFixed(1)}°C • {overview.environment.relative_humidity_pct.toFixed(0)}% RH
                        </span>
                    </div>

                    {/* Line Tabs */}
                    <div className="flex items-center rounded-lg bg-gray-100 p-0.5 text-xs font-medium">
                        {overview.lines.map((line) => {
                            const isSelected = line.line_id === selectedLineId;
                            return (
                                <button
                                    key={line.line_id}
                                    onClick={() => setSelectedLineId(line.line_id)}
                                    className={`rounded-md px-2.5 py-1 transition-all ${
                                        isSelected
                                            ? "bg-white text-gray-900 font-semibold shadow-xs"
                                            : "text-gray-500 hover:text-gray-800"
                                    }`}
                                >
                                    {line.line_name}
                                </button>
                            );
                        })}
                    </div>

                    {/* Machine tech badge (desktop) */}
                    {currentLine && (
                        <span className="hidden xl:inline-block text-[11px] font-medium text-gray-400">
                            {currentLine.technology}
                        </span>
                    )}
                </div>

                {/* Right: Active Syringe Pot Life Ticker & Expand Button */}
                <div className="flex items-center gap-2 sm:gap-3">
                    {/* Syringe Pot Life Countdown Chip */}
                    {mountedSyringe ? (
                        <Link
                            href="/telemetry"
                            className={`flex items-center gap-2 rounded-lg px-2.5 py-1 text-xs font-medium border transition hover:opacity-90 ${
                                potStatus === "CRITICAL"
                                    ? "bg-rose-50 border-rose-300 text-rose-700 animate-pulse"
                                    : potStatus === "WARNING"
                                    ? "bg-amber-50 border-amber-300 text-amber-800"
                                    : potStatus === "EXPIRED"
                                    ? "bg-gray-100 border-gray-300 text-gray-600"
                                    : "bg-indigo-50 border-indigo-200 text-indigo-700"
                            }`}
                        >
                            <Clock size={13} className="shrink-0" />
                            <div className="flex items-center gap-1.5">
                                <span className="font-semibold hidden sm:inline">
                                    Pot Life:
                                </span>
                                <span className="font-mono font-bold tracking-tight">
                                    {formatSecondsToHms(liveRemainingSeconds)}
                                </span>
                                <span className="text-[10px] opacity-75 hidden lg:inline">
                                    ({mountedSyringe.material_name.split(" ")[0]})
                                </span>
                            </div>
                        </Link>
                    ) : (
                        <span className="text-xs text-gray-400 italic hidden sm:inline">
                            No syringe mounted
                        </span>
                    )}

                    {/* Quick Link to Telemetry Hub */}
                    <Link
                        href="/telemetry"
                        title="Open Telemetry & Pot Life Hub"
                        className="hidden md:flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-semibold text-[#5848e8] hover:bg-[#eeebff] transition"
                    >
                        <Radio size={13} />
                        <span>Telemetry</span>
                        <ExternalLink size={11} />
                    </Link>

                    {/* Collapse / Expand Toggle */}
                    <button
                        onClick={toggleExpanded}
                        aria-label={isExpanded ? "Collapse sensor telemetry" : "Expand sensor telemetry"}
                        className="flex h-7 w-7 items-center justify-center rounded-lg text-gray-400 hover:bg-gray-100 hover:text-gray-700 transition"
                    >
                        {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    </button>
                </div>
            </div>

            {/* Expanded Sensor Ribbon Detail */}
            {isExpanded && currentLine && (
                <div className="border-t border-gray-100 bg-gray-50/70 px-4 py-2 sm:px-6 transition-all">
                    <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-y-2 gap-x-4">
                        {/* 4 Sensor Pills */}
                        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 sm:gap-3 flex-1">
                            {/* Fluid Pressure */}
                            <div className="flex items-center gap-2 rounded-lg bg-white px-2.5 py-1.5 border border-gray-200/80 shadow-2xs">
                                <div className="flex h-7 w-7 items-center justify-center rounded-md bg-blue-50 text-blue-600">
                                    <Gauge size={14} />
                                </div>
                                <div>
                                    <div className="text-[10px] font-medium text-gray-400 leading-tight">
                                        Fluid Feed
                                    </div>
                                    <div className="text-xs font-bold text-gray-800">
                                        {currentLine.fluid_pressure.value.toFixed(1)}{" "}
                                        <span className="text-[10px] font-normal text-gray-500">
                                            {currentLine.fluid_pressure.unit}
                                        </span>
                                    </div>
                                </div>
                            </div>

                            {/* Vacuum Backpressure */}
                            <div className="flex items-center gap-2 rounded-lg bg-white px-2.5 py-1.5 border border-gray-200/80 shadow-2xs">
                                <div className="flex h-7 w-7 items-center justify-center rounded-md bg-cyan-50 text-cyan-600">
                                    <Wind size={14} />
                                </div>
                                <div>
                                    <div className="text-[10px] font-medium text-gray-400 leading-tight">
                                        Anti-Drool Vac
                                    </div>
                                    <div className="text-xs font-bold text-gray-800">
                                        {currentLine.vacuum_pressure.value.toFixed(1)}{" "}
                                        <span className="text-[10px] font-normal text-gray-500">
                                            {currentLine.vacuum_pressure.unit}
                                        </span>
                                    </div>
                                </div>
                            </div>

                            {/* Nozzle Heater */}
                            <div className="flex items-center gap-2 rounded-lg bg-white px-2.5 py-1.5 border border-gray-200/80 shadow-2xs">
                                <div className="flex h-7 w-7 items-center justify-center rounded-md bg-amber-50 text-amber-600">
                                    <Thermometer size={14} />
                                </div>
                                <div>
                                    <div className="text-[10px] font-medium text-gray-400 leading-tight">
                                        Nozzle Temp
                                    </div>
                                    <div className="text-xs font-bold text-gray-800">
                                        {currentLine.nozzle_temp.value.toFixed(1)}{" "}
                                        <span className="text-[10px] font-normal text-gray-500">
                                            {currentLine.nozzle_temp.unit}
                                        </span>
                                    </div>
                                </div>
                            </div>

                            {/* Syringe Temp */}
                            <div className="flex items-center gap-2 rounded-lg bg-white px-2.5 py-1.5 border border-gray-200/80 shadow-2xs">
                                <div className="flex h-7 w-7 items-center justify-center rounded-md bg-emerald-50 text-emerald-600">
                                    <Layers size={14} />
                                </div>
                                <div>
                                    <div className="text-[10px] font-medium text-gray-400 leading-tight">
                                        Barrel Temp
                                    </div>
                                    <div className="text-xs font-bold text-gray-800">
                                        {currentLine.syringe_temp.value.toFixed(1)}{" "}
                                        <span className="text-[10px] font-normal text-gray-500">
                                            {currentLine.syringe_temp.unit}
                                        </span>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Tip & Volume Status */}
                        {mountedSyringe && (
                            <div className="hidden lg:flex items-center gap-3 text-xs text-gray-500 border-l border-gray-200 pl-4">
                                <div className="flex items-center gap-1.5">
                                    <span className="font-medium text-gray-400">Volume:</span>
                                    <span className="font-semibold text-gray-700">
                                        {mountedSyringe.current_volume_cc.toFixed(1)} / {mountedSyringe.barrel_size_cc} cc ({mountedSyringe.volume_percent}%)
                                    </span>
                                </div>
                                <div className="flex items-center gap-1.5">
                                    <span className="font-medium text-gray-400">Tip:</span>
                                    <span className="font-semibold text-gray-700">
                                        {mountedSyringe.nozzle_tip.gauge} ({mountedSyringe.nozzle_tip.wear_percentage}% wear)
                                    </span>
                                    {mountedSyringe.nozzle_tip.purge_required && (
                                        <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-700">
                                            PURGE REQ
                                        </span>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
