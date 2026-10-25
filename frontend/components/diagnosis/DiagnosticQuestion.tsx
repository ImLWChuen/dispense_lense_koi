"use client";

import { HelpCircle, CheckCircle2 } from "lucide-react";

/**
 * Represents a single selectable option for a diagnostic discriminator question.
 */
interface QuestionOption {
    /** Unique value submitted to the backend when selected (e.g., 'yes', 'no', 'above_threshold') */
    value: string;
    /** Human-readable text label displayed to the line engineer */
    label: string;
}

/**
 * Props for the DiagnosticQuestion component.
 */
interface DiagnosticQuestionProps {
    /** Unique identifier for the question node within the diagnostic tree */
    questionId: string;
    /** The formulation of the question displayed to the operator */
    text: string;
    /** Explains why this question is being asked (e.g. discriminating between viscosity vs pressure) */
    purpose: string;
    /** List of choices available for answering */
    options: QuestionOption[];
    /** Currently selected option value, if any */
    selectedValue?: string | null;
    /** Callback invoked when the user selects an option */
    onAnswer?: (value: string) => void;
    /** Whether this question has already been answered and committed */
    isAnswered?: boolean;
    /** Whether interactions are disabled (e.g., while awaiting backend response or in read-only mode) */
    disabled?: boolean;
}

/**
 * DiagnosticQuestion
 * 
 * Renders an interactive diagnostic inquiry card with dynamic option badges.
 * Visual cues transition between pending state (purple theme with Help icon) and
 * answered state (emerald green theme with Checkmark icon).
 */
export default function DiagnosticQuestion({
    text,
    purpose,
    options,
    selectedValue,
    onAnswer,
    isAnswered = false,
    disabled = false,
}: DiagnosticQuestionProps) {
    return (
        /* Outer Card: Adjusts border and subtle background tint based on answered status */
        <div
            className={`rounded-2xl border p-6 shadow-sm transition ${isAnswered
                    ? "border-emerald-200 bg-emerald-50/30"
                    : "border-gray-200 bg-white"
                }`}
        >
            <div className="flex items-start gap-3.5">
                {/* State Badge: Green checkmark if answered, purple help icon if awaiting answer */}
                <div
                    className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${isAnswered
                            ? "bg-emerald-100 text-emerald-600"
                            : "bg-[#eeebff] text-[#6d5dfc]"
                        }`}
                    aria-hidden="true"
                >
                    {isAnswered ? (
                        <CheckCircle2 size={20} />
                    ) : (
                        <HelpCircle size={20} />
                    )}
                </div>

                {/* Question Details and Action Options */}
                <div className="flex-1">
                    {/* Primary question prompt */}
                    <p className="text-base font-semibold text-gray-900 leading-snug">
                        {text}
                    </p>

                    {/* Explanatory diagnostic rationale explaining what this question discriminates */}
                    <p className="mt-1.5 text-xs leading-5 text-gray-500">
                        <span className="font-semibold text-gray-400 uppercase tracking-wider text-[10px]">
                            Diagnostic Purpose:{" "}
                        </span>
                        {purpose}
                    </p>

                    {/* Option Selection Buttons */}
                    <div className="mt-5 flex flex-wrap gap-2.5" role="group" aria-label="Question options">
                        {options.map((option, idx) => {
                            const isSelected = selectedValue === option.value;
                            const isOptionDisabled = isAnswered || disabled;

                            return (
                                <button
                                    key={option.value}
                                    onClick={() => !isOptionDisabled && onAnswer?.(option.value)}
                                    disabled={isOptionDisabled}
                                    aria-pressed={isSelected}
                                    className={`group inline-flex items-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-semibold transition ${isSelected
                                            ? "border-[#6d5dfc] bg-[#6d5dfc] text-white shadow-xs"
                                            : isAnswered
                                                ? "border-gray-200 bg-gray-50 text-gray-400"
                                                : isOptionDisabled
                                                    ? "border-gray-200 bg-gray-50 text-gray-400 cursor-not-allowed opacity-60"
                                                    : "border-gray-200 bg-white text-gray-700 hover:border-[#6d5dfc] hover:bg-[#eeebff]/30 hover:text-[#5848e8] shadow-2xs"
                                        }`}
                                >
                                    {/* Keyboard shortcut hint index (1-based) shown before answering */}
                                    {!isAnswered && (
                                        <kbd
                                            className={`inline-flex h-5 w-5 items-center justify-center rounded text-[10px] font-bold ${isSelected
                                                    ? "bg-white/20 text-white"
                                                    : "bg-gray-100 text-gray-500 group-hover:bg-[#eeebff] group-hover:text-[#5848e8]"
                                                }`}
                                        >
                                            {idx + 1}
                                        </kbd>
                                    )}
                                    <span>{option.label}</span>
                                </button>
                            );
                        })}
                    </div>
                </div>
            </div>
        </div>
    );
}
