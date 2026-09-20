"use client";

import { useEffect, useState, use, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
    ArrowLeft,
    CheckCircle2,
    Download,
    FileText,
    Calendar,
    Settings,
    Activity,
    AlertTriangle,
    Sparkles,
    Loader2,
    ShieldAlert,
    ShieldCheck,
    Cpu,
    Check,
    HelpCircle,
} from "lucide-react";

import PageContainer from "@/components/layout/PageContainer";
import { reportsApi, CaseReportResponse, EightDReportResponse } from "@/lib/api/reports";
import EightDReportView from "@/components/reports/EightDReportView";

function ReportDetailContent({
    params,
}: {
    params: Promise<{ id: string }>;
}) {
    const resolvedParams = use(params);
    const { id } = resolvedParams;

    const searchParams = useSearchParams();
    const initialFormat = searchParams.get("format") === "8d" ? "8d" : "standard";

    // View format: Standard vs 8D
    const [reportFormat, setReportFormat] = useState<"standard" | "8d">(initialFormat);

    // Standard Report State
    const [report, setReport] = useState<CaseReportResponse | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isDownloadingPdf, setIsDownloadingPdf] = useState(false);
    const [isGeneratingAi, setIsGeneratingAi] = useState(false);
    const [aiSummary, setAiSummary] = useState<string | null>(null);
    const [aiSource, setAiSource] = useState<"llm" | "deterministic" | null>(null);

    // 8D Report State
    const [eightDReport, setEightDReport] = useState<EightDReportResponse | null>(null);
    const [isLoading8D, setIsLoading8D] = useState(false);
    const [isDownloading8D, setIsDownloading8D] = useState(false);

    useEffect(() => {
        const fetchReportData = async () => {
            try {
                setIsLoading(true);
                setError(null);
                const data = await reportsApi.getCaseReport(id);
                setReport(data);

                if (data.current_diagnosis?.explanation) {
                    setAiSummary(data.current_diagnosis.explanation);
                    setAiSource("deterministic");
                }
            } catch (err: any) {
                console.warn("Failed to load real case report, displaying sample/fallback view:", err);
                setError(err.message || "Failed to load case report.");
            } finally {
                setIsLoading(false);
            }
        };

        if (id) {
            fetchReportData();
        }
    }, [id]);

    const fetch8DData = async () => {
        try {
            setIsLoading8D(true);
            const data = await reportsApi.get8DReport(id);
            setEightDReport(data);
        } catch (err: any) {
            console.warn("Failed to load 8D report:", err);
        } finally {
            setIsLoading8D(false);
        }
    };

    useEffect(() => {
        if (reportFormat === "8d" && !eightDReport) {
            fetch8DData();
        }
    }, [reportFormat, id]);

    const handleDownloadPdf = () => {
        setIsDownloadingPdf(true);
        try {
            const filename = report
                ? `dispenselens-case-${report.case_id}-r${report.current_revision}.pdf`
                : `case-${id}-report.pdf`;
            reportsApi.downloadPdf(id, filename);
        } finally {
            setTimeout(() => setIsDownloadingPdf(false), 1500);
        }
    };

    const handleDownload8DPdf = () => {
        setIsDownloading8D(true);
        try {
            const filename = `dispenselens-8d-${id}-r${report?.current_revision || 1}.pdf`;
            reportsApi.download8DPdf(id, filename);
        } finally {
            setTimeout(() => setIsDownloading8D(false), 1500);
        }
    };

    const handleGenerateAiSummary = async () => {
        setIsGeneratingAi(true);
        try {
            const res = await reportsApi.generateAiSummary(id);
            setAiSummary(res.summary);
            setAiSource(res.source);
        } catch (err: any) {
            console.error("Error generating AI summary:", err);
            alert("Unable to generate AI summary: " + (err.message || "Unknown error"));
        } finally {
            setIsGeneratingAi(false);
        }
    };

    const shortId = id.length > 8 ? id.substring(0, 8).toUpperCase() : id;
    const reportCode = `RPT-${shortId}`;
    const caseRef = `DSP-${shortId}`;

    const isResolved =
        report?.outcome_summary?.is_resolved ||
        report?.issue_condition === "RESOLVED" ||
        report?.issue_condition === "IssueCondition.RESOLVED";

    const topCause = report?.current_diagnosis?.ranked_causes?.[0];
    const confirmedCauses = report?.outcome_summary?.confirmed_causes || [];

    return (
        <PageContainer>
            {/* Top Bar with Back Link and Format Switcher */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
                <Link
                    href="/reports"
                    className="inline-flex items-center gap-2 text-sm font-medium text-gray-500 hover:text-gray-900 transition"
                >
                    <ArrowLeft size={16} />
                    Back to Reports
                </Link>

                {/* Report Format Switcher */}
                <div className="flex items-center gap-1 bg-gray-100 p-1.5 rounded-2xl border border-gray-200 shadow-sm">
                    <button
                        onClick={() => setReportFormat("standard")}
                        className={`flex items-center gap-1.5 rounded-xl px-3.5 py-1.5 text-xs font-semibold transition ${
                            reportFormat === "standard"
                                ? "bg-white text-gray-900 shadow-sm"
                                : "text-gray-600 hover:text-gray-900"
                        }`}
                    >
                        <FileText size={14} className={reportFormat === "standard" ? "text-[#6d5dfc]" : ""} />
                        Diagnostic Report
                    </button>
                    <button
                        onClick={() => setReportFormat("8d")}
                        className={`flex items-center gap-1.5 rounded-xl px-3.5 py-1.5 text-xs font-semibold transition ${
                            reportFormat === "8d"
                                ? "bg-white text-gray-900 shadow-sm"
                                : "text-gray-600 hover:text-gray-900"
                        }`}
                    >
                        <ShieldCheck size={14} className={reportFormat === "8d" ? "text-[#6d5dfc]" : ""} />
                        8D Quality & CAPA Report (AIAG / VDA)
                    </button>
                </div>
            </div>

            {/* 8D Report View Mode */}
            {reportFormat === "8d" ? (
                isLoading8D ? (
                    <div className="flex flex-col items-center justify-center py-24 text-gray-400">
                        <Loader2 size={32} className="animate-spin text-[#6d5dfc] mb-3" />
                        <p className="text-sm font-medium">Assembling AIAG / VDA 8D Quality Compliance Report...</p>
                    </div>
                ) : eightDReport ? (
                    <EightDReportView
                        report={eightDReport}
                        onDownloadPdf={handleDownload8DPdf}
                        isDownloadingPdf={isDownloading8D}
                    />
                ) : (
                    <div className="text-center py-16 text-gray-500">
                        Unable to load 8D report data.
                    </div>
                )
            ) : (
                /* Standard Diagnostic Report View Mode */
                <>
                    {/* Report Header */}
                    <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-6 mb-8 pb-6 border-b border-gray-200">
                        <div>
                            <div className="flex flex-wrap items-center gap-2.5 mb-2">
                                <span
                                    className={`inline-flex items-center gap-1.5 rounded-full px-3 py-0.5 text-xs font-semibold ${
                                        isResolved
                                            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                                            : "bg-amber-50 text-amber-700 border border-amber-200"
                                    }`}
                                >
                                    {isResolved ? (
                                        <CheckCircle2 size={13} />
                                    ) : (
                                        <AlertTriangle size={13} />
                                    )}
                                    {isResolved ? "Complete / Resolved" : "Under Investigation"}
                                </span>

                                <span className="text-xs font-semibold text-gray-400">•</span>

                                <span className="text-xs font-medium text-gray-600 bg-gray-100 px-2.5 py-0.5 rounded-full">
                                    Diagnostic Case Report
                                </span>

                                {report?.current_revision && (
                                    <span className="text-xs font-medium text-[#6d5dfc] bg-[#6d5dfc]/10 px-2.5 py-0.5 rounded-full">
                                        Revision {report.current_revision}
                                    </span>
                                )}
                            </div>

                            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-gray-900">
                                {report?.defect_name || report?.description || "Dispensing Diagnostic Report"}
                            </h1>

                            <div className="mt-2.5 flex flex-wrap items-center gap-4 text-xs sm:text-sm text-gray-500">
                                <div className="flex items-center gap-1.5 font-mono">
                                    <FileText size={15} className="text-gray-400" />
                                    <span className="font-semibold text-gray-700">{reportCode}</span>
                                </div>

                                <div className="flex items-center gap-1.5">
                                    <Calendar size={15} className="text-gray-400" />
                                    <span>
                                        {report?.created_at
                                            ? new Date(report.created_at).toLocaleDateString("en-US", {
                                                  month: "short",
                                                  day: "numeric",
                                                  year: "numeric",
                                                  hour: "2-digit",
                                                  minute: "2-digit",
                                              })
                                            : "Sep 15, 2026"}
                                    </span>
                                </div>

                                <div className="flex items-center gap-1.5">
                                    <span className="text-gray-400">Ref:</span>
                                    <span className="font-mono text-gray-700">{caseRef}</span>
                                </div>
                            </div>
                        </div>

                        {/* Action Buttons */}
                        <div className="flex flex-wrap items-center gap-3">
                            <button
                                onClick={handleGenerateAiSummary}
                                disabled={isGeneratingAi}
                                className="inline-flex items-center gap-2 rounded-xl border border-[#6d5dfc]/30 bg-[#eeebff] px-4 py-2.5 text-sm font-semibold text-[#5848e8] shadow-sm transition hover:bg-[#e4e0ff] disabled:opacity-50"
                            >
                                {isGeneratingAi ? (
                                    <Loader2 size={16} className="animate-spin text-[#6d5dfc]" />
                                ) : (
                                    <Sparkles size={16} className="text-[#6d5dfc]" />
                                )}
                                {aiSummary ? "Regenerate AI Summary" : "Generate AI Summary"}
                            </button>

                            <button
                                onClick={handleDownloadPdf}
                                disabled={isDownloadingPdf}
                                className="inline-flex items-center gap-2 rounded-xl bg-[#6d5dfc] px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-[#5848e8] disabled:opacity-70"
                            >
                                {isDownloadingPdf ? (
                                    <Loader2 size={16} className="animate-spin" />
                                ) : (
                                    <Download size={16} />
                                )}
                                Download PDF
                            </button>
                        </div>
                    </div>

                    {/* Main Content Grid */}
                    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                        {/* Left 2 Columns: Summary & Diagnostic Details */}
                        <div className="lg:col-span-2 space-y-6">
                            {/* AI Executive Summary Card */}
                            <div className="relative overflow-hidden rounded-2xl border border-[#6d5dfc]/20 bg-gradient-to-br from-white via-white to-[#f5f3ff] p-6 shadow-sm">
                                <div className="flex items-center justify-between mb-4">
                                    <div className="flex items-center gap-2">
                                        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#6d5dfc] text-white">
                                            <Sparkles size={18} />
                                        </div>
                                        <div>
                                            <h2 className="text-base font-bold text-gray-900">
                                                Executive Summary
                                            </h2>
                                            <p className="text-xs text-gray-500">
                                                Synthesized case findings and operational impact
                                            </p>
                                        </div>
                                    </div>

                                    {aiSource && (
                                        <span className="text-xs font-mono font-medium text-[#6d5dfc] bg-[#6d5dfc]/10 px-2 py-0.5 rounded-full">
                                            {aiSource === "llm" ? "AI Generated" : "Deterministic Summary"}
                                        </span>
                                    )}
                                </div>

                                <div className="text-sm leading-relaxed text-gray-700 bg-white/80 p-4 rounded-xl border border-gray-100 shadow-inner">
                                    {aiSummary ? (
                                        <p>{aiSummary}</p>
                                    ) : (
                                        <p className="text-gray-400 italic">
                                            Click &quot;Generate AI Summary&quot; above to synthesize an automated executive briefing for this case.
                                        </p>
                                    )}
                                </div>
                            </div>

                            {/* Root Cause & Evidence Findings Card */}
                            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                                <div className="flex items-center justify-between mb-4">
                                    <div className="flex items-center gap-2">
                                        <ShieldAlert size={18} className="text-[#6d5dfc]" />
                                        <h2 className="text-base font-bold text-gray-900">
                                            Root Cause Analysis
                                        </h2>
                                    </div>

                                    {topCause && (
                                        <span className="text-xs font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-0.5 rounded-full border border-emerald-200">
                                            {Math.round(topCause.score * 100)}% Match
                                        </span>
                                    )}
                                </div>

                                {topCause ? (
                                    <div className="space-y-4">
                                        <div className="p-4 rounded-xl bg-gray-50 border border-gray-100">
                                            <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">
                                                Leading Hypothesis
                                            </span>
                                            <h3 className="text-base font-bold text-gray-900 mt-1">
                                                {topCause.cause_name}
                                            </h3>
                                            <p className="mt-1 text-xs sm:text-sm text-gray-600">
                                                {report?.current_diagnosis?.explanation || "Confirmed via diagnostic checks."}
                                            </p>
                                        </div>

                                        {/* Confirmed Causes List */}
                                        {confirmedCauses.length > 0 && (
                                            <div>
                                                <h4 className="text-xs font-bold uppercase tracking-wider text-gray-400 mb-2">
                                                    Confirmed Causes
                                                </h4>
                                                <div className="flex flex-wrap gap-2">
                                                    {confirmedCauses.map((c, idx) => (
                                                        <span
                                                            key={idx}
                                                            className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-800 border border-emerald-200"
                                                        >
                                                            <Check size={13} />
                                                            {c}
                                                        </span>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                ) : (
                                    <div className="text-center py-6 text-gray-400 text-sm">
                                        No root cause determined yet.
                                    </div>
                                )}
                            </div>

                            {/* Action History & Timeline */}
                            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                                <div className="flex items-center gap-2 mb-4">
                                    <Activity size={18} className="text-[#6d5dfc]" />
                                    <h2 className="text-base font-bold text-gray-900">
                                        Audit & Action History
                                    </h2>
                                </div>

                                {report?.lifecycle_events && report.lifecycle_events.length > 0 ? (
                                    <div className="relative pl-6 space-y-6 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-gray-200">
                                        {report.lifecycle_events.map((event, idx) => (
                                            <div key={idx} className="relative">
                                                <div className="absolute -left-[27px] top-1 h-3.5 w-3.5 rounded-full border-2 border-white bg-[#6d5dfc]" />
                                                <div className="flex flex-wrap items-center justify-between gap-2">
                                                    <span className="text-xs font-bold text-gray-800">
                                                        {event.event_type.replace(/_/g, " ")}
                                                    </span>
                                                    <span className="text-[11px] font-mono text-gray-400">
                                                        {event.created_at ? new Date(event.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "10:00"}
                                                    </span>
                                                </div>
                                                <p className="mt-1 text-xs text-gray-600">
                                                    {event.details || `State shifted to ${event.resulting_issue_condition}`}
                                                </p>
                                                {event.actor && (
                                                    <span className="mt-1 inline-block text-[10px] font-medium text-gray-400 bg-gray-100 px-2 py-0.5 rounded">
                                                        By: {event.actor}
                                                    </span>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <p className="text-xs text-gray-400 italic">No lifecycle events recorded.</p>
                                )}
                            </div>
                        </div>

                        {/* Right Column: Case Info & Metadata */}
                        <div className="space-y-6">
                            {/* Case Parameters Card */}
                            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                                <h3 className="text-sm font-bold text-gray-900 mb-4 pb-2 border-b border-gray-100">
                                    Process & Equipment Specs
                                </h3>

                                <dl className="space-y-3.5 text-xs">
                                    <div>
                                        <dt className="text-xs font-semibold uppercase tracking-wider text-gray-400">
                                            Defect Category
                                        </dt>
                                        <dd className="mt-0.5 font-semibold text-gray-800">
                                            {report?.defect_code || "D01"} - {report?.defect_name || "Tailing"}
                                        </dd>
                                    </div>

                                    <div>
                                        <dt className="text-xs font-semibold uppercase tracking-wider text-gray-400">
                                            Dispensing Material
                                        </dt>
                                        <dd className="mt-0.5 font-medium text-gray-700">
                                            {report?.material || "UV-Curable Optical Adhesive"}
                                        </dd>
                                    </div>

                                    <div>
                                        <dt className="text-xs font-semibold uppercase tracking-wider text-gray-400">
                                            Dispensing Method
                                        </dt>
                                        <dd className="mt-0.5 font-medium text-gray-700">
                                            {report?.method || "Piezoelectric Jetting"}
                                        </dd>
                                    </div>

                                    {report?.machine_context && (
                                        <div>
                                            <dt className="text-xs font-semibold uppercase tracking-wider text-gray-400">
                                                Machine Context
                                            </dt>
                                            <dd className="mt-1 font-mono text-xs text-gray-600 bg-gray-50 p-2 rounded-lg break-all">
                                                {JSON.stringify(report.machine_context)}
                                            </dd>
                                        </div>
                                    )}

                                    <div>
                                        <dt className="text-xs font-semibold uppercase tracking-wider text-gray-400">
                                            PDF Export Status
                                        </dt>
                                        <dd className="mt-1 flex items-center gap-1.5 text-xs text-emerald-700 font-medium">
                                            <CheckCircle2 size={13} />
                                            Ready for download
                                        </dd>
                                    </div>
                                </dl>
                            </div>

                            {/* Preventative Recommendations */}
                            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                                <div className="flex items-center gap-2 mb-4">
                                    <Settings size={18} className="text-[#6d5dfc]" />
                                    <h3 className="text-sm font-bold text-gray-900">
                                        Recommendations
                                    </h3>
                                </div>

                                <ul className="space-y-3 text-xs sm:text-sm text-gray-600">
                                    <li className="flex items-start gap-2">
                                        <div className="mt-1.5 h-1.5 w-1.5 rounded-full bg-[#6d5dfc] shrink-0" />
                                        <span>Maintain routine nozzle purge cycle every 2 hours during continuous line operations.</span>
                                    </li>
                                    <li className="flex items-start gap-2">
                                        <div className="mt-1.5 h-1.5 w-1.5 rounded-full bg-[#6d5dfc] shrink-0" />
                                        <span>Verify fluid temperature stability when ambient temperature exceeds 25°C.</span>
                                    </li>
                                    <li className="flex items-start gap-2">
                                        <div className="mt-1.5 h-1.5 w-1.5 rounded-full bg-[#6d5dfc] shrink-0" />
                                        <span>Retain diagnostic report and revision logs for equipment maintenance history.</span>
                                    </li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </>
            )}
        </PageContainer>
    );
}

export default function ReportDetailPage({
    params,
}: {
    params: Promise<{ id: string }>;
}) {
    return (
        <Suspense
            fallback={
                <div className="flex min-h-[400px] items-center justify-center">
                    <Loader2 size={32} className="animate-spin text-[#6d5dfc]" />
                </div>
            }
        >
            <ReportDetailContent params={params} />
        </Suspense>
    );
}
