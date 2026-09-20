"use client";

import { useState, useEffect, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Plus, Search, Filter, X, RefreshCw, AlertCircle } from "lucide-react";

import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";
import PageContainer from "@/components/layout/PageContainer";

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

function CasesContent() {
    const searchParams = useSearchParams();
    const initialSearch = searchParams.get("search") || "";

    const [cases, setCases] = useState<DurableCaseResponse[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Search and filter state
    const [searchQuery, setSearchQuery] = useState(initialSearch);
    const [statusFilter, setStatusFilter] = useState("ALL");

    useEffect(() => {
        const queryFromUrl = searchParams.get("search");
        if (queryFromUrl !== null) {
            setSearchQuery(queryFromUrl);
        }
    }, [searchParams]);

    const fetchCases = async () => {
        setIsLoading(true);
        setError(null);
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

    useEffect(() => {
        fetchCases();
    }, []);

    // Filtered cases
    const filteredCases = cases.filter((c) => {
        // Status filter
        if (statusFilter !== "ALL" && c.issue_condition !== statusFilter) {
            return false;
        }

        // Search filter
        if (!searchQuery.trim()) return true;
        const q = searchQuery.toLowerCase().trim();
        const matchesId = c.case_id.toLowerCase().includes(q);
        const matchesDefect =
            (c.defect_name && c.defect_name.toLowerCase().includes(q)) ||
            (c.defect_code && c.defect_code.toLowerCase().includes(q));
        const matchesEquipment =
            c.machine_context?.equipment != null &&
            String(c.machine_context.equipment).toLowerCase().includes(q);
        const matchesStatus = c.issue_condition.toLowerCase().includes(q);

        return matchesId || matchesDefect || matchesEquipment || matchesStatus;
    });

    return (
        <PageContainer>
            {/* Header / Title */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-gray-900">
                        Diagnostic Cases
                    </h1>
                    <p className="mt-2 text-sm text-gray-500">
                        Manage and track active and historical dispensing issues.
                    </p>
                </div>

                <div className="flex items-center gap-3">
                    <button
                        onClick={fetchCases}
                        className="inline-flex items-center gap-1.5 rounded-xl border border-gray-200 bg-white px-3.5 py-2 text-sm font-medium text-gray-700 shadow-sm transition hover:bg-gray-50"
                        title="Refresh cases"
                    >
                        <RefreshCw size={15} className={isLoading ? "animate-spin text-[#6d5dfc]" : "text-gray-400"} />
                        Refresh
                    </button>

                    <Link
                        href="/diagnosis/new"
                        className="inline-flex items-center gap-2 rounded-xl bg-[#6d5dfc] px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-[#5848e8]"
                    >
                        <Plus size={18} />
                        New Diagnosis
                    </Link>
                </div>
            </div>

            {/* Table Filters & Search */}
            <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center">
                {/* Search Input */}
                <div className="relative flex-1">
                    <Search
                        className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400"
                        size={18}
                    />
                    <input
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="Search cases by ID, equipment, defect, or status..."
                        className="w-full rounded-xl border border-gray-200 bg-white py-2.5 pl-10 pr-9 text-sm outline-none transition focus:border-[#6d5dfc] focus:ring-1 focus:ring-[#6d5dfc]"
                    />
                    {searchQuery && (
                        <button
                            onClick={() => setSearchQuery("")}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                            title="Clear search"
                        >
                            <X size={15} />
                        </button>
                    )}
                </div>

                {/* Status Dropdown */}
                <div className="relative flex items-center">
                    <Filter size={16} className="absolute left-3.5 text-gray-400 pointer-events-none" />
                    <select
                        value={statusFilter}
                        onChange={(e) => setStatusFilter(e.target.value)}
                        className="appearance-none rounded-xl border border-gray-200 bg-white py-2.5 pl-9 pr-8 text-sm font-medium text-gray-700 outline-none transition hover:bg-gray-50 focus:border-[#6d5dfc] focus:ring-1 focus:ring-[#6d5dfc] cursor-pointer"
                    >
                        <option value="ALL">All Statuses</option>
                        <option value="UNRESOLVED">Unresolved</option>
                        <option value="RESOLVED">Resolved</option>
                        <option value="RECOVERY_PENDING_VERIFICATION">Pending Verification</option>
                        <option value="RECURRED">Recurred</option>
                    </select>
                </div>
            </div>

            {/* Match Counter / Active Filter Notice */}
            <div className="mt-4 flex items-center justify-between text-xs text-gray-500">
                <p>
                    Showing <span className="font-semibold text-gray-900">{filteredCases.length}</span> of{" "}
                    <span className="font-semibold text-gray-900">{cases.length}</span> cases
                    {searchQuery && <span> matching &quot;{searchQuery}&quot;</span>}
                    {statusFilter !== "ALL" && <span> with status &quot;{formatStatus(statusFilter)}&quot;</span>}
                </p>

                {(searchQuery || statusFilter !== "ALL") && (
                    <button
                        onClick={() => {
                            setSearchQuery("");
                            setStatusFilter("ALL");
                        }}
                        className="text-[#6d5dfc] hover:underline font-medium"
                    >
                        Reset filters
                    </button>
                )}
            </div>

            {/* Cases Table */}
            <div className="mt-4 overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">
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
                                    <td colSpan={6} className="px-6 py-12 text-center text-gray-500">
                                        <RefreshCw size={24} className="mx-auto animate-spin text-[#6d5dfc] mb-2" />
                                        Loading cases...
                                    </td>
                                </tr>
                            ) : error ? (
                                <tr>
                                    <td colSpan={6} className="px-6 py-8 text-center text-red-500">
                                        <AlertCircle size={20} className="mx-auto text-red-500 mb-1" />
                                        {error}
                                    </td>
                                </tr>
                            ) : filteredCases.length === 0 ? (
                                <tr>
                                    <td colSpan={6} className="px-6 py-12 text-center">
                                        <p className="text-sm font-semibold text-gray-800">
                                            {cases.length === 0
                                                ? "No diagnostic cases found."
                                                : "No cases match your search criteria."}
                                        </p>
                                        <p className="mt-1 text-xs text-gray-500">
                                            {cases.length === 0
                                                ? "Start a new diagnosis to create your first case."
                                                : "Try searching with a different keyword or resetting your filters."}
                                        </p>
                                        {(searchQuery || statusFilter !== "ALL") && (
                                            <button
                                                onClick={() => {
                                                    setSearchQuery("");
                                                    setStatusFilter("ALL");
                                                }}
                                                className="mt-3 rounded-lg border border-gray-200 bg-gray-50 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-100 transition"
                                            >
                                                Clear Search & Filters
                                            </button>
                                        )}
                                    </td>
                                </tr>
                            ) : (
                                filteredCases.map((caseItem) => (
                                    <tr key={caseItem.case_id} className="transition hover:bg-gray-50/80">
                                        <td className="px-6 py-4 font-mono font-medium text-gray-900">
                                            #{caseItem.case_id.split("-")[0]}
                                        </td>
                                        <td className="px-6 py-4 font-medium text-gray-900">
                                            {caseItem.defect_name || caseItem.defect_code || "Unknown Defect"}
                                        </td>
                                        <td className="px-6 py-4 text-gray-600">
                                            {caseItem.machine_context?.equipment || "Dispensing Line"}
                                        </td>
                                        <td className="px-6 py-4">
                                            <span
                                                className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-medium ${
                                                    statusColors[caseItem.issue_condition as keyof typeof statusColors] ||
                                                    "bg-gray-100 text-gray-700"
                                                }`}
                                            >
                                                {formatStatus(caseItem.issue_condition)}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4 text-xs text-gray-500">
                                            {new Date(caseItem.created_at).toLocaleDateString()}
                                        </td>
                                        <td className="px-6 py-4 text-right">
                                            <Link
                                                href={`/diagnosis/${caseItem.case_id}`}
                                                className="inline-flex items-center gap-1 font-medium text-[#5848e8] hover:text-[#6d5dfc]"
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
    );
}

export default function CasesPage() {
    return (
        <div className="min-h-screen">
            <Sidebar />
            <div className="ml-64">
                <Header />
                <Suspense fallback={<div className="p-8 text-center text-sm text-gray-500">Loading cases...</div>}>
                    <CasesContent />
                </Suspense>
            </div>
        </div>
    );
}
