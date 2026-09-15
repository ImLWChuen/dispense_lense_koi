"use client";

import { useState } from "react";
import {
    CheckCircle2,
    XCircle,
    AlertTriangle,
    Shield,
} from "lucide-react";

interface EngineerVerificationProps {
    causeName?: string;
    causeDescription?: string;
    confidence?: number;
    onConfirm?: (notes: string, recoveryAction?: string) => void;
    onReject?: (notes: string) => void;
}

export default function EngineerVerification({
    causeName = "Nozzle Restriction",
    causeDescription = "Partial blockage of the dispensing nozzle was confirmed by visual inspection.",
    confidence = 87,
    onConfirm,
    onReject,
}: EngineerVerificationProps) {
    const [decision, setDecision] = useState<
        "confirm" | "reject" | null
    >(null);
    const [notes, setNotes] = useState("");
    const [recoveryAction, setRecoveryAction] = useState("");
    const [isSubmitting, setIsSubmitting] = useState(false);

    const handleConfirm = async () => {
        setIsSubmitting(true);
        try {
            await onConfirm?.(notes, recoveryAction);
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleReject = async () => {
        setIsSubmitting(true);
        try {
            await onReject?.(notes);
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="space-y-6">
            {/* Cause Summary */}
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#eeebff] text-[#6d5dfc]">
                        <Shield size={20} />
                    </div>

                    <div>
                        <h2 className="text-base font-semibold text-gray-900">
                            Cause Verification
                        </h2>

                        <p className="text-xs text-gray-500">
                            Review and verify the diagnosed cause
                        </p>
                    </div>
                </div>

                <div className="mt-5 rounded-xl bg-gray-50 p-4">
                    <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
                        Top Candidate Cause
                    </p>

                    <p className="mt-2 text-lg font-bold text-gray-900">
                        {causeName}
                    </p>

                    <p className="mt-1 text-xs leading-5 text-gray-500">
                        {causeDescription}
                    </p>

                    <div className="mt-3 flex items-center gap-3">
                        <div className="h-2 w-24 overflow-hidden rounded-full bg-gray-200">
                            <div
                                className="h-full rounded-full bg-[#6d5dfc]"
                                style={{ width: `${Math.round(confidence)}%` }}
                            />
                        </div>

                        <span className="text-sm font-semibold text-[#5848e8]">
                            {Math.round(confidence)}% confidence
                        </span>
                    </div>
                </div>
            </div>

            {/* Decision */}
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                <h2 className="text-base font-semibold text-gray-900">
                    Engineer Decision
                </h2>

                <p className="mt-1 text-xs text-gray-500">
                    Confirm or reject the diagnosed cause based on your
                    engineering judgement
                </p>

                <div className="mt-5 grid grid-cols-2 gap-3">
                    <button
                        onClick={() => setDecision("confirm")}
                        disabled={isSubmitting}
                        className={`flex items-center gap-3 rounded-xl border p-4 transition disabled:opacity-50 ${
                            decision === "confirm"
                                ? "border-green-400 bg-green-50 ring-1 ring-green-400"
                                : "border-gray-200 hover:border-green-300 hover:bg-green-50/50"
                        }`}
                    >
                        <CheckCircle2
                            size={22}
                            className={
                                decision === "confirm"
                                    ? "text-green-600"
                                    : "text-gray-400"
                            }
                        />

                        <div className="text-left">
                            <p className="text-sm font-semibold text-gray-900">
                                Confirm Cause
                            </p>

                            <p className="text-[10px] text-gray-500">
                                The diagnosed cause is correct
                            </p>
                        </div>
                    </button>

                    <button
                        onClick={() => setDecision("reject")}
                        disabled={isSubmitting}
                        className={`flex items-center gap-3 rounded-xl border p-4 transition disabled:opacity-50 ${
                            decision === "reject"
                                ? "border-red-400 bg-red-50 ring-1 ring-red-400"
                                : "border-gray-200 hover:border-red-300 hover:bg-red-50/50"
                        }`}
                    >
                        <XCircle
                            size={22}
                            className={
                                decision === "reject"
                                    ? "text-red-600"
                                    : "text-gray-400"
                            }
                        />

                        <div className="text-left">
                            <p className="text-sm font-semibold text-gray-900">
                                Reject Cause
                            </p>

                            <p className="text-[10px] text-gray-500">
                                The diagnosed cause is incorrect
                            </p>
                        </div>
                    </button>
                </div>

                <div className="mt-5">
                    <label className="block text-sm font-medium text-gray-700">
                        Engineer Notes
                    </label>

                    <textarea
                        value={notes}
                        onChange={(e) => setNotes(e.target.value)}
                        placeholder="Add your observations and reasoning..."
                        rows={3}
                        disabled={isSubmitting}
                        className="mt-1.5 w-full rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 text-sm outline-none transition placeholder:text-gray-400 focus:border-[#6d5dfc] focus:bg-white disabled:opacity-50"
                    />
                </div>

                {decision === "reject" && (
                    <button 
                        onClick={handleReject}
                        disabled={isSubmitting || !notes}
                        className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-red-600 px-6 py-3 text-sm font-semibold text-white transition hover:bg-red-700 disabled:opacity-50"
                    >
                        <XCircle size={16} />
                        {isSubmitting ? "Submitting..." : "Submit Rejection"}
                    </button>
                )}
            </div>

            {/* Recovery Action */}
            {decision === "confirm" && (
                <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                    <h2 className="text-base font-semibold text-gray-900">
                        Recovery Action
                    </h2>

                    <p className="mt-1 text-xs text-gray-500">
                        Describe the corrective action taken to resolve the
                        issue
                    </p>

                    <textarea
                        value={recoveryAction}
                        onChange={(e) => setRecoveryAction(e.target.value)}
                        placeholder="e.g. Cleaned nozzle tip with solvent, replaced O-ring seal..."
                        rows={3}
                        disabled={isSubmitting}
                        className="mt-4 w-full rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 text-sm outline-none transition placeholder:text-gray-400 focus:border-[#6d5dfc] focus:bg-white disabled:opacity-50"
                    />

                    <div className="mt-4 flex items-center gap-2 rounded-lg bg-amber-50 px-3 py-2">
                        <AlertTriangle
                            size={14}
                            className="text-amber-600"
                        />

                        <p className="text-xs text-amber-700">
                            After performing the recovery action, verify
                            that the dispensing issue is resolved before
                            marking the case as complete.
                        </p>
                    </div>

                    <button 
                        onClick={handleConfirm}
                        disabled={isSubmitting || !recoveryAction}
                        className="mt-5 inline-flex items-center gap-2 rounded-xl bg-green-600 px-6 py-3 text-sm font-semibold text-white transition hover:bg-green-700 disabled:opacity-50"
                    >
                        <CheckCircle2 size={16} />
                        {isSubmitting ? "Submitting..." : "Mark as Resolved"}
                    </button>
                </div>
            )}
        </div>
    );
}
