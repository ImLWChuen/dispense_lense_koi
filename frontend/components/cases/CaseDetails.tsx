import Link from "next/link";
import {
    CheckCircle2,
    Clock3,
    AlertTriangle,
    User,
    Calendar,
    Stethoscope,
    GitBranch,
} from "lucide-react";
import type { DurableCaseResponse } from "@/types/api";
import {
    deriveCaseTimeline,
    deriveCurrentRevision,
    deriveTopRankedCause,
    deriveCaseOwner,
    formatIssueCondition,
    formatCaseTimestamp,
} from "@/lib/case-detail-state";

interface CaseDetailsProps {
    caseData?: DurableCaseResponse | null;
}

const statusColors: Record<string, string> = {
    UNRESOLVED: "bg-yellow-100 text-yellow-700 border border-yellow-200",
    RECOVERY_PENDING_VERIFICATION: "bg-blue-100 text-blue-700 border border-blue-200",
    RESOLVED: "bg-emerald-100 text-emerald-700 border border-emerald-200",
    RECURRED: "bg-red-100 text-red-700 border border-red-200",
};

export default function CaseDetails({ caseData }: CaseDetailsProps) {
    if (!caseData) {
        return (
            <div className="rounded-2xl border border-gray-200 bg-white p-8 shadow-sm flex flex-col items-center justify-center text-center text-gray-500">
                <p className="text-sm font-medium">Case details not available.</p>
            </div>
        );
    }

    const timeline = deriveCaseTimeline(caseData);
    const currentRevision = deriveCurrentRevision(caseData);
    const topCause = deriveTopRankedCause(caseData);
    const caseOwner = deriveCaseOwner(caseData);
    const isResolved =
        caseData.issue_condition === "RESOLVED" ||
        caseData.issue_condition === "IssueCondition.RESOLVED";

    const cleanCondition = caseData.issue_condition.replace("IssueCondition.", "");
    const badgeStyle =
        statusColors[cleanCondition] || "bg-gray-100 text-gray-700 border border-gray-200";

    return (
        <div className="space-y-6">
            {/* Header Card */}
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
                    <div>
                        <div className="flex items-center gap-2.5">
                            <h2 className="text-xl font-bold font-mono text-gray-900">
                                {caseData.case_id}
                            </h2>
                            <span className="text-xs font-semibold text-gray-400">•</span>
                            <span className="text-xs font-medium text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full">
                                Case Detail
                            </span>
                        </div>

                        <p className="mt-1.5 text-sm text-gray-600 font-medium">
                            {caseData.defect_name || caseData.defect_code || "Unknown Defect"}
                            {caseData.machine_context?.equipment
                                ? ` · ${String(caseData.machine_context.equipment)}`
                                : ""}
                        </p>
                    </div>

                    <span
                        className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold self-start ${badgeStyle}`}
                    >
                        {isResolved ? <CheckCircle2 size={13} /> : <AlertTriangle size={13} />}
                        {formatIssueCondition(caseData.issue_condition)}
                    </span>
                </div>

                {/* Persisted Metadata Grid */}
                <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4 border-t border-gray-100 pt-5">
                    <div className="flex items-center gap-2.5">
                        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gray-100 text-gray-500 shrink-0">
                            <User size={15} />
                        </div>
                        <div>
                            <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
                                Case Owner
                            </p>
                            <p className="text-xs font-medium text-gray-700 truncate">{caseOwner}</p>
                        </div>
                    </div>

                    <div className="flex items-center gap-2.5">
                        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gray-100 text-gray-500 shrink-0">
                            <Calendar size={15} />
                        </div>
                        <div>
                            <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
                                Created
                            </p>
                            <p className="text-xs font-medium text-gray-700 truncate">
                                {formatCaseTimestamp(caseData.created_at)}
                            </p>
                        </div>
                    </div>

                    <div className="flex items-center gap-2.5">
                        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#eeebff] text-[#6d5dfc] shrink-0">
                            <GitBranch size={15} />
                        </div>
                        <div>
                            <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
                                Revision
                            </p>
                            <p className="text-xs font-semibold text-gray-900">
                                Rev {currentRevision}
                            </p>
                        </div>
                    </div>

                    <div className="flex items-center gap-2.5">
                        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gray-100 text-gray-500 shrink-0">
                            <Stethoscope size={15} />
                        </div>
                        <div>
                            <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
                                Top Cause
                            </p>
                            <p className="text-xs font-medium text-gray-700 truncate">
                                {topCause || "None identified"}
                            </p>
                        </div>
                    </div>
                </div>

                {/* Primary Action Links */}
                <div className="mt-6 flex flex-wrap gap-3 border-t border-gray-100 pt-5">
                    <Link
                        href={`/diagnosis/${caseData.case_id}`}
                        className="rounded-xl bg-[#6d5dfc] px-4 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-[#5848e8]"
                    >
                        View Diagnosis
                    </Link>

                    <Link
                        href={`/reports/${caseData.case_id}`}
                        className="rounded-xl border border-gray-200 bg-white px-4 py-2 text-xs font-semibold text-gray-700 shadow-sm transition hover:bg-gray-50"
                    >
                        View Report
                    </Link>
                </div>
            </div>

            {/* Timeline */}
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                <div className="flex items-center justify-between border-b border-gray-100 pb-4">
                    <div>
                        <h3 className="text-base font-bold text-gray-900">Case Timeline</h3>
                        <p className="mt-0.5 text-xs text-gray-500">
                            Deterministic chronological audit of all case events and revisions
                        </p>
                    </div>
                    <span className="text-xs font-medium text-gray-400">
                        {timeline.length} {timeline.length === 1 ? "event" : "events"}
                    </span>
                </div>

                <div className="mt-6 space-y-0">
                    {timeline.length === 0 ? (
                        <p className="text-xs text-gray-500 italic py-4">No events found.</p>
                    ) : (
                        timeline.map((entry, index) => (
                            <div key={entry.key} className="relative flex gap-4 pb-6 last:pb-0">
                                {index < timeline.length - 1 && (
                                    <div className="absolute left-[13px] top-6 h-full w-px bg-gray-200" />
                                )}
                                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#eeebff] text-[#6d5dfc] z-10">
                                    <Clock3 size={13} />
                                </div>
                                <div className="flex-1 min-w-0">
                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                        <p className="text-sm font-semibold text-gray-900">
                                            {entry.event}
                                        </p>
                                        <div className="flex items-center gap-2">
                                            {entry.revision !== undefined && (
                                                <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-mono font-medium text-gray-600">
                                                    Rev {entry.revision}
                                                </span>
                                            )}
                                            <span className="text-[11px] text-gray-400">
                                                {entry.displayTime}
                                            </span>
                                        </div>
                                    </div>
                                    <p className="mt-1 text-xs text-gray-600 leading-relaxed">
                                        {entry.detail}
                                    </p>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </div>
        </div>
    );
}
