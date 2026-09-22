"use client";

import { useState, useEffect } from "react";
import {
    Activity,
    AlertOctagon,
    AlertTriangle,
    CheckCircle2,
    Clock,
    Droplet,
    Gauge,
    Layers,
    Plus,
    Radio,
    RefreshCw,
    Sliders,
    Sparkles,
    Thermometer,
    ThermometerSnowflake,
    Trash2,
    Wind,
    Play,
    X,
} from "lucide-react";
import {
    ConsumableItem,
    ConsumableState,
    LineTelemetrySnapshot,
    telemetryApi,
    TelemetryOverviewResponse,
} from "@/lib/api/telemetry";
import LiveTelemetryRibbon from "@/components/telemetry/LiveTelemetryRibbon";
import SyringePotLifeCard from "@/components/telemetry/SyringePotLifeCard";
import SensorGauges from "@/components/telemetry/SensorGauges";
import ThawModal from "@/components/telemetry/ThawModal";

export default function TelemetryPage() {
    const [activeTab, setActiveTab] = useState<"syringes" | "sensors">("syringes");
    const [overview, setOverview] = useState<TelemetryOverviewResponse | null>(null);
    const [consumables, setConsumables] = useState<ConsumableItem[]>([]);
    const [filterState, setFilterState] = useState<string>("ALL");
    const [selectedLineId, setSelectedLineId] = useState<string>("line-a");
    const [isThawModalOpen, setIsThawModalOpen] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [autoRefresh, setAutoRefresh] = useState(true);

    // Modal states
    const [mountingItem, setMountingItem] = useState<ConsumableItem | null>(null);
    const [targetLineId, setTargetLineId] = useState("line-a");
    const [scrappingItem, setScrappingItem] = useState<ConsumableItem | null>(null);
    const [scrapReason, setScrapReason] = useState("EXPIRED_POT_LIFE");
    const [scrapNotes, setScrapNotes] = useState("");

    const loadData = async () => {
        try {
            const [ov, cons] = await Promise.all([
                telemetryApi.getOverview(),
                telemetryApi.getConsumables(),
            ]);
            setOverview(ov);
            setConsumables(cons);
        } catch (err) {
            console.error("Failed to load telemetry data:", err);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        loadData();
    }, []);

    // Live auto-refresh interval
    useEffect(() => {
        if (!autoRefresh) return;
        const interval = setInterval(() => {
            loadData();
        }, 4000);
        return () => clearInterval(interval);
    }, [autoRefresh]);

    const handleMountSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!mountingItem) return;
        try {
            await telemetryApi.mountConsumable(mountingItem.id, { line_id: targetLineId });
            setMountingItem(null);
            loadData();
        } catch (err) {
            console.error("Mount failed:", err);
        }
    };

    const handleScrapSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!scrappingItem) return;
        try {
            await telemetryApi.scrapConsumable(scrappingItem.id, {
                reason: scrapReason,
                notes: scrapNotes,
            });
            setScrappingItem(null);
            setScrapNotes("");
            loadData();
        } catch (err) {
            console.error("Scrap failed:", err);
        }
    };

    // Filtered consumables
    const filteredConsumables = consumables.filter((item) => {
        if (filterState === "ALL") return item.state !== "SCRAPPED";
        if (filterState === "MOUNTED") return item.state === "MOUNTED";
        if (filterState === "THAWING") return item.state === "THAWING";
        if (filterState === "READY") return item.state === "READY";
        if (filterState === "EXPIRED") return item.state === "EXPIRED";
        if (filterState === "SCRAPPED") return item.state === "SCRAPPED";
        return true;
    });

    // KPI counts
    const mountedCount = consumables.filter((c) => c.state === "MOUNTED").length;
    const thawingCount = consumables.filter((c) => c.state === "THAWING").length;
    const criticalCount = consumables.filter(
        (c) => c.state === "MOUNTED" && (c.pot_life_status === "CRITICAL" || c.pot_life_status === "WARNING")
    ).length;
    const lowVolCount = consumables.filter(
        (c) => c.state === "MOUNTED" && c.volume_percent < 25
    ).length;

    const currentLine = overview?.lines.find((l) => l.line_id === selectedLineId) || overview?.lines[0];

    return (
        <div className="min-h-screen bg-[#f7f8fa] dark:bg-[#0b0f19] text-gray-900 dark:text-gray-100 p-4 sm:p-6 lg:p-8 transition-colors duration-200">
            <div className="mx-auto max-w-7xl space-y-6">
                {/* Page Header */}
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#6d5dfc]">
                            <Radio size={14} />
                            Cleanroom Automation & Materials
                        </div>
                        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-gray-900 mt-1">
                            Cleanroom Telemetry & Syringe Pot Life
                        </h1>
                        <p className="text-xs sm:text-sm text-gray-500 mt-1">
                            Live sensor streams, adhesive defrost monitoring, and consumable expiration tracking.
                        </p>
                    </div>

                    {/* Actions: Thaw New Syringe & Live Toggle */}
                    <div className="flex items-center gap-3">
                        <button
                            onClick={() => setAutoRefresh((prev) => !prev)}
                            className={`flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-semibold border transition ${
                                autoRefresh
                                    ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                                    : "bg-white text-gray-600 border-gray-200"
                            }`}
                        >
                            <span className={`h-2 w-2 rounded-full ${autoRefresh ? "bg-emerald-500 animate-pulse" : "bg-gray-400"}`} />
                            {autoRefresh ? "Live Stream (4s)" : "Stream Paused"}
                        </button>

                        <button
                            onClick={() => setIsThawModalOpen(true)}
                            className="flex items-center gap-2 rounded-xl bg-[#5848e8] hover:bg-[#4939d8] text-white px-4 py-2.5 text-xs font-bold shadow-sm shadow-indigo-200 transition"
                        >
                            <Plus size={15} />
                            Thaw New Syringe
                        </button>
                    </div>
                </div>

                {/* Tab Switcher */}
                <div className="flex items-center gap-2 border-b border-gray-200 pb-2">
                    <button
                        onClick={() => setActiveTab("syringes")}
                        className={`flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-semibold transition ${
                            activeTab === "syringes"
                                ? "bg-[#eeebff] text-[#5848e8]"
                                : "text-gray-500 hover:text-gray-800 hover:bg-gray-100"
                        }`}
                    >
                        <Clock size={15} />
                        Syringe Pot Life & Consumables
                        <span className="rounded-full bg-white px-1.5 py-0.5 text-[10px] font-bold text-gray-700 shadow-2xs">
                            {consumables.length}
                        </span>
                    </button>

                    <button
                        onClick={() => setActiveTab("sensors")}
                        className={`flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-semibold transition ${
                            activeTab === "sensors"
                                ? "bg-[#eeebff] text-[#5848e8]"
                                : "text-gray-500 hover:text-gray-800 hover:bg-gray-100"
                        }`}
                    >
                        <Gauge size={15} />
                        Cleanroom & Machine Sensors
                        {overview && (
                            <span className="rounded-full bg-emerald-100 px-1.5 py-0.5 text-[10px] font-bold text-emerald-800">
                                ISO 5
                            </span>
                        )}
                    </button>
                </div>

                {/* TAB 1: Syringe Pot Life & Consumables */}
                {activeTab === "syringes" && (
                    <div className="space-y-6">
                        {/* KPI Summary Banner */}
                        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                            <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-xs">
                                <div className="flex items-center justify-between">
                                    <span className="text-xs font-medium text-gray-500">Active Mounted</span>
                                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600">
                                        <Play size={15} />
                                    </div>
                                </div>
                                <div className="text-2xl font-bold text-gray-900 mt-2 font-mono">
                                    {mountedCount}
                                </div>
                                <div className="text-[11px] text-emerald-600 font-medium mt-0.5">
                                    Mounted across Lines A–D
                                </div>
                            </div>

                            <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-xs">
                                <div className="flex items-center justify-between">
                                    <span className="text-xs font-medium text-gray-500">Defrosting</span>
                                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-sky-50 text-sky-600">
                                        <ThermometerSnowflake size={15} />
                                    </div>
                                </div>
                                <div className="text-2xl font-bold text-gray-900 mt-2 font-mono">
                                    {thawingCount}
                                </div>
                                <div className="text-[11px] text-sky-600 font-medium mt-0.5">
                                    Thawing in cleanroom racks
                                </div>
                            </div>

                            <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-xs">
                                <div className="flex items-center justify-between">
                                    <span className="text-xs font-medium text-gray-500">Pot Life Warning</span>
                                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-50 text-amber-600">
                                        <AlertTriangle size={15} />
                                    </div>
                                </div>
                                <div className="text-2xl font-bold text-gray-900 mt-2 font-mono">
                                    {criticalCount}
                                </div>
                                <div className="text-[11px] text-amber-600 font-medium mt-0.5">
                                    &lt; 2h work window left
                                </div>
                            </div>

                            <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-xs">
                                <div className="flex items-center justify-between">
                                    <span className="text-xs font-medium text-gray-500">Low Volume</span>
                                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-rose-50 text-rose-600">
                                        <Droplet size={15} />
                                    </div>
                                </div>
                                <div className="text-2xl font-bold text-gray-900 mt-2 font-mono">
                                    {lowVolCount}
                                </div>
                                <div className="text-[11px] text-rose-600 font-medium mt-0.5">
                                    &lt; 25% fluid remaining
                                </div>
                            </div>
                        </div>

                        {/* Filter Bar */}
                        <div className="flex flex-wrap items-center justify-between gap-3">
                            <div className="flex items-center rounded-xl bg-gray-100 p-1 text-xs font-medium">
                                {["ALL", "MOUNTED", "THAWING", "READY", "EXPIRED"].map((st) => (
                                    <button
                                        key={st}
                                        onClick={() => setFilterState(st)}
                                        className={`rounded-lg px-3 py-1.5 transition ${
                                            filterState === st
                                                ? "bg-white text-gray-900 font-bold shadow-xs"
                                                : "text-gray-500 hover:text-gray-800"
                                        }`}
                                    >
                                        {st}
                                    </button>
                                ))}
                            </div>

                            <button
                                onClick={loadData}
                                className="flex items-center gap-1.5 rounded-xl border border-gray-200 bg-white px-3 py-1.5 text-xs font-semibold text-gray-600 hover:bg-gray-50 transition"
                            >
                                <RefreshCw size={13} />
                                Refresh Consumables
                            </button>
                        </div>

                        {/* Consumables Grid */}
                        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
                            {filteredConsumables.map((item) => (
                                <SyringePotLifeCard
                                    key={item.id}
                                    item={item}
                                    onUpdate={loadData}
                                    onMountClick={(it) => {
                                        setMountingItem(it);
                                        setTargetLineId("line-a");
                                    }}
                                    onScrapClick={(it) => {
                                        setScrappingItem(it);
                                        setScrapReason("EXPIRED_POT_LIFE");
                                    }}
                                />
                            ))}
                        </div>
                    </div>
                )}

                {/* TAB 2: Cleanroom & Machine Sensors */}
                {activeTab === "sensors" && (
                    <div className="space-y-6">
                        {/* Cleanroom Facility Overview Card */}
                        {overview && (
                            <div className="rounded-2xl border border-emerald-200 bg-linear-to-r from-emerald-50/70 to-teal-50/50 p-5 shadow-xs">
                                <div className="flex flex-wrap items-center justify-between gap-4">
                                    <div className="flex items-center gap-3">
                                        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-500 text-white shadow-md shadow-emerald-200">
                                            <Wind size={24} />
                                        </div>
                                        <div>
                                            <div className="flex items-center gap-2">
                                                <h3 className="text-base font-bold text-gray-900">
                                                    Cleanroom Facility Ambient Environment
                                                </h3>
                                                <span className="rounded-full bg-emerald-600 px-2 py-0.5 text-[10px] font-bold text-white uppercase tracking-wider">
                                                    {overview.environment.iso_class}
                                                </span>
                                            </div>
                                            <p className="text-xs text-emerald-800 font-medium">
                                                Active HEPA filtration, positive differential air pressure sealed cleanroom
                                            </p>
                                        </div>
                                    </div>

                                    {/* Facility Sensors Grid */}
                                    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                                        <div className="rounded-xl bg-white/90 p-2.5 border border-emerald-100 shadow-2xs">
                                            <span className="text-[10px] font-medium text-gray-400 block">Ambient Temp</span>
                                            <span className="text-sm font-bold text-gray-800 font-mono">
                                                {overview.environment.ambient_temp_c.toFixed(1)} °C
                                            </span>
                                            <span className="text-[10px] text-emerald-600 block">Nominal (22.0°C)</span>
                                        </div>

                                        <div className="rounded-xl bg-white/90 p-2.5 border border-emerald-100 shadow-2xs">
                                            <span className="text-[10px] font-medium text-gray-400 block">Relative Humidity</span>
                                            <span className="text-sm font-bold text-gray-800 font-mono">
                                                {overview.environment.relative_humidity_pct.toFixed(0)} %
                                            </span>
                                            <span className="text-[10px] text-emerald-600 block">Nominal (45%)</span>
                                        </div>

                                        <div className="rounded-xl bg-white/90 p-2.5 border border-emerald-100 shadow-2xs">
                                            <span className="text-[10px] font-medium text-gray-400 block">Diff Pressure</span>
                                            <span className="text-sm font-bold text-gray-800 font-mono">
                                                +{overview.environment.differential_pressure_pa.toFixed(1)} Pa
                                            </span>
                                            <span className="text-[10px] text-emerald-600 block">Positive Seal</span>
                                        </div>

                                        <div className="rounded-xl bg-white/90 p-2.5 border border-emerald-100 shadow-2xs">
                                            <span className="text-[10px] font-medium text-gray-400 block">Particles (≥0.5µm)</span>
                                            <span className="text-sm font-bold text-gray-800 font-mono">
                                                {overview.environment.particle_count_per_m3} /m³
                                            </span>
                                            <span className="text-[10px] text-emerald-600 block">&lt; 3,520 Limit</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Machine Line Selector */}
                        <div className="flex items-center justify-between gap-4 border-b border-gray-200 pb-3">
                            <div className="flex items-center gap-2">
                                <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider mr-2">
                                    Dispense Line:
                                </span>
                                {overview?.lines.map((l) => (
                                    <button
                                        key={l.line_id}
                                        onClick={() => setSelectedLineId(l.line_id)}
                                        className={`rounded-xl px-3 py-1.5 text-xs font-bold transition ${
                                            selectedLineId === l.line_id
                                                ? "bg-gray-900 text-white shadow-xs"
                                                : "bg-white text-gray-600 border border-gray-200 hover:bg-gray-50"
                                        }`}
                                    >
                                        {l.line_name}
                                    </button>
                                ))}
                            </div>

                            {currentLine && (
                                <div className="text-xs text-gray-500">
                                    Technology: <span className="font-semibold text-gray-800">{currentLine.technology}</span>
                                    <span className="mx-2">•</span>
                                    Rate: <span className="font-semibold text-gray-800">{currentLine.valve_cycle_freq_hz} Hz</span>
                                </div>
                            )}
                        </div>

                        {/* Physical Sensor Gauges for Selected Line */}
                        {currentLine && (
                            <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-4">
                                <SensorGauges
                                    reading={currentLine.fluid_pressure}
                                    iconType="pressure"
                                />
                                <SensorGauges
                                    reading={currentLine.vacuum_pressure}
                                    iconType="vacuum"
                                />
                                <SensorGauges
                                    reading={currentLine.nozzle_temp}
                                    iconType="temperature"
                                />
                                <SensorGauges
                                    reading={currentLine.syringe_temp}
                                    iconType="generic"
                                />
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* Thaw Modal */}
            <ThawModal
                isOpen={isThawModalOpen}
                onClose={() => setIsThawModalOpen(false)}
                onSuccess={loadData}
            />

            {/* Mount Modal */}
            {mountingItem && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-gray-900/50 backdrop-blur-xs p-4">
                    <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl border border-gray-100">
                        <div className="flex justify-between items-center mb-4">
                            <h3 className="text-base font-bold text-gray-900">
                                Mount Syringe to Line
                            </h3>
                            <button
                                onClick={() => setMountingItem(null)}
                                className="text-gray-400 hover:text-gray-600"
                            >
                                <X size={18} />
                            </button>
                        </div>
                        <p className="text-xs text-gray-600 mb-4">
                            Assign <strong>{mountingItem.lot_number}</strong> ({mountingItem.material_name}) to an active automated line. This starts the <strong>{mountingItem.pot_life_hours}h pot life work window</strong>.
                        </p>

                        <form onSubmit={handleMountSubmit} className="space-y-4">
                            <div>
                                <label className="block text-xs font-semibold text-gray-700 mb-1">
                                    Target Production Line
                                </label>
                                <select
                                    value={targetLineId}
                                    onChange={(e) => setTargetLineId(e.target.value)}
                                    className="w-full rounded-xl border border-gray-300 px-3 py-2 text-xs text-gray-900 focus:outline-none focus:ring-1 focus:ring-[#5848e8]"
                                >
                                    <option value="line-a">Line A - Piezoelectric Jetting</option>
                                    <option value="line-b">Line B - Auger Micro-Screw</option>
                                    <option value="line-c">Line C - Time-Pressure Pneumatic</option>
                                    <option value="line-d">Line D - Piston Positive Displacement</option>
                                </select>
                            </div>

                            <div className="flex justify-end gap-2 pt-2 border-t border-gray-100">
                                <button
                                    type="button"
                                    onClick={() => setMountingItem(null)}
                                    className="rounded-xl px-4 py-2 text-xs font-semibold text-gray-600 hover:bg-gray-100"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    className="rounded-xl bg-[#5848e8] hover:bg-[#4939d8] text-white px-4 py-2 text-xs font-bold shadow-xs"
                                >
                                    Mount & Start Pot Life
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* Scrap Modal */}
            {scrappingItem && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-gray-900/50 backdrop-blur-xs p-4">
                    <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl border border-gray-100">
                        <div className="flex justify-between items-center mb-4">
                            <h3 className="text-base font-bold text-gray-900">
                                Scrap Consumable Lot
                            </h3>
                            <button
                                onClick={() => setScrappingItem(null)}
                                className="text-gray-400 hover:text-gray-600"
                            >
                                <X size={18} />
                            </button>
                        </div>
                        <p className="text-xs text-gray-600 mb-4">
                            Retire <strong>{scrappingItem.lot_number}</strong> ({scrappingItem.material_name}) from active production. This will unmount the barrel and record an audit scrap reason.
                        </p>

                        <form onSubmit={handleScrapSubmit} className="space-y-4">
                            <div>
                                <label className="block text-xs font-semibold text-gray-700 mb-1">
                                    Disposal / Scrap Reason
                                </label>
                                <select
                                    value={scrapReason}
                                    onChange={(e) => setScrapReason(e.target.value)}
                                    className="w-full rounded-xl border border-gray-300 px-3 py-2 text-xs text-gray-900 focus:outline-none focus:ring-1 focus:ring-[#5848e8]"
                                >
                                    <option value="EXPIRED_POT_LIFE">Expired Pot Life Work Window</option>
                                    <option value="VISCOSITY_DRIFT">Viscosity / Rheology Drift</option>
                                    <option value="AIR_BUBBLES">Trapped Air Bubbles / Cavitation</option>
                                    <option value="CONTAMINATION">Particulate Contamination</option>
                                    <option value="NOZZLE_DAMAGE">Nozzle / Tip Clog & Damage</option>
                                </select>
                            </div>

                            <div>
                                <label className="block text-xs font-semibold text-gray-700 mb-1">
                                    Operator Audit Notes
                                </label>
                                <textarea
                                    rows={2}
                                    value={scrapNotes}
                                    onChange={(e) => setScrapNotes(e.target.value)}
                                    placeholder="Optional scrap log notes..."
                                    className="w-full rounded-xl border border-gray-300 px-3 py-2 text-xs text-gray-900 focus:outline-none focus:ring-1 focus:ring-[#5848e8]"
                                />
                            </div>

                            <div className="flex justify-end gap-2 pt-2 border-t border-gray-100">
                                <button
                                    type="button"
                                    onClick={() => setScrappingItem(null)}
                                    className="rounded-xl px-4 py-2 text-xs font-semibold text-gray-600 hover:bg-gray-100"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    className="rounded-xl bg-rose-600 hover:bg-rose-700 text-white px-4 py-2 text-xs font-bold shadow-xs"
                                >
                                    Confirm Scrap
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}
