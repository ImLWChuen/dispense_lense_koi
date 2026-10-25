"use client";

import Link from "next/link";
import {
    Activity,
    MessageSquare,
    ClipboardCheck,
    UserCheck,
    BarChart3,
    Check,
    ChevronRight,
    ArrowLeft,
    Clock,
    ShieldAlert,
} from "lucide-react";
import { DurableCaseResponse } from "@/types/api";

/**
 * Props for DiagnosticStepper component.
 */
interface DiagnosticStepperProps {
    /** Case identifier used to construct navigation links */
    caseId: string;
    /** Current active workflow tab / step */
    activeStep: "overview" | "questions" | "troubleshooting" | "verification" | "analysis";
    /** Full durable case payload from the backend to compute dynamic completion badges */
    caseData?: DurableCaseResponse | null;
}

/**
 * DiagnosticStepper
 * 
 * Sticky/header multi-stage navigation bar guiding line engineers through the 5-phase
 * dispensing failure diagnosis workflow:
 * 1. Overview (Defect intake, telemetry & vision overlays)
 * 2. Questions (Dynamic discriminator Q&A)
 * 3. Physical Checks (SOP troubleshooting checklist)
 * 4. Verification (Recovery run validation & sign-off)
 * 5. Scoring & Analysis (Bayesian cause rank distribution & weights)
 */
export default function DiagnosticStepper({
    caseId,
    activeStep,
    caseData,
}: DiagnosticStepperProps) {
    // Truncate UUID for clean breadcrumb display
    const shortId = caseId.includes("-") ? caseId.split("-")[0] : caseId;

    // Derived progress metrics from case data payload
    const diagnosis = caseData?.diagnosis || caseData?.initial_diagnosis;
    const answeredCount = caseData?.previous_answers?.length || 0;
    const isQuestionsDone = !diagnosis?.next_question && answeredCount > 0;

    // Count physical SOP troubleshooting actions executed and completed
    const completedChecks = caseData?.previous_check_results?.filter(
        (c) => c.execution_status === "COMPLETED"
    ).length || 0;
    const isChecksDone = !diagnosis?.next_check && (caseData?.previous_check_results?.length || 0) > 0;

    // Check if case is officially marked resolved
    const isResolved =
        caseData?.issue_condition === "RESOLVED" ||
        caseData?.issue_condition === "IssueCondition.RESOLVED";

    // Format badge colors according to condition severity / lifecycle phase
    const condition = caseData?.issue_condition || "UNRESOLVED";
    const statusColor =
        condition === "RESOLVED"
            ? "bg-emerald-50 text-emerald-700 border-emerald-200"
            : condition === "RECOVERY_PENDING_VERIFICATION"
            ? "bg-blue-50 text-blue-700 border-blue-200"
            : "bg-amber-50 text-amber-700 border-amber-200";

    // Step definitions with dynamic statuses and deep links
    const steps = [
        {
            id: "overview",
            name: "Overview",
            badge: "Intake",
            href: `/diagnosis/${caseId}`,
            icon: Activity,
            isCompleted: true,
            isCurrent: activeStep === "overview",
        },
        {
            id: "questions",
            name: "Questions",
            badge: isQuestionsDone ? "Complete" : `${answeredCount} answered`,
            href: `/diagnosis/${caseId}/questions`,
            icon: MessageSquare,
            isCompleted: isQuestionsDone,
            isCurrent: activeStep === "questions",
        },
        {
            id: "troubleshooting",
            name: "Physical Checks",
            badge: isChecksDone ? "Complete" : completedChecks > 0 ? `${completedChecks} done` : "SOP",
            href: `/diagnosis/${caseId}/troubleshooting`,
            icon: ClipboardCheck,
            isCompleted: isChecksDone,
            isCurrent: activeStep === "troubleshooting",
        },
        {
            id: "verification",
            name: "Verification",
            badge: isResolved ? "Resolved" : "Sign-off",
            href: `/diagnosis/${caseId}/verification`,
            icon: UserCheck,
            isCompleted: isResolved,
            isCurrent: activeStep === "verification",
        },
        {
            id: "analysis",
            name: "Scoring & Analysis",
            badge: "Bayesian",
            href: `/diagnosis/${caseId}/analysis`,
            icon: BarChart3,
            isCompleted: Boolean(diagnosis?.ranked_causes?.length),
            isCurrent: activeStep === "analysis",
        },
    ];

    return (
        <div className="mb-8 rounded-2xl border border-gray-200/80 bg-white p-4 sm:p-5 shadow-xs">
            {/* Top Meta Bar: Case ID breadcrumb, defect tag, line context, and resolution badge */}
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-100 pb-3.5">
                <div className="flex items-center gap-2 sm:gap-3">
                    <Link
                        href="/cases"
                        className="inline-flex items-center gap-1 text-xs font-semibold text-gray-500 hover:text-[#6d5dfc] transition"
                        title="Return to case list"
                    >
                        <ArrowLeft size={14} />
                        <span className="hidden sm:inline">Cases /</span>
                    </Link>

                    <div className="flex items-center gap-2">
                        {/* Short case token */}
                        <span className="font-mono text-xs font-bold text-gray-900 bg-gray-100 px-2 py-0.5 rounded-md">
                            #{shortId}
                        </span>

                        {/* Defect label */}
                        {caseData?.defect_name && (
                            <span className="text-xs font-semibold text-gray-800 truncate max-w-[200px] sm:max-w-xs">
                                {caseData.defect_name}
                            </span>
                        )}

                        {/* Production line context */}
                        {caseData?.machine_context?.equipment && (
                            <span className="hidden md:inline-flex rounded border border-gray-200 bg-gray-50 px-1.5 py-0.5 text-[10px] font-medium text-gray-600">
                                Line {String(caseData.machine_context.equipment)}
                            </span>
                        )}
                    </div>
                </div>

                {/* Case Lifecycle Condition Pill */}
                <div className="flex items-center gap-2">
                    <span
                        className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-bold ${statusColor}`}
                    >
                        <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden="true" />
                        {condition.replace(/_/g, " ")}
                    </span>
                </div>
            </div>

            {/* Stepper Navigation Strip: Horizontally scrollable step pills */}
            <nav aria-label="Diagnostic Workflow Steps" className="mt-3.5 flex items-center justify-between gap-2 overflow-x-auto pb-1 sm:pb-0 scrollbar-none">
                {steps.map((step, idx) => {
                    const Icon = step.icon;

                    return (
                        <div key={step.id} className="flex items-center flex-1 min-w-[140px] first:pl-0 last:pr-0">
                            <Link
                                href={step.href}
                                aria-current={step.isCurrent ? "step" : undefined}
                                className={`group flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 transition ${
                                    step.isCurrent
                                        ? "bg-[#eeebff] text-[#5848e8] shadow-xs"
                                        : "hover:bg-gray-50 text-gray-600"
                                }`}
                            >
                                {/* Step Icon: Checkmark if finished, distinct brand color if current */}
                                <div
                                    className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition ${
                                        step.isCurrent
                                            ? "bg-[#6d5dfc] text-white shadow-xs"
                                            : step.isCompleted
                                            ? "bg-emerald-100 text-emerald-700"
                                            : "bg-gray-100 text-gray-400 group-hover:bg-gray-200"
                                    }`}
                                >
                                    {step.isCompleted && !step.isCurrent ? (
                                        <Check size={16} strokeWidth={2.5} />
                                    ) : (
                                        <Icon size={16} strokeWidth={step.isCurrent ? 2.2 : 1.8} />
                                    )}
                                </div>

                                {/* Step Label & Sub-status */}
                                <div className="min-w-0">
                                    <p
                                        className={`text-xs font-semibold truncate ${
                                            step.isCurrent
                                                ? "text-[#5848e8]"
                                                : "text-gray-800 group-hover:text-gray-900"
                                        }`}
                                    >
                                        {step.name}
                                    </p>
                                    <p
                                        className={`text-[10px] truncate ${
                                            step.isCurrent
                                                ? "text-[#6d5dfc] font-medium"
                                                : "text-gray-400"
                                        }`}
                                    >
                                        {step.badge}
                                    </p>
                                </div>
                            </Link>

                            {/* Separator Chevron between steps */}
                            {idx < steps.length - 1 && (
                                <ChevronRight
                                    size={15}
                                    className="hidden xl:block text-gray-300 mx-1 shrink-0"
                                    aria-hidden="true"
                                />
                            )}
                        </div>
                    );
                })}
            </nav>
        </div>
    );
}
