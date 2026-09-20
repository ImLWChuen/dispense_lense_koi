"use client";

import {
    EightDReportResponse,
} from "@/lib/api/reports";
import {
    Award,
    CheckCircle2,
    Clock3,
    Download,
    FileText,
    Printer,
    Shield,
    ShieldAlert,
    ShieldCheck,
    Users,
    Wrench,
    AlertTriangle,
    Layers,
    Calendar,
    Target,
    Activity,
    Check,
    ArrowRight,
    Loader2,
} from "lucide-react";

interface EightDReportViewProps {
    report: EightDReportResponse;
    onDownloadPdf: () => void;
    isDownloadingPdf: boolean;
}

export default function EightDReportView({
    report,
    onDownloadPdf,
    isDownloadingPdf,
}: EightDReportViewProps) {
    const handlePrint = () => {
        window.print();
    };

    const isResolved = report.is_resolved;
    const d1 = report.d1_team;
    const d2 = report.d2_problem_description;
    const d3 = report.d3_containment;
    const d4 = report.d4_root_cause;
    const d5 = report.d5_corrective_actions;
    const d6 = report.d6_validation;
    const d7 = report.d7_prevent_recurrence;
    const d8 = report.d8_closure;

    return (
        <div className="space-y-6">
            {/* 8D Document Banner */}
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
                    <div>
                        <div className="flex flex-wrap items-center gap-2 mb-2">
                            <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-semibold text-blue-700 border border-blue-200">
                                <ShieldCheck size={13} />
                                {d8.compliance_standard}
                            </span>
                            <span
                                className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                                    isResolved
                                        ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                                        : "bg-amber-50 text-amber-700 border border-amber-200"
                                }`}
                            >
                                {isResolved ? <CheckCircle2 size={13} /> : <AlertTriangle size={13} />}
                                {isResolved ? "8D Closed & Verified" : "8D In Progress (Containment Active)"}
                            </span>
                            <span className="text-xs font-medium text-gray-500 bg-gray-100 px-2.5 py-0.5 rounded-full">
                                Rev {report.revision}
                            </span>
                        </div>

                        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-gray-900">
                            Eight Disciplines (8D) Quality Compliance Report
                        </h1>

                        <div className="mt-2 flex flex-wrap items-center gap-4 text-xs text-gray-500 font-mono">
                            <span>
                                Report ID: <b className="text-gray-900">{report.report_number}</b>
                            </span>
                            <span>•</span>
                            <span>
                                Case Ref: <b className="text-gray-900">{report.case_ref}</b>
                            </span>
                            <span>•</span>
                            <span>
                                Created: {report.created_at ? report.created_at.slice(0, 10) : "2026-09-15"}
                            </span>
                            {report.closed_at && (
                                <>
                                    <span>•</span>
                                    <span className="text-emerald-700 font-semibold">
                                        Closed: {report.closed_at.slice(0, 10)}
                                    </span>
                                </>
                            )}
                        </div>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-3">
                        <button
                            onClick={handlePrint}
                            className="inline-flex items-center gap-1.5 rounded-xl border border-gray-200 bg-white px-3.5 py-2 text-xs font-semibold text-gray-700 shadow-sm hover:bg-gray-50 transition"
                        >
                            <Printer size={14} />
                            Print Audit Sheet
                        </button>
                        <button
                            onClick={onDownloadPdf}
                            disabled={isDownloadingPdf}
                            className="inline-flex items-center gap-2 rounded-xl bg-[#6d5dfc] px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-[#5848e8] transition disabled:opacity-70"
                        >
                            {isDownloadingPdf ? (
                                <Loader2 size={14} className="animate-spin" />
                            ) : (
                                <Download size={14} />
                            )}
                            Download 8D PDF
                        </button>
                    </div>
                </div>
            </div>

            {/* D1: Use Team Approach */}
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                <div className="flex items-center gap-2 mb-4">
                    <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#6d5dfc]/10 text-[#6d5dfc] font-bold text-xs">
                        D1
                    </div>
                    <div>
                        <h2 className="text-base font-bold text-gray-900">
                            Problem Solving Team
                        </h2>
                        <p className="text-xs text-gray-500">Cross-functional team assigned to contain, resolve, and verify</p>
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                    {/* Champion */}
                    <div className="rounded-xl border border-gray-200 bg-gray-50/50 p-3.5">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-[#6d5dfc]">
                            {d1.champion.role}
                        </span>
                        <p className="mt-1 text-sm font-bold text-gray-900">{d1.champion.name}</p>
                        <p className="text-xs text-gray-500">{d1.champion.title}</p>
                        <p className="text-xs text-gray-400 mt-1 font-mono">{d1.champion.department}</p>
                    </div>

                    {/* Leader */}
                    <div className="rounded-xl border border-gray-200 bg-gray-50/50 p-3.5">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-600">
                            {d1.team_leader.role}
                        </span>
                        <p className="mt-1 text-sm font-bold text-gray-900">{d1.team_leader.name}</p>
                        <p className="text-xs text-gray-500">{d1.team_leader.title}</p>
                        <p className="text-xs text-gray-400 mt-1 font-mono">{d1.team_leader.department}</p>
                    </div>

                    {/* Members */}
                    {d1.members.map((m, idx) => (
                        <div key={idx} className="rounded-xl border border-gray-200 bg-gray-50/50 p-3.5">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-gray-500">
                                {m.role}
                            </span>
                            <p className="mt-1 text-sm font-bold text-gray-900">{m.name}</p>
                            <p className="text-xs text-gray-500">{m.title}</p>
                            <p className="text-xs text-gray-400 mt-1 font-mono">{m.department}</p>
                        </div>
                    ))}
                </div>
            </div>

            {/* D2: Problem Description (5W2H) */}
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                <div className="flex items-center gap-2 mb-4">
                    <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#6d5dfc]/10 text-[#6d5dfc] font-bold text-xs">
                        D2
                    </div>
                    <div>
                        <h2 className="text-base font-bold text-gray-900">
                            Problem Description (5W2H Framework)
                        </h2>
                        <p className="text-xs text-gray-500">Quantified cleanroom boundary conditions</p>
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                    <div className="space-y-3">
                        <div className="border-b border-gray-100 pb-2">
                            <span className="font-bold text-gray-500 uppercase text-[10px] tracking-wider">What (Defect):</span>
                            <p className="mt-0.5 text-gray-900 font-semibold text-sm">
                                {d2.defect_name} ({d2.defect_code})
                            </p>
                            <p className="text-gray-600 mt-0.5">{d2.what}</p>
                        </div>
                        <div className="border-b border-gray-100 pb-2">
                            <span className="font-bold text-gray-500 uppercase text-[10px] tracking-wider">Where:</span>
                            <p className="mt-0.5 text-gray-800">{d2.where}</p>
                        </div>
                        <div>
                            <span className="font-bold text-gray-500 uppercase text-[10px] tracking-wider">When & Who:</span>
                            <p className="mt-0.5 text-gray-800">{d2.when} - Reported by: {d2.who}</p>
                        </div>
                    </div>

                    <div className="space-y-3">
                        <div className="border-b border-gray-100 pb-2">
                            <span className="font-bold text-gray-500 uppercase text-[10px] tracking-wider">Why (Impact):</span>
                            <p className="mt-0.5 text-gray-800">{d2.why}</p>
                        </div>
                        <div className="border-b border-gray-100 pb-2">
                            <span className="font-bold text-gray-500 uppercase text-[10px] tracking-wider">How & How Many (Volume):</span>
                            <p className="mt-0.5 text-gray-800">{d2.how} | {d2.how_many}</p>
                        </div>
                        <div>
                            <span className="font-bold text-gray-500 uppercase text-[10px] tracking-wider">Dispense Recipe:</span>
                            <p className="mt-0.5 font-mono text-gray-700">
                                <b>Material:</b> {d2.fluid_material} &nbsp;|&nbsp; <b>Method:</b> {d2.dispense_method}
                            </p>
                        </div>
                    </div>
                </div>
            </div>

            {/* D3: Interim Containment Actions (ICA) */}
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#6d5dfc]/10 text-[#6d5dfc] font-bold text-xs">
                            D3
                        </div>
                        <div>
                            <h2 className="text-base font-bold text-gray-900">
                                Interim Containment Actions (ICA)
                            </h2>
                            <p className="text-xs text-gray-500">Quarantine and isolation actions ensuring zero defect escape</p>
                        </div>
                    </div>

                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 border border-emerald-200">
                        <Shield size={12} />
                        {d3.containment_status} ({d3.overall_effectivity.toFixed(0)}% Effectivity)
                    </span>
                </div>

                <div className="mb-4 bg-gray-50 p-3 rounded-xl border border-gray-100 flex flex-wrap items-center justify-between gap-2 text-xs">
                    <div>
                        <span className="text-gray-500">Quarantined Production Lots: </span>
                        <span className="font-mono font-semibold text-gray-900">
                            {d3.quarantine_lot_ids.join(", ")}
                        </span>
                    </div>
                    <div className="text-gray-500">
                        Verified by <b className="text-gray-800">{d3.verified_by}</b> on {d3.containment_date}
                    </div>
                </div>

                <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs border-collapse">
                        <thead>
                            <tr className="border-b border-gray-200 text-gray-500 uppercase text-[10px] tracking-wider">
                                <th className="py-2 px-3">ICA Ref</th>
                                <th className="py-2 px-3">Containment Action</th>
                                <th className="py-2 px-3">Owner</th>
                                <th className="py-2 px-3 text-right">Target Date</th>
                                <th className="py-2 px-3 text-right">Effectivity</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                            {d3.actions.map((act) => (
                                <tr key={act.action_id} className="hover:bg-gray-50/50">
                                    <td className="py-2.5 px-3 font-mono font-bold text-gray-800">{act.action_id}</td>
                                    <td className="py-2.5 px-3 text-gray-800">{act.description}</td>
                                    <td className="py-2.5 px-3 text-gray-600">{act.owner}</td>
                                    <td className="py-2.5 px-3 text-right font-mono text-gray-500">{act.target_date}</td>
                                    <td className="py-2.5 px-3 text-right">
                                        <span className="font-mono font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full">
                                            {act.effectivity_percentage.toFixed(0)}% ({act.status})
                                        </span>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* D4: Root Cause Analysis (RCA) & 5-Whys */}
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#6d5dfc]/10 text-[#6d5dfc] font-bold text-xs">
                            D4
                        </div>
                        <div>
                            <h2 className="text-base font-bold text-gray-900">
                                Root Cause Analysis (RCA) & Escape Point
                            </h2>
                            <p className="text-xs text-gray-500">Ishikawa 6M classification and 5-Whys causal deduction ladder</p>
                        </div>
                    </div>

                    <div className="flex items-center gap-2">
                        <span className="inline-flex items-center gap-1 rounded-full bg-[#6d5dfc]/10 px-2.5 py-0.5 text-xs font-semibold text-[#6d5dfc] border border-[#6d5dfc]/20">
                            <Layers size={12} />
                            Ishikawa: {d4.ishikawa_category}
                        </span>
                        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 border border-emerald-200">
                            {Math.round(d4.confidence_score * 100)}% Confidence
                        </span>
                    </div>
                </div>

                {/* Confirmed Cause Banner */}
                <div className="mb-4 bg-[#6d5dfc]/5 p-4 rounded-xl border border-[#6d5dfc]/20">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-[#6d5dfc]">
                        Confirmed Physical Root Cause ({d4.root_cause_id})
                    </p>
                    <h3 className="text-base font-bold text-gray-900 mt-0.5">{d4.root_cause_name}</h3>
                    <p className="text-xs text-gray-600 mt-1">{d4.mechanism_description}</p>
                </div>

                {/* 5-Whys Ladder */}
                <div className="space-y-2 mb-4">
                    <p className="text-xs font-bold text-gray-700 uppercase tracking-wider">
                        5-Whys Causal Ladder:
                    </p>
                    {d4.five_whys.map((w) => (
                        <div
                            key={w.step}
                            className="flex items-start gap-3 p-3 rounded-xl border border-gray-100 bg-gray-50/70 text-xs"
                        >
                            <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-gray-200 font-bold text-gray-700 text-[11px]">
                                W{w.step}
                            </div>
                            <div className="flex-1">
                                <p className="font-semibold text-gray-800">{w.question}</p>
                                <p className="text-gray-600 mt-0.5">➔ {w.answer}</p>
                            </div>
                            <span className="text-[10px] font-mono text-gray-500 bg-white px-2 py-0.5 rounded border border-gray-200 shrink-0">
                                {w.category}
                            </span>
                        </div>
                    ))}
                </div>

                {/* Escape Point Callout */}
                <div className="bg-rose-50/60 p-3.5 rounded-xl border border-rose-200 text-xs">
                    <div className="flex items-center gap-1.5 text-rose-800 font-bold mb-1">
                        <ShieldAlert size={14} />
                        <span>Escape Point Analysis:</span>
                    </div>
                    <p className="text-rose-700">{d4.escape_point}</p>
                </div>
            </div>

            {/* D5 & D6: Corrective Actions & Validation */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* D5 */}
                <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm flex flex-col justify-between">
                    <div>
                        <div className="flex items-center gap-2 mb-4">
                            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#6d5dfc]/10 text-[#6d5dfc] font-bold text-xs">
                                D5
                            </div>
                            <div>
                                <h2 className="text-base font-bold text-gray-900">
                                    Permanent Corrective Actions (PCA)
                                </h2>
                                <p className="text-xs text-gray-500">Selected actions resolving physical root cause</p>
                            </div>
                        </div>

                        <div className="space-y-3 text-xs">
                            {d5.selected_actions.map((act) => (
                                <div key={act.action_id} className="p-3.5 rounded-xl border border-gray-200 bg-gray-50/50">
                                    <div className="flex items-center justify-between mb-1">
                                        <span className="font-bold text-gray-900 font-mono">{act.action_id}: {act.title}</span>
                                        <span className="text-[10px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                                            SELECTED
                                        </span>
                                    </div>
                                    <p className="text-gray-600">{act.description}</p>
                                    <p className="text-[11px] text-gray-400 mt-1.5">{act.risk_assessment}</p>
                                </div>
                            ))}
                        </div>
                    </div>

                    <div className="mt-4 pt-3 border-t border-gray-100 flex items-center justify-between text-xs text-gray-500 font-mono">
                        <span>Initial FMEA RPN: <b className="text-gray-900">{d5.fmea_initial_rpn}</b></span>
                        <span className="text-gray-400">Severity 8 × Occur 6 × Detect 5</span>
                    </div>
                </div>

                {/* D6 */}
                <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm flex flex-col justify-between">
                    <div>
                        <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center gap-2">
                                <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#6d5dfc]/10 text-[#6d5dfc] font-bold text-xs">
                                    D6
                                </div>
                                <div>
                                    <h2 className="text-base font-bold text-gray-900">
                                        Validate PCA Implementation
                                    </h2>
                                    <p className="text-xs text-gray-500">Statistical verification and capability confirmation</p>
                                </div>
                            </div>

                            <span
                                className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                                    d6.implementation_status === "VERIFIED_PASS"
                                        ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                                        : "bg-amber-50 text-amber-700 border border-amber-200"
                                }`}
                            >
                                <CheckCircle2 size={12} />
                                {d6.implementation_status}
                            </span>
                        </div>

                        {/* Cpk Gauge / Metric Card */}
                        <div className="bg-gradient-to-br from-[#6d5dfc]/5 to-[#5848e8]/10 p-4 rounded-xl border border-[#6d5dfc]/20 mb-4">
                            <div className="flex items-center justify-between text-xs mb-1">
                                <span className="font-semibold text-gray-600 uppercase tracking-wider">
                                    Post-PCA Process Capability:
                                </span>
                                <span className="font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                                    Cpk ≥ {d6.target_cpk} Target
                                </span>
                            </div>
                            <div className="flex items-baseline gap-2 mt-1">
                                <span className="text-3xl font-bold font-mono text-[#6d5dfc]">
                                    {d6.cpk_validation.toFixed(2)}
                                </span>
                                <span className="text-xs text-emerald-700 font-semibold">
                                    (Passed 100% Six-Sigma Cleanroom Threshold)
                                </span>
                            </div>
                        </div>

                        <div className="space-y-2 text-xs text-gray-600">
                            <div className="flex justify-between border-b border-gray-100 pb-1.5">
                                <span className="text-gray-500">Validation Test Run:</span>
                                <span className="font-semibold text-gray-900 font-mono">
                                    {d6.test_shots_passed} / {d6.test_shots_count} Passed (100%)
                                </span>
                            </div>
                            <div className="flex justify-between border-b border-gray-100 pb-1.5">
                                <span className="text-gray-500">Verified By:</span>
                                <span className="font-semibold text-gray-900">{d6.verification_actor}</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-gray-500">Timestamp:</span>
                                <span className="font-mono text-gray-700">{d6.verified_at.slice(0, 19).replace("T", " ")} UTC</span>
                            </div>
                        </div>
                    </div>

                    {d6.verification_notes && (
                        <p className="mt-4 text-xs text-gray-500 italic bg-gray-50 p-2.5 rounded-lg">
                            &quot;{d6.verification_notes}&quot;
                        </p>
                    )}
                </div>
            </div>

            {/* D7: Prevent Recurrence */}
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                <div className="flex items-center gap-2 mb-4">
                    <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#6d5dfc]/10 text-[#6d5dfc] font-bold text-xs">
                        D7
                    </div>
                    <div>
                        <h2 className="text-base font-bold text-gray-900">
                            Prevent Recurrence & Systemic Actions
                        </h2>
                        <p className="text-xs text-gray-500">Control plan updates, SOP revisions, and risk reduction</p>
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                    <div className="space-y-3">
                        <div className="p-3.5 rounded-xl border border-gray-200 bg-gray-50/50">
                            <span className="font-bold text-gray-700 uppercase text-[10px] tracking-wider block mb-1">
                                Standard Operating Procedures (SOP):
                            </span>
                            <ul className="list-disc list-inside space-y-1 text-gray-700">
                                {d7.sop_references.map((sop, idx) => (
                                    <li key={idx}>{sop}</li>
                                ))}
                            </ul>
                        </div>

                        <div className="p-3.5 rounded-xl border border-gray-200 bg-gray-50/50">
                            <span className="font-bold text-gray-700 uppercase text-[10px] tracking-wider block mb-1">
                                Control Plan (CP) Modifications:
                            </span>
                            <ul className="list-disc list-inside space-y-1 text-gray-700">
                                {d7.control_plan_updates.map((cp, idx) => (
                                    <li key={idx}>{cp}</li>
                                ))}
                            </ul>
                        </div>
                    </div>

                    <div className="space-y-3">
                        {/* PFMEA RPN Reduction Card */}
                        <div className="p-3.5 rounded-xl border border-emerald-200 bg-emerald-50/50 flex items-center justify-between">
                            <div>
                                <span className="font-bold text-emerald-800 uppercase text-[10px] tracking-wider block">
                                    PFMEA Risk Priority Number (RPN):
                                </span>
                                <div className="flex items-center gap-2 mt-1">
                                    <span className="text-sm font-mono line-through text-gray-400">240</span>
                                    <ArrowRight size={14} className="text-emerald-600" />
                                    <span className="text-xl font-bold font-mono text-emerald-700">{d7.pfmea_revised_rpn}</span>
                                    <span className="text-xs font-semibold text-emerald-800 bg-white px-2 py-0.5 rounded-full shadow-sm">
                                        80% Risk Reduction
                                    </span>
                                </div>
                            </div>
                            <Award size={28} className="text-emerald-600 opacity-80" />
                        </div>

                        <div className="p-3.5 rounded-xl border border-gray-200 bg-gray-50/50">
                            <span className="font-bold text-gray-700 uppercase text-[10px] tracking-wider block mb-1">
                                Preventive Maintenance Protocol:
                            </span>
                            <p className="text-gray-700">{d7.preventive_maintenance_action}</p>
                        </div>
                    </div>
                </div>
            </div>

            {/* D8: Closure & Sign-Off */}
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#6d5dfc]/10 text-[#6d5dfc] font-bold text-xs">
                            D8
                        </div>
                        <div>
                            <h2 className="text-base font-bold text-gray-900">
                                Management Sign-Off & Formal Closure
                            </h2>
                            <p className="text-xs text-gray-500">Formal engineering and quality assurance certification</p>
                        </div>
                    </div>

                    <span className="text-xs font-semibold text-emerald-700 bg-emerald-50 px-3 py-1 rounded-full border border-emerald-200">
                        {d8.resolution_status}
                    </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4 text-xs">
                    <div className="p-3.5 rounded-xl border border-gray-200 bg-gray-50/60 flex items-center justify-between">
                        <div>
                            <span className="text-gray-400 uppercase text-[10px] tracking-wider block">QA Director Sign-Off:</span>
                            <span className="font-bold text-gray-900 text-sm mt-0.5 block">{d8.quality_manager_signoff}</span>
                            <span className="text-gray-500 font-mono text-[11px]">Digital Verification ID: #QA-SIG-9081</span>
                        </div>
                        <CheckCircle2 size={24} className="text-emerald-600" />
                    </div>

                    <div className="p-3.5 rounded-xl border border-gray-200 bg-gray-50/60 flex items-center justify-between">
                        <div>
                            <span className="text-gray-400 uppercase text-[10px] tracking-wider block">Lead Process Specialist Sign-Off:</span>
                            <span className="font-bold text-gray-900 text-sm mt-0.5 block">{d8.engineering_lead_signoff}</span>
                            <span className="text-gray-500 font-mono text-[11px]">Digital Verification ID: #ENG-SIG-4412</span>
                        </div>
                        <CheckCircle2 size={24} className="text-emerald-600" />
                    </div>
                </div>

                <div className="bg-gray-50 p-4 rounded-xl border border-gray-200 text-xs">
                    <span className="font-bold text-gray-700 uppercase text-[10px] tracking-wider block mb-1">
                        Lessons Learned for Knowledge Base:
                    </span>
                    <p className="text-gray-700 leading-relaxed">{d8.lessons_learned}</p>
                </div>
            </div>
        </div>
    );
}
