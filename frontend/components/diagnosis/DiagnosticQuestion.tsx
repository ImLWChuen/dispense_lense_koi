"use client";

import { HelpCircle, CheckCircle2 } from "lucide-react";

interface QuestionOption {
    value: string;
    label: string;
}

interface DiagnosticQuestionProps {
    questionId: string;
    text: string;
    purpose: string;
    options: QuestionOption[];
    selectedValue?: string | null;
    onAnswer?: (value: string) => void;
    isAnswered?: boolean;
    disabled?: boolean;
}

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
        <div
            className={`rounded-2xl border p-6 shadow-sm transition ${
                isAnswered
                    ? "border-emerald-200 bg-emerald-50/30"
                    : "border-gray-200 bg-white"
            }`}
        >
            <div className="flex items-start gap-3.5">
                <div
                    className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${
                        isAnswered
                            ? "bg-emerald-100 text-emerald-600"
                            : "bg-[#eeebff] text-[#6d5dfc]"
                    }`}
                >
                    {isAnswered ? (
                        <CheckCircle2 size={20} />
                    ) : (
                        <HelpCircle size={20} />
                    )}
                </div>

                <div className="flex-1">
                    <p className="text-base font-semibold text-gray-900 leading-snug">
                        {text}
                    </p>

                    <p className="mt-1.5 text-xs leading-5 text-gray-500">
                        <span className="font-semibold text-gray-400 uppercase tracking-wider text-[10px]">
                            Diagnostic Purpose:{" "}
                        </span>
                        {purpose}
                    </p>

                    <div className="mt-5 flex flex-wrap gap-2.5">
                        {options.map((option, idx) => {
                            const isSelected = selectedValue === option.value;
                            const isOptionDisabled = isAnswered || disabled;

                            return (
                                <button
                                    key={option.value}
                                    onClick={() => onAnswer?.(option.value)}
                                    disabled={isAnswered}
                                    className={`group inline-flex items-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-semibold transition ${
                                        isSelected
                                            ? "border-[#6d5dfc] bg-[#6d5dfc] text-white shadow-xs"
                                            : isAnswered
                                            ? "border-gray-200 bg-gray-50 text-gray-400"
                                            : "border-gray-200 bg-white text-gray-700 hover:border-[#6d5dfc] hover:bg-[#eeebff]/30 hover:text-[#5848e8] shadow-2xs"
                                    }`}
                                >
                                    {!isAnswered && (
                                        <kbd
                                            className={`inline-flex h-5 w-5 items-center justify-center rounded text-[10px] font-bold ${
                                                isSelected
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
