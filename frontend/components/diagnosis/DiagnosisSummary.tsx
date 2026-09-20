import { Stethoscope } from "lucide-react";
import ConfidenceScore from "./ConfidenceScore";
import { DurableCaseResponse } from "@/types/api";

interface DiagnosisSummaryProps {
    caseData?: DurableCaseResponse;
    status?: string;
}

export default function DiagnosisSummary({
    caseData,
    status: externalStatus,
}: DiagnosisSummaryProps) {
    const diagnosis = caseData?.diagnosis || caseData?.initial_diagnosis;
    const defect = diagnosis?.defect_name || diagnosis?.defect || "No defect identified";
    const defectDescription = caseData?.description || "No problem description recorded.";
    const topScore = typeof diagnosis?.ranked_causes?.[0]?.score === "number"
        ? Math.round(diagnosis.ranked_causes[0].score)
        : null;
    const computedStatus = caseData?.issue_condition === "RECOVERY_PENDING_VERIFICATION"
        ? "Pending Verification"
        : caseData?.issue_condition === "RESOLVED"
        ? "Resolved"
        : caseData?.issue_condition === "UNRESOLVED"
        ? "In Progress"
        : caseData?.issue_condition === "RECURRENCE_CONFIRMED"
        ? "Recurrence Confirmed"
        : caseData?.issue_condition;
    const status = externalStatus || computedStatus || "Not recorded";
    const causesCount = diagnosis?.ranked_causes?.length ?? 0;
    const observationsCount = caseData?.observations?.length ?? 0;
    const caseIdText = caseData?.case_id ? `Case ${caseData.case_id}` : "Case not recorded";

    return (
        <div className="rounded-2xl border border-gray-200 bg-white shadow-sm">
            <div className="border-b border-gray-100 px-6 py-5">
                <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#eeebff] text-[#6d5dfc]">
                        <Stethoscope size={20} />
                    </div>

                    <div>
                        <h2 className="text-base font-semibold text-gray-900">
                            Diagnosis Summary
                        </h2>

                        <p className="text-xs text-gray-500">
                            {caseIdText}
                        </p>
                    </div>

                    <span className="ml-auto inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700">
                        {status}
                    </span>
                </div>
            </div>

            <div className="p-6">
                <div className="rounded-xl bg-gray-50 p-4">
                    <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
                        Identified Defect
                    </p>

                    <p className="mt-2 text-lg font-bold text-gray-900">
                        {defect}
                    </p>

                    <p className="mt-1 text-xs leading-5 text-gray-500">
                        {defectDescription}
                    </p>
                </div>

                <div className="mt-5">
                    <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
                        Top Evidence Support
                    </p>

                    <div className="mt-2">
                        {topScore !== null ? (
                            <ConfidenceScore score={topScore} size="lg" label="Evidence Support" />
                        ) : (
                            <p className="text-sm text-gray-500">No ranked causes evaluated</p>
                        )}
                    </div>
                </div>

                <div className="mt-5 grid grid-cols-2 gap-4">
                    <div className="rounded-xl bg-gray-50 p-3 text-center">
                        <p className="text-2xl font-bold text-gray-900">
                            {causesCount}
                        </p>

                        <p className="mt-1 text-[10px] font-medium uppercase tracking-wide text-gray-500">
                            Candidate Causes
                        </p>
                    </div>

                    <div className="rounded-xl bg-gray-50 p-3 text-center">
                        <p className="text-2xl font-bold text-gray-900">
                            {observationsCount}
                        </p>

                        <p className="mt-1 text-[10px] font-medium uppercase tracking-wide text-gray-500">
                            Observations
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
}
