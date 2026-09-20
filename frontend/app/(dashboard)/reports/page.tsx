"use client";

import { useEffect, useState, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
    FileText,
    CheckCircle2,
    Clock3,
    Plus,
    Download,
    Search,
    AlertCircle,
    Loader2,
    X,
} from "lucide-react";

import PageContainer from "@/components/layout/PageContainer";
import { reportsApi } from "@/lib/api/reports";
import { DurableCaseResponse } from "@/types/api";

interface ReportItem {
    id: string;
    displayId: string;
    caseRef: string;
    title: string;
    date: string;
    type: string;
    status: string;
    isResolved: boolean;
}

function ReportsContent() {
    const searchParams = useSearchParams();
    const initialSearch = searchParams.get("search") || "";

    const [reports, setReports] = useState<ReportItem[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [searchQuery, setSearchQuery] = useState(initialSearch);
    const [downloadingId, setDownloadingId] = useState<string | null>(null);

    useEffect(() => {
        const q = searchParams.get("search");
        if (q !== null) {
            setSearchQuery(q);
        }
    }, [searchParams]);

    const loadReports = async () => {
        try {
            setIsLoading(true);
            setError(null);
            const cases = await reportsApi.listCasesForReports();
            if (cases && cases.length > 0) {
                const mapped: ReportItem[] = cases.map((c: DurableCaseResponse) => {
                    const shortId = c.case_id.substring(0, 8).toUpperCase();
                    const isResolved =
                        c.issue_condition === "RESOLVED" ||
                        c.issue_condition === "IssueCondition.RESOLVED";
                    const cleanStatus = isResolved
                        ? "Complete"
                        : c.issue_condition.replace("IssueCondition.", "").replace(/_/g, " ");

                    const dateStr = c.created_at
                        ? new Date(c.created_at).toLocaleDateString("en-US", {
                              month: "short",
                              day: "numeric",
                              year: "numeric",
                          })
                        : "Recent";

                    return {
                        id: c.case_id,
                        displayId: `RPT-${shortId}`,
                        caseRef: `DSP-${shortId}`,
                        title: c.defect_name || c.description || "Dispensing Diagnostic Report",
                        date: dateStr,
                        type: "Diagnostic Report",
                        status: cleanStatus,
                        isResolved,
                    };
                });
                setReports(mapped);
            } else {
                setReports([]);
            }
        } catch (err: unknown) {
            console.error("Failed to load reports from cases API:", err);
            const msg = err instanceof Error ? err.message : "Failed to load reports.";
            setError(msg);
            setReports([]);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        loadReports();
    }, []);

    const handleDownloadPdf = (e: React.MouseEvent, reportId: string) => {
        e.stopPropagation();
        e.preventDefault();
        setDownloadingId(reportId);
        try {
            reportsApi.downloadPdf(reportId);
        } finally {
            setTimeout(() => setDownloadingId(null), 1200);
        }
    };

    const filteredReports = reports.filter(
        (r) =>
            r.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
            r.displayId.toLowerCase().includes(searchQuery.toLowerCase()) ||
            r.caseRef.toLowerCase().includes(searchQuery.toLowerCase())
    );

    return (
        <PageContainer>
            {/* Page Header */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                    <p className="text-sm font-semibold tracking-wide text-[#6d5dfc]">
                        Documentation & Quality
                    </p>
                    <h1 className="mt-1 text-3xl font-bold tracking-tight text-gray-900">
                        Diagnostic Reports
                    </h1>
                    <p className="mt-1 text-sm text-gray-500">
                        View, search, and export PDF reports for all diagnostic cases.
                    </p>
                </div>

                <div className="flex items-center gap-3">
                    <Link
                        href="/diagnosis/new"
                        className="inline-flex items-center gap-2 rounded-xl bg-[#6d5dfc] px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-[#5848e8]"
                    >
                        <Plus size={16} />
                        New Diagnosis Case
                    </Link>
                </div>
            </div>

            {/* Search & Filter Bar */}
            <div className="mt-6 flex items-center justify-between gap-4">
                <div className="relative flex-1 max-w-md">
                    <Search
                        size={18}
                        className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400"
                    />
                    <input
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="Search reports by title, report ID, or case ref..."
                        className="h-10 w-full rounded-xl border border-gray-200 bg-white pl-10 pr-9 text-sm text-gray-900 outline-none transition placeholder:text-gray-400 focus:border-[#6d5dfc] focus:ring-2 focus:ring-[#6d5dfc]/10"
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
                <div className="text-sm text-gray-500">
                    Showing <span className="font-semibold text-gray-900">{filteredReports.length}</span> reports
                </div>
            </div>

            {error && (
                <div className="mt-4 flex items-center justify-between rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                    <div className="flex items-center gap-2">
                        <AlertCircle size={18} className="text-red-500 shrink-0" />
                        <span>{error}</span>
                    </div>
                    <button
                        onClick={loadReports}
                        className="rounded-lg bg-red-100 px-3 py-1 text-xs font-semibold text-red-800 hover:bg-red-200 transition"
                    >
                        Retry
                    </button>
                </div>
            )}

            {/* Reports Table */}
            <div className="mt-4 rounded-2xl border border-gray-200 bg-white shadow-sm overflow-hidden">
                        {isLoading ? (
                            <div className="flex flex-col items-center justify-center py-20 text-gray-500">
                                <Loader2 className="h-8 w-8 animate-spin text-[#6d5dfc] mb-3" />
                                <p className="text-sm font-medium">Loading case reports...</p>
                            </div>
                        ) : filteredReports.length === 0 ? (
                            <div className="flex flex-col items-center justify-center py-16 text-center">
                                <AlertCircle className="h-10 w-10 text-gray-300 mb-3" />
                                <p className="text-base font-semibold text-gray-900">No reports found</p>
                                <p className="mt-1 text-sm text-gray-500">
                                    {searchQuery ? "No reports matched your search criteria." : "No diagnostic cases have been recorded yet."}
                                </p>
                            </div>
                        ) : (
                            <div className="overflow-x-auto">
                                <table className="w-full text-left">
                                    <thead>
                                        <tr className="border-b border-gray-100 bg-gray-50/50 text-xs font-semibold uppercase tracking-wider text-gray-500">
                                            <th className="px-6 py-3.5">Report ID</th>
                                            <th className="px-6 py-3.5">Title</th>
                                            <th className="px-6 py-3.5">Case Ref</th>
                                            <th className="px-6 py-3.5">Type</th>
                                            <th className="px-6 py-3.5">Date</th>
                                            <th className="px-6 py-3.5">Status</th>
                                            <th className="px-6 py-3.5 text-right">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-gray-100">
                                        {filteredReports.map((report) => (
                                            <tr
                                                key={report.id}
                                                className="group transition hover:bg-gray-50/70"
                                            >
                                                <td className="px-6 py-4">
                                                    <Link
                                                        href={`/reports/${report.id}`}
                                                        className="flex items-center gap-2 text-sm font-semibold text-gray-900 group-hover:text-[#6d5dfc]"
                                                    >
                                                        <FileText size={15} className="text-gray-400 group-hover:text-[#6d5dfc]" />
                                                        {report.displayId}
                                                    </Link>
                                                </td>

                                                <td className="px-6 py-4">
                                                    <Link
                                                        href={`/reports/${report.id}`}
                                                        className="text-sm font-medium text-gray-800 hover:underline block max-w-xs truncate"
                                                        title={report.title}
                                                    >
                                                        {report.title}
                                                    </Link>
                                                </td>

                                                <td className="px-6 py-4 text-xs font-mono text-gray-600">
                                                    {report.caseRef}
                                                </td>

                                                <td className="px-6 py-4">
                                                    <div className="flex items-center gap-1.5">
                                                        <span className="rounded-md bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-600">
                                                            {report.type}
                                                        </span>
                                                        <Link
                                                            href={`/reports/${report.id}?format=8d`}
                                                            className="rounded-md bg-[#6d5dfc]/10 text-[#6d5dfc] px-2 py-0.5 text-[11px] font-semibold hover:bg-[#6d5dfc]/20 transition"
                                                            title="View 8D Quality & CAPA Report"
                                                        >
                                                            8D Ready
                                                        </Link>
                                                    </div>
                                                </td>

                                                <td className="px-6 py-4 text-xs text-gray-500 whitespace-nowrap">
                                                    {report.date}
                                                </td>

                                                <td className="px-6 py-4">
                                                    <span
                                                        className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${
                                                            report.isResolved
                                                                ? "bg-emerald-50 text-emerald-700"
                                                                : "bg-amber-50 text-amber-700"
                                                        }`}
                                                    >
                                                        {report.isResolved ? (
                                                            <CheckCircle2 size={13} />
                                                        ) : (
                                                            <Clock3 size={13} />
                                                        )}
                                                        {report.status}
                                                    </span>
                                                </td>

                                                <td className="px-6 py-4 text-right whitespace-nowrap">
                                                    <div className="flex items-center justify-end gap-1.5">
                                                        <button
                                                            onClick={(e) => handleDownloadPdf(e, report.id)}
                                                            disabled={downloadingId === report.id}
                                                            className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-xs font-medium text-gray-700 shadow-sm transition hover:bg-gray-50 hover:text-gray-900 disabled:opacity-50"
                                                            title="Download Case PDF"
                                                        >
                                                            {downloadingId === report.id ? (
                                                                <Loader2 size={13} className="animate-spin text-[#6d5dfc]" />
                                                            ) : (
                                                                <Download size={13} className="text-gray-500" />
                                                            )}
                                                            PDF
                                                        </button>

                                                        <Link
                                                            href={`/reports/${report.id}?format=8d`}
                                                            className="inline-flex items-center gap-1 rounded-lg border border-[#6d5dfc]/30 bg-[#6d5dfc]/5 px-2.5 py-1.5 text-xs font-semibold text-[#5848e8] transition hover:bg-[#6d5dfc]/15"
                                                            title="Open 8D Quality Report"
                                                        >
                                                            8D Audit
                                                        </Link>

                                                        <Link
                                                            href={`/reports/${report.id}`}
                                                            className="inline-flex items-center gap-1 rounded-lg bg-gray-100 px-2.5 py-1.5 text-xs font-medium text-gray-700 transition hover:bg-[#6d5dfc] hover:text-white"
                                                        >
                                                            View
                                                        </Link>
                                                    </div>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </div>
                </PageContainer>
    );
}

export default function ReportsPage() {
    return (
        <Suspense fallback={<div className="p-8 text-center text-sm text-gray-500">Loading reports...</div>}>
            <ReportsContent />
        </Suspense>
    );
}
