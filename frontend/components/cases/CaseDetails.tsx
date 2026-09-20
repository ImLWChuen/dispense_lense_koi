import Link from "next/link";
import {
    CheckCircle2,
    Clock3,
    AlertTriangle,
    User,
    Calendar,
    Wrench,
    Stethoscope,
} from "lucide-react";
import { DurableCaseResponse } from "@/types/api";

interface CaseDetailsProps {
    caseData?: DurableCaseResponse;
    caseId?: string;
}

const statusColors = {
    "UNRESOLVED": "bg-yellow-100 text-yellow-700",
    "RECOVERY_PENDING_VERIFICATION": "bg-blue-100 text-blue-700",
    "RESOLVED": "bg-emerald-100 text-emerald-700",
    "RECURRED": "bg-red-100 text-red-700",
};

const formatStatus = (status: string) => {
    return status.split('_').map(word => word.charAt(0) + word.slice(1).toLowerCase()).join(' ');
};

export default function CaseDetails({ caseData }: CaseDetailsProps) {
    if (!caseData) {
        return (
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm flex justify-center text-gray-500">
                Case details not available.
            </div>
        );
    }

    const timeline = [];
    
    // Created event
    timeline.push({
        event: "Case created",
        time: new Date(caseData.created_at).toLocaleString(),
        detail: `Symptom: ${caseData.description}`
    });

    // Revisions / Diagnosis
    if (caseData.analysis_revisions && caseData.analysis_revisions.length > 0) {
        caseData.analysis_revisions.forEach((rev, idx) => {
            timeline.push({
                event: `Diagnosis Revision ${rev.revision_number}`,
                time: new Date(rev.timestamp).toLocaleString(),
                detail: rev.new_evidence_summary || `Analysis updated.`
            });
        });
    }

    // Answers
    if (caseData.previous_answers && caseData.previous_answers.length > 0) {
        caseData.previous_answers.forEach((ans) => {
            timeline.push({
                event: `Question Answered`,
                time: new Date(ans.answered_at).toLocaleString(),
                detail: `Answer: ${ans.answer_text || ans.answer_value}`
            });
        });
    }

    // Check Results
    if (caseData.previous_check_results && caseData.previous_check_results.length > 0) {
        caseData.previous_check_results.forEach((check) => {
            timeline.push({
                event: `Troubleshooting Check: ${check.execution_status}`,
                time: new Date(check.checked_at).toLocaleString(),
                detail: `Finding: ${check.finding}`
            });
        });
    }

    // Sort timeline by time
    timeline.sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());

    const isResolved = caseData.issue_condition === "RESOLVED";

    return (
        <div className="space-y-6">
            {/* Header Card */}
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                <div className="flex items-start justify-between">
                    <div>
                        <h2 className="text-xl font-bold text-gray-900">
                            {caseData.case_id}
                        </h2>

                        <p className="mt-1 text-sm text-gray-500">
                            {caseData.defect_name || caseData.defect_code || "Unknown Defect"} 
                            {caseData.machine_context?.equipment ? ` · ${caseData.machine_context.equipment}` : ""}
                        </p>
                    </div>

                    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${statusColors[caseData.issue_condition as keyof typeof statusColors] || "bg-gray-100 text-gray-700"}`}>
                        {isResolved && <CheckCircle2 size={13} />}
                        {!isResolved && <AlertTriangle size={13} />}
                        {formatStatus(caseData.issue_condition)}
                    </span>
                </div>

                <div className="mt-5 grid grid-cols-2 gap-4 md:grid-cols-4">
                    <div className="flex items-center gap-2">
                        <User size={14} className="text-gray-400" />
                        <div>
                            <p className="text-[10px] text-gray-400">Engineer</p>
                            <p className="text-xs font-medium text-gray-700">Engineer</p>
                        </div>
                    </div>

                    <div className="flex items-center gap-2">
                        <Calendar size={14} className="text-gray-400" />
                        <div>
                            <p className="text-[10px] text-gray-400">Created</p>
                            <p className="text-xs font-medium text-gray-700">
                                {new Date(caseData.created_at).toLocaleDateString()}
                            </p>
                        </div>
                    </div>

                    <div className="flex items-center gap-2">
                        <Stethoscope size={14} className="text-gray-400" />
                        <div>
                            <p className="text-[10px] text-gray-400">Top Cause</p>
                            <p className="text-xs font-medium text-gray-700">
                                {caseData.diagnosis?.ranked_causes?.[0]?.cause_name || "Pending..."}
                            </p>
                        </div>
                    </div>
                </div>

                <div className="mt-5 flex gap-2">
                    <Link
                        href={`/diagnosis/${caseData.case_id}`}
                        className="rounded-lg bg-[#6d5dfc] px-4 py-2 text-xs font-semibold text-white transition hover:bg-[#5848e8]"
                    >
                        View Diagnosis
                    </Link>

                    <Link
                        href={`/reports/${caseData.case_id}`}
                        className="rounded-lg border border-gray-200 px-4 py-2 text-xs font-semibold text-gray-600 transition hover:bg-gray-50"
                    >
                        View Report
                    </Link>
                </div>
            </div>

            {/* Timeline */}
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                <h2 className="text-base font-semibold text-gray-900">
                    Case Timeline
                </h2>
                <p className="mt-1 text-xs text-gray-500">
                    Complete lifecycle of this case
                </p>

                <div className="mt-5 space-y-0">
                    {timeline.length === 0 ? (
                        <p className="text-xs text-gray-500">No events found.</p>
                    ) : (
                        timeline.map((entry, index) => (
                            <div key={index} className="relative flex gap-3 pb-6 last:pb-0">
                                {index < timeline.length - 1 && (
                                    <div className="absolute left-[11px] top-6 h-full w-px bg-gray-200" />
                                )}
                                <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#eeebff]">
                                    <Clock3 size={12} className="text-[#6d5dfc]" />
                                </div>
                                <div>
                                    <p className="text-sm font-medium text-gray-900">
                                        {entry.event}
                                    </p>
                                    <p className="mt-0.5 text-[10px] text-gray-400">
                                        {entry.time}
                                    </p>
                                    <p className="mt-1 text-xs text-gray-500">
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
