"use client";

import { useEffect, useState, useCallback, use, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
    ArrowLeft,
    CheckCircle2,
    Download,
    FileText,
    Calendar,
    AlertTriangle,
    Sparkles,
    Loader2,
    ShieldCheck,
    AlertCircle,
} from "lucide-react";

import PageContainer from "@/components/layout/PageContainer";
import { reportsApi, CaseReportResponse, EightDReportResponse } from "@/lib/api/reports";
import EightDReportView from "@/components/reports/EightDReportView";
import ReportPreview from "@/components/reports/ReportPreview";

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

    const reloadReport = useCallback(() => {
        if (!id) return;
        setIsLoading(true);
        setError(null);
        reportsApi
            .getCaseReport(id)
            .then((data) => {
                setReport(data);
                if (data.current_diagnosis?.explanation) {
                    setAiSummary(data.current_diagnosis.explanation);
                    setAiSource("deterministic");
                }
                setError(null);
            })
            .catch((err: unknown) => {
                console.error("Failed to load real case report:", err);
                setError(err instanceof Error ? err.message : "Failed to load case report.");
            })
            .finally(() => {
                setIsLoading(false);
            });
    }, [id]);

    useEffect(() => {
        if (!id) return;
        let isCurrent = true;
        reportsApi
            .getCaseReport(id)
            .then((data) => {
                if (isCurrent) {
                    setReport(data);
                    if (data.current_diagnosis?.explanation) {
                        setAiSummary(data.current_diagnosis.explanation);
                        setAiSource("deterministic");
                    }
                    setError(null);
                    setIsLoading(false);
                }
            })
            .catch((err: unknown) => {
                if (isCurrent) {
                    console.error("Failed to load real case report:", err);
                    setError(err instanceof Error ? err.message : "Failed to load case report.");
                    setIsLoading(false);
                }
            });

        return () => {
            isCurrent = false;
        };
    }, [id]);

    const fetch8DData = async () => {
        try {
            setIsLoading8D(true);
            const data = await reportsApi.get8DReport(id);
            setEightDReport(data);
        } catch (err: unknown) {
            console.warn("Failed to load 8D report:", err);
        } finally {
            setIsLoading8D(false);
        }
    };

    useEffect(() => {
        if (reportFormat === "8d" && !eightDReport) {
            fetch8DData();
        }
    }, [reportFormat, id, eightDReport]);

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
        } catch (err: unknown) {
            console.error("Error generating AI summary:", err);
            alert("Unable to generate AI summary: " + (err instanceof Error ? err.message : "Unknown error"));
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
                    {isLoading ? (
                        <div className="flex min-h-[400px] flex-col items-center justify-center">
                            <Loader2 size={32} className="animate-spin text-[#6d5dfc] mb-3" />
                            <p className="text-sm font-medium text-gray-500">Loading diagnostic case report...</p>
                        </div>
                    ) : error || !report ? (
                        <div className="rounded-2xl border border-rose-200 bg-white p-8 text-center shadow-sm">
                            <AlertCircle className="h-10 w-10 text-rose-500 mx-auto mb-3" />
                            <h2 className="text-base font-bold text-gray-900">Report Unavailable</h2>
                            <p className="mt-1 text-sm text-gray-600 mb-4">{error || "The requested case report could not be found."}</p>
                            <button
                                onClick={reloadReport}
                                className="rounded-xl bg-[#6d5dfc] px-4 py-2 text-xs font-semibold text-white hover:bg-[#5848e8] transition"
                            >
                                Try Again
                            </button>
                        </div>
                    ) : (
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

                                        {report.current_revision && (
                                            <span className="text-xs font-medium text-[#6d5dfc] bg-[#6d5dfc]/10 px-2.5 py-0.5 rounded-full">
                                                Revision {report.current_revision}
                                            </span>
                                        )}
                                    </div>

                                    <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-gray-900">
                                        {report.defect_name || report.description || "Dispensing Diagnostic Report"}
                                    </h1>

                                    <div className="mt-2.5 flex flex-wrap items-center gap-4 text-xs sm:text-sm text-gray-500">
                                        <div className="flex items-center gap-1.5 font-mono">
                                            <FileText size={15} className="text-gray-400" />
                                            <span className="font-semibold text-gray-700">{reportCode}</span>
                                        </div>

                                        <div className="flex items-center gap-1.5">
                                            <Calendar size={15} className="text-gray-400" />
                                            <span>
                                                {report.created_at
                                                    ? new Date(report.created_at).toLocaleString()
                                                    : "Not recorded"}
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

                            {/* Executive Summary Card if generated */}
                            {aiSummary && (
                                <div className="mb-6 relative overflow-hidden rounded-2xl border border-[#6d5dfc]/20 bg-gradient-to-br from-white via-white to-[#f5f3ff] p-6 shadow-sm">
                                    <div className="flex items-center justify-between mb-4">
                                        <div className="flex items-center gap-2">
                                            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#6d5dfc] text-white">
                                                <Sparkles size={16} />
                                            </div>
                                            <div>
                                                <h2 className="text-base font-bold text-gray-900">
                                                    Executive Summary
                                                </h2>
                                                <p className="text-xs text-gray-500">
                                                    {aiSource === "llm"
                                                        ? "Synthesized by Bounded LLM Service"
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

                                    <div className="rounded-xl bg-white/80 p-4 border border-[#6d5dfc]/10 text-sm leading-relaxed text-gray-700 whitespace-pre-line">
                                        {aiSummary}
                                    </div>
                                </div>
                            )}

                            {/* Formal Typed Report Preview */}
                            <ReportPreview report={report} />
                        </>
                    )}
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
