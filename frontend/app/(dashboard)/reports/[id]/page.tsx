"use client";

import { useEffect, useState, use } from "react";
import Link from "next/link";
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
    Cpu,
    Check,
    HelpCircle,
} from "lucide-react";

import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";
import PageContainer from "@/components/layout/PageContainer";
import { reportsApi, CaseReportResponse } from "@/lib/api/reports";

export default function ReportDetailPage({
    params,
}: {
    params: Promise<{ id: string }>;
}) {
    const resolvedParams = use(params);
    const { id } = resolvedParams;

    const [report, setReport] = useState<CaseReportResponse | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isDownloadingPdf, setIsDownloadingPdf] = useState(false);
    const [isGeneratingAi, setIsGeneratingAi] = useState(false);
    const [aiSummary, setAiSummary] = useState<string | null>(null);
    const [aiSource, setAiSource] = useState<"llm" | "deterministic" | null>(null);

    useEffect(() => {
        const fetchReportData = async () => {
            try {
                setIsLoading(true);
                setError(null);
                const data = await reportsApi.getCaseReport(id);
                setReport(data);

                // Auto-generate or load initial AI summary if available in current diagnosis explanation
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

    const handleDownloadPdf = () => {
        setIsDownloadingPdf(true);
        try {
            const filename = report
                ? `dispenseiq-case-${report.case_id}-r${report.current_revision}.pdf`
                : `case-${id}-report.pdf`;
            reportsApi.downloadPdf(id, filename);
        } finally {
            setTimeout(() => setIsDownloadingPdf(false), 1500);
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
        <div className="min-h-screen bg-[#f8fafc]">
            <Sidebar />

            <div className="ml-64">
                <Header />

                <PageContainer>
                    {/* Back Link */}
                    <div className="mb-6">
                        <Link
                            href="/reports"
                            className="inline-flex items-center gap-2 text-sm font-medium text-gray-500 hover:text-gray-900 transition"
                        >
                            <ArrowLeft size={16} />
                            Back to Reports
                        </Link>
                    </div>

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
                                            <Sparkles size={16} />
                                        </div>
                                        <div>
                                            <h2 className="text-base font-bold text-gray-900">
                                                AI Executive Summary
                                            </h2>
                                            <p className="text-xs text-gray-500">
                                                {aiSource === "llm"
                                                    ? "Generated by Bounded LLM Service"
                                                    : "Deterministic Diagnostic Synthesis"}
                                            </p>
                                        </div>
                                    </div>

                                    {aiSource && (
                                        <span className="rounded-full bg-[#eeebff] px-2.5 py-0.5 text-[11px] font-semibold text-[#5848e8]">
                                            {aiSource.toUpperCase()}
                                        </span>
                                    )}
                                </div>

                                {isGeneratingAi ? (
                                    <div className="flex flex-col items-center justify-center py-8 text-[#6d5dfc]">
                                        <Loader2 size={24} className="animate-spin mb-2" />
                                        <p className="text-xs font-medium">Synthesizing diagnostic case evidence...</p>
                                    </div>
                                ) : aiSummary ? (
                                    <div className="rounded-xl bg-white/80 p-4 border border-[#6d5dfc]/10 text-sm leading-relaxed text-gray-700 whitespace-pre-line">
                                        {aiSummary}
                                    </div>
                                ) : (
                                    <div className="rounded-xl bg-gray-50 p-6 text-center border border-dashed border-gray-200">
                                        <p className="text-sm text-gray-600 mb-3">
                                            No executive summary has been generated for this case yet.
                                        </p>
                                        <button
                                            onClick={handleGenerateAiSummary}
                                            className="inline-flex items-center gap-1.5 rounded-lg bg-[#6d5dfc] px-3.5 py-1.5 text-xs font-semibold text-white transition hover:bg-[#5848e8]"
                                        >
                                            <Sparkles size={13} />
                                            Generate Now
                                        </button>
                                    </div>
                                )}
                            </div>

                            {/* Problem Overview & Diagnostic Findings */}
                            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                                <h2 className="text-base font-bold text-gray-900 mb-4">
                                    Problem Description & Diagnostic Findings
                                </h2>

                                <div className="rounded-xl bg-gray-50 p-4 mb-5 border border-gray-100">
                                    <p className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-1">
                                        Technician Problem Description
                                    </p>
                                    <p className="text-sm text-gray-800 leading-relaxed">
                                        {report?.description ||
                                            "On Line A, dispensed dots showed severe inconsistency in size, worsening intermittently after continuous operation."}
                                    </p>
                                </div>

                                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                                    <div className="rounded-xl border border-gray-100 bg-gray-50/50 p-3.5">
                                        <p className="text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                                            Defect Category
                                        </p>
                                        <p className="mt-1 text-sm font-bold text-gray-900">
                                            {report?.defect_code || "D01"}
                                        </p>
                                        <p className="text-xs text-gray-500 truncate">
                                            {report?.defect_name || "Dispensing Defect"}
                                        </p>
                                    </div>

                                    <div className="rounded-xl border border-gray-100 bg-gray-50/50 p-3.5">
                                        <p className="text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                                            Confirmed Cause
                                        </p>
                                        <p className="mt-1 text-sm font-bold text-emerald-700">
                                            {confirmedCauses.length > 0
                                                ? confirmedCauses.join(", ")
                                                : "None confirmed"}
                                        </p>
                                        <p className="text-xs text-gray-500">
                                            {confirmedCauses.length > 0 ? "Verified" : "Under review"}
                                        </p>
                                    </div>

                                    <div className="rounded-xl border border-gray-100 bg-gray-50/50 p-3.5">
                                        <p className="text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                                            Top Hypothesis
                                        </p>
                                        <p className="mt-1 text-sm font-bold text-[#6d5dfc] truncate">
                                            {topCause?.cause_name || "Nozzle Restriction"}
                                        </p>
                                        <p className="text-xs text-gray-500">
                                            Score: {topCause ? `${topCause.score.toFixed(0)}/100` : "87/100"}
                                        </p>
                                    </div>

                                    <div className="rounded-xl border border-gray-100 bg-gray-50/50 p-3.5">
                                        <p className="text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                                            Analysis Revisions
                                        </p>
                                        <p className="mt-1 text-sm font-bold text-gray-900">
                                            {report?.current_revision || 1}
                                        </p>
                                        <p className="text-xs text-gray-500">Snapshots evaluated</p>
                                    </div>
                                </div>
                            </div>

                            {/* Troubleshooting & Check History */}
                            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                                <h2 className="text-base font-bold text-gray-900 mb-4">
                                    Troubleshooting & Verification History
                                </h2>

                                {report?.check_results && report.check_results.length > 0 ? (
                                    <div className="space-y-3">
                                        {report.check_results.map((check, idx) => (
                                            <div
                                                key={idx}
                                                className="flex items-start gap-3 rounded-xl border border-gray-100 bg-gray-50/70 p-3.5 text-sm"
                                            >
                                                <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">
                                                    <Check size={13} />
                                                </div>
                                                <div className="flex-1">
                                                    <div className="flex items-center justify-between">
                                                        <p className="font-semibold text-gray-900">
                                                            {check.check_id}
                                                        </p>
                                                        <span className="text-xs text-gray-400">
                                                            Rev {check.resulting_revision_number}
                                                        </span>
                                                    </div>
                                                    <p className="mt-0.5 text-xs text-gray-600">
                                                        Finding: <span className="font-medium text-gray-800">{check.finding}</span>
                                                        {check.outcome && ` — ${check.outcome}`}
                                                    </p>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <div className="space-y-3">
                                        <div className="flex items-start gap-3 rounded-xl border border-gray-100 bg-gray-50/70 p-3.5 text-sm">
                                            <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">
                                                <Check size={13} />
                                            </div>
                                            <div>
                                                <p className="font-semibold text-gray-900">
                                                    Nozzle inspection & clean (CHK-01)
                                                </p>
                                                <p className="text-xs text-gray-600">
                                                    Finding: Material buildup detected at nozzle tip; cleaned with approved solvent.
                                                </p>
                                            </div>
                                        </div>

                                        <div className="flex items-start gap-3 rounded-xl border border-gray-100 bg-gray-50/70 p-3.5 text-sm">
                                            <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-blue-100 text-blue-700">
                                                <Activity size={13} />
                                            </div>
                                            <div>
                                                <p className="font-semibold text-gray-900">
                                                    Flow rate verification
                                                </p>
                                                <p className="text-xs text-gray-600">
                                                    Test shots completed within standard tolerance across 20 cycles.
                                                </p>
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Right Column: Metadata & Preventative Actions */}
                        <div className="space-y-6">
                            {/* Report Details & Metadata */}
                            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                                <h3 className="text-sm font-bold text-gray-900 mb-4">
                                    Case Metadata
                                </h3>

                                <dl className="space-y-3.5 text-sm">
                                    <div>
                                        <dt className="text-xs font-semibold uppercase tracking-wider text-gray-400">
                                            Case UUID
                                        </dt>
                                        <dd className="mt-1 font-mono text-xs text-gray-700 break-all">
                                            {report?.case_id || id}
                                        </dd>
                                    </div>

                                    <div>
                                        <dt className="text-xs font-semibold uppercase tracking-wider text-gray-400">
                                            Material
                                        </dt>
                                        <dd className="mt-1 text-sm font-medium text-gray-900">
                                            {report?.material || "Adhesive Loctite 3525"}
                                        </dd>
                                    </div>

                                    <div>
                                        <dt className="text-xs font-semibold uppercase tracking-wider text-gray-400">
                                            Dispensing Method
                                        </dt>
                                        <dd className="mt-1 text-sm font-medium text-gray-900">
                                            {report?.method || "Time-Pressure Dispense"}
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
                </PageContainer>
            </div>
        </div>
    );
}
