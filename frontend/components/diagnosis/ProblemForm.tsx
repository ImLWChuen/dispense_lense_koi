"use client";

import { useState } from "react";
import {
    AlertTriangle,
    Droplets,
    CircleDot,
    Scaling,
    CircleOff,
    Waves,
    Wind,
    Check,
} from "lucide-react";

export interface ProblemFormData {
    defect: string | null;
    description: string;
    equipment: string;
    material: string;
    depositSize: string;
    frequency: string;
    location: string;
    recentChange?: string;
}

const defectTypes = [
    {
        code: "D01_TOO_LITTLE",
        shortCode: "D01",
        tag: "Undersized",
        name: "Too Little Material",
        description: "Dispensed volume is consistently less than target amount (< 80% nominal).",
        accent: "text-[#6d5dfc]",
        badgeBg: "bg-indigo-50 text-[#5848e8] border-indigo-200",
        renderVisual: () => (
            <svg className="h-10 w-10 text-[#6d5dfc]" viewBox="0 0 40 40" fill="none">
                <circle cx="20" cy="20" r="14" stroke="#cbd5e1" strokeWidth="1.5" strokeDasharray="3 3" />
                <circle cx="20" cy="20" r="6" fill="currentColor" opacity="0.9" />
            </svg>
        ),
    },
    {
        code: "D02_TOO_MUCH",
        shortCode: "D02",
        tag: "Oversized",
        name: "Too Much Material",
        description: "Dispensed volume is consistently more than target amount (> 120% nominal).",
        accent: "text-blue-600",
        badgeBg: "bg-blue-50 text-blue-700 border-blue-200",
        renderVisual: () => (
            <svg className="h-10 w-10 text-blue-600" viewBox="0 0 40 40" fill="none">
                <circle cx="20" cy="20" r="10" stroke="#cbd5e1" strokeWidth="1.5" strokeDasharray="3 3" />
                <circle cx="20" cy="20" r="16" fill="currentColor" opacity="0.65" />
                <circle cx="20" cy="20" r="10" fill="currentColor" opacity="0.9" />
            </svg>
        ),
    },
    {
        code: "D03_INCONSISTENT_SIZE",
        shortCode: "D03",
        tag: "Shot Variance",
        name: "Inconsistent Size",
        description: "Dispensed volume varies significantly from shot to shot on same substrate.",
        accent: "text-amber-600",
        badgeBg: "bg-amber-50 text-amber-700 border-amber-200",
        renderVisual: () => (
            <svg className="h-10 w-10 text-amber-600" viewBox="0 0 40 40" fill="none">
                <circle cx="8" cy="20" r="4" fill="currentColor" opacity="0.85" />
                <circle cx="20" cy="20" r="11" fill="currentColor" opacity="0.85" />
                <circle cx="33" cy="20" r="7" fill="currentColor" opacity="0.85" />
            </svg>
        ),
    },
    {
        code: "D04_MISSING_DOTS",
        shortCode: "D04",
        tag: "Empty Target",
        name: "Missing Dots",
        description: "One or more designated dispensing positions receive zero fluid delivery.",
        accent: "text-rose-600",
        badgeBg: "bg-rose-50 text-rose-700 border-rose-200",
        renderVisual: () => (
            <svg className="h-10 w-10 text-rose-600" viewBox="0 0 40 40" fill="none">
                <circle cx="8" cy="20" r="6" fill="currentColor" opacity="0.85" />
                <circle cx="20" cy="20" r="7" stroke="#f43f5e" strokeWidth="1.5" strokeDasharray="2 2" />
                <path d="M17 17L23 23M23 17L17 23" stroke="#f43f5e" strokeWidth="1.5" strokeLinecap="round" />
                <circle cx="32" cy="20" r="6" fill="currentColor" opacity="0.85" />
            </svg>
        ),
    },
    {
        code: "D05_SPREADING",
        shortCode: "D05",
        tag: "Halo Bleed",
        name: "Spreading",
        description: "Material wets out uncontrollably past target diameter into active lens area.",
        accent: "text-teal-600",
        badgeBg: "bg-teal-50 text-teal-700 border-teal-200",
        renderVisual: () => (
            <svg className="h-10 w-10 text-teal-600" viewBox="0 0 40 40" fill="none">
                <circle cx="20" cy="20" r="16" fill="currentColor" opacity="0.15" />
                <circle cx="20" cy="20" r="11" fill="currentColor" opacity="0.35" />
                <circle cx="20" cy="20" r="6" fill="currentColor" opacity="0.9" />
            </svg>
        ),
    },
    {
        code: "D06_BUBBLES_ABNORMAL_SHAPE",
        shortCode: "D06",
        tag: "Void Bubble",
        name: "Bubbles / Abnormal Shape",
        description: "Deposits contain trapped air voids, stringing tails, or irregular geometry.",
        accent: "text-purple-600",
        badgeBg: "bg-purple-50 text-purple-700 border-purple-200",
        renderVisual: () => (
            <svg className="h-10 w-10 text-purple-600" viewBox="0 0 40 40" fill="none">
                <path d="M12 23 C10 15, 16 10, 25 11 C31 12, 34 19, 31 25 C27 30, 15 30, 12 23 Z" fill="currentColor" opacity="0.8" />
                <circle cx="19" cy="18" r="4.5" fill="white" stroke="currentColor" strokeWidth="1.2" />
            </svg>
        ),
    },
];

const equipmentOptions = [
    "Dispensing Line A",
    "Dispensing Line B",
    "Dispensing Line C",
    "Dispensing Line D",
];

const depositSizeOptions = [
    { label: "Undersized (smaller than target)", value: "undersized" },
    { label: "Oversized (larger than target)", value: "oversized" },
    { label: "Inconsistent (shot-to-shot variance)", value: "inconsistent" },
];

const frequencyOptions = [
    { label: "Consistent (occurs steadily / every shot)", value: "consistent" },
    { label: "Intermittent (occurs sporadically / occasionally)", value: "intermittent" },
];

const locationOptions = [
    { label: "All dispensing points (systemic)", value: "all_points" },
    { label: "Specific nozzle (localized)", value: "specific_nozzle" },
    { label: "Random locations", value: "random_locations" },
    { label: "Varies across points", value: "varies_across_points" },
];

const recentChangeOptions = [
    { label: "No recent changes / Normal operation", value: "none" },
    { label: "Material refilled or new batch loaded", value: "material_refilled" },
    { label: "Nozzle cleaned, replaced, or adjusted", value: "nozzle_changed" },
    { label: "Dispensing parameters or pressure modified", value: "parameters_changed" },
    { label: "Equipment restarted or serviced", value: "equipment_serviced" },
];

interface ProblemFormProps {
    onSubmit?: (data: ProblemFormData) => void;
    isSubmitting?: boolean;
}

export default function ProblemForm({ onSubmit, isSubmitting = false }: ProblemFormProps) {
    const [selectedDefect, setSelectedDefect] = useState<string | null>(null);
    const [description, setDescription] = useState("");
    const [equipment, setEquipment] = useState("");
    const [material, setMaterial] = useState("");
    const [depositSize, setDepositSize] = useState("");
    const [frequency, setFrequency] = useState("");
    const [location, setLocation] = useState("");
    const [recentChange, setRecentChange] = useState("");

    const handleSubmit = () => {
        onSubmit?.({
            defect: selectedDefect,
            description,
            equipment,
            material,
            depositSize,
            frequency,
            location,
            recentChange,
        });
    };

    return (
        <div className="space-y-8">
            {/* Problem Description */}
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                <h2 className="text-base font-semibold text-gray-900">
                    Problem Description
                </h2>

                <p className="mt-1 text-xs text-gray-500">
                    Describe the dispensing symptom you are observing
                </p>

                <div className="mt-5 space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-gray-700">
                            Symptom Description
                        </label>

                        <textarea
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            placeholder="e.g. Dispensed dots are significantly smaller than expected and appear flat on the substrate..."
                            rows={4}
                            className="mt-1.5 w-full rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 text-sm outline-none transition placeholder:text-gray-400 focus:border-[#6d5dfc] focus:bg-white"
                        />
                    </div>

                    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                        <div>
                            <label className="block text-sm font-medium text-gray-700">
                                Equipment / Line
                            </label>

                            <select
                                value={equipment}
                                onChange={(e) => setEquipment(e.target.value)}
                                className="mt-1.5 w-full rounded-xl border border-gray-200 bg-gray-50 px-4 py-2.5 text-sm outline-none transition focus:border-[#6d5dfc] focus:bg-white"
                            >
                                <option value="">Select equipment</option>

                                {equipmentOptions.map((opt) => (
                                    <option key={opt} value={opt}>
                                        {opt}
                                    </option>
                                ))}
                            </select>
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-700">
                                Material Type
                            </label>

                            <input
                                type="text"
                                value={material}
                                onChange={(e) => setMaterial(e.target.value)}
                                placeholder="e.g. Epoxy adhesive, Solder paste"
                                className="mt-1.5 w-full rounded-xl border border-gray-200 bg-gray-50 px-4 py-2.5 text-sm outline-none transition placeholder:text-gray-400 focus:border-[#6d5dfc] focus:bg-white"
                            />
                        </div>
                    </div>
                </div>
            </div>

            {/* Visual Defect Taxonomy Picker */}
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                    <div>
                        <h2 className="text-base font-semibold text-gray-900">
                            Observed Defect Taxonomy
                        </h2>
                        <p className="mt-1 text-xs text-gray-500">
                            Select the optical defect pattern matching your dispensing inspection
                        </p>
                    </div>

                    {selectedDefect && (
                        <button
                            type="button"
                            onClick={() => setSelectedDefect(null)}
                            className="text-xs font-semibold text-[#6d5dfc] hover:underline self-start sm:self-auto"
                        >
                            Clear selection
                        </button>
                    )}
                </div>

                <div className="mt-5 grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
                    {defectTypes.map((defect) => {
                        const isSelected = selectedDefect === defect.code;

                        return (
                            <div
                                key={defect.code}
                                onClick={() => setSelectedDefect(defect.code)}
                                className={`group relative flex flex-col justify-between rounded-2xl border p-4 text-left cursor-pointer transition-all duration-150 ${
                                    isSelected
                                        ? "border-[#6d5dfc] bg-[#eeebff]/30 shadow-md ring-2 ring-[#6d5dfc]/25"
                                        : "border-gray-200 bg-white hover:border-gray-300 hover:shadow-xs hover:bg-gray-50/60"
                                }`}
                            >
                                <div>
                                    {/* Card Header: Code Badge & Selected Indicator */}
                                    <div className="flex items-center justify-between gap-2">
                                        <div className="flex items-center gap-1.5">
                                            <span
                                                className={`rounded-md border px-1.5 py-0.5 font-mono text-[11px] font-bold ${defect.badgeBg}`}
                                            >
                                                {defect.shortCode}
                                            </span>
                                            <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-semibold text-gray-500">
                                                {defect.tag}
                                            </span>
                                        </div>

                                        <div
                                            className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border transition ${
                                                isSelected
                                                    ? "border-[#6d5dfc] bg-[#6d5dfc] text-white"
                                                    : "border-gray-200 bg-white text-transparent group-hover:border-gray-300"
                                            }`}
                                        >
                                            <Check size={11} strokeWidth={3} />
                                        </div>
                                    </div>

                                    {/* Visual Micro-Illustration */}
                                    <div className="my-3 flex items-center justify-center rounded-xl bg-gray-50/80 py-2.5 border border-gray-100 group-hover:bg-gray-100/50 transition">
                                        {defect.renderVisual()}
                                    </div>

                                    {/* Defect Title & Description */}
                                    <h3
                                        className={`text-sm font-bold tracking-tight transition ${
                                            isSelected ? "text-[#5848e8]" : "text-gray-900 group-hover:text-gray-900"
                                        }`}
                                    >
                                        {defect.name}
                                    </h3>

                                    <p className="mt-1 text-xs text-gray-500 leading-relaxed">
                                        {defect.description}
                                    </p>
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Dispensing Problem Discovery */}
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                    <div>
                        <h2 className="text-base font-semibold text-gray-900">
                            Dispensing Problem Discovery
                        </h2>
                        <p className="mt-1 text-xs text-gray-500">
                            Smart discovery questions to establish defect characteristics and process variables
                        </p>
                    </div>
                </div>

                <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                    <div>
                        <label className="block text-xs font-semibold text-gray-700">
                            1. Dispensing Amount (Size)
                        </label>
                        <p className="text-[10px] text-gray-400 mb-1.5">Too large, too small, or varying?</p>
                        <select
                            value={depositSize}
                            onChange={(e) => setDepositSize(e.target.value)}
                            className="w-full rounded-xl border border-gray-200 bg-gray-50 px-3 py-2.5 text-xs outline-none transition focus:border-[#6d5dfc] focus:bg-white"
                        >
                            <option value="">Select size observation...</option>
                            {depositSizeOptions.map((opt) => (
                                <option key={opt.value} value={opt.value}>
                                    {opt.label}
                                </option>
                            ))}
                        </select>
                    </div>

                    <div>
                        <label className="block text-xs font-semibold text-gray-700">
                            2. Defect Frequency
                        </label>
                        <p className="text-[10px] text-gray-400 mb-1.5">Continuously or occasionally?</p>
                        <select
                            value={frequency}
                            onChange={(e) => setFrequency(e.target.value)}
                            className="w-full rounded-xl border border-gray-200 bg-gray-50 px-3 py-2.5 text-xs outline-none transition focus:border-[#6d5dfc] focus:bg-white"
                        >
                            <option value="">Select frequency pattern...</option>
                            {frequencyOptions.map((opt) => (
                                <option key={opt.value} value={opt.value}>
                                    {opt.label}
                                </option>
                            ))}
                        </select>
                    </div>

                    <div>
                        <label className="block text-xs font-semibold text-gray-700">
                            3. Recent Changes
                        </label>
                        <p className="text-[10px] text-gray-400 mb-1.5">Material, nozzle, or parameters?</p>
                        <select
                            value={recentChange}
                            onChange={(e) => setRecentChange(e.target.value)}
                            className="w-full rounded-xl border border-gray-200 bg-gray-50 px-3 py-2.5 text-xs outline-none transition focus:border-[#6d5dfc] focus:bg-white"
                        >
                            <option value="">Select recent change...</option>
                            {recentChangeOptions.map((opt) => (
                                <option key={opt.value} value={opt.value}>
                                    {opt.label}
                                </option>
                            ))}
                        </select>
                    </div>

                    <div>
                        <label className="block text-xs font-semibold text-gray-700">
                            4. Defect Location
                        </label>
                        <p className="text-[10px] text-gray-400 mb-1.5">One location or across all points?</p>
                        <select
                            value={location}
                            onChange={(e) => setLocation(e.target.value)}
                            className="w-full rounded-xl border border-gray-200 bg-gray-50 px-3 py-2.5 text-xs outline-none transition focus:border-[#6d5dfc] focus:bg-white"
                        >
                            <option value="">Select location pattern...</option>
                            {locationOptions.map((opt) => (
                                <option key={opt.value} value={opt.value}>
                                    {opt.label}
                                </option>
                            ))}
                        </select>
                    </div>
                </div>
            </div>

            {/* Submit */}
            <div className="flex justify-end">
                <button
                    type="button"
                    onClick={handleSubmit}
                    disabled={!selectedDefect || !description.trim() || isSubmitting}
                    className="inline-flex items-center gap-2 rounded-xl bg-[#6d5dfc] px-6 py-3 text-sm font-semibold text-white transition hover:bg-[#5848e8] disabled:cursor-not-allowed disabled:opacity-50"
                >
                    <AlertTriangle size={16} />
                    {isSubmitting ? "Submitting Case..." : "Start Diagnosis"}
                </button>
            </div>
        </div>
    );
}
