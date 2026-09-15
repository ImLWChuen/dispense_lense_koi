"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";

import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";
import PageContainer from "@/components/layout/PageContainer";
import QuestionProgress from "@/components/diagnosis/QuestionProgress";
import DiagnosticQuestion from "@/components/diagnosis/DiagnosticQuestion";

const mockQuestions = [
    {
        id: "Q01",
        text: "Does the problem occur immediately after startup or only after the machine has been running for a while?",
        purpose:
            "Distinguishes thermal/time-related causes (air expansion, material viscosity change) from static issues.",
        options: [
            { value: "immediately", label: "Immediately at startup" },
            {
                value: "after_prolonged_operation",
                label: "After prolonged operation",
            },
            { value: "both", label: "Both / No pattern" },
        ],
    },
    {
        id: "Q02",
        text: "Does the defect occur across all dispensing points or only at specific nozzles/locations?",
        purpose:
            "Distinguishes system-wide causes (pressure, material) from localized causes (nozzle blockage, valve).",
        options: [
            { value: "all_points", label: "All dispensing points" },
            { value: "specific_nozzle", label: "Specific nozzle / location" },
            { value: "random", label: "Random / Varies" },
        ],
    },
    {
        id: "Q03",
        text: "Has the nozzle recently been replaced, cleaned, or maintained?",
        purpose: "Determines whether nozzle condition is a likely factor.",
        options: [
            { value: "YES", label: "Yes" },
            { value: "NO", label: "No" },
            { value: "UNKNOWN", label: "Unknown" },
        ],
    },
    {
        id: "Q04",
        text: "Does performing a purge cycle improve the dispensing temporarily?",
        purpose:
            "A positive purge response strongly suggests trapped air or dried material in the path.",
        options: [
            { value: "YES", label: "Yes, improves temporarily" },
            { value: "NO", label: "No improvement" },
            { value: "NOT_TESTED", label: "Not tested" },
        ],
    },
    {
        id: "Q05",
        text: "Was the dispensing material recently changed or is a new batch being used?",
        purpose:
            "Material batch variation can significantly affect dispensing performance.",
        options: [
            { value: "YES", label: "Yes, new material/batch" },
            { value: "NO", label: "No, same material" },
            { value: "UNKNOWN", label: "Unknown" },
        ],
    },
];

export default function QuestionsPage() {
    const [answers, setAnswers] = useState<Record<string, string>>({});

    const answeredCount = Object.keys(answers).length;
    const currentQuestionIndex = Math.min(
        answeredCount,
        mockQuestions.length - 1
    );

    const handleAnswer = (questionId: string, value: string) => {
        setAnswers((prev) => ({ ...prev, [questionId]: value }));
    };

    return (
        <div className="min-h-screen">
            <Sidebar />

            <div className="ml-64">
                <Header />

                <PageContainer>
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-sm font-medium text-[#6d5dfc]">
                                Diagnostic workflow · DSP-2026-0185
                            </p>

                            <h1 className="mt-1 text-3xl font-bold tracking-tight text-gray-900">
                                Diagnostic Questions
                            </h1>

                            <p className="mt-2 text-sm text-gray-500">
                                Answer these questions to refine the cause
                                ranking and improve diagnostic accuracy.
                            </p>
                        </div>

                        <Link
                            href="/diagnosis/DSP-2026-0185"
                            className="text-sm font-medium text-[#5848e8] hover:text-[#6d5dfc]"
                        >
                            ← Back to Diagnosis
                        </Link>
                    </div>

                    <div className="mt-8 grid grid-cols-1 gap-8 xl:grid-cols-3">
                        <div className="space-y-4 xl:col-span-2">
                            {mockQuestions.map((q, index) => (
                                <DiagnosticQuestion
                                    key={q.id}
                                    questionId={q.id}
                                    text={q.text}
                                    purpose={q.purpose}
                                    options={q.options}
                                    selectedValue={answers[q.id] ?? null}
                                    onAnswer={(value) =>
                                        handleAnswer(q.id, value)
                                    }
                                    isAnswered={
                                        answers[q.id] !== undefined &&
                                        index < currentQuestionIndex
                                    }
                                />
                            ))}

                            {answeredCount === mockQuestions.length && (
                                <div className="flex justify-end">
                                    <Link
                                        href="/diagnosis/DSP-2026-0185/troubleshooting"
                                        className="inline-flex items-center gap-2 rounded-xl bg-[#6d5dfc] px-6 py-3 text-sm font-semibold text-white transition hover:bg-[#5848e8]"
                                    >
                                        Continue to Troubleshooting
                                        <ArrowRight size={16} />
                                    </Link>
                                </div>
                            )}
                        </div>

                        <div>
                            <QuestionProgress
                                current={answeredCount}
                                total={mockQuestions.length}
                            />

                            <div className="mt-6 rounded-2xl border border-[#ded9ff] bg-[#faf9ff] p-5">
                                <p className="text-sm font-semibold text-gray-900">
                                    Why these questions?
                                </p>

                                <p className="mt-2 text-xs leading-5 text-gray-600">
                                    Each question is selected by the diagnostic
                                    engine to gather evidence that distinguishes
                                    between the candidate causes. Your answers
                                    update the evidence weights and re-rank the
                                    probable causes.
                                </p>
                            </div>
                        </div>
                    </div>
                </PageContainer>
            </div>
        </div>
    );
}
