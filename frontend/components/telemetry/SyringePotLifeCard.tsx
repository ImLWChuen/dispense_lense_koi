"use client";

import { useState, useEffect } from "react";
import {
    AlertOctagon,
    AlertTriangle,
    CheckCircle2,
    Clock,
    Droplet,
    Flame,
    Gauge,
    Layers,
    Play,
    RefreshCw,
    Sparkles,
    Trash2,
    Wrench,
} from "lucide-react";
import {
    ConsumableItem,
    PotLifeStatus,
    telemetryApi,
} from "@/lib/api/telemetry";

interface SyringePotLifeCardProps {
    item: ConsumableItem;
    onUpdate?: () => void;
    onMountClick?: (item: ConsumableItem) => void;
    onScrapClick?: (item: ConsumableItem) => void;
}

function formatSeconds(sec: number): string {
    if (sec <= 0) return "00h 00m 00s";
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    return `${h.toString().padStart(2, "0")}h ${m.toString().padStart(2, "0")}m ${s.toString().padStart(2, "0")}s`;
}

export default function SyringePotLifeCard({
    item,
    onUpdate,
    onMountClick,
    onScrapClick,
}: SyringePotLifeCardProps) {
    const [secondsRemaining, setSecondsRemaining] = useState<number>(
        item.remaining_pot_life_seconds
    );
    const [isPurging, setIsPurging] = useState(false);

    // Live ticking countdown for mounted / ready items
    useEffect(() => {
        if (!item.pot_life_expiry_time) {
            setSecondsRemaining(item.remaining_pot_life_seconds);
            return;
        }

        const updateSec = () => {
            const expiry = new Date(item.pot_life_expiry_time!).getTime();
            const rem = Math.max(0, Math.floor((expiry - Date.now()) / 1000));
            setSecondsRemaining(rem);
        };

        updateSec();
        const timer = setInterval(updateSec, 1000);
        return () => clearInterval(timer);
    }, [item.pot_life_expiry_time, item.remaining_pot_life_seconds]);

    // Handle nozzle tip purge
    const handlePurge = async () => {
        setIsPurging(true);
        try {
            await telemetryApi.purgeConsumable(item.id, {
                purge_duration_ms: 500,
                test_shot_count: 5,
            });
            if (onUpdate) onUpdate();
        } catch (err) {
            console.error("Purge failed:", err);
        } finally {
            setIsPurging(false);
        }
    };

    // Determine color and status
    let currentPotStatus: PotLifeStatus = "OPTIMAL";
    if (item.state === "EXPIRED" || secondsRemaining <= 0) {
        currentPotStatus = "EXPIRED";
    } else if (secondsRemaining < 1800) {
        currentPotStatus = "CRITICAL";
    } else if (secondsRemaining < 7200) {
        currentPotStatus = "WARNING";
    }

    const totalPotSeconds = item.pot_life_hours * 3600;
    const potPercent = Math.min(
        100,
        Math.max(0, Math.round((secondsRemaining / totalPotSeconds) * 100))
    );

    // SVG Circular progress radius
    const radius = 34;
    const circumference = 2 * Math.PI * radius;
    const potStrokeOffset = circumference - (potPercent / 100) * circumference;

    const thawStrokeOffset =
        circumference - (item.thaw_progress_pct / 100) * circumference;

    return (
        <div className="flex flex-col justify-between rounded-2xl border border-gray-200 bg-white p-5 shadow-xs transition hover:shadow-md">
            <div>
                {/* Header: Lot & State Tag */}
                <div className="flex items-start justify-between gap-2 mb-3">
                    <div>
                        <div className="flex items-center gap-2">
                            <span className="font-mono text-xs font-bold text-gray-900">
                                {item.lot_number}
                            </span>
                            {item.line_id && (
                                <span className="rounded-md bg-indigo-50 px-2 py-0.5 text-[11px] font-bold text-indigo-700 uppercase">
                                    {item.line_id.replace("-", " ")}
                                </span>
                            )}
                        </div>
                        <h3 className="text-sm font-semibold text-gray-800 mt-0.5">
                            {item.material_name}
                        </h3>
                    </div>

                    {/* State Badge */}
                    <div>
                        {item.state === "MOUNTED" && (
                            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-bold text-emerald-700 border border-emerald-200">
                                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                                MOUNTED
                            </span>
                        )}
                        {item.state === "THAWING" && (
                            <span className="inline-flex items-center gap-1 rounded-full bg-sky-50 px-2.5 py-0.5 text-xs font-bold text-sky-700 border border-sky-200">
                                <RefreshCw size={11} className="animate-spin text-sky-600" />
                                THAWING
                            </span>
                        )}
                        {item.state === "READY" && (
                            <span className="inline-flex items-center gap-1 rounded-full bg-indigo-50 px-2.5 py-0.5 text-xs font-bold text-indigo-700 border border-indigo-200">
                                <CheckCircle2 size={11} className="text-indigo-600" />
                                READY
                            </span>
                        )}
                        {item.state === "EXPIRED" && (
                            <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2.5 py-0.5 text-xs font-bold text-rose-700 border border-rose-200">
                                <AlertOctagon size={11} className="text-rose-600" />
                                EXPIRED
                            </span>
                        )}
                        {item.state === "SCRAPPED" && (
                            <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-bold text-gray-500">
                                SCRAPPED
                            </span>
                        )}
                    </div>
                </div>

                {/* Primary Metric Ring Section */}
                <div className="my-4 flex items-center justify-between rounded-xl bg-gray-50/80 p-3.5 border border-gray-100">
                    {/* Ring Display */}
                    <div className="relative flex h-20 w-20 shrink-0 items-center justify-center">
                        <svg className="h-20 w-20 -rotate-90 transform" viewBox="0 0 80 80">
                            <circle
                                cx="40"
                                cy="40"
                                r={radius}
                                className="stroke-gray-200"
                                strokeWidth="6"
                                fill="transparent"
                            />
                            {item.state === "THAWING" ? (
                                <circle
                                    cx="40"
                                    cy="40"
                                    r={radius}
                                    className="stroke-sky-500 transition-all duration-500"
                                    strokeWidth="6"
                                    strokeDasharray={circumference}
                                    strokeDashoffset={thawStrokeOffset}
                                    strokeLinecap="round"
                                    fill="transparent"
                                />
                            ) : (
                                <circle
                                    cx="40"
                                    cy="40"
                                    r={radius}
                                    className={`transition-all duration-500 ${
                                        currentPotStatus === "CRITICAL"
                                            ? "stroke-rose-500"
                                            : currentPotStatus === "WARNING"
                                            ? "stroke-amber-500"
                                            : currentPotStatus === "EXPIRED"
                                            ? "stroke-gray-400"
                                            : "stroke-emerald-500"
                                    }`}
                                    strokeWidth="6"
                                    strokeDasharray={circumference}
                                    strokeDashoffset={potStrokeOffset}
                                    strokeLinecap="round"
                                    fill="transparent"
                                />
                            )}
                        </svg>

                        {/* Ring center icon or percent */}
                        <div className="absolute text-center">
                            {item.state === "THAWING" ? (
                                <span className="text-xs font-bold text-sky-700">
                                    {item.thaw_progress_pct}%
                                </span>
                            ) : (
                                <span
                                    className={`text-xs font-bold ${
                                        currentPotStatus === "CRITICAL"
                                            ? "text-rose-600"
                                            : currentPotStatus === "WARNING"
                                            ? "text-amber-600"
                                            : currentPotStatus === "EXPIRED"
                                            ? "text-gray-500"
                                            : "text-emerald-600"
                                    }`}
                                >
                                    {potPercent}%
                                </span>
                            )}
                        </div>
                    </div>

                    {/* Metric Text & Timer */}
                    <div className="flex-1 pl-4">
                        {item.state === "THAWING" ? (
                            <div>
                                <span className="text-[11px] font-semibold text-sky-600 uppercase tracking-wider">
                                    Defrost in Progress
                                </span>
                                <div className="text-sm font-bold text-gray-800 mt-0.5">
                                    {item.thaw_duration_minutes}m ambient thaw
                                </div>
                                <p className="text-[11px] text-gray-500 mt-0.5">
                                    Rack: {item.cleanroom_rack || "CR-STAGING"}
                                </p>
                            </div>
                        ) : (
                            <div>
                                <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
                                    Pot Life Work Window
                                </span>
                                <div
                                    className={`text-base font-mono font-bold tracking-tight mt-0.5 ${
                                        currentPotStatus === "CRITICAL"
                                            ? "text-rose-600 animate-pulse"
                                            : currentPotStatus === "WARNING"
                                            ? "text-amber-700"
                                            : currentPotStatus === "EXPIRED"
                                            ? "text-gray-500 line-through"
                                            : "text-gray-900"
                                    }`}
                                >
                                    {formatSeconds(secondsRemaining)}
                                </div>
                                <div className="flex items-center gap-1.5 mt-1">
                                    <span
                                        className={`inline-block h-2 w-2 rounded-full ${
                                            currentPotStatus === "CRITICAL"
                                                ? "bg-rose-500"
                                                : currentPotStatus === "WARNING"
                                                ? "bg-amber-500"
                                                : currentPotStatus === "EXPIRED"
                                                ? "bg-gray-400"
                                                : "bg-emerald-500"
                                        }`}
                                    />
                                    <span className="text-xs font-semibold text-gray-600">
                                        {currentPotStatus}
                                    </span>
                                    <span className="text-[11px] text-gray-400">
                                        (Max {item.pot_life_hours}h)
                                    </span>
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {/* Syringe Fluid Volume Bar */}
                <div className="mb-3">
                    <div className="flex justify-between text-xs mb-1">
                        <span className="font-medium text-gray-500 flex items-center gap-1">
                            <Droplet size={12} className="text-blue-500" />
                            Fluid Level
                        </span>
                        <span className="font-semibold text-gray-800">
                            {item.current_volume_cc.toFixed(1)} / {item.barrel_size_cc} cc ({item.volume_percent}%)
                        </span>
                    </div>
                    <div className="h-2 w-full rounded-full bg-gray-100 overflow-hidden">
                        <div
                            className={`h-full rounded-full transition-all duration-300 ${
                                item.volume_percent < 15
                                    ? "bg-rose-500"
                                    : item.volume_percent < 30
                                    ? "bg-amber-500"
                                    : "bg-blue-500"
                            }`}
                            style={{ width: `${item.volume_percent}%` }}
                        />
                    </div>
                    <div className="flex justify-between text-[11px] text-gray-400 mt-1">
                        <span>~{item.estimated_shots_remaining.toLocaleString()} shots remaining</span>
                        {item.volume_percent < 20 && (
                            <span className="font-bold text-rose-600">LOW VOLUME</span>
                        )}
                    </div>
                </div>

                {/* Nozzle Tip Wear & Maintenance */}
                <div className="rounded-xl border border-gray-100 bg-gray-50/50 p-2.5 text-xs">
                    <div className="flex items-center justify-between">
                        <span className="font-semibold text-gray-700">
                            Tip: {item.nozzle_tip.gauge} ({item.nozzle_tip.tip_type})
                        </span>
                        <span className="text-[11px] font-medium text-gray-500">
                            {item.nozzle_tip.wear_percentage}% wear
                        </span>
                    </div>
                    <div className="flex items-center justify-between mt-1 text-[11px] text-gray-500">
                        <span>
                            Cycles: {item.nozzle_tip.cycle_count.toLocaleString()} / {item.nozzle_tip.max_rated_cycles.toLocaleString()}
                        </span>
                        {item.nozzle_tip.purge_required ? (
                            <span className="font-bold text-amber-700 bg-amber-100 px-1.5 py-0.5 rounded">
                                PURGE OVERDUE
                            </span>
                        ) : (
                            <span className="text-gray-400">Purged OK</span>
                        )}
                    </div>
                </div>
            </div>

            {/* Bottom Actions */}
            <div className="mt-4 pt-3 border-t border-gray-100 flex items-center justify-between gap-2">
                {item.state === "MOUNTED" && (
                    <>
                        <button
                            onClick={handlePurge}
                            disabled={isPurging}
                            className="flex items-center gap-1.5 rounded-lg bg-gray-100 hover:bg-gray-200 px-3 py-1.5 text-xs font-semibold text-gray-700 transition"
                        >
                            <RefreshCw size={13} className={isPurging ? "animate-spin" : ""} />
                            {isPurging ? "Purging..." : "Purge Tip"}
                        </button>

                        <button
                            onClick={() => onScrapClick && onScrapClick(item)}
                            className="flex items-center gap-1.5 rounded-lg text-xs font-medium text-gray-400 hover:text-rose-600 hover:bg-rose-50 px-2.5 py-1.5 transition"
                        >
                            <Trash2 size={13} />
                            Scrap
                        </button>
                    </>
                )}

                {item.state === "READY" && (
                    <button
                        onClick={() => onMountClick && onMountClick(item)}
                        className="w-full flex items-center justify-center gap-2 rounded-lg bg-[#5848e8] hover:bg-[#4939d8] text-white px-3 py-2 text-xs font-semibold shadow-xs transition"
                    >
                        <Play size={13} />
                        Mount to Production Line
                    </button>
                )}

                {item.state === "THAWING" && (
                    <div className="w-full text-center text-xs font-medium text-sky-600 italic">
                        Keep sealed until defrost cycle finishes
                    </div>
                )}

                {(item.state === "EXPIRED" || item.state === "SCRAPPED") && (
                    <button
                        onClick={() => onScrapClick && onScrapClick(item)}
                        className="w-full flex items-center justify-center gap-1.5 rounded-lg bg-rose-50 text-rose-700 border border-rose-200 hover:bg-rose-100 px-3 py-1.5 text-xs font-semibold transition"
                    >
                        <Trash2 size={13} />
                        Dispose / Scrap Lot
                    </button>
                )}
            </div>
        </div>
    );
}
