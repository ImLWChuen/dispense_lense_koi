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
import { formatOutcomeLabel } from "@/lib/diagnostic-workflow-state";

export interface TroubleshootingAction {
    id: string;
    name: string;
    description: string;
    procedure: string;
    effortLevel: "low" | "medium" | "high";
    applicableCauses: string[];
    status: "pending" | "completed" | "blocked" | "skipped" | "failed" | "inconclusive";
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
}

export default function TroubleshootingChecklist({
    actions,
    activeCheckId,
    onSubmit,
    isSubmitting = false,
}: TroubleshootingChecklistProps) {
    // Determine active check or default to first pending
    const activeCheck = actions.find((a) => a.id === activeCheckId) || actions.find((a) => a.status === "pending") || actions[0];

    // Form state for active check execution
    const [selectedStatus, setSelectedStatus] = useState<"COMPLETED" | "BLOCKED" | "SKIPPED">("COMPLETED");
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
        setFormError(null);

        if (selectedStatus === "COMPLETED") {
            if ((selectedFinding === "SUPPORTS" || selectedFinding === "CONTRADICTS") && !selectedOutcome) {
                setFormError(`Please select a canonical outcome for a ${selectedFinding.toLowerCase()} finding.`);
                return;
            }
        } else if (selectedStatus === "BLOCKED" && !notes.trim()) {
            setFormError("Please explain why this check was blocked in the notes below.");
            return;
        }

        try {
            await onSubmit?.({
                check_id: actionId,
                execution_status: selectedStatus,
                finding: selectedStatus === "COMPLETED" ? selectedFinding : "UNKNOWN",
                outcome: selectedStatus === "COMPLETED" && (selectedFinding === "SUPPORTS" || selectedFinding === "CONTRADICTS") ? selectedOutcome : null,
                finding_details: notes.trim() || null,
            });

            // Clear inputs on success
            setSelectedOutcome("");
            setNotes("");
            setFormError(null);
        } catch (err: unknown) {
            console.error("Check submission error in component:", err);
            const msg = err instanceof Error ? err.message : "Failed to submit check result.";
            setFormError(msg);
        }
    };

    return (
        <div className="space-y-4">
            {actions.map((action) => {
                const isActive = action.status === "pending" || action.id === activeCheck?.id;
                const isExpanded = expanded[action.id] ?? isActive;
                const config = statusConfig[action.status] || statusConfig.pending;
                const StatusIcon = config.icon;
                const effort = effortConfig[action.effortLevel] || effortConfig.medium;
                const possibleOutcomes = action.possibleOutcomes || [];

                return (
                    <div
                        key={action.id}
                        className={`rounded-xl border bg-white shadow-sm transition ${
                            isActive
                                ? "border-[#6d5dfc]/40 ring-1 ring-[#6d5dfc]/20"
                                : action.status === "completed"
                                ? "border-green-200"
                                : "border-gray-200"
                        }`}
                    >
                        {/* Header */}
                        <button
                            onClick={() => toggleExpand(action.id)}
                            className="flex w-full items-center gap-3 p-5 text-left"
                            type="button"
                        >
                            <StatusIcon size={20} className={config.className} />

                            <div className="min-w-0 flex-1">
                                <div className="flex items-center gap-2">
                                    <p className="text-sm font-semibold text-gray-900 font-mono">
                                        [{action.id}] {action.name}
                                    </p>

                                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${effort.className}`}>
                                        {effort.label}
                                    </span>

                                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                                        isActive ? "bg-purple-50 text-[#6d5dfc]" : "bg-gray-100 text-gray-600"
                                    }`}>
                                        {config.label}
                                    </span>
                                </div>

                                <p className="mt-0.5 text-xs text-gray-500">{action.description}</p>
                            </div>

                            {isExpanded ? (
                                <ChevronUp size={16} className="shrink-0 text-gray-400" />
                            ) : (
                                <ChevronDown size={16} className="shrink-0 text-gray-400" />
                            )}
                        </button>

                        {/* Expanded Content */}
                        {isExpanded && (
                            <div className="border-t border-gray-100 px-5 pb-5 pt-4">
                                {/* Procedure */}
                                <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
                                    Standard Operating Procedure
                                </p>
                                <div className="mt-2 rounded-lg bg-gray-50 p-3.5">
                                    {action.procedure.split("\n").map((step, i) => (
                                        <p key={i} className="text-xs leading-5 text-gray-700 font-sans">
                                            {step}
                                        </p>
                                    ))}
                                </div>

                                {/* Target causes */}
                                {action.applicableCauses && action.applicableCauses.length > 0 && (
                                    <div className="mt-3">
                                        <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-400">
                                            Investigated Causes
                                        </p>
                                        <div className="mt-1 flex flex-wrap gap-1.5">
                                            {action.applicableCauses.map((cause) => (
                                                <span
                                                    key={cause}
                                                    className="rounded-md bg-[#eeebff] px-2 py-0.5 text-[10px] font-medium text-[#5848e8]"
                                                >
                                                    {cause.replace(/_/g, " ")}
                                                </span>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {/* Historical Finding Display if already executed */}
                                {!isActive && action.status !== "pending" && (
                                    <div className="mt-4 rounded-xl border border-gray-200 bg-gray-50/70 p-4">
                                        <p className="text-xs font-semibold text-gray-700">Recorded Finding</p>
                                        <div className="mt-1.5 grid grid-cols-2 gap-2 text-xs">
                                            <div>
                                                <span className="text-gray-500">Execution Status: </span>
                                                <span className="font-semibold text-gray-800">{action.status.toUpperCase()}</span>
                                            </div>
                                            {action.finding && (
                                                <div>
                                                    <span className="text-gray-500">Finding: </span>
                                                    <span className="font-semibold text-gray-800">{action.finding}</span>
                                                </div>
                                            )}
                                            {action.outcome && (
                                                <div>
                                                    <span className="text-gray-500">Canonical Outcome: </span>
                                                    <span className="font-mono font-medium text-[#5848e8]">
                                                        {action.outcome} ({formatOutcomeLabel(action.outcome)})
                                                    </span>
                                                </div>
                                            )}
                                        </div>
                                        {action.findingDetails && (
                                            <p className="mt-2 text-xs text-gray-600 italic">
                                                &quot;{action.findingDetails}&quot;
                                            </p>
                                        )}
                                    </div>
                                )}

                                {/* Active Check Execution Controls */}
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

                                        {/* Status Selection */}
                                        <div>
                                            <label className="block text-xs font-semibold text-gray-700 mb-1.5">
                                                Check Execution Status
                                            </label>
                                            <div className="flex gap-2">
                                                {(["COMPLETED", "BLOCKED", "SKIPPED"] as const).map((s) => (
                                                    <button
                                                        key={s}
                                                        type="button"
                                                        onClick={() => {
                                                            setSelectedStatus(s);
                                                            setFormError(null);
                                                        }}
                                                        className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                                                            selectedStatus === s
                                                                ? s === "COMPLETED"
                                                                    ? "bg-green-600 text-white shadow-sm"
                                                                    : s === "BLOCKED"
                                                                    ? "bg-rose-600 text-white shadow-sm"
                                                                    : "bg-gray-700 text-white shadow-sm"
                                                                : "border border-gray-200 bg-white text-gray-700 hover:bg-gray-50"
                                                        }`}
                                                    >
                                                        {s}
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
                                                                placeholder="Enter canonical outcome key (e.g. blockage_found)..."
                                                                className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs font-mono outline-none focus:border-[#6d5dfc]"
                                                            />
                                                        )}
                                                    </div>
                                                )}
                                            </>
                                        )}

                                        {/* Notes / Details */}
                                        <div>
                                            <label className="block text-xs font-semibold text-gray-700 mb-1">
                                                Technician Observations & Notes {selectedStatus === "BLOCKED" && <span className="text-rose-500">*</span>}
                                            </label>
                                            <textarea
                                                value={notes}
                                                onChange={(e) => setNotes(e.target.value)}
                                                placeholder={
                                                    selectedStatus === "BLOCKED"
                                                        ? "State why this check could not be completed..."
                                                        : "Record physical inspection measurements, observations, or equipment condition..."
                                                }
                                                rows={2}
                                                className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs outline-none transition placeholder:text-gray-400 focus:border-[#6d5dfc]"
                                            />
                                        </div>

                                        {/* Submit Action */}
                                        <div className="flex justify-end pt-1">
                                            <button
                                                type="button"
                                                onClick={() => handleSubmit(action.id)}
                                                disabled={isSubmitting}
                                                className="inline-flex items-center gap-2 rounded-xl bg-[#6d5dfc] px-4 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-[#5848e8] disabled:opacity-50"
                                            >
                                                {isSubmitting ? (
                                                    <>
                                                        <Loader2 size={13} className="animate-spin" />
                                                        Saving Finding...
                                                    </>
                                                ) : (
                                                    <>
                                                        <CheckCircle2 size={14} />
                                                        Submit Check Finding
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
