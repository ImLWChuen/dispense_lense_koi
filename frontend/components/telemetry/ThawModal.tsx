"use client";

import { useState } from "react";
import {
    AlertTriangle,
    Clock,
    Flame,
    Layers,
    Refrigerator,
    Sparkles,
    ThermometerSnowflake,
    X,
} from "lucide-react";
import { telemetryApi, ThawRequest } from "@/lib/api/telemetry";

interface ThawModalProps {
    isOpen: boolean;
    onClose: () => void;
    onSuccess: () => void;
}

const MATERIALS = [
    {
        code: "NOA-68",
        name: "Norland NOA 68 Optical Adhesive",
        type: "UV Acrylic",
        defaultDuration: 45,
        defaultCc: 30.0,
        potLifeHours: 8.0,
        desc: "Precision optical index-matching adhesive. 8h pot life post-thaw.",
    },
    {
        code: "LOCTITE-382",
        name: "Loctite 382 TakPak Prism",
        type: "Cyanoacrylate Gel",
        defaultDuration: 30,
        defaultCc: 20.0,
        potLifeHours: 12.0,
        desc: "Surface-insensitive rapid tacking adhesive. 12h work window.",
    },
    {
        code: "EPO-TEK-353ND",
        name: "EPO-TEK 353ND Optical Epoxy",
        type: "Thermal Epoxy",
        defaultDuration: 60,
        defaultCc: 10.0,
        potLifeHours: 4.0,
        desc: "High-temperature dual-part epoxy. Short 4h working life.",
    },
    {
        code: "DOW-OE6630",
        name: "Dow Corning OE-6630 LED Gel",
        type: "Optical Silicone",
        defaultDuration: 40,
        defaultCc: 55.0,
        potLifeHours: 6.0,
        desc: "High-transparency LED silicone encapsulant. 6h work window.",
    },
];

export default function ThawModal({ isOpen, onClose, onSuccess }: ThawModalProps) {
    const [selectedCode, setSelectedCode] = useState("NOA-68");
    const [lotNumber, setLotNumber] = useState(`LOT-NOA68-${new Date().toISOString().slice(2, 10).replace(/-/g, "")}`);
    const [durationMinutes, setDurationMinutes] = useState(45);
    const [barrelSizeCc, setBarrelSizeCc] = useState(30.0);
    const [rackLocation, setRackLocation] = useState("RACK-CR1-04");
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    if (!isOpen) return null;

    const handleMaterialChange = (code: string) => {
        setSelectedCode(code);
        const mat = MATERIALS.find((m) => m.code === code);
        if (mat) {
            setDurationMinutes(mat.defaultDuration);
            setBarrelSizeCc(mat.defaultCc);
            const dateCode = new Date().toISOString().slice(2, 10).replace(/-/g, "");
            setLotNumber(`LOT-${code.replace(/[^A-Z0-9]/g, "")}-${dateCode}`);
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsSubmitting(true);
        setError(null);

        try {
            const req: ThawRequest = {
                material_code: selectedCode,
                lot_number: lotNumber.trim() || `LOT-${Date.now()}`,
                thaw_duration_minutes: Number(durationMinutes),
                barrel_size_cc: Number(barrelSizeCc),
                cleanroom_rack: rackLocation.trim() || "RACK-CR1-01",
            };

            await telemetryApi.thawConsumable(req);
            onSuccess();
            onClose();
        } catch (err: any) {
            setError(err.message || "Failed to start thaw cycle.");
        } finally {
            setIsSubmitting(false);
        }
    };

    const selectedMat = MATERIALS.find((m) => m.code === selectedCode) || MATERIALS[0];

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-gray-900/50 backdrop-blur-xs p-4 overflow-y-auto">
            <div className="relative w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl border border-gray-100">
                {/* Close Button */}
                <button
                    onClick={onClose}
                    className="absolute right-4 top-4 rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition"
                >
                    <X size={18} />
                </button>

                {/* Header */}
                <div className="flex items-center gap-3 mb-5">
                    <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-sky-50 text-sky-600 border border-sky-100">
                        <ThermometerSnowflake size={22} />
                    </div>
                    <div>
                        <h2 className="text-lg font-bold text-gray-900">
                            Thaw Syringe from Cold Storage
                        </h2>
                        <p className="text-xs text-gray-500">
                            Transfer -40°C frozen adhesive to cleanroom defrost rack
                        </p>
                    </div>
                </div>

                {error && (
                    <div className="mb-4 rounded-xl bg-rose-50 p-3 text-xs text-rose-700 border border-rose-200">
                        {error}
                    </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-4">
                    {/* Material Selector */}
                    <div>
                        <label className="block text-xs font-semibold uppercase tracking-wider text-gray-500 mb-1.5">
                            Adhesive Formulation
                        </label>
                        <div className="grid grid-cols-2 gap-2">
                            {MATERIALS.map((m) => (
                                <button
                                    key={m.code}
                                    type="button"
                                    onClick={() => handleMaterialChange(m.code)}
                                    className={`flex flex-col items-start rounded-xl p-2.5 text-left border transition ${
                                        selectedCode === m.code
                                            ? "border-[#5848e8] bg-[#eeebff]/50 ring-1 ring-[#5848e8]"
                                            : "border-gray-200 hover:border-gray-300 hover:bg-gray-50"
                                    }`}
                                >
                                    <span className="font-bold text-xs text-gray-900">
                                        {m.code}
                                    </span>
                                    <span className="text-[11px] text-gray-500 line-clamp-1">
                                        {m.name}
                                    </span>
                                    <span className="mt-1 inline-block rounded bg-white px-1.5 py-0.5 text-[10px] font-medium text-gray-600 border border-gray-100">
                                        {m.type} • {m.potLifeHours}h Pot Life
                                    </span>
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Lot Number & Cleanroom Rack */}
                    <div className="grid grid-cols-2 gap-3">
                        <div>
                            <label className="block text-xs font-medium text-gray-700 mb-1">
                                Lot Number
                            </label>
                            <input
                                type="text"
                                required
                                value={lotNumber}
                                onChange={(e) => setLotNumber(e.target.value)}
                                className="w-full rounded-xl border border-gray-300 px-3 py-2 text-xs font-mono text-gray-900 focus:border-[#5848e8] focus:outline-none focus:ring-1 focus:ring-[#5848e8]"
                            />
                        </div>

                        <div>
                            <label className="block text-xs font-medium text-gray-700 mb-1">
                                Cleanroom Rack ID
                            </label>
                            <input
                                type="text"
                                required
                                value={rackLocation}
                                onChange={(e) => setRackLocation(e.target.value)}
                                className="w-full rounded-xl border border-gray-300 px-3 py-2 text-xs text-gray-900 focus:border-[#5848e8] focus:outline-none focus:ring-1 focus:ring-[#5848e8]"
                            />
                        </div>
                    </div>

                    {/* Barrel Size & Duration */}
                    <div className="grid grid-cols-2 gap-3">
                        <div>
                            <label className="block text-xs font-medium text-gray-700 mb-1">
                                Syringe Capacity (cc)
                            </label>
                            <select
                                value={barrelSizeCc}
                                onChange={(e) => setBarrelSizeCc(Number(e.target.value))}
                                className="w-full rounded-xl border border-gray-300 px-3 py-2 text-xs text-gray-900 focus:border-[#5848e8] focus:outline-none focus:ring-1 focus:ring-[#5848e8]"
                            >
                                <option value={10.0}>10 cc Barrel</option>
                                <option value={20.0}>20 cc Barrel</option>
                                <option value={30.0}>30 cc Barrel (Standard)</option>
                                <option value={55.0}>55 cc Barrel (High-Cap)</option>
                            </select>
                        </div>

                        <div>
                            <label className="block text-xs font-medium text-gray-700 mb-1">
                                Defrost Duration (Mins)
                            </label>
                            <input
                                type="number"
                                min={10}
                                max={180}
                                required
                                value={durationMinutes}
                                onChange={(e) => setDurationMinutes(Number(e.target.value))}
                                className="w-full rounded-xl border border-gray-300 px-3 py-2 text-xs text-gray-900 focus:border-[#5848e8] focus:outline-none focus:ring-1 focus:ring-[#5848e8]"
                            />
                        </div>
                    </div>

                    {/* Cleanroom Standard SOP Notice */}
                    <div className="flex items-start gap-2.5 rounded-xl bg-amber-50/80 p-3 border border-amber-200 text-amber-800 text-[11px] leading-relaxed">
                        <AlertTriangle size={15} className="shrink-0 text-amber-600 mt-0.5" />
                        <div>
                            <span className="font-bold">SOP ACT02 Cleanroom Rule:</span> Syringes must thaw vertically tip-down at 22°C ambient with hermetic cap sealed. Never microwave or heat thaw. Once thaw completes, <strong>{selectedMat.potLifeHours}h working window</strong> begins.
                        </div>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-gray-100">
                        <button
                            type="button"
                            onClick={onClose}
                            className="rounded-xl px-4 py-2 text-xs font-semibold text-gray-600 hover:bg-gray-100 transition"
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            disabled={isSubmitting}
                            className="flex items-center gap-2 rounded-xl bg-[#5848e8] hover:bg-[#4939d8] text-white px-5 py-2 text-xs font-bold shadow-sm transition disabled:opacity-50"
                        >
                            <Clock size={14} />
                            {isSubmitting ? "Starting..." : "Start Thaw Defrost Cycle"}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
