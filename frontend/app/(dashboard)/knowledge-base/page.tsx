"use client";

import { useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import {
    Search,
    AlertTriangle,
    Wrench,
    BookOpen,
    Link2,
    X,
} from "lucide-react";

import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";
import PageContainer from "@/components/layout/PageContainer";

const tabs = ["Defects", "Causes", "Actions", "Rules"];

const defects = [
    {
        code: "D01",
        name: "Too Little Material",
        description:
            "Dispensed volume is consistently less than the target amount, resulting in undersized deposits.",
        causes: ["Nozzle Restriction", "Air Supply", "Material Condition", "Pressure", "Parameters", "Equipment"],
    },
    {
        code: "D02",
        name: "Too Much Material",
        description:
            "Dispensed volume is consistently more than the target amount, resulting in oversized deposits.",
        causes: ["Parameters", "Pressure", "Material Condition", "Nozzle Condition", "Equipment", "Valve"],
    },
    {
        code: "D03",
        name: "Inconsistent Size",
        description:
            "Dispensed volume varies from shot to shot, producing deposits of different sizes.",
        causes: ["Air Supply", "Nozzle Restriction", "Material Condition", "Pressure", "Parameters", "Equipment"],
    },
    {
        code: "D04",
        name: "Missing Dots",
        description:
            "One or more dispensing locations receive no material at all.",
        causes: ["Nozzle Restriction", "Air Supply", "Valve", "Material Condition", "Equipment", "Pressure"],
    },
    {
        code: "D05",
        name: "Spreading",
        description:
            "Dispensed material spreads excessively on the substrate instead of forming a controlled dot.",
        causes: ["Material Condition", "Parameters", "Temperature", "Substrate", "Nozzle Condition", "Equipment"],
    },
    {
        code: "D06",
        name: "Bubbles / Abnormal Shape",
        description:
            "Dispensed deposits contain trapped air bubbles or exhibit abnormal shapes.",
        causes: ["Air Supply", "Material Condition", "Nozzle Condition", "Parameters", "Equipment", "Valve"],
    },
];

const causes = [
    { id: "air_supply_issue", name: "Air / Supply Issue", defectCount: 4, description: "Trapped air or inconsistent air pressure in the material supply path." },
    { id: "nozzle_restriction", name: "Nozzle Restriction", defectCount: 3, description: "Partial or complete blockage of the dispensing nozzle." },
    { id: "material_condition", name: "Material Condition", defectCount: 6, description: "Material properties outside acceptable range." },
    { id: "pressure_instability", name: "Pressure Instability", defectCount: 4, description: "Inconsistent dispensing pressure from the supply system." },
    { id: "parameter_issue", name: "Parameter Issue", defectCount: 5, description: "Dispensing parameters incorrectly configured." },
    { id: "equipment_condition", name: "Equipment Condition", defectCount: 6, description: "Mechanical wear, misalignment, or calibration drift." },
    { id: "valve_issue", name: "Valve Issue", defectCount: 3, description: "Dispensing valve malfunction or wear." },
    { id: "temperature_issue", name: "Temperature Issue", defectCount: 1, description: "Temperature outside acceptable range affects viscosity." },
    { id: "substrate_condition", name: "Substrate Condition", defectCount: 1, description: "Substrate surface affects wetting behaviour." },
    { id: "nozzle_condition", name: "Nozzle Condition", defectCount: 3, description: "Nozzle tip damage or contamination." },
];

const actions = [
    { id: "ACT01", name: "Inspect Nozzle", effort: "Low", causes: "Nozzle Restriction, Nozzle Condition", description: "Visual inspection under microscope to check for partial obstruction or residue." },
    { id: "ACT02", name: "Check Material Supply", effort: "Low", causes: "Material Condition, Air Supply", description: "Inspect syringe barrel, fluid levels, and check for air bubble pockets." },
    { id: "ACT03", name: "Perform Test Shots", effort: "Medium", causes: "Pressure, Parameters, Equipment", description: "Dispense test matrix on reference substrate and weigh on analytical balance." },
    { id: "ACT04", name: "Verify Pressure Settings", effort: "Medium", causes: "Pressure, Parameters", description: "Check regulator gauge readings against recipe specification." },
    { id: "ACT05", name: "Inspect Valve Assembly", effort: "High", causes: "Valve, Equipment", description: "Disassemble valve body, check seal integrity and diaphragm wear." },
    { id: "ACT06", name: "Check Temperature", effort: "Low", causes: "Temperature, Material Condition", description: "Measure syringe heater and ambient cleanroom temperature." },
    { id: "ACT07", name: "Inspect Substrate", effort: "Low", causes: "Substrate Condition", description: "Verify surface cleanliness and surface tension with dyne pens." },
    { id: "ACT08", name: "Calibrate Equipment", effort: "High", causes: "Equipment Condition, Parameters", description: "Run automated nozzle offset calibration and height sensor check." },
];

const evidenceRules = [
    { id: "R01", category: "Visual Observation", defect: "Too Little Material", observation: "Dot diameter < 80% nominal", inferredCause: "Nozzle Restriction, Low Pressure", weight: 0.85 },
    { id: "R02", category: "Visual Observation", defect: "Too Much Material", observation: "Dot diameter > 120% nominal", inferredCause: "High Pressure, Excessive Open Time", weight: 0.80 },
    { id: "R03", category: "Syringe Check", defect: "Missing Dots", observation: "Air bubble visible in fluid line", inferredCause: "Air Supply Issue", weight: 0.95 },
    { id: "R04", category: "Pressure Check", defect: "Inconsistent Size", observation: "Pressure gauge fluctuates > 5%", inferredCause: "Pressure Instability", weight: 0.90 },
    { id: "R05", category: "Environmental", defect: "Spreading", observation: "Cleanroom temperature > 24°C", inferredCause: "Temperature Issue / Viscosity Drop", weight: 0.75 },
    { id: "R06", category: "Nozzle Inspection", defect: "Bubbles / Abnormal Shape", observation: "Dried adhesive buildup on tip", inferredCause: "Nozzle Condition", weight: 0.88 },
];

function KnowledgeBaseContent() {
    const searchParams = useSearchParams();

    const tabFromUrl = searchParams.get("tab");
    const searchFromUrl = searchParams.get("search");

    const [activeTab, setActiveTab] = useState(
        tabFromUrl && tabs.includes(tabFromUrl) ? tabFromUrl : "Defects"
    );
    const [search, setSearch] = useState(searchFromUrl || "");

    const [prevTab, setPrevTab] = useState(tabFromUrl);
    const [prevSearch, setPrevSearch] = useState(searchFromUrl);

    if (tabFromUrl !== prevTab) {
        setPrevTab(tabFromUrl);
        if (tabFromUrl && tabs.includes(tabFromUrl)) {
            setActiveTab(tabFromUrl);
        }
    }

    if (searchFromUrl !== prevSearch) {
        setPrevSearch(searchFromUrl);
        if (searchFromUrl !== null) {
            setSearch(searchFromUrl);
        }
    }

    const q = search.trim().toLowerCase();

    // Filtered data for each tab
    const filteredDefects = defects.filter((d) => {
        if (!q) return true;
        return (
            d.name.toLowerCase().includes(q) ||
            d.code.toLowerCase().includes(q) ||
            d.description.toLowerCase().includes(q) ||
            d.causes.some((c) => c.toLowerCase().includes(q))
        );
    });

    const filteredCauses = causes.filter((c) => {
        if (!q) return true;
        return (
            c.name.toLowerCase().includes(q) ||
            c.id.toLowerCase().includes(q) ||
            c.description.toLowerCase().includes(q)
        );
    });

    const filteredActions = actions.filter((a) => {
        if (!q) return true;
        return (
            a.name.toLowerCase().includes(q) ||
            a.id.toLowerCase().includes(q) ||
            a.causes.toLowerCase().includes(q) ||
            a.effort.toLowerCase().includes(q) ||
            (a.description && a.description.toLowerCase().includes(q))
        );
    });

    const filteredRules = evidenceRules.filter((r) => {
        if (!q) return true;
        return (
            r.id.toLowerCase().includes(q) ||
            r.category.toLowerCase().includes(q) ||
            r.defect.toLowerCase().includes(q) ||
            r.observation.toLowerCase().includes(q) ||
            r.inferredCause.toLowerCase().includes(q)
        );
    });

    return (
        <PageContainer>
            <div>
                <p className="text-sm font-medium text-[#6d5dfc]">
                    Reference data
                </p>

                <h1 className="mt-1 text-3xl font-bold tracking-tight text-gray-900">
                    Knowledge Base
                </h1>

                <p className="mt-2 text-sm text-gray-500">
                    Explore the diagnostic knowledge, defect profiles, and root cause rules that power the
                    DispenseIQ engine.
                </p>
            </div>

            {/* Search + Tabs */}
            <div className="mt-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex gap-1 overflow-x-auto pb-1 sm:pb-0">
                    {tabs.map((tab) => (
                        <button
                            key={tab}
                            onClick={() => setActiveTab(tab)}
                            className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
                                activeTab === tab
                                    ? "bg-[#6d5dfc] text-white shadow-sm"
                                    : "text-gray-600 hover:bg-gray-100"
                            }`}
                        >
                            {tab}
                        </button>
                    ))}
                </div>

                <div className="relative w-full sm:w-[320px]">
                    <Search
                        size={16}
                        className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
                    />

                    <input
                        type="text"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        placeholder={`Search ${activeTab.toLowerCase()} by name, code, or cause...`}
                        className="h-10 w-full rounded-xl border border-gray-200 bg-gray-50 pl-9 pr-9 text-sm outline-none transition focus:border-[#6d5dfc] focus:bg-white focus:ring-1 focus:ring-[#6d5dfc]"
                    />

                    {search && (
                        <button
                            onClick={() => setSearch("")}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                            title="Clear search"
                        >
                            <X size={15} />
                        </button>
                    )}
                </div>
            </div>

            {/* Search status / Clear info */}
            {search && (
                <div className="mt-4 flex items-center justify-between text-xs text-gray-500">
                    <p>
                        Filtering {activeTab} for &quot;<span className="font-semibold text-gray-900">{search}</span>&quot;
                    </p>
                    <button
                        onClick={() => setSearch("")}
                        className="text-[#6d5dfc] hover:underline font-medium"
                    >
                        Clear search
                    </button>
                </div>
            )}

            {/* Content Tabs */}
            <div className="mt-6">
                {/* Defects Tab */}
                {activeTab === "Defects" && (
                    filteredDefects.length > 0 ? (
                        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                            {filteredDefects.map((defect) => (
                                <div
                                    key={defect.code}
                                    className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm transition hover:border-gray-300"
                                >
                                    <div className="flex items-start gap-3">
                                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-red-50 text-red-600">
                                            <AlertTriangle size={17} />
                                        </div>

                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2">
                                                <p className="text-sm font-semibold text-gray-900">
                                                    {defect.name}
                                                </p>

                                                <span className="rounded-md bg-gray-100 px-1.5 py-0.5 text-[10px] font-medium text-gray-500">
                                                    {defect.code}
                                                </span>
                                            </div>

                                            <p className="mt-1 text-xs leading-5 text-gray-500">
                                                {defect.description}
                                            </p>

                                            <div className="mt-3 flex flex-wrap gap-1">
                                                {defect.causes.map((c) => (
                                                    <span
                                                        key={c}
                                                        className="rounded-md bg-[#eeebff] px-1.5 py-0.5 text-[10px] font-medium text-[#5848e8]"
                                                    >
                                                        {c}
                                                    </span>
                                                ))}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="rounded-2xl border border-gray-200 bg-white p-12 text-center">
                            <AlertTriangle size={28} className="mx-auto text-gray-300 mb-2" />
                            <p className="text-sm font-semibold text-gray-800">No defects match your search</p>
                            <p className="mt-1 text-xs text-gray-500">No defect profiles found matching &quot;{search}&quot;.</p>
                            <button
                                onClick={() => setSearch("")}
                                className="mt-3 rounded-lg border border-gray-200 bg-gray-50 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-100 transition"
                            >
                                Clear Search
                            </button>
                        </div>
                    )
                )}

                {/* Causes Tab */}
                {activeTab === "Causes" && (
                    filteredCauses.length > 0 ? (
                        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                            {filteredCauses.map((cause) => (
                                <div
                                    key={cause.id}
                                    className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm transition hover:border-gray-300"
                                >
                                    <div className="flex items-start gap-3">
                                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-amber-50 text-amber-600">
                                            <Link2 size={17} />
                                        </div>

                                        <div className="flex-1 min-w-0">
                                            <p className="text-sm font-semibold text-gray-900">
                                                {cause.name}
                                            </p>

                                            <p className="mt-1 text-xs leading-5 text-gray-500">
                                                {cause.description}
                                            </p>

                                            <p className="mt-2 text-[10px] text-gray-400">
                                                Applicable to{" "}
                                                <span className="font-medium text-gray-600">
                                                    {cause.defectCount} defect types
                                                </span>
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="rounded-2xl border border-gray-200 bg-white p-12 text-center">
                            <Link2 size={28} className="mx-auto text-gray-300 mb-2" />
                            <p className="text-sm font-semibold text-gray-800">No root causes match your search</p>
                            <p className="mt-1 text-xs text-gray-500">No causes found matching &quot;{search}&quot;.</p>
                            <button
                                onClick={() => setSearch("")}
                                className="mt-3 rounded-lg border border-gray-200 bg-gray-50 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-100 transition"
                            >
                                Clear Search
                            </button>
                        </div>
                    )
                )}

                {/* Actions Tab */}
                {activeTab === "Actions" && (
                    filteredActions.length > 0 ? (
                        <div className="rounded-2xl border border-gray-200 bg-white shadow-sm overflow-hidden">
                            <div className="overflow-x-auto">
                                <table className="w-full text-left">
                                    <thead>
                                        <tr className="border-b border-gray-100 bg-gray-50/50">
                                            <th className="px-6 py-3.5 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                                ID
                                            </th>
                                            <th className="px-6 py-3.5 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                                Action
                                            </th>
                                            <th className="px-6 py-3.5 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                                Effort
                                            </th>
                                            <th className="px-6 py-3.5 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                                Applicable Causes
                                            </th>
                                        </tr>
                                    </thead>

                                    <tbody className="divide-y divide-gray-100">
                                        {filteredActions.map((action) => (
                                            <tr
                                                key={action.id}
                                                className="transition hover:bg-gray-50/70"
                                            >
                                                <td className="px-6 py-3.5 text-xs font-mono font-medium text-gray-500">
                                                    {action.id}
                                                </td>

                                                <td className="px-6 py-3.5">
                                                    <p className="text-sm font-medium text-gray-900">
                                                        {action.name}
                                                    </p>
                                                    {action.description && (
                                                        <p className="text-xs text-gray-500 mt-0.5">
                                                            {action.description}
                                                        </p>
                                                    )}
                                                </td>

                                                <td className="px-6 py-3.5">
                                                    <span
                                                        className={`rounded-full px-2.5 py-0.5 text-[11px] font-medium ${
                                                            action.effort === "Low"
                                                                ? "bg-green-50 text-green-700"
                                                                : action.effort === "Medium"
                                                                  ? "bg-amber-50 text-amber-700"
                                                                  : "bg-red-50 text-red-700"
                                                        }`}
                                                    >
                                                        {action.effort}
                                                    </span>
                                                </td>

                                                <td className="px-6 py-3.5 text-xs text-gray-600">
                                                    {action.causes}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    ) : (
                        <div className="rounded-2xl border border-gray-200 bg-white p-12 text-center">
                            <Wrench size={28} className="mx-auto text-gray-300 mb-2" />
                            <p className="text-sm font-semibold text-gray-800">No actions match your search</p>
                            <p className="mt-1 text-xs text-gray-500">No recommended actions found matching &quot;{search}&quot;.</p>
                            <button
                                onClick={() => setSearch("")}
                                className="mt-3 rounded-lg border border-gray-200 bg-gray-50 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-100 transition"
                            >
                                Clear Search
                            </button>
                        </div>
                    )
                )}

                {/* Rules Tab */}
                {activeTab === "Rules" && (
                    <div className="space-y-4">
                        <div className="rounded-2xl border border-[#ded9ff] bg-[#faf9ff] p-6 text-center">
                            <BookOpen
                                size={36}
                                className="mx-auto text-[#6d5dfc]/60"
                            />

                            <h3 className="mt-3 text-base font-semibold text-gray-900">
                                Diagnostic Evidence Rules
                            </h3>

                            <p className="mt-1 text-xs text-gray-600 max-w-xl mx-auto">
                                The engine uses 455 evidence mapping rules across observations, operator questions, and
                                physical checks to score candidate causes.
                            </p>
                        </div>

                        {filteredRules.length > 0 ? (
                            <div className="rounded-2xl border border-gray-200 bg-white shadow-sm overflow-hidden">
                                <div className="overflow-x-auto">
                                    <table className="w-full text-left text-sm">
                                        <thead>
                                            <tr className="border-b border-gray-100 bg-gray-50/50 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                                <th className="px-6 py-3.5">Rule ID</th>
                                                <th className="px-6 py-3.5">Category</th>
                                                <th className="px-6 py-3.5">Defect</th>
                                                <th className="px-6 py-3.5">Observation / Condition</th>
                                                <th className="px-6 py-3.5">Inferred Cause</th>
                                                <th className="px-6 py-3.5 text-right">Confidence Weight</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-gray-100">
                                            {filteredRules.map((rule) => (
                                                <tr key={rule.id} className="transition hover:bg-gray-50/70">
                                                    <td className="px-6 py-3.5 font-mono text-xs font-semibold text-gray-600">
                                                        {rule.id}
                                                    </td>
                                                    <td className="px-6 py-3.5 text-xs text-gray-600">
                                                        {rule.category}
                                                    </td>
                                                    <td className="px-6 py-3.5 font-medium text-gray-900">
                                                        {rule.defect}
                                                    </td>
                                                    <td className="px-6 py-3.5 text-xs text-gray-700">
                                                        {rule.observation}
                                                    </td>
                                                    <td className="px-6 py-3.5 text-xs font-medium text-[#5848e8]">
                                                        {rule.inferredCause}
                                                    </td>
                                                    <td className="px-6 py-3.5 text-right font-mono text-xs font-semibold text-gray-700">
                                                        {(rule.weight * 100).toFixed(0)}%
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        ) : (
                            <div className="rounded-2xl border border-gray-200 bg-white p-12 text-center">
                                <BookOpen size={28} className="mx-auto text-gray-300 mb-2" />
                                <p className="text-sm font-semibold text-gray-800">No rules match your search</p>
                                <p className="mt-1 text-xs text-gray-500">No evidence rules found matching &quot;{search}&quot;.</p>
                                <button
                                    onClick={() => setSearch("")}
                                    className="mt-3 rounded-lg border border-gray-200 bg-gray-50 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-100 transition"
                                >
                                    Clear Search
                                </button>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </PageContainer>
    );
}

export default function KnowledgeBasePage() {
    return (
        <div className="min-h-screen">
            <Sidebar />
            <div className="ml-64">
                <Header />
                <Suspense fallback={<div className="p-8 text-center text-sm text-gray-500">Loading knowledge base...</div>}>
                    <KnowledgeBaseContent />
                </Suspense>
            </div>
        </div>
    );
}
