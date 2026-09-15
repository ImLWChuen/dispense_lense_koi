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
}

export default function DiagnosticQuestion({
    text,
    purpose,
    options,
    selectedValue,
    onAnswer,
    isAnswered = false,
}: DiagnosticQuestionProps) {
    return (
        <div
            className={`rounded-2xl border p-6 shadow-sm transition ${
                isAnswered
                    ? "border-green-200 bg-green-50/30"
                    : "border-gray-200 bg-white"
            }`}
        >
            <div className="flex items-start gap-3">
                <div
                    className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${
                        isAnswered
                            ? "bg-green-100 text-green-600"
                            : "bg-[#eeebff] text-[#6d5dfc]"
                    }`}
                >
                    {isAnswered ? (
                        <CheckCircle2 size={18} />
                    ) : (
                        <HelpCircle size={18} />
                    )}
                </div>

                <div className="flex-1">
                    <p className="text-sm font-semibold text-gray-900">
                        {text}
                    </p>

                    <p className="mt-1.5 text-xs leading-5 text-gray-500">
                        <span className="font-medium text-gray-400">
                            Purpose:{" "}
                        </span>
                        {purpose}
                    </p>

                    <div className="mt-4 flex flex-wrap gap-2">
                        {options.map((option) => {
                            const isSelected = selectedValue === option.value;

                            return (
                                <button
                                    key={option.value}
                                    onClick={() => onAnswer?.(option.value)}
                                    disabled={isAnswered}
                                    className={`rounded-lg border px-4 py-2 text-sm font-medium transition ${
                                        isSelected
                                            ? "border-[#6d5dfc] bg-[#6d5dfc] text-white"
                                            : isAnswered
                                              ? "border-gray-200 bg-gray-50 text-gray-400"
                                              : "border-gray-200 bg-white text-gray-700 hover:border-[#6d5dfc] hover:bg-[#faf9ff] hover:text-[#5848e8]"
                                    }`}
                                >
                                    {option.label}
                                </button>
                            );
                        })}
                    </div>
                </div>
            </div>
        </div>
    );
}
