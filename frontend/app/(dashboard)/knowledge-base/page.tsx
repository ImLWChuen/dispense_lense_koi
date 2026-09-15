"use client";

import { useState } from "react";
import {
    Search,
    AlertTriangle,
    Wrench,
    HelpCircle,
    BookOpen,
    Link2,
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
    { id: "ACT01", name: "Inspect Nozzle", effort: "Low", causes: "Nozzle Restriction, Nozzle Condition" },
    { id: "ACT02", name: "Check Material Supply", effort: "Low", causes: "Material Condition, Air Supply" },
    { id: "ACT03", name: "Perform Test Shots", effort: "Medium", causes: "Pressure, Parameters, Equipment" },
    { id: "ACT04", name: "Verify Pressure Settings", effort: "Medium", causes: "Pressure, Parameters" },
    { id: "ACT05", name: "Inspect Valve Assembly", effort: "High", causes: "Valve, Equipment" },
    { id: "ACT06", name: "Check Temperature", effort: "Low", causes: "Temperature, Material Condition" },
    { id: "ACT07", name: "Inspect Substrate", effort: "Low", causes: "Substrate Condition" },
    { id: "ACT08", name: "Calibrate Equipment", effort: "High", causes: "Equipment Condition, Parameters" },
];

export default function KnowledgeBasePage() {
    const [activeTab, setActiveTab] = useState("Defects");
    const [search, setSearch] = useState("");

    return (
        <div className="min-h-screen">
            <Sidebar />

            <div className="ml-64">
                <Header />

                <PageContainer>
                    <div>
                        <p className="text-sm font-medium text-[#6d5dfc]">
                            Reference data
                        </p>

                        <h1 className="mt-1 text-3xl font-bold tracking-tight text-gray-900">
                            Knowledge Base
                        </h1>

                        <p className="mt-2 text-sm text-gray-500">
                            Explore the diagnostic knowledge that powers the
                            DispenseIQ engine.
                        </p>
                    </div>

                    {/* Search + Tabs */}
                    <div className="mt-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                        <div className="flex gap-1">
                            {tabs.map((tab) => (
                                <button
                                    key={tab}
                                    onClick={() => setActiveTab(tab)}
                                    className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
                                        activeTab === tab
                                            ? "bg-[#6d5dfc] text-white"
                                            : "text-gray-600 hover:bg-gray-100"
                                    }`}
                                >
                                    {tab}
                                </button>
                            ))}
                        </div>

                        <div className="relative w-[280px]">
                            <Search
                                size={16}
                                className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
                            />

                            <input
                                type="text"
                                value={search}
                                onChange={(e) => setSearch(e.target.value)}
                                placeholder={`Search ${activeTab.toLowerCase()}...`}
                                className="h-9 w-full rounded-lg border border-gray-200 bg-gray-50 pl-9 pr-3 text-sm outline-none transition focus:border-[#6d5dfc] focus:bg-white"
                            />
                        </div>
                    </div>

                    {/* Content */}
                    <div className="mt-6">
                        {activeTab === "Defects" && (
                            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                                {defects
                                    .filter(
                                        (d) =>
                                            !search ||
                                            d.name
                                                .toLowerCase()
                                                .includes(search.toLowerCase())
                                    )
                                    .map((defect) => (
                                        <div
                                            key={defect.code}
                                            className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm"
                                        >
                                            <div className="flex items-start gap-3">
                                                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-red-50 text-red-600">
                                                    <AlertTriangle size={17} />
                                                </div>

                                                <div>
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
                        )}

                        {activeTab === "Causes" && (
                            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                                {causes
                                    .filter(
                                        (c) =>
                                            !search ||
                                            c.name
                                                .toLowerCase()
                                                .includes(search.toLowerCase())
                                    )
                                    .map((cause) => (
                                        <div
                                            key={cause.id}
                                            className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm"
                                        >
                                            <div className="flex items-start gap-3">
                                                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-amber-50 text-amber-600">
                                                    <Link2 size={17} />
                                                </div>

                                                <div>
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
                        )}

                        {activeTab === "Actions" && (
                            <div className="rounded-2xl border border-gray-200 bg-white shadow-sm">
                                <table className="w-full">
                                    <thead>
                                        <tr className="border-b border-gray-100 text-left">
                                            <th className="px-6 py-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                                ID
                                            </th>

                                            <th className="px-6 py-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                                Action
                                            </th>

                                            <th className="px-6 py-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                                Effort
                                            </th>

                                            <th className="px-6 py-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                                Applicable Causes
                                            </th>
                                        </tr>
                                    </thead>

                                    <tbody>
                                        {actions
                                            .filter(
                                                (a) =>
                                                    !search ||
                                                    a.name
                                                        .toLowerCase()
                                                        .includes(
                                                            search.toLowerCase()
                                                        )
                                            )
                                            .map((action) => (
                                                <tr
                                                    key={action.id}
                                                    className="border-b border-gray-50 last:border-0"
                                                >
                                                    <td className="px-6 py-3 text-xs font-medium text-gray-500">
                                                        {action.id}
                                                    </td>

                                                    <td className="px-6 py-3 text-sm font-medium text-gray-900">
                                                        {action.name}
                                                    </td>

                                                    <td className="px-6 py-3">
                                                        <span
                                                            className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
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

                                                    <td className="px-6 py-3 text-xs text-gray-500">
                                                        {action.causes}
                                                    </td>
                                                </tr>
                                            ))}
                                    </tbody>
                                </table>
                            </div>
                        )}

                        {activeTab === "Rules" && (
                            <div className="rounded-2xl border border-[#ded9ff] bg-[#faf9ff] p-8 text-center">
                                <BookOpen
                                    size={40}
                                    className="mx-auto text-[#6d5dfc]/40"
                                />

                                <h3 className="mt-4 text-base font-semibold text-gray-900">
                                    Evidence Rules
                                </h3>

                                <p className="mt-2 text-sm text-gray-500">
                                    The engine uses {455} evidence mapping rules
                                    across observations, questions, and
                                    troubleshooting checks to score candidate
                                    causes.
                                </p>

                                <p className="mt-1 text-xs text-gray-400">
                                    Rules are maintained in the backend
                                    knowledge base and are not editable from the
                                    UI.
                                </p>
                            </div>
                        )}
                    </div>
                </PageContainer>
            </div>
        </div>
    );
}
