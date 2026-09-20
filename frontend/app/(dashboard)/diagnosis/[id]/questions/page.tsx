"use client";

import { useState, useEffect, useCallback, use } from "react";
import Link from "next/link";
import { ArrowRight, CheckCircle2, Keyboard } from "lucide-react";

import PageContainer from "@/components/layout/PageContainer";
import DiagnosticStepper from "@/components/diagnosis/DiagnosticStepper";
import QuestionProgress from "@/components/diagnosis/QuestionProgress";
import DiagnosticQuestion from "@/components/diagnosis/DiagnosticQuestion";
import { casesApi } from "@/lib/api/cases";
import { DurableCaseResponse } from "@/types/api";

function normalizeOptions(options?: string[]) {
    if (!options || options.length === 0) {
        return [
            { value: "YES", label: "Yes" },
            { value: "NO", label: "No" },
            { value: "UNKNOWN", label: "Unknown" }
        ];
    }
    return options.map(opt => {
        if (typeof opt === 'string') {
            return { 
                value: opt, 
                label: opt.charAt(0).toUpperCase() + opt.slice(1).toLowerCase().replace(/_/g, ' ') 
            };
        }
        return opt;
    });
}

export default function QuestionsPage({ params }: { params: Promise<{ id: string }> }) {
    const resolvedParams = use(params);
    const [caseData, setCaseData] = useState<DurableCaseResponse | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);

    // Track previously answered questions to display them in the history
    const history = caseData?.previous_answers || [];

    const fetchCase = useCallback(async () => {
        try {
            const data = await casesApi.getCase(resolvedParams.id);
            setCaseData(data);
            setError(null);
        } catch (err: unknown) {
            console.error("Failed to fetch case", err);
            const message = err instanceof Error ? err.message : "Failed to load case data.";
            setError(message);
        } finally {
            setIsLoading(false);
        }
    }, [resolvedParams.id]);

    useEffect(() => {
        let isCurrent = true;
        casesApi
            .getCase(resolvedParams.id)
            .then((data) => {
                if (isCurrent) {
                    setCaseData(data);
                    setError(null);
                    setIsLoading(false);
                }
            })
            .catch((err: unknown) => {
                if (isCurrent) {
                    const message = err instanceof Error ? err.message : "Failed to load case data.";
                    setError(message);
                    setIsLoading(false);
                }
            });

        return () => {
            isCurrent = false;
        };
    }, [resolvedParams.id]);

    const diagnosis = caseData?.diagnosis || caseData?.initial_diagnosis;
    const nextQuestion = diagnosis?.next_question;
    const isDone = !nextQuestion && !isLoading;

    const handleAnswer = useCallback(async (questionId: string, value: string) => {
        if (!caseData?.diagnosis?.analysis_revision) return;
        
        setIsSubmitting(true);
        try {
            await casesApi.submitAnswer(
                caseData.case_id, 
                questionId, 
                value, 
                caseData.diagnosis.analysis_revision.revision_number
            );
            
            // Refresh to get the next question
            await fetchCase();
        } catch (err: unknown) {
            console.error("Failed to submit answer", err);
            const message = err instanceof Error ? err.message : "Failed to submit answer.";
            setError(message);
        } finally {
            setIsSubmitting(false);
        }
    }, [caseData, fetchCase]);

    // Cleanroom Keyboard Shortcuts: Press 1, 2, 3, etc. to submit answers instantly
    useEffect(() => {
        if (!nextQuestion || isSubmitting || isLoading) return;

        const currentOptions = normalizeOptions(nextQuestion.options);

        const handleKeyDown = (e: KeyboardEvent) => {
            const targetTag = (e.target as HTMLElement)?.tagName;
            if (["INPUT", "TEXTAREA", "SELECT"].includes(targetTag)) {
                return;
            }

            const key = e.key.toLowerCase();
            let optIdx = -1;

            if (key === "1") optIdx = 0;
            else if (key === "2") optIdx = 1;
            else if (key === "3") optIdx = 2;
            else if (key === "4") optIdx = 3;
            else if (key === "y") {
                const idx = currentOptions.findIndex((o) => o.value.toLowerCase().includes("yes"));
                if (idx !== -1) optIdx = idx;
            } else if (key === "n") {
                const idx = currentOptions.findIndex((o) => o.value.toLowerCase().includes("no"));
                if (idx !== -1) optIdx = idx;
            }

            if (optIdx >= 0 && optIdx < currentOptions.length) {
                e.preventDefault();
                handleAnswer(nextQuestion.question_id, currentOptions[optIdx].value);
            }
        };

        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [nextQuestion, isSubmitting, isLoading, handleAnswer]);

    if (isLoading && !caseData) {
        return (
            <PageContainer>
                <div className="flex h-64 items-center justify-center">
                    <p className="text-gray-500">Loading questions...</p>
                </div>
            </PageContainer>
        );
    }

    return (
        <PageContainer>
            <DiagnosticStepper
                caseId={resolvedParams.id}
                activeStep="questions"
                caseData={caseData}
            />

            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                    <div className="flex items-center gap-2.5">
                        <h1 className="text-3xl font-bold tracking-tight text-gray-900">
                            Diagnostic Questions
                        </h1>
                        {!isDone && (
                            <span className="hidden sm:inline-flex items-center gap-1.5 rounded-full border border-indigo-200 bg-[#eeebff] px-2.5 py-0.5 text-xs font-semibold text-[#5848e8]">
                                <Keyboard size={13} />
                                Hotkeys: Press 1, 2, 3
                            </span>
                        )}
                    </div>

                    <p className="mt-2 text-sm text-gray-500">
                        Answer these questions to refine the cause ranking and improve diagnostic accuracy.
                    </p>
                </div>

                <Link
                    href={`/diagnosis/${resolvedParams.id}`}
                    className="text-sm font-medium text-[#5848e8] hover:text-[#6d5dfc]"
                >
                    ← Back to Overview
                </Link>
            </div>

                    {error && (
                        <div className="mt-4 rounded-xl bg-red-50 p-4 text-sm text-red-700">
                            {error}
                        </div>
                    )}

                    <div className="mt-8 grid grid-cols-1 gap-8 xl:grid-cols-3">
                        <div className="space-y-4 xl:col-span-2">
                            {history.map((q, index) => (
                                <DiagnosticQuestion
                                    key={`hist-${q.question_id}-${index}`}
                                    questionId={q.question_id}
                                    text={q.text || q.answer_text || `Question ${q.question_id}`}
                                    purpose={q.reasoning || "Historical answer retrieved from diagnostic engine."}
                                    options={q.options ? normalizeOptions(q.options) : [{ value: q.answer_value, label: q.answer_value.charAt(0).toUpperCase() + q.answer_value.slice(1).toLowerCase().replace(/_/g, ' ') }]}
                                    selectedValue={q.answer_value}
                                    onAnswer={() => {}}
                                    isAnswered={true}
                                />
                            ))}

                            {nextQuestion && (
                                <DiagnosticQuestion
                                    key={nextQuestion.question_id}
                                    questionId={nextQuestion.question_id}
                                    text={nextQuestion.text}
                                    purpose={nextQuestion.purpose || nextQuestion.reasoning || ""}
                                    options={normalizeOptions(nextQuestion.options)}
                                    selectedValue={null}
                                    onAnswer={(value) => handleAnswer(nextQuestion.question_id, value)}
                                    isAnswered={isSubmitting}
                                />
                            )}

                            {isDone && (
                                <div className="rounded-2xl border border-emerald-100 bg-emerald-50 p-6 text-center">
                                    <CheckCircle2 className="mx-auto mb-3 h-10 w-10 text-emerald-500" />
                                    <h3 className="text-lg font-semibold text-emerald-800">No more questions</h3>
                                    <p className="mt-2 text-sm text-emerald-700">
                                        The diagnostic engine has gathered enough evidence from questions.
                                        You should now proceed to physical troubleshooting checks.
                                    </p>
                                    <Link
                                        href={`/diagnosis/${resolvedParams.id}/troubleshooting`}
                                        className="mt-5 inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-6 py-3 text-sm font-semibold text-white transition hover:bg-emerald-700"
                                    >
                                        Continue to Troubleshooting
                                        <ArrowRight size={16} />
                                    </Link>
                                </div>
                            )}

                            {history.length > 0 && !isDone && (
                                <div className="flex justify-end pt-4">
                                    <Link
                                        href={`/diagnosis/${resolvedParams.id}/troubleshooting`}
                                        className="inline-flex items-center gap-2 rounded-xl border border-gray-200 bg-white px-6 py-3 text-sm font-semibold text-gray-700 transition hover:bg-gray-50"
                                    >
                                        Skip remaining questions
                                        <ArrowRight size={16} />
                                    </Link>
                                </div>
                            )}
                        </div>

                        <div>
                            {/* In a real app we'd track total questions vs answered, but engine provides dynamically */}
                            <QuestionProgress
                                current={history.length}
                                total={history.length + (nextQuestion ? 1 : 0)}
                            />

                            <div className="mt-6 rounded-2xl border border-[#ded9ff] bg-[#faf9ff] p-5">
                                <p className="text-sm font-semibold text-gray-900">
                                    Why these questions?
                                </p>

                                <p className="mt-2 text-xs leading-5 text-gray-600">
                                    Each question is dynamically selected by the diagnostic
                                    engine to gather evidence that best distinguishes
                                    between the candidate causes. Your answers
                                    update the evidence weights and re-rank the
                                    probable causes.
                                </p>
                            </div>
                        </div>
                    </div>
                </PageContainer>
    );
}
