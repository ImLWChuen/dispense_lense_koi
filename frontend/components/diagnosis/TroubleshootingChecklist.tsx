"use client";

import { useState } from "react";
import {
    CheckCircle2,
    Circle,
    Clock3,
    Ban,
    HelpCircle,
    ChevronDown,
    ChevronUp,
    AlertCircle,
    Loader2,
} from "lucide-react";
import {
    formatOutcomeLabel,
    resolveActiveCheck,
    ValidExecutionStatus,
} from "@/lib/diagnostic-workflow-state";

export interface TroubleshootingAction {
    id: string;
    name: string;
    description: string;
    procedure: string;
    effortLevel: "low" | "medium" | "high";
    applicableCauses: string[];
    status: "pending" | "completed" | "blocked" | "skipped" | "failed" | "unknown" | "not_applicable" | "inconclusive";
    possibleOutcomes?: string[];
    // Historical recorded details if already completed
    finding?: string;
    outcome?: string;
    findingDetails?: string;
}

const effortConfig = {
    low: { className: "bg-green-50 text-green-700", label: "Low Effort" },
    medium: { className: "bg-amber-50 text-amber-700", label: "Medium Effort" },
    high: { className: "bg-red-50 text-red-700", label: "High Effort" },
};

const statusConfig: Record<string, { icon: typeof Circle; className: string; label: string }> = {
    pending: { icon: Circle, className: "text-gray-400", label: "Active / Pending" },
    completed: { icon: CheckCircle2, className: "text-green-600", label: "Completed" },
    blocked: { icon: Ban, className: "text-red-500", label: "Blocked" },
    skipped: { icon: Clock3, className: "text-gray-400", label: "Skipped" },
    failed: { icon: Ban, className: "text-rose-500", label: "Failed" },
    unknown: { icon: HelpCircle, className: "text-purple-500", label: "Unknown" },
    not_applicable: { icon: HelpCircle, className: "text-slate-500", label: "Not Applicable" },
    inconclusive: { icon: HelpCircle, className: "text-amber-500", label: "Inconclusive" },
};

export interface TroubleshootingCheckSubmitParams {
    check_id: string;
    execution_status: string;
    finding?: string;
    outcome?: string | null;
    finding_details?: string | null;
}

interface TroubleshootingChecklistProps {
    actions: TroubleshootingAction[];
    activeCheckId?: string;
    onSubmit?: (params: TroubleshootingCheckSubmitParams) => Promise<void> | void;
    isSubmitting?: boolean;
    disabled?: boolean;
}

const executionStatusOptions: { value: ValidExecutionStatus; label: string; activeClass: string }[] = [
    { value: "COMPLETED", label: "Completed", activeClass: "bg-green-600 text-white shadow-sm" },
    { value: "BLOCKED", label: "Blocked", activeClass: "bg-rose-600 text-white shadow-sm" },
    { value: "SKIPPED", label: "Skipped", activeClass: "bg-gray-700 text-white shadow-sm" },
    { value: "FAILED", label: "Failed", activeClass: "bg-amber-600 text-white shadow-sm" },
    { value: "UNKNOWN", label: "Unknown", activeClass: "bg-purple-600 text-white shadow-sm" },
    { value: "NOT_APPLICABLE", label: "Not Applicable", activeClass: "bg-slate-600 text-white shadow-sm" },
];

export default function TroubleshootingChecklist({
    actions,
    activeCheckId,
    onSubmit,
    isSubmitting = false,
    disabled = false,
}: TroubleshootingChecklistProps) {
    // Resolve active check safely: only resolves if a genuinely pending check exists
    const activeCheck = resolveActiveCheck(actions, activeCheckId);

    // Form state for active check execution
    const [selectedStatus, setSelectedStatus] = useState<ValidExecutionStatus>("COMPLETED");
    const [selectedFinding, setSelectedFinding] = useState<"SUPPORTS" | "CONTRADICTS" | "INCONCLUSIVE">("SUPPORTS");
    const [selectedOutcome, setSelectedOutcome] = useState<string>("");
    const [notes, setNotes] = useState<string>("");
    const [formError, setFormError] = useState<string | null>(null);

    // Accordion state
    const [expanded, setExpanded] = useState<Record<string, boolean>>(() => {
        const initial: Record<string, boolean> = {};
        if (activeCheck) {
            initial[activeCheck.id] = true;
        }
        return initial;
    });

    const toggleExpand = (id: string) => {
        setExpanded((prev) => ({ ...prev, [id]: !prev[id] }));
    };

    const handleSubmit = async (actionId: string) => {
        if (disabled || isSubmitting) return;
        setFormError(null);

        if (selectedStatus === "COMPLETED") {
            if ((selectedFinding === "SUPPORTS" || selectedFinding === "CONTRADICTS") && !selectedOutcome) {
                setFormError(`Please select a canonical outcome for a ${selectedFinding.toLowerCase()} finding.`);
                return;
            }
        } else {
            // For any non-completed status (BLOCKED, SKIPPED, FAILED, UNKNOWN, NOT_APPLICABLE):
            if (!notes.trim()) {
                setFormError(
                    `Please explain why this check was marked as ${selectedStatus.replace(/_/g, " ").toLowerCase()} in the notes below.`
                );
                return;
            }
        }

        try {
            await onSubmit?.({
                check_id: actionId,
                execution_status: selectedStatus,
                finding: selectedStatus === "COMPLETED" ? selectedFinding : "UNKNOWN",
                outcome:
                    selectedStatus === "COMPLETED" &&
                    (selectedFinding === "SUPPORTS" || selectedFinding === "CONTRADICTS")
                        ? selectedOutcome
                        : null,
                finding_details: notes.trim() || null,
            });

            // Clear inputs ONLY on confirmed success:
            setSelectedOutcome("");
            setNotes("");
            setSelectedStatus("COMPLETED");
            setSelectedFinding("SUPPORTS");
            setFormError(null);
        } catch (err: unknown) {
            console.error("Check submission error in component:", err);
            const msg = err instanceof Error ? err.message : "Failed to submit check result.";
            setFormError(msg);
            // Inputs are preserved on failure!
        }
    };

    return (
        <div className="space-y-4">
            {actions.map((action) => {
                const isActive = Boolean(activeCheck && action.id === activeCheck.id);
                const isExpanded = expanded[action.id] ?? isActive;
                const config = statusConfig[action.status] || statusConfig.pending;
                const StatusIcon = config.icon;
                const possibleOutcomes = action.possibleOutcomes || [];

                return (
                    <div
                        key={action.id}
                        className={`rounded-2xl border bg-white shadow-sm transition ${
                            isActive
                                ? "border-[#6d5dfc] ring-1 ring-[#6d5dfc]"
                                : "border-gray-200"
                        }`}
                    >
                        {/* Header / Summary */}
                        <div
                            className="flex items-center justify-between p-5 cursor-pointer select-none"
                            onClick={() => toggleExpand(action.id)}
                        >
                            <div className="flex items-center gap-4">
                                <div className="shrink-0">
                                    <StatusIcon className={`h-6 w-6 ${config.className}`} />
                                </div>

                                <div>
                                    <div className="flex items-center gap-2.5">
                                        <span className="font-mono text-xs font-bold text-gray-500">
                                            {action.id}
                                        </span>
                                        <h3 className="text-sm font-semibold text-gray-900">
                                            {action.name}
                                        </h3>
                                        <span
                                            className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                                                effortConfig[action.effortLevel].className
                                            }`}
                                        >
                                            {effortConfig[action.effortLevel].label}
                                        </span>
                                        <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-600">
                                            {config.label}
                                        </span>
                                    </div>

                                    <p className="mt-1 text-xs text-gray-500">
                                        {action.description}
                                    </p>
                                </div>
                            </div>

                            <button
                                type="button"
                                className="text-gray-400 hover:text-gray-600 p-1"
                                aria-label={isExpanded ? "Collapse" : "Expand"}
                            >
                                {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                            </button>
                        </div>

                        {/* Collapsible Content */}
                        {isExpanded && (
                            <div className="border-t border-gray-100 p-5 pt-4">
                                <div>
                                    <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-400">
                                        Standard Operating Procedure
                                    </h4>
                                    <p className="mt-1 text-xs whitespace-pre-line text-gray-700 leading-relaxed bg-gray-50 p-3 rounded-xl border border-gray-100">
                                        {action.procedure}
                                    </p>
                                </div>

                                {action.applicableCauses && action.applicableCauses.length > 0 && (
                                    <div className="mt-4">
                                        <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-400">
                                            Target Causes Evaluated
                                        </h4>
                                        <div className="mt-1.5 flex flex-wrap gap-1.5">
                                            {action.applicableCauses.map((cause) => (
                                                <span
                                                    key={cause}
                                                    className="rounded-md bg-[#faf9ff] border border-[#ded9ff] px-2 py-0.5 text-[10px] font-medium text-[#5848e8]"
                                                >
                                                    {cause.replace(/_/g, " ")}
                                                </span>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {/* Historical Recorded Details */}
                                {action.status !== "pending" && (
                                    <div className="mt-4 rounded-xl border border-gray-100 bg-gray-50/70 p-3 text-xs space-y-1">
                                        <div className="flex items-center justify-between">
                                            <span className="font-semibold text-gray-700">Recorded Finding:</span>
                                            <span className="font-bold text-gray-900">{action.finding || "UNKNOWN"}</span>
                                        </div>
                                        {action.outcome && (
                                            <div className="flex items-center justify-between">
                                                <span className="font-semibold text-gray-700">Canonical Outcome:</span>
                                                <span className="font-mono text-[#5848e8]">
                                                    {action.outcome} ({formatOutcomeLabel(action.outcome)})
                                                </span>
                                            </div>
                                        )}
                                        {action.findingDetails && (
                                            <p className="text-gray-600 italic mt-1 pt-1 border-t border-gray-200">
                                                &quot;{action.findingDetails}&quot;
                                            </p>
                                        )}
                                    </div>
                                )}

                                {/* Active Check Execution Controls (Only if genuinely active pending check) */}
                                {isActive && (
                                    <div className="mt-5 space-y-4 rounded-xl border border-[#ded9ff] bg-[#faf9ff] p-4">
                                        <p className="text-xs font-bold uppercase tracking-wide text-gray-900">
                                            Record Physical Check Result
                                        </p>

                                        {formError && (
                                            <div className="flex items-center gap-2 rounded-lg bg-rose-50 p-2.5 text-xs text-rose-700 border border-rose-200">
                                                <AlertCircle size={14} className="shrink-0" />
                                                <span>{formError}</span>
                                            </div>
                                        )}

                                        {/* Status Selection (All 6 supported statuses) */}
                                        <div>
                                            <label className="block text-xs font-semibold text-gray-700 mb-1.5">
                                                Check Execution Status
                                            </label>
                                            <div className="flex flex-wrap gap-2">
                                                {executionStatusOptions.map((opt) => (
                                                    <button
                                                        key={opt.value}
                                                        type="button"
                                                        onClick={() => {
                                                            setSelectedStatus(opt.value);
                                                            setFormError(null);
                                                        }}
                                                        className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                                                            selectedStatus === opt.value
                                                                ? opt.activeClass
                                                                : "border border-gray-200 bg-white text-gray-700 hover:bg-gray-50"
                                                        }`}
                                                    >
                                                        {opt.label}
                                                    </button>
                                                ))}
                                            </div>
                                        </div>

                                        {/* Finding and Outcome if Completed */}
                                        {selectedStatus === "COMPLETED" && (
                                            <>
                                                <div>
                                                    <label className="block text-xs font-semibold text-gray-700 mb-1.5">
                                                        Evidence Finding
                                                    </label>
                                                    <div className="grid grid-cols-3 gap-2">
                                                        {(["SUPPORTS", "CONTRADICTS", "INCONCLUSIVE"] as const).map((f) => (
                                                            <button
                                                                key={f}
                                                                type="button"
                                                                onClick={() => {
                                                                    setSelectedFinding(f);
                                                                    setFormError(null);
                                                                }}
                                                                className={`rounded-lg px-3 py-2 text-xs font-medium text-center transition ${
                                                                    selectedFinding === f
                                                                        ? "border-2 border-[#6d5dfc] bg-white text-[#5848e8] font-bold shadow-sm"
                                                                        : "border border-gray-200 bg-white text-gray-600 hover:bg-gray-50"
                                                                }`}
                                                            >
                                                                {f}
                                                            </button>
                                                        ))}
                                                    </div>
                                                </div>

                                                {/* Canonical Outcome selection if SUPPORTS or CONTRADICTS */}
                                                {(selectedFinding === "SUPPORTS" || selectedFinding === "CONTRADICTS") && (
                                                    <div>
                                                        <label className="block text-xs font-semibold text-gray-700 mb-1.5">
                                                            Canonical Outcome Key <span className="text-rose-500">*</span>
                                                        </label>
                                                        {possibleOutcomes.length > 0 ? (
                                                            <div className="space-y-1.5">
                                                                {possibleOutcomes.map((outcomeKey) => (
                                                                    <label
                                                                        key={outcomeKey}
                                                                        className={`flex items-center gap-2.5 rounded-lg border p-2.5 text-xs cursor-pointer transition ${
                                                                            selectedOutcome === outcomeKey
                                                                                ? "border-[#6d5dfc] bg-white ring-1 ring-[#6d5dfc]"
                                                                                : "border-gray-200 bg-white hover:bg-gray-50"
                                                                        }`}
                                                                    >
                                                                        <input
                                                                            type="radio"
                                                                            name={`outcome-${action.id}`}
                                                                            value={outcomeKey}
                                                                            checked={selectedOutcome === outcomeKey}
                                                                            onChange={() => setSelectedOutcome(outcomeKey)}
                                                                            className="text-[#6d5dfc] focus:ring-[#6d5dfc]"
                                                                        />
                                                                        <span className="font-semibold text-gray-900">
                                                                            {formatOutcomeLabel(outcomeKey)}
                                                                        </span>
                                                                        <span className="font-mono text-[11px] text-gray-400 ml-auto">
                                                                            ({outcomeKey})
                                                                        </span>
                                                                    </label>
                                                                ))}
                                                            </div>
                                                        ) : (
                                                            <input
                                                                type="text"
                                                                value={selectedOutcome}
                                                                onChange={(e) => setSelectedOutcome(e.target.value)}
                                                                placeholder="e.g. blockage_found, no_blockage"
                                                                className="w-full rounded-xl border border-gray-200 bg-white px-3.5 py-2 text-xs font-mono text-gray-900 outline-none focus:border-[#6d5dfc]"
                                                            />
                                                        )}
                                                    </div>
                                                )}
                                            </>
                                        )}

                                        {/* Notes / Reason */}
                                        <div>
                                            <label className="block text-xs font-semibold text-gray-700 mb-1.5">
                                                Technician Observations & Notes{" "}
                                                {selectedStatus !== "COMPLETED" && (
                                                    <span className="text-rose-500">* (Reason required)</span>
                                                )}
                                            </label>
                                            <textarea
                                                value={notes}
                                                onChange={(e) => setNotes(e.target.value)}
                                                placeholder={
                                                    selectedStatus === "COMPLETED"
                                                        ? "Describe observed physical state (e.g. dried adhesive buildup in orifice)..."
                                                        : `Explain reason for marking as ${selectedStatus.replace(/_/g, " ").toLowerCase()}...`
                                                }
                                                rows={2}
                                                disabled={isSubmitting || disabled}
                                                className="w-full rounded-xl border border-gray-200 bg-white p-3 text-xs outline-none focus:border-[#6d5dfc] placeholder:text-gray-400"
                                            />
                                        </div>

                                        {/* Submit Button */}
                                        <div className="flex justify-end pt-1">
                                            <button
                                                type="button"
                                                onClick={() => handleSubmit(action.id)}
                                                disabled={isSubmitting || disabled}
                                                className="inline-flex items-center gap-2 rounded-xl bg-[#6d5dfc] px-5 py-2.5 text-xs font-semibold text-white transition hover:bg-[#5848e8] disabled:opacity-50"
                                            >
                                                {isSubmitting ? (
                                                    <>
                                                        <Loader2 size={14} className="animate-spin" />
                                                        Saving Result...
                                                    </>
                                                ) : (
                                                    <>
                                                        <CheckCircle2 size={14} />
                                                        Submit Check Result
                                                    </>
                                                )}
                                            </button>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                );
            })}
        </div>
    );
}
