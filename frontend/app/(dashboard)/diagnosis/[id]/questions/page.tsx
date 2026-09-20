"use client";

import { useState, useEffect, useCallback, use } from "react";
import Link from "next/link";
import { ArrowRight, CheckCircle2, AlertCircle, RefreshCw } from "lucide-react";

import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";
import PageContainer from "@/components/layout/PageContainer";
import QuestionProgress from "@/components/diagnosis/QuestionProgress";
import DiagnosticQuestion from "@/components/diagnosis/DiagnosticQuestion";
import { casesApi } from "@/lib/api/cases";
import { DurableCaseResponse } from "@/types/api";
import { deriveQuestionsView } from "@/lib/diagnostic-workflow-state";

export default function QuestionsPage({ params }: { params: Promise<{ id: string }> }) {
    const resolvedParams = use(params);
    const [caseData, setCaseData] = useState<DurableCaseResponse | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);

    const history = caseData?.previous_answers || [];

    const fetchCase = useCallback(async () => {
        setIsLoading(true);
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

    const handleAnswer = async (questionId: string, value: string) => {
        if (!caseData?.diagnosis?.analysis_revision) return;

        setIsSubmitting(true);
        try {
            const res = await casesApi.submitAnswer(
                caseData.case_id,
                questionId,
                value,
                caseData.diagnosis.analysis_revision.revision_number
            );
            setCaseData(res);
            setError(null);
        } catch (err: unknown) {
            console.error("Failed to submit answer", err);
            const message = err instanceof Error ? err.message : "Failed to submit answer.";
            setError(message);
            // Refresh to synchronize with latest persisted case state
            await fetchCase();
        } finally {
            setIsSubmitting(false);
        }
    };

    const diagnosis = caseData?.diagnosis || caseData?.initial_diagnosis;
    const nextQuestion = diagnosis?.next_question;

    const derived = deriveQuestionsView({
        isLoading,
        error,
        caseData,
        hasNextQuestion: Boolean(nextQuestion),
    });

    const normalizeOptions = (options?: string[]) => {
        if (!options || options.length === 0) {
            return [
                { value: "YES", label: "Yes" },
                { value: "NO", label: "No" },
                { value: "UNKNOWN", label: "Unknown" },
            ];
        }
        return options.map((opt) => {
            if (typeof opt === "string") {
                return {
                    value: opt,
                    label: opt.charAt(0).toUpperCase() + opt.slice(1).toLowerCase().replace(/_/g, " "),
                };
            }
            return opt;
        });
    };

    // 1. Initial Loading
    if (derived.showInitialLoading) {
        return (
            <div className="min-h-screen">
                <Sidebar />
                <div className="ml-64">
                    <Header />
                    <PageContainer>
                        <div className="flex h-64 items-center justify-center">
                            <p className="text-gray-500">Loading questions...</p>
                        </div>
                    </PageContainer>
                </div>
            </div>
        );
    }

    // 2. Dedicated Error (Initial request failure)
    if (derived.showDedicatedError) {
        return (
            <div className="min-h-screen">
                <Sidebar />
                <div className="ml-64">
                    <Header />
                    <PageContainer>
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm font-medium text-[#6d5dfc]">
                                    Diagnostic workflow · {resolvedParams.id.split("-")[0]}
                                </p>
                                <h1 className="mt-1 text-3xl font-bold tracking-tight text-gray-900">
                                    Diagnostic Questions
                                </h1>
                            </div>
                            <Link
                                href={`/diagnosis/${resolvedParams.id}`}
                                className="text-sm font-medium text-[#5848e8] hover:text-[#6d5dfc]"
                            >
                                ← Back to Diagnosis
                            </Link>
                        </div>

                        <div className="mt-8 rounded-2xl border border-red-200 bg-red-50 p-6 text-center">
                            <AlertCircle className="mx-auto mb-3 h-10 w-10 text-red-500" />
                            <h3 className="text-lg font-semibold text-red-800">Failed to load questions</h3>
                            <p className="mt-2 text-sm text-red-700">
                                {error || "Unable to retrieve diagnostic questions for this case."}
                            </p>
                            <div className="mt-5 flex justify-center gap-4">
                                <button
                                    onClick={fetchCase}
                                    className="inline-flex items-center gap-2 rounded-xl bg-red-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-red-700"
                                >
                                    <RefreshCw size={16} />
                                    Retry
                                </button>
                                <Link
                                    href={`/diagnosis/${resolvedParams.id}`}
                                    className="inline-flex items-center gap-2 rounded-xl border border-gray-300 bg-white px-5 py-2.5 text-sm font-semibold text-gray-700 transition hover:bg-gray-50"
                                >
                                    Return to Diagnosis
                                </Link>
                            </div>
                        </div>
                    </PageContainer>
                </div>
            </div>
        );
    }

    // 3. Loaded state (with active question or no next question)
    return (
        <div className="min-h-screen">
            <Sidebar />

            <div className="ml-64">
                <Header />

                <PageContainer>
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-sm font-medium text-[#6d5dfc]">
                                Diagnostic workflow · {resolvedParams.id.split("-")[0]}
                            </p>

                            <h1 className="mt-1 text-3xl font-bold tracking-tight text-gray-900">
                                Diagnostic Questions
                            </h1>

                            <p className="mt-2 text-sm text-gray-500">
                                Answer these questions to refine the cause ranking and improve diagnostic accuracy.
                            </p>
                        </div>

                        <Link
                            href={`/diagnosis/${resolvedParams.id}`}
                            className="text-sm font-medium text-[#5848e8] hover:text-[#6d5dfc]"
                        >
                            ← Back to Diagnosis
                        </Link>
                    </div>

                    {/* Stale / mutation error banner */}
                    {derived.showStaleBanner && (
                        <div className="mt-4 flex items-center justify-between rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
                            <div>
                                <p className="font-semibold">Update Failed</p>
                                <p className="mt-0.5">{error}. Persisted case data has been re-synchronized.</p>
                            </div>
                            <button
                                onClick={fetchCase}
                                className="inline-flex items-center gap-1 rounded-lg border border-amber-300 bg-white px-3 py-1.5 text-xs font-semibold text-amber-800 hover:bg-amber-100"
                            >
                                <RefreshCw size={14} />
                                Refresh
                            </button>
                        </div>
                    )}

                    <div className="mt-8 grid grid-cols-1 gap-8 xl:grid-cols-3">
                        <div className="space-y-4 xl:col-span-2">
                            {/* Question history */}
                            {history.map((q, index) => (
                                <DiagnosticQuestion
                                    key={`hist-${q.question_id}-${index}`}
                                    questionId={q.question_id}
                                    text={q.text || q.answer_text || `Question ${q.question_id}`}
                                    purpose={q.reasoning || "Historical answer retrieved from diagnostic engine."}
                                    options={
                                        q.options
                                            ? normalizeOptions(q.options)
                                            : [
                                                  {
                                                      value: q.answer_value,
                                                      label:
                                                          q.answer_value.charAt(0).toUpperCase() +
                                                          q.answer_value.slice(1).toLowerCase().replace(/_/g, " "),
                                                  },
                                              ]
                                    }
                                    selectedValue={q.answer_value}
                                    onAnswer={() => {}}
                                    isAnswered={true}
                                />
                            ))}

                            {/* Active Next Question */}
                            {derived.showActiveQuestion && nextQuestion && (
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

                            {/* Truthful Neutral Completion: No more questions available */}
                            {derived.showNoNextQuestion && (
                                <div className="rounded-2xl border border-gray-200 bg-white p-6 text-center shadow-sm">
                                    <CheckCircle2 className="mx-auto mb-3 h-10 w-10 text-[#6d5dfc]" />
                                    <h3 className="text-lg font-semibold text-gray-900">No Additional Questions</h3>
                                    <p className="mt-2 text-sm text-gray-600">
                                        No additional questions are currently recommended by the diagnostic engine.
                                        Proceeding to physical troubleshooting checks is a technician choice.
                                    </p>
                                    <Link
                                        href={`/diagnosis/${resolvedParams.id}/troubleshooting`}
                                        className="mt-5 inline-flex items-center gap-2 rounded-xl bg-[#6d5dfc] px-6 py-3 text-sm font-semibold text-white transition hover:bg-[#5848e8]"
                                    >
                                        Proceed to Troubleshooting Checks
                                        <ArrowRight size={16} />
                                    </Link>
                                </div>
                            )}

                            {/* Option to skip remaining questions if active question is present */}
                            {derived.showActiveQuestion && (
                                <div className="flex justify-end pt-4">
                                    <Link
                                        href={`/diagnosis/${resolvedParams.id}/troubleshooting`}
                                        className="inline-flex items-center gap-2 rounded-xl border border-gray-200 bg-white px-6 py-3 text-sm font-semibold text-gray-700 transition hover:bg-gray-50"
                                    >
                                        Proceed to Troubleshooting Checks
                                        <ArrowRight size={16} />
                                    </Link>
                                </div>
                            )}
                        </div>

                        <div>
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
            </div>
        </div>
    );
}
