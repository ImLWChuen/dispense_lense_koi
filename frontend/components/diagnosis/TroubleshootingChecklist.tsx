"use client";

import { useState } from "react";
import {
    CheckCircle2,
    Circle,
    Clock3,
    Ban,
    ChevronDown,
    ChevronUp,
} from "lucide-react";

interface TroubleshootingAction {
    id: string;
    name: string;
    description: string;
    procedure: string;
    effortLevel: "low" | "medium" | "high";
    applicableCauses: string[];
}

const effortConfig = {
    low: { className: "bg-green-50 text-green-700", label: "Low Effort" },
    medium: { className: "bg-amber-50 text-amber-700", label: "Medium Effort" },
    high: { className: "bg-red-50 text-red-700", label: "High Effort" },
};

type CheckStatus = "pending" | "completed" | "blocked" | "skipped";

const statusConfig = {
    pending: { icon: Circle, className: "text-gray-400", label: "Pending" },
    completed: {
        icon: CheckCircle2,
        className: "text-green-600",
        label: "Completed",
    },
    blocked: { icon: Ban, className: "text-red-500", label: "Blocked" },
    skipped: { icon: Clock3, className: "text-gray-400", label: "Skipped" },
};

interface TroubleshootingChecklistProps {
    actions: TroubleshootingAction[];
}

export default function TroubleshootingChecklist({
    actions,
}: TroubleshootingChecklistProps) {
    const [statuses, setStatuses] = useState<Record<string, CheckStatus>>({});
    const [expanded, setExpanded] = useState<Record<string, boolean>>({});
    const [findings, setFindings] = useState<Record<string, string>>({});

    const toggleExpand = (id: string) => {
        setExpanded((prev) => ({ ...prev, [id]: !prev[id] }));
    };

    const setStatus = (id: string, status: CheckStatus) => {
        setStatuses((prev) => ({ ...prev, [id]: status }));
    };

    return (
        <div className="space-y-3">
            {actions.map((action) => {
                const currentStatus = statuses[action.id] || "pending";
                const isExpanded = expanded[action.id] || false;
                const StatusIcon = statusConfig[currentStatus].icon;
                const effort = effortConfig[action.effortLevel];

                return (
                    <div
                        key={action.id}
                        className={`rounded-xl border bg-white shadow-sm transition ${
                            currentStatus === "completed"
                                ? "border-green-200"
                                : "border-gray-200"
                        }`}
                    >
                        {/* Header */}
                        <button
                            onClick={() => toggleExpand(action.id)}
                            className="flex w-full items-center gap-3 p-5 text-left"
                        >
                            <StatusIcon
                                size={20}
                                className={
                                    statusConfig[currentStatus].className
                                }
                            />

                            <div className="min-w-0 flex-1">
                                <div className="flex items-center gap-2">
                                    <p className="text-sm font-semibold text-gray-900">
                                        {action.name}
                                    </p>

                                    <span
                                        className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${effort.className}`}
                                    >
                                        {effort.label}
                                    </span>
                                </div>

                                <p className="mt-0.5 text-xs text-gray-500">
                                    {action.description}
                                </p>
                            </div>

                            {isExpanded ? (
                                <ChevronUp
                                    size={16}
                                    className="shrink-0 text-gray-400"
                                />
                            ) : (
                                <ChevronDown
                                    size={16}
                                    className="shrink-0 text-gray-400"
                                />
                            )}
                        </button>

                        {/* Expanded content */}
                        {isExpanded && (
                            <div className="border-t border-gray-100 px-5 pb-5 pt-4">
                                <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
                                    Procedure
                                </p>

                                <div className="mt-2 rounded-lg bg-gray-50 p-3">
                                    {action.procedure
                                        .split("\n")
                                        .map((step, i) => (
                                            <p
                                                key={i}
                                                className="text-xs leading-5 text-gray-600"
                                            >
                                                {step}
                                            </p>
                                        ))}
                                </div>

                                <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                    Applicable Causes
                                </p>

                                <div className="mt-1.5 flex flex-wrap gap-1.5">
                                    {action.applicableCauses.map((cause) => (
                                        <span
                                            key={cause}
                                            className="rounded-md bg-[#eeebff] px-2 py-0.5 text-[10px] font-medium text-[#5848e8]"
                                        >
                                            {cause.replace(/_/g, " ")}
                                        </span>
                                    ))}
                                </div>

                                <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                    Findings
                                </p>

                                <textarea
                                    value={findings[action.id] || ""}
                                    onChange={(e) =>
                                        setFindings((prev) => ({
                                            ...prev,
                                            [action.id]: e.target.value,
                                        }))
                                    }
                                    placeholder="Record your findings here..."
                                    rows={2}
                                    className="mt-1.5 w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-xs outline-none transition placeholder:text-gray-400 focus:border-[#6d5dfc] focus:bg-white"
                                />

                                <div className="mt-3 flex gap-2">
                                    <button
                                        onClick={() =>
                                            setStatus(action.id, "completed")
                                        }
                                        className="rounded-lg bg-green-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-green-700"
                                    >
                                        Mark Complete
                                    </button>

                                    <button
                                        onClick={() =>
                                            setStatus(action.id, "blocked")
                                        }
                                        className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-semibold text-gray-600 transition hover:bg-gray-50"
                                    >
                                        Mark Blocked
                                    </button>

                                    <button
                                        onClick={() =>
                                            setStatus(action.id, "skipped")
                                        }
                                        className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-semibold text-gray-600 transition hover:bg-gray-50"
                                    >
                                        Skip
                                    </button>
                                </div>
                            </div>
                        )}
                    </div>
                );
            })}
        </div>
    );
}
