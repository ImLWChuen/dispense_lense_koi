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
} from "lucide-react";

const defectTypes = [
    {
        code: "D01_TOO_LITTLE",
        name: "Too Little Material",
        description: "Undersized deposits, less than target amount",
        icon: Droplets,
    },
    {
        code: "D02_TOO_MUCH",
        name: "Too Much Material",
        description: "Oversized deposits, more than target amount",
        icon: Waves,
    },
    {
        code: "D03_INCONSISTENT_SIZE",
        name: "Inconsistent Size",
        description: "Deposit volume varies from shot to shot",
        icon: Scaling,
    },
    {
        code: "D04_MISSING_DOTS",
        name: "Missing Dots",
        description: "One or more locations receive no material",
        icon: CircleOff,
    },
    {
        code: "D05_SPREADING",
        name: "Spreading",
        description: "Material spreads excessively on substrate",
        icon: CircleDot,
    },
    {
        code: "D06_BUBBLES_ABNORMAL_SHAPE",
        name: "Bubbles / Abnormal Shape",
        description: "Trapped air bubbles or irregular deposit shapes",
        icon: Wind,
    },
];

const equipmentOptions = [
    "Dispensing Line A",
    "Dispensing Line B",
    "Dispensing Line C",
    "Dispensing Line D",
];

const depositSizeOptions = [
    "undersized",
    "oversized",
    "inconsistent",
    "normal",
];

const frequencyOptions = [
    "Every shot",
    "Intermittent",
    "After prolonged operation",
    "First shots only",
];

const locationOptions = [
    "All dispensing points",
    "Specific nozzle",
    "Random locations",
    "Edge positions only",
];

interface ProblemFormProps {
    onSubmit?: (data: Record<string, unknown>) => void;
}

export default function ProblemForm({ onSubmit }: ProblemFormProps) {
    const [selectedDefect, setSelectedDefect] = useState<string | null>(null);
    const [description, setDescription] = useState("");
    const [equipment, setEquipment] = useState("");
    const [depositSize, setDepositSize] = useState("");
    const [frequency, setFrequency] = useState("");
    const [location, setLocation] = useState("");

    const handleSubmit = () => {
        onSubmit?.({
            defect: selectedDefect,
            description,
            equipment,
            depositSize,
            frequency,
            location,
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
                                placeholder="e.g. Epoxy adhesive, Solder paste"
                                className="mt-1.5 w-full rounded-xl border border-gray-200 bg-gray-50 px-4 py-2.5 text-sm outline-none transition placeholder:text-gray-400 focus:border-[#6d5dfc] focus:bg-white"
                            />
                        </div>
                    </div>
                </div>
            </div>

            {/* Defect Type */}
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                <h2 className="text-base font-semibold text-gray-900">
                    Observed Defect Type
                </h2>

                <p className="mt-1 text-xs text-gray-500">
                    Select the primary defect category that best matches the symptom
                </p>

                <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {defectTypes.map((defect) => {
                        const Icon = defect.icon;
                        const isSelected = selectedDefect === defect.code;

                        return (
                            <button
                                key={defect.code}
                                onClick={() => setSelectedDefect(defect.code)}
                                className={`flex items-start gap-3 rounded-xl border p-4 text-left transition ${
                                    isSelected
                                        ? "border-[#6d5dfc] bg-[#eeebff] ring-1 ring-[#6d5dfc]"
                                        : "border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50"
                                }`}
                            >
                                <div
                                    className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${
                                        isSelected
                                            ? "bg-[#6d5dfc] text-white"
                                            : "bg-gray-100 text-gray-500"
                                    }`}
                                >
                                    <Icon size={18} />
                                </div>

                                <div>
                                    <p
                                        className={`text-sm font-semibold ${
                                            isSelected
                                                ? "text-[#5848e8]"
                                                : "text-gray-900"
                                        }`}
                                    >
                                        {defect.name}
                                    </p>

                                    <p className="mt-0.5 text-xs text-gray-500">
                                        {defect.description}
                                    </p>
                                </div>
                            </button>
                        );
                    })}
                </div>
            </div>

            {/* Observations */}
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                <h2 className="text-base font-semibold text-gray-900">
                    Observations
                </h2>

                <p className="mt-1 text-xs text-gray-500">
                    Provide additional details to improve diagnostic accuracy
                </p>

                <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-3">
                    <div>
                        <label className="block text-sm font-medium text-gray-700">
                            Deposit Size
                        </label>

                        <select
                            value={depositSize}
                            onChange={(e) => setDepositSize(e.target.value)}
                            className="mt-1.5 w-full rounded-xl border border-gray-200 bg-gray-50 px-4 py-2.5 text-sm outline-none transition focus:border-[#6d5dfc] focus:bg-white"
                        >
                            <option value="">Select observation</option>

                            {depositSizeOptions.map((opt) => (
                                <option key={opt} value={opt}>
                                    {opt.charAt(0).toUpperCase() + opt.slice(1)}
                                </option>
                            ))}
                        </select>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-700">
                            Frequency Pattern
                        </label>

                        <select
                            value={frequency}
                            onChange={(e) => setFrequency(e.target.value)}
                            className="mt-1.5 w-full rounded-xl border border-gray-200 bg-gray-50 px-4 py-2.5 text-sm outline-none transition focus:border-[#6d5dfc] focus:bg-white"
                        >
                            <option value="">Select pattern</option>

                            {frequencyOptions.map((opt) => (
                                <option key={opt} value={opt}>
                                    {opt}
                                </option>
                            ))}
                        </select>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-700">
                            Location Pattern
                        </label>

                        <select
                            value={location}
                            onChange={(e) => setLocation(e.target.value)}
                            className="mt-1.5 w-full rounded-xl border border-gray-200 bg-gray-50 px-4 py-2.5 text-sm outline-none transition focus:border-[#6d5dfc] focus:bg-white"
                        >
                            <option value="">Select pattern</option>

                            {locationOptions.map((opt) => (
                                <option key={opt} value={opt}>
                                    {opt}
                                </option>
                            ))}
                        </select>
                    </div>
                </div>
            </div>

            {/* Submit */}
            <div className="flex justify-end">
                <button
                    onClick={handleSubmit}
                    disabled={!selectedDefect || !description}
                    className="inline-flex items-center gap-2 rounded-xl bg-[#6d5dfc] px-6 py-3 text-sm font-semibold text-white transition hover:bg-[#5848e8] disabled:cursor-not-allowed disabled:opacity-50"
                >
                    <AlertTriangle size={16} />
                    Start Diagnosis
                </button>
            </div>
        </div>
    );
}
