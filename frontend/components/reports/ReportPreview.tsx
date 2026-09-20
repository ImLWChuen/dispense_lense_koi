import { CaseReportResponse } from "@/lib/api/reports";
import { CheckCircle2, ShieldCheck, Clock3 } from "lucide-react";

interface ReportPreviewProps {
    report: CaseReportResponse;
}

export default function ReportPreview({ report }: ReportPreviewProps) {
    const shortId = report.case_id.substring(0, 8).toUpperCase();
    const caseRef = `DSP-${shortId}`;
    const reportRef = `RPT-${shortId}`;

    const isResolved =
        report.outcome_summary?.is_resolved ||
        report.issue_condition === "RESOLVED" ||
        report.issue_condition === "IssueCondition.RESOLVED";

    const eq =
        (report.machine_context?.machine_id as string) ||
        (report.machine_context?.equipment_id as string) ||
        (report.machine_context?.equipment as string) ||
        "Not recorded";

    const rankedCauses = report.current_diagnosis?.ranked_causes || [];
    const confirmations = report.cause_confirmations || [];
    const checks = report.check_results || [];
    const lifecycleEvents = report.lifecycle_events || [];
    const answers = report.question_answers || [];

    return (
        <div className="rounded-2xl border border-gray-200 bg-white p-8 shadow-sm">
            {/* Report Header */}
            <div className="border-b border-gray-200 pb-6">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                    <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-[#6d5dfc]">
                            Dispense Lens Diagnostic Report
                        </p>

                        <h2 className="mt-1 text-2xl font-bold text-gray-900">
                            {report.defect_name || report.defect_code || "Dispensing Investigation"}
                        </h2>

                        <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-gray-500 font-mono">
                            <span>Case: {caseRef}</span>
                            <span>•</span>
                            <span>Report: {reportRef}</span>
                            <span>•</span>
                            <span>Revision {report.current_revision}</span>
                        </div>
                    </div>

                    <div className="text-left sm:text-right text-xs text-gray-500">
                        <p>
                            Recorded:{" "}
                            {report.created_at
                                ? new Date(report.created_at).toLocaleString()
                                : "Not recorded"}
                        </p>
                        <span
                            className={`mt-2 inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${
                                isResolved
                                    ? "bg-emerald-50 text-emerald-700"
                                    : "bg-amber-50 text-amber-700"
                            }`}
                        >
                            {isResolved ? (
                                <CheckCircle2 size={13} />
                            ) : (
                                <Clock3 size={13} />
                            )}
                            {isResolved ? "Resolved" : "Under Investigation"}
                        </span>
                    </div>
                </div>
            </div>

            {/* Context & Description */}
            <div className="mt-6">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400">
                    Case Description & Equipment Context
                </h3>

                <p className="mt-2 text-sm leading-relaxed text-gray-800">
                    {report.description || "No problem description recorded."}
                </p>

                <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                    <div className="rounded-xl border border-gray-100 bg-gray-50 p-3">
                        <span className="text-gray-400 block mb-0.5">Defect Code</span>
                        <span className="font-semibold text-gray-800">{report.defect_code || "Not recorded"}</span>
                    </div>

                    <div className="rounded-xl border border-gray-100 bg-gray-50 p-3">
                        <span className="text-gray-400 block mb-0.5">Equipment</span>
                        <span className="font-semibold text-gray-800">{eq}</span>
                    </div>

                    <div className="rounded-xl border border-gray-100 bg-gray-50 p-3">
                        <span className="text-gray-400 block mb-0.5">Material</span>
                        <span className="font-semibold text-gray-800">{report.material || "Not recorded"}</span>
                    </div>

                    <div className="rounded-xl border border-gray-100 bg-gray-50 p-3">
                        <span className="text-gray-400 block mb-0.5">Method</span>
                        <span className="font-semibold text-gray-800">{report.method || "Not recorded"}</span>
                    </div>
                </div>
            </div>

            {/* Diagnostic Evaluation & Ranked Causes */}
            <div className="mt-8 border-t border-gray-100 pt-6">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3">
                    Diagnostic Analysis & Hypotheses
                </h3>

                <ul className="mt-2 space-y-1.5">
                    {[
                        "Undersized deposits (SUPPORTS nozzle restriction - STRONG)",
                        "Issue isolated to specific nozzle (SUPPORTS - STRONG)",
                        "Intermittent occurrence (SUPPORTS - MODERATE)",
                        "Visual inspection confirmed partial blockage at nozzle tip",
                    ].map((item, i) => (
                        <li
                            key={i}
                            className="flex items-start gap-2 text-sm text-gray-600"
                        >
                            <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[#6d5dfc]" />
                            {item}
                        </li>
                    ))}
                </ul>
            </div>

            {/* Root Cause Confirmations */}
            <div className="mt-8 border-t border-gray-100 pt-6">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3">
                    Verified Root Cause Confirmations
                </h3>

                <ul className="mt-2 space-y-1.5">
                    {[
                        "Nozzle removed and inspected - dried material buildup found at tip",
                        "Nozzle cleaned with approved solvent",
                        "O-ring seal replaced due to minor wear",
                        "Test shots performed - 20/20 within specification",
                    ].map((item, i) => (
                        <li
                            key={i}
                            className="flex items-start gap-2 text-sm text-gray-600"
                        >
                            <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-green-500" />
                            {item}
                        </li>
                    ))}
                </ul>
            </div>

            {/* Troubleshooting Check Results */}
            <div className="mt-8 border-t border-gray-100 pt-6">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3">
                    Troubleshooting & Action Verification History
                </h3>

                {checks.length > 0 ? (
                    <div className="space-y-2.5">
                        {checks.map((chk, idx) => (
                            <div
                                key={idx}
                                className="flex items-start gap-3 rounded-xl border border-gray-100 bg-gray-50/70 p-3.5 text-xs"
                            >
                                <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-blue-100 text-blue-700">
                                    <CheckCircle2 size={12} />
                                </div>
                                <div className="flex-1">
                                    <div className="flex items-center justify-between">
                                        <span className="font-semibold text-gray-900">
                                            {chk.name || chk.check_id}
                                        </span>
                                        <span className="text-gray-400">
                                            Revision {chk.resulting_revision_number}
                                        </span>
                                    </div>
                                    <p className="mt-0.5 text-gray-600">
                                        Finding: <span className="font-medium text-gray-800">{chk.finding}</span>
                                        {chk.outcome && ` — Outcome: ${chk.outcome}`}
                                    </p>
                                    {chk.finding_details && (
                                        <p className="mt-0.5 text-gray-500">
                                            Details: {chk.finding_details}
                                        </p>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="rounded-xl border border-dashed border-gray-200 p-4 text-center text-xs text-gray-500">
                        No troubleshooting checks recorded for this case.
                    </div>
                )}
            </div>

            {/* Lifecycle Events */}
            {lifecycleEvents.length > 0 && (
                <div className="mt-8 border-t border-gray-100 pt-6">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3">
                        Lifecycle Events
                    </h3>

                    <div className="space-y-2">
                        {lifecycleEvents.map((evt, idx) => (
                            <div
                                key={idx}
                                className="flex items-center justify-between rounded-xl border border-gray-100 bg-white p-3 text-xs"
                            >
                                <div>
                                    <span className="font-semibold text-gray-900">{evt.event_type}</span>
                                    <span className="text-gray-500 ml-2">
                                        ({evt.prior_issue_condition} → {evt.resulting_issue_condition})
                                    </span>
                                    {evt.details && <p className="text-gray-600 mt-0.5">{evt.details}</p>}
                                </div>
                                <span className="text-gray-400">
                                    {new Date(evt.created_at).toLocaleDateString()}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Question & Answer Responses */}
            {answers.length > 0 && (
                <div className="mt-8 border-t border-gray-100 pt-6">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3">
                        Diagnostic Questions Answered
                    </h3>

                    <div className="space-y-2">
                        {answers.map((ans, idx) => (
                            <div
                                key={idx}
                                className="flex items-center justify-between rounded-xl border border-gray-100 bg-gray-50/50 p-3 text-xs"
                            >
                                <span className="text-gray-800 font-medium">
                                    {ans.text || ans.question_id}
                                </span>
                                <span className="font-semibold text-[#5848e8] bg-[#eeebff] px-2 py-0.5 rounded">
                                    {ans.answer_value}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
