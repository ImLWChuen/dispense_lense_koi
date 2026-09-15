"use client";

import { useState } from "react";
import { Search, SlidersHorizontal } from "lucide-react";

const statusOptions = ["All", "In Progress", "Resolved", "Needs Review"];
const defectOptions = [
    "All",
    "Too Little Material",
    "Too Much Material",
    "Inconsistent Size",
    "Missing Dots",
    "Spreading",
    "Bubbles / Abnormal Shape",
];
const equipmentOptions = [
    "All",
    "Dispensing Line A",
    "Dispensing Line B",
    "Dispensing Line C",
    "Dispensing Line D",
];

interface CaseFiltersProps {
    onFilterChange?: (filters: Record<string, string>) => void;
}

export default function CaseFilters({ onFilterChange }: CaseFiltersProps) {
    const [search, setSearch] = useState("");
    const [status, setStatus] = useState("All");
    const [defect, setDefect] = useState("All");
    const [equipment, setEquipment] = useState("All");

    const handleChange = (key: string, value: string) => {
        const newFilters: Record<string, string> = {
            search,
            status,
            defect,
            equipment,
            [key]: value,
        };

        if (key === "search") setSearch(value);
        if (key === "status") setStatus(value);
        if (key === "defect") setDefect(value);
        if (key === "equipment") setEquipment(value);

        onFilterChange?.(newFilters);
    };

    return (
        <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
            <div className="flex flex-wrap items-center gap-3">
                {/* Search */}
                <div className="relative min-w-[240px] flex-1">
                    <Search
                        size={16}
                        className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
                    />

                    <input
                        type="text"
                        value={search}
                        onChange={(e) =>
                            handleChange("search", e.target.value)
                        }
                        placeholder="Search cases..."
                        className="h-9 w-full rounded-lg border border-gray-200 bg-gray-50 pl-9 pr-3 text-sm outline-none transition focus:border-[#6d5dfc] focus:bg-white"
                    />
                </div>

                {/* Status */}
                <select
                    value={status}
                    onChange={(e) =>
                        handleChange("status", e.target.value)
                    }
                    className="h-9 rounded-lg border border-gray-200 bg-gray-50 px-3 text-sm outline-none transition focus:border-[#6d5dfc] focus:bg-white"
                >
                    {statusOptions.map((opt) => (
                        <option key={opt} value={opt}>
                            {opt === "All" ? "All Statuses" : opt}
                        </option>
                    ))}
                </select>

                {/* Defect */}
                <select
                    value={defect}
                    onChange={(e) =>
                        handleChange("defect", e.target.value)
                    }
                    className="h-9 rounded-lg border border-gray-200 bg-gray-50 px-3 text-sm outline-none transition focus:border-[#6d5dfc] focus:bg-white"
                >
                    {defectOptions.map((opt) => (
                        <option key={opt} value={opt}>
                            {opt === "All" ? "All Defects" : opt}
                        </option>
                    ))}
                </select>

                {/* Equipment */}
                <select
                    value={equipment}
                    onChange={(e) =>
                        handleChange("equipment", e.target.value)
                    }
                    className="h-9 rounded-lg border border-gray-200 bg-gray-50 px-3 text-sm outline-none transition focus:border-[#6d5dfc] focus:bg-white"
                >
                    {equipmentOptions.map((opt) => (
                        <option key={opt} value={opt}>
                            {opt === "All" ? "All Equipment" : opt}
                        </option>
                    ))}
                </select>

                <button className="flex h-9 items-center gap-1.5 rounded-lg border border-gray-200 px-3 text-sm text-gray-600 transition hover:bg-gray-50">
                    <SlidersHorizontal size={14} />
                    More
                </button>
            </div>
        </div>
    );
}
