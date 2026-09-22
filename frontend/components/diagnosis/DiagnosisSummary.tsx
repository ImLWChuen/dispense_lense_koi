import { Stethoscope } from "lucide-react";
import ConfidenceScore from "./ConfidenceScore";
import { DurableCaseResponse } from "@/types/api";

interface DiagnosisSummaryProps {
    caseData?: DurableCaseResponse;
    status?: string;
}

const DEFECT_POSSIBLE_SYMPTOMS: Record<string, string[]> = {
    D01_TOO_LITTLE: [
        "Dispensed volume is consistently less than target specification (< 80%)",
        "Thin deposit profile with insufficient substrate coverage",
        "Higher risk of cold joint or mechanical detachment",
    ],
    D02_TOO_MUCH: [
        "Dispensed volume consistently exceeds target specification (> 120%)",
        "Tall or bulging deposit profile with excessive fluid height",
        "Material spreading toward adjacent keep-out zones",
    ],
    D03_INCONSISTENT_SIZE: [
        "Some dispensing dots are larger than nominal",
        "Some dispensing dots are smaller than nominal",
        "Dispensing results are not shot-to-shot repeatable",
    ],
    D04_MISSING_DOTS: [
        "One or more designated positions receive zero material delivery",
        "Blank substrate pads observed during post-dispense inspection",
        "Intermittent shot starvation or nozzle valve skip",
    ],
    D05_SPREADING: [
        "Material wets out uncontrollably past target diameter into keep-out zones",
        "Loss of crisp dot boundary definition with edge bleeding / haloing",
        "Substrate surface contamination or low fluid viscosity observed",
    ],
    D06_BUBBLES_ABNORMAL_SHAPE: [
        "Visible air void or cavity trapped inside the dispensed deposit",
        "Asymmetric elongation, stringing tails, or satellite droplets",
        "Deposit shape deviates significantly from circular symmetry",
    ],
};

export default function DiagnosisSummary({
    caseData,
    status: externalStatus,
}: DiagnosisSummaryProps) {
    const diagnosis = caseData?.diagnosis || caseData?.initial_diagnosis;
    const defectCode = caseData?.defect_code || (diagnosis as any)?.defect_code || "";
    const defect = diagnosis?.defect_name || diagnosis?.defect || "No defect identified";
    const defectDescription = caseData?.description || "No problem description recorded.";
    const topScore = typeof diagnosis?.ranked_causes?.[0]?.score === "number"
        ? Math.round(diagnosis.ranked_causes[0].score)
        : null;

    // Retrieve canonical symptoms for identified defect (Step 2 - NSW Automation)
    let symptoms: string[] = [];
    if (defectCode && DEFECT_POSSIBLE_SYMPTOMS[defectCode]) {
        symptoms = DEFECT_POSSIBLE_SYMPTOMS[defectCode];
    } else {
        // Fallback matching by defect name
        const lowerName = defect.toLowerCase();
        if (lowerName.includes("inconsistent")) {
            symptoms = DEFECT_POSSIBLE_SYMPTOMS["D03_INCONSISTENT_SIZE"];
        } else if (lowerName.includes("little") || lowerName.includes("undersize")) {
            symptoms = DEFECT_POSSIBLE_SYMPTOMS["D01_TOO_LITTLE"];
        } else if (lowerName.includes("much") || lowerName.includes("oversize")) {
            symptoms = DEFECT_POSSIBLE_SYMPTOMS["D02_TOO_MUCH"];
        } else if (lowerName.includes("missing")) {
            symptoms = DEFECT_POSSIBLE_SYMPTOMS["D04_MISSING_DOTS"];
        } else if (lowerName.includes("spread")) {
            symptoms = DEFECT_POSSIBLE_SYMPTOMS["D05_SPREADING"];
        } else if (lowerName.includes("bubble") || lowerName.includes("abnormal")) {
            symptoms = DEFECT_POSSIBLE_SYMPTOMS["D06_BUBBLES_ABNORMAL_SHAPE"];
        }
    }

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
                        <div className="flex items-center gap-2">
                            <span className="rounded bg-indigo-50 text-[#5848e8] border border-indigo-200 px-1.5 py-0.2 text-[9px] font-bold uppercase tracking-wider">
                                Step 2
                            </span>
                            <h2 className="text-base font-semibold text-gray-900">
                                Diagnosis Summary
                            </h2>
                        </div>

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
                <div className="rounded-xl bg-gray-50 p-4 border border-gray-100">
                    <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
                        Identified Dispensing Defect
                    </p>

                    <p className="mt-1.5 text-lg font-bold text-gray-900">
                        {defect}
                    </p>

                    <p className="mt-1 text-xs leading-5 text-gray-500">
                        {defectDescription}
                    </p>
                </div>

                <div className="mt-5">
                    <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
                        Defect Confidence Level
                    </p>

                    <div className="mt-2">
                        {topScore !== null ? (
                            <ConfidenceScore score={topScore} size="lg" label="Confidence Level" showStars={true} />
                        ) : (
                            <p className="text-sm text-gray-500">No ranked causes evaluated</p>
                        )}
                    </div>
                </div>

                {/* Step 2: Characteristic Symptoms */}
                {symptoms.length > 0 && (
                    <div className="mt-5 rounded-xl border border-indigo-100 bg-[#faf9ff] p-3.5">
                        <p className="text-xs font-semibold text-gray-800 mb-2">
                            Possible Defect Symptoms:
                        </p>
                        <ul className="space-y-1.5 text-xs text-gray-600">
                            {symptoms.map((symptom, idx) => (
                                <li key={idx} className="flex items-start gap-2">
                                    <span className="text-[#6d5dfc] font-bold shrink-0">•</span>
                                    <span>{symptom}</span>
                                </li>
                            ))}
                        </ul>
                    </div>
                )}

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
