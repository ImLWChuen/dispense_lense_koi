"use client";

import Link from "next/link";
import { Plus, Search, Filter } from "lucide-react";

import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";
import PageContainer from "@/components/layout/PageContainer";
import CaseFilters from "@/components/cases/CaseFilters";
import CaseTable from "@/components/cases/CaseTable";

import { useState, useEffect } from "react";
import { casesApi } from "@/lib/api/cases";
import { DurableCaseResponse } from "@/types/api";

const statusColors = {
    "UNRESOLVED": "bg-yellow-100 text-yellow-700",
    "RECOVERY_PENDING_VERIFICATION": "bg-blue-100 text-blue-700",
    "RESOLVED": "bg-emerald-100 text-emerald-700",
    "RECURRED": "bg-red-100 text-red-700",
};

const formatStatus = (status: string) => {
    return status.split('_').map(word => word.charAt(0) + word.slice(1).toLowerCase()).join(' ');
};

export default function CasesPage() {
    const [cases, setCases] = useState<DurableCaseResponse[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchCases = async () => {
            try {
                const data = await casesApi.listCases();
                setCases(data);
            } catch (err: any) {
                console.error("Failed to fetch cases:", err);
                setError(err.message || "Failed to load cases.");
            } finally {
                setIsLoading(false);
            }
        };

        fetchCases();
    }, []);

    return (
        <div className="min-h-screen">
            <Sidebar />

            <div className="ml-64">
                <Header />

                <PageContainer>
                    <div className="flex items-center justify-between">
                        <div>
                            <h1 className="text-3xl font-bold tracking-tight text-gray-900">
                                Diagnostic Cases
                            </h1>
                            <p className="mt-2 text-sm text-gray-500">
                                Manage and track active and historical dispensing
                                issues.
                            </p>
                        </div>

                        <Link
                            href="/diagnosis/new"
                            className="inline-flex items-center gap-2 rounded-xl bg-[#6d5dfc] px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-[#5848e8]"
                        >
                            <Plus size={18} />
                            New Diagnosis
                        </Link>
                    </div>

                    {/* Table Filters / Search (Placeholder UI) */}
                    <div className="mt-8 flex flex-col gap-4 sm:flex-row sm:items-center">
                        <div className="relative flex-1">
                            <Search
                                className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400"
                                size={18}
                            />
                            <input
                                type="text"
                                placeholder="Search cases by ID, equipment, or defect..."
                                className="w-full rounded-xl border border-gray-200 bg-white py-2.5 pl-10 pr-4 text-sm outline-none transition focus:border-[#6d5dfc] focus:ring-1 focus:ring-[#6d5dfc]"
                            />
                        </div>

                        <button className="inline-flex items-center gap-2 rounded-xl border border-gray-200 bg-white px-4 py-2.5 text-sm font-medium text-gray-700 transition hover:bg-gray-50">
                            <Filter size={16} className="text-gray-400" />
                            Filter Status
                        </button>
                    </div>

                    {/* Cases Table */}
                    <div className="mt-6 overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">
                        <div className="overflow-x-auto">
                            <table className="w-full whitespace-nowrap text-left text-sm">
                                <thead className="bg-gray-50 text-gray-500">
                                    <tr>
                                        <th className="px-6 py-4 font-medium">Case ID</th>
                                        <th className="px-6 py-4 font-medium">Defect Type</th>
                                        <th className="px-6 py-4 font-medium">Equipment</th>
                                        <th className="px-6 py-4 font-medium">Status</th>
                                        <th className="px-6 py-4 font-medium">Created</th>
                                        <th className="px-6 py-4 font-medium text-right">Actions</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-100 text-gray-700">
                                    {isLoading ? (
                                        <tr>
                                            <td colSpan={6} className="px-6 py-8 text-center text-gray-500">
                                                Loading cases...
                                            </td>
                                        </tr>
                                    ) : error ? (
                                        <tr>
                                            <td colSpan={6} className="px-6 py-8 text-center text-red-500">
                                                {error}
                                            </td>
                                        </tr>
                                    ) : cases.length === 0 ? (
                                        <tr>
                                            <td colSpan={6} className="px-6 py-8 text-center text-gray-500">
                                                No cases found. Start a new diagnosis to create one.
                                            </td>
                                        </tr>
                                    ) : (
                                        cases.map((caseItem) => (
                                            <tr key={caseItem.case_id} className="transition hover:bg-gray-50">
                                                <td className="px-6 py-4 font-medium text-gray-900">
                                                    {caseItem.case_id.split('-')[0]}
                                                </td>
                                                <td className="px-6 py-4">
                                                    {caseItem.defect_name || caseItem.defect_code || "Unknown Defect"}
                                                </td>
                                                <td className="px-6 py-4 text-gray-500">
                                                    {caseItem.machine_context?.equipment || "Unknown Line"}
                                                </td>
                                                <td className="px-6 py-4">
                                                    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-medium ${statusColors[caseItem.issue_condition as keyof typeof statusColors] || "bg-gray-100 text-gray-700"}`}>
                                                        {formatStatus(caseItem.issue_condition)}
                                                    </span>
                                                </td>
                                                <td className="px-6 py-4 text-gray-500">
                                                    {new Date(caseItem.created_at).toLocaleDateString()}
                                                </td>
                                                <td className="px-6 py-4 text-right">
                                                    <Link
                                                        href={`/diagnosis/${caseItem.case_id}`}
                                                        className="font-medium text-[#5848e8] hover:text-[#6d5dfc]"
                                                    >
                                                        View Details
                                                    </Link>
                                                </td>
                                            </tr>
                                        ))
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </PageContainer>
            </div>
        </div>
    );
}
