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

interface CaseDetailsProps {
    caseId?: string;
}

const mockTimeline = [
    {
        event: "Case created",
        time: "Sep 15, 2026 · 10:30 AM",
        detail: "Symptom: undersized deposits on Dispensing Line A",
    },
    {
        event: "Initial diagnosis completed",
        time: "Sep 15, 2026 · 10:32 AM",
        detail: "Defect: Too Little Material · 5 candidate causes ranked",
    },
    {
        event: "Diagnostic questions completed",
        time: "Sep 15, 2026 · 10:48 AM",
        detail: "5 questions answered · Cause ranking refined",
    },
    {
        event: "Troubleshooting checks started",
        time: "Sep 15, 2026 · 11:05 AM",
        detail: "Nozzle inspection completed · Blockage found",
    },
    {
        event: "Cause confirmed",
        time: "Sep 15, 2026 · 11:22 AM",
        detail: "Engineer verified: Nozzle Restriction",
    },
    {
        event: "Case resolved",
        time: "Sep 15, 2026 · 11:35 AM",
        detail: "Nozzle cleaned and replaced · Verified dispensing normal",
    },
];

export default function CaseDetails({ caseId = "DSP-2026-0184" }: CaseDetailsProps) {
    return (
        <div className="space-y-6">
            {/* Header Card */}
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                <div className="flex items-start justify-between">
                    <div>
                        <h2 className="text-xl font-bold text-gray-900">
                            {caseId}
                        </h2>

                        <p className="mt-1 text-sm text-gray-500">
                            Too Little Material · Dispensing Line A
                        </p>
                    </div>

                    <span className="inline-flex items-center gap-1.5 rounded-full bg-green-50 px-2.5 py-1 text-xs font-medium text-green-700">
                        <CheckCircle2 size={13} />
                        Resolved
                    </span>
                </div>

                <div className="mt-5 grid grid-cols-2 gap-4 md:grid-cols-4">
                    <div className="flex items-center gap-2">
                        <User size={14} className="text-gray-400" />

                        <div>
                            <p className="text-[10px] text-gray-400">
                                Engineer
                            </p>

                            <p className="text-xs font-medium text-gray-700">
                                Sarah Mitchell
                            </p>
                        </div>
                    </div>

                    <div className="flex items-center gap-2">
                        <Calendar size={14} className="text-gray-400" />

                        <div>
                            <p className="text-[10px] text-gray-400">
                                Created
                            </p>

                            <p className="text-xs font-medium text-gray-700">
                                Sep 15, 2026
                            </p>
                        </div>
                    </div>

                    <div className="flex items-center gap-2">
                        <Stethoscope size={14} className="text-gray-400" />

                        <div>
                            <p className="text-[10px] text-gray-400">
                                Root Cause
                            </p>

                            <p className="text-xs font-medium text-gray-700">
                                Nozzle Restriction
                            </p>
                        </div>
                    </div>

                    <div className="flex items-center gap-2">
                        <Wrench size={14} className="text-gray-400" />

                        <div>
                            <p className="text-[10px] text-gray-400">
                                Resolution
                            </p>

                            <p className="text-xs font-medium text-gray-700">
                                Nozzle cleaned
                            </p>
                        </div>
                    </div>
                </div>

                <div className="mt-5 flex gap-2">
                    <Link
                        href={`/diagnosis/${caseId}`}
                        className="rounded-lg bg-[#6d5dfc] px-4 py-2 text-xs font-semibold text-white transition hover:bg-[#5848e8]"
                    >
                        View Diagnosis
                    </Link>

                    <Link
                        href={`/reports/${caseId}`}
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
                    {mockTimeline.map((entry, index) => (
                        <div
                            key={index}
                            className="relative flex gap-3 pb-6 last:pb-0"
                        >
                            {index < mockTimeline.length - 1 && (
                                <div className="absolute left-[11px] top-6 h-full w-px bg-gray-200" />
                            )}

                            <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#eeebff]">
                                <Clock3
                                    size={12}
                                    className="text-[#6d5dfc]"
                                />
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
                    ))}
                </div>
            </div>
        </div>
    );
}
