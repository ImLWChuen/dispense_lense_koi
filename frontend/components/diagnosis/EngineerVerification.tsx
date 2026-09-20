"use client";

import { useState } from "react";
import {
    CheckCircle2,
    AlertTriangle,
    Shield,
    Wrench,
    RotateCcw,
    Info,
    Check,
    X,
    History,
} from "lucide-react";
import { DurableCaseResponse } from "@/types/api";
import {
    getAvailableLifecycleActions,
    formatEvidenceSupport,
    shouldShowVerificationBadge,
} from "@/lib/diagnostic-workflow-state";

export interface EngineerVerificationProps {
    caseData: DurableCaseResponse;
    onConfirmCause: (causeId: string, notes?: string) => Promise<void>;
    onSubmitRecoveryAction: (recoveryDetails: string) => Promise<void>;
    onSubmitRecoveryVerification: (passed: boolean, details?: string) => Promise<void>;
    onSubmitRecurrence: (details: string) => Promise<void>;
    isSubmitting?: boolean;
}

export default function EngineerVerification({
    caseData,
    onConfirmCause,
    onSubmitRecoveryAction,
    onSubmitRecoveryVerification,
    onSubmitRecurrence,
    isSubmitting = false,
}: EngineerVerificationProps) {
    const issueCondition = (caseData.issue_condition || "UNRESOLVED").toUpperCase();
    const legalActions = getAvailableLifecycleActions(issueCondition);

    const diagnosis = caseData.diagnosis || caseData.initial_diagnosis;
    const rankedCauses = diagnosis?.ranked_causes || [];
    const previousConfirmations = caseData.previous_confirmations || [];
    const lifecycleEvents = caseData.lifecycle_events || [];

    // Local form states
    const [selectedCauseId, setSelectedCauseId] = useState<string>(
        rankedCauses[0]?.cause_id || ""
    );
    const [causeNotes, setCauseNotes] = useState<string>("");
    const [recoveryDetails, setRecoveryDetails] = useState<string>("");
    const [verificationPassed, setVerificationPassed] = useState<boolean>(true);
    const [verificationDetails, setVerificationDetails] = useState<string>("");
    const [recurrenceDetails, setRecurrenceDetails] = useState<string>("");

    const [actionError, setActionError] = useState<string | null>(null);

    // Handlers
    const handleCauseConfirmSubmit = async () => {
        if (!selectedCauseId) {
            setActionError("Please select a candidate cause to confirm.");
            return;
        }
        setActionError(null);
        try {
            await onConfirmCause(selectedCauseId, causeNotes);
            setCauseNotes("");
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : "Failed to confirm cause.";
            setActionError(msg);
        }
    };

    const handleRecoveryActionSubmit = async () => {
        if (!recoveryDetails.trim()) {
            setActionError("Please enter the corrective / recovery action taken.");
            return;
        }
        setActionError(null);
        try {
            await onSubmitRecoveryAction(recoveryDetails.trim());
            setRecoveryDetails("");
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : "Failed to record recovery action.";
            setActionError(msg);
        }
    };

    const handleVerificationSubmit = async () => {
        if (!verificationDetails.trim()) {
            setActionError("Please provide verification details or test observations.");
            return;
        }
        setActionError(null);
        try {
            await onSubmitRecoveryVerification(verificationPassed, verificationDetails.trim());
            setVerificationDetails("");
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : "Failed to record recovery verification.";
            setActionError(msg);
        }
    };

    const handleRecurrenceSubmit = async () => {
        if (!recurrenceDetails.trim()) {
            setActionError("Please enter the recurrence details observed.");
            return;
        }
        setActionError(null);
        try {
            await onSubmitRecurrence(recurrenceDetails.trim());
            setRecurrenceDetails("");
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : "Failed to report recurrence.";
            setActionError(msg);
        }
    };

    // Helper for condition badge styling
    const getConditionBadge = (condition: string) => {
        switch (condition) {
            case "RESOLVED":
                return {
                    label: "Resolved",
                    className: "bg-emerald-50 text-emerald-700 border-emerald-200",
                };
            case "RECOVERY_PENDING_VERIFICATION":
                return {
                    label: "Recovery Pending Verification",
                    className: "bg-amber-50 text-amber-700 border-amber-200",
                };
            case "RECURRED":
                return {
                    label: "Recurred",
                    className: "bg-rose-50 text-rose-700 border-rose-200",
                };
            case "UNRESOLVED":
            default:
                return {
                    label: "Unresolved",
                    className: "bg-blue-50 text-blue-700 border-blue-200",
                };
        }
    };

    const conditionBadge = getConditionBadge(issueCondition);

    return (
        <div className="space-y-6">
            {/* Status & Issue Condition Banner */}
            <div className="flex items-center justify-between rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
                <div>
                    <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">
                        Persisted Issue Condition
                    </span>
                    <div className="mt-1 flex items-center gap-3">
                        <span
                            className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold ${conditionBadge.className}`}
                        >
                            {conditionBadge.label}
                        </span>
                        <span className="text-xs text-gray-500">
                            Current Revision: {caseData.current_revision ?? caseData.diagnosis?.analysis_revision?.revision_number ?? 1}
                        </span>
                    </div>
                </div>

                <div className="text-right text-xs text-gray-500">
                    Case ID: <span className="font-mono font-semibold text-gray-700">{caseData.case_id}</span>
                </div>
            </div>

            {actionError && (
                <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                    {actionError}
                </div>
            )}

            {/* 1. Cause Confirmation Section */}
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#eeebff] text-[#6d5dfc]">
                        <Shield size={20} />
                    </div>
                    <div>
                        <h2 className="text-base font-semibold text-gray-900">
                            Candidate Causes & Evidence Support
                        </h2>
                        <p className="text-xs text-gray-500">
                            Scores reflect evidence support gathered by the diagnostic engine. Cause confirmation is independent of issue resolution.
                        </p>
                    </div>
                </div>

                {/* Ranked Causes List */}
                <div className="mt-5 space-y-3">
                    {rankedCauses.length === 0 ? (
                        <p className="text-sm text-gray-500">No candidate causes available.</p>
                    ) : (
                        rankedCauses.map((cause) => {
                            const isSelected = selectedCauseId === cause.cause_id;
                            const isConfirmed = previousConfirmations.some(
                                (c) => c.cause_id === cause.cause_id
                            );

                            return (
                                <div
                                    key={cause.cause_id}
                                    onClick={() => legalActions.canConfirmCause && setSelectedCauseId(cause.cause_id)}
                                    className={`relative flex cursor-pointer items-start justify-between rounded-xl border p-4 transition ${
                                        isSelected
                                            ? "border-[#6d5dfc] bg-[#faf9ff] ring-1 ring-[#6d5dfc]"
                                            : "border-gray-200 hover:border-gray-300 bg-gray-50/50"
                                    }`}
                                >
                                    <div className="pr-4">
                                        <div className="flex items-center gap-2">
                                            <p className="text-sm font-bold text-gray-900">
                                                {cause.cause_name.replace(/_/g, " ")}
                                            </p>
                                            {isConfirmed && (
                                                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
                                                    <Check size={12} /> Confirmed
                                                </span>
                                            )}
                                        </div>
                                        <p className="mt-1 text-xs text-gray-600">
                                            {cause.description || "No cause description provided."}
                                        </p>
                                    </div>

                                    <div className="text-right whitespace-nowrap">
                                        <span className="text-xs font-semibold uppercase tracking-wide text-gray-400 block">
                                            Evidence Support
                                        </span>
                                        <span className="text-sm font-bold text-[#5848e8]">
                                            {formatEvidenceSupport(cause.score)}
                                        </span>
                                    </div>
                                </div>
                            );
                        })
                    )}
                </div>

                {/* Confirmed Causes History if any */}
                {previousConfirmations.length > 0 && (
                    <div className="mt-5 rounded-xl border border-emerald-100 bg-emerald-50/60 p-4">
                        <p className="text-xs font-bold uppercase tracking-wider text-emerald-800">
                            Confirmed Cause Records
                        </p>
                        <div className="mt-2 space-y-2">
                            {previousConfirmations.map((conf, i) => (
                                <div key={i} className="text-xs text-emerald-900">
                                    <span className="font-semibold">{conf.cause_id}</span> confirmed by{" "}
                                    <span className="font-medium">{conf.confirmed_by}</span> (Revision{" "}
                                    {conf.resulting_revision_number}):{" "}
                                    <span className="italic">{conf.notes || "No technician notes recorded."}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Cause Confirmation Form (Only when issue is UNRESOLVED or RECURRED) */}
                {legalActions.canConfirmCause ? (
                    <div className="mt-6 border-t border-gray-100 pt-5">
                        <label className="block text-xs font-semibold uppercase tracking-wider text-gray-500">
                            Confirm Cause Assessment (Optional)
                        </label>
                        <textarea
                            value={causeNotes}
                            onChange={(e) => setCauseNotes(e.target.value)}
                            placeholder="Technician observation notes verifying this cause..."
                            rows={2}
                            disabled={isSubmitting}
                            className="mt-2 w-full rounded-xl border border-gray-200 bg-gray-50 px-4 py-2.5 text-sm outline-none transition placeholder:text-gray-400 focus:border-[#6d5dfc] focus:bg-white disabled:opacity-50"
                        />
                        <div className="mt-3 flex items-center justify-between">
                            <p className="text-xs text-gray-500">
                                Selecting confirm saves an explicit confirmation record without altering issue condition.
                            </p>
                            <button
                                onClick={handleCauseConfirmSubmit}
                                disabled={isSubmitting || !selectedCauseId}
                                className="inline-flex items-center gap-1.5 rounded-xl bg-[#6d5dfc] px-4 py-2 text-xs font-semibold text-white transition hover:bg-[#5848e8] disabled:opacity-50"
                            >
                                <Check size={14} />
                                {isSubmitting ? "Submitting..." : "Confirm Selected Cause"}
                            </button>
                        </div>
                    </div>
                ) : (
                    <div className="mt-4 rounded-xl bg-gray-50 p-3 text-xs text-gray-500">
                        Cause confirmation is available when a case is Unresolved or Recurred.
                    </div>
                )}

                {/* Honest Callout on Cause Rejection */}
                <div className="mt-5 flex items-start gap-2.5 rounded-xl border border-blue-100 bg-blue-50/50 p-3.5">
                    <Info size={16} className="mt-0.5 text-blue-600 shrink-0" />
                    <p className="text-xs leading-relaxed text-blue-900">
                        <span className="font-semibold">Note on Cause Rejection:</span> The diagnostic engine evaluates evidence support scores. There is no persisted cause-rejection endpoint in the system. If the top candidate causes do not match your findings, you can continue physical troubleshooting checks or perform corrective recovery directly.
                    </p>
                </div>
            </div>

            {/* 2. Recovery Action Section (UNRESOLVED or RECURRED) */}
            {legalActions.canSubmitRecoveryAction && (
                <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                    <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-50 text-amber-600">
                            <Wrench size={20} />
                        </div>
                        <div>
                            <h2 className="text-base font-semibold text-gray-900">
                                Record Corrective / Recovery Action
                            </h2>
                            <p className="text-xs text-gray-500">
                                Document the maintenance or corrective step taken. This action transitions the case to Recovery Pending Verification.
                            </p>
                        </div>
                    </div>

                    <div className="mt-4">
                        <label className="block text-xs font-semibold uppercase tracking-wider text-gray-500">
                            Corrective Action Details
                        </label>
                        <textarea
                            value={recoveryDetails}
                            onChange={(e) => setRecoveryDetails(e.target.value)}
                            placeholder="e.g., Cleaned nozzle orifice with ultrasonic bath, replaced O-ring seal, calibrated fluid pressure..."
                            rows={3}
                            disabled={isSubmitting}
                            className="mt-2 w-full rounded-xl border border-gray-200 bg-gray-50 px-4 py-2.5 text-sm outline-none transition placeholder:text-gray-400 focus:border-[#6d5dfc] focus:bg-white disabled:opacity-50"
                        />

                        <div className="mt-4 flex items-center justify-between">
                            <p className="text-xs text-gray-500">
                                Does not require a confirmed cause; cases may be recovered directly.
                            </p>
                            <button
                                onClick={handleRecoveryActionSubmit}
                                disabled={isSubmitting || !recoveryDetails.trim()}
                                className="inline-flex items-center gap-1.5 rounded-xl bg-amber-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-amber-700 disabled:opacity-50"
                            >
                                <Wrench size={16} />
                                {isSubmitting ? "Recording..." : "Record Recovery Action"}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* 3. Recovery Verification Section (RECOVERY_PENDING_VERIFICATION) */}
            {legalActions.canVerifyRecovery && (
                <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                    <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600">
                            <CheckCircle2 size={20} />
                        </div>
                        <div>
                            <h2 className="text-base font-semibold text-gray-900">
                                Recovery Verification
                            </h2>
                            <p className="text-xs text-gray-500">
                                Verify whether the corrective action successfully fixed the dispensing defect.
                            </p>
                        </div>
                    </div>

                    <div className="mt-5 grid grid-cols-2 gap-4">
                        <button
                            type="button"
                            onClick={() => setVerificationPassed(true)}
                            disabled={isSubmitting}
                            className={`flex items-center gap-3 rounded-xl border p-4 text-left transition ${
                                verificationPassed
                                    ? "border-emerald-500 bg-emerald-50 ring-1 ring-emerald-500"
                                    : "border-gray-200 hover:border-gray-300 bg-gray-50"
                            }`}
                        >
                            <CheckCircle2
                                size={22}
                                className={verificationPassed ? "text-emerald-600" : "text-gray-400"}
                            />
                            <div>
                                <p className="text-sm font-semibold text-gray-900">
                                    Verification Passed
                                </p>
                                <p className="text-xs text-gray-500">
                                    Issue fixed; transitions case to Resolved.
                                </p>
                            </div>
                        </button>

                        <button
                            type="button"
                            onClick={() => setVerificationPassed(false)}
                            disabled={isSubmitting}
                            className={`flex items-center gap-3 rounded-xl border p-4 text-left transition ${
                                !verificationPassed
                                    ? "border-rose-500 bg-rose-50 ring-1 ring-rose-500"
                                    : "border-gray-200 hover:border-gray-300 bg-gray-50"
                            }`}
                        >
                            <AlertTriangle
                                size={22}
                                className={!verificationPassed ? "text-rose-600" : "text-gray-400"}
                            />
                            <div>
                                <p className="text-sm font-semibold text-gray-900">
                                    Verification Failed
                                </p>
                                <p className="text-xs text-gray-500">
                                    Defect persists; returns case to Unresolved.
                                </p>
                            </div>
                        </button>
                    </div>

                    <div className="mt-4">
                        <label className="block text-xs font-semibold uppercase tracking-wider text-gray-500">
                            Verification Details / Test Observations
                        </label>
                        <textarea
                            value={verificationDetails}
                            onChange={(e) => setVerificationDetails(e.target.value)}
                            placeholder="Describe the test shot results, measured dot sizes, or failure symptoms..."
                            rows={3}
                            disabled={isSubmitting}
                            className="mt-2 w-full rounded-xl border border-gray-200 bg-gray-50 px-4 py-2.5 text-sm outline-none transition placeholder:text-gray-400 focus:border-[#6d5dfc] focus:bg-white disabled:opacity-50"
                        />

                        <div className="mt-4 flex justify-end">
                            <button
                                onClick={handleVerificationSubmit}
                                disabled={isSubmitting || !verificationDetails.trim()}
                                className={`inline-flex items-center gap-1.5 rounded-xl px-5 py-2.5 text-sm font-semibold text-white transition disabled:opacity-50 ${
                                    verificationPassed
                                        ? "bg-emerald-600 hover:bg-emerald-700"
                                        : "bg-rose-600 hover:bg-rose-700"
                                }`}
                            >
                                {verificationPassed ? <Check size={16} /> : <X size={16} />}
                                {isSubmitting
                                    ? "Submitting..."
                                    : verificationPassed
                                    ? "Submit Passed Verification"
                                    : "Submit Failed Verification"}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* 4. Recurrence Reporting Section (RESOLVED) */}
            {legalActions.canReportRecurrence && (
                <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                    <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-rose-50 text-rose-600">
                            <RotateCcw size={20} />
                        </div>
                        <div>
                            <h2 className="text-base font-semibold text-gray-900">
                                Report Issue Recurrence
                            </h2>
                            <p className="text-xs text-gray-500">
                                If the dispensing defect returns after resolution, report recurrence to re-open the case as Recurred.
                            </p>
                        </div>
                    </div>

                    <div className="mt-4">
                        <label className="block text-xs font-semibold uppercase tracking-wider text-gray-500">
                            Recurrence Observations
                        </label>
                        <textarea
                            value={recurrenceDetails}
                            onChange={(e) => setRecurrenceDetails(e.target.value)}
                            placeholder="Describe how and when the issue recurred (e.g., dots became undersized after 500 dispense cycles)..."
                            rows={3}
                            disabled={isSubmitting}
                            className="mt-2 w-full rounded-xl border border-gray-200 bg-gray-50 px-4 py-2.5 text-sm outline-none transition placeholder:text-gray-400 focus:border-[#6d5dfc] focus:bg-white disabled:opacity-50"
                        />

                        <div className="mt-4 flex justify-end">
                            <button
                                onClick={handleRecurrenceSubmit}
                                disabled={isSubmitting || !recurrenceDetails.trim()}
                                className="inline-flex items-center gap-1.5 rounded-xl bg-rose-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-rose-700 disabled:opacity-50"
                            >
                                <RotateCcw size={16} />
                                {isSubmitting ? "Reporting..." : "Report Recurrence"}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* 5. Lifecycle History Timeline */}
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gray-100 text-gray-600">
                        <History size={20} />
                    </div>
                    <div>
                        <h2 className="text-base font-semibold text-gray-900">
                            Lifecycle History
                        </h2>
                        <p className="text-xs text-gray-500">
                            Audit log of state transitions, recovery actions, and verifications
                        </p>
                    </div>
                </div>

                <div className="mt-5">
                    {lifecycleEvents.length === 0 ? (
                        <p className="text-xs text-gray-500 italic py-2">
                            No lifecycle events recorded yet for this case.
                        </p>
                    ) : (
                        <div className="space-y-3">
                            {lifecycleEvents.map((evt, idx) => (
                                <div
                                    key={idx}
                                    className="flex items-start justify-between rounded-xl border border-gray-100 bg-gray-50/70 p-3.5 text-xs"
                                >
                                    <div>
                                        <div className="flex items-center gap-2">
                                            <span className="font-semibold text-gray-900 uppercase">
                                                {evt.event_type.replace(/_/g, " ")}
                                            </span>
                                            <span className="text-gray-400">·</span>
                                            <span className="font-mono text-gray-600">
                                                {evt.prior_issue_condition || "UNKNOWN"} → {evt.resulting_issue_condition}
                                            </span>
                                            {shouldShowVerificationBadge(evt.event_type, evt.verification_passed) && (
                                                <span
                                                    className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                                                        evt.verification_passed
                                                            ? "bg-emerald-100 text-emerald-800"
                                                            : "bg-rose-100 text-rose-800"
                                                    }`}
                                                >
                                                    {evt.verification_passed ? "PASSED" : "FAILED"}
                                                </span>
                                            )}
                                        </div>
                                        <p className="mt-1 text-gray-700">
                                            {evt.details || "No additional details recorded."}
                                        </p>
                                    </div>
                                    <div className="text-right whitespace-nowrap text-gray-400">
                                        <p>Rev {evt.resulting_revision_number}</p>
                                        <p className="mt-0.5">by {evt.actor || "technician"}</p>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
