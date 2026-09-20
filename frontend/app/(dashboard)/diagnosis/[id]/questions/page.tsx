"use client";

import { useState, useEffect, useCallback, use } from "react";
import Link from "next/link";
import { ArrowRight, CheckCircle2, Keyboard, RefreshCw } from "lucide-react";

import PageContainer from "@/components/layout/PageContainer";
import DiagnosticStepper from "@/components/diagnosis/DiagnosticStepper";
import QuestionProgress from "@/components/diagnosis/QuestionProgress";
import DiagnosticQuestion from "@/components/diagnosis/DiagnosticQuestion";
import { casesApi } from "@/lib/api/cases";
import { DurableCaseResponse } from "@/types/api";
import {
    deriveQuestionsView,
    coordinateWorkflowMutation,
    retryWorkflowRefresh,
    RefreshWarningKind,
} from "@/lib/diagnostic-workflow-state";

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
    const [refreshWarning, setRefreshWarning] = useState<string | null>(null);
    const [refreshWarningKind, setRefreshWarningKind] = useState<RefreshWarningKind | null>(null);
    const [isRefreshRequired, setIsRefreshRequired] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);

    const history = caseData?.previous_answers || [];

    const fetchCase = useCallback(async () => {
        setIsLoading(true);
        try {
            const data = await casesApi.getCase(resolvedParams.id);
            setCaseData(data);
            setError(null);
            setRefreshWarning(null);
            setRefreshWarningKind(null);
            setIsRefreshRequired(false);
        } catch (err: unknown) {
            console.error("Failed to fetch case", err);
            const message = err instanceof Error ? err.message : "Failed to load case data.";
            setError(message);
        } finally {
            setIsLoading(false);
        }
    }, [resolvedParams.id]);

    const handleRetryRefresh = async () => {
        if (!caseData) return;
        setIsSubmitting(true);
        try {
            await retryWorkflowRefresh({
                currentCase: caseData,
                previousWarningKind: refreshWarningKind,
                performRefresh: () => casesApi.getCase(caseData.case_id),
                onStateChange: (state) => {
                    setCaseData(state.caseData);
                    setError(state.mutationError);
                    setRefreshWarning(state.refreshWarning);
                    setRefreshWarningKind(state.refreshWarningKind || null);
                    setIsRefreshRequired(state.isRefreshRequired);
                },
            });
        } finally {
            setIsSubmitting(false);
        }
    };

    useEffect(() => {
        let isCurrent = true;
        casesApi
            .getCase(resolvedParams.id)
            .then((data) => {
                if (isCurrent) {
                    setCaseData(data);
                    setError(null);
                    setRefreshWarning(null);
                    setRefreshWarningKind(null);
                    setIsRefreshRequired(false);
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
            await coordinateWorkflowMutation({
                currentCase: caseData,
                isRefreshRequired,
                performMutation: () =>
                    casesApi.submitAnswer(
                        caseData.case_id,
                        questionId,
                        value,
                        caseData.diagnosis!.analysis_revision!.revision_number
                    ),
                performRefresh: () => casesApi.getCase(caseData.case_id),
                onStateChange: (state) => {
                    setCaseData(state.caseData);
                    setError(state.mutationError);
                    setRefreshWarning(state.refreshWarning);
                    setRefreshWarningKind(state.refreshWarningKind || null);
                    setIsRefreshRequired(state.isRefreshRequired);
                },
            });
        } catch (err: unknown) {
            console.error("Failed to submit answer", err);
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


    const derived = deriveQuestionsView({
        isLoading,
        error,
        caseData,
        hasNextQuestion: Boolean(nextQuestion),
    });


    // 1. Initial Loading
    if (derived.showInitialLoading) {
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

                    {/* Distinct Refresh Warning Banner (POST succeeded, but GET failed, OR both failed) */}
                    {refreshWarning && (
                        <div className="mt-4 flex items-center justify-between rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
                            <div>
                                <p className="font-semibold">
                                    {refreshWarningKind === "state_refresh_required"
                                        ? "State Refresh Required"
                                        : "Action Saved"}
                                </p>
                                <p className="mt-0.5">{refreshWarning}</p>
                                {refreshWarningKind === "state_refresh_required" && error && (
                                    <p className="mt-1 text-xs text-amber-700">Error: {error}</p>
                                )}
                            </div>
                            <button
                                onClick={handleRetryRefresh}
                                disabled={isSubmitting}
                                className="inline-flex items-center gap-1 rounded-lg border border-amber-300 bg-white px-3 py-1.5 text-xs font-semibold text-amber-800 hover:bg-amber-100 disabled:opacity-50"
                            >
                                <RefreshCw size={14} className={isSubmitting ? "animate-spin" : ""} />
                                Refresh Case
                            </button>
                        </div>
                    )}

                    {/* Stale / mutation error banner (POST failed, but GET succeeded) */}
                    {derived.showStaleBanner && !refreshWarning && (
                        <div className="mt-4 flex items-center justify-between rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
                            <div>
                                <p className="font-semibold">Update Failed</p>
                                <p className="mt-0.5">{error}. Persisted case data has been re-synchronized.</p>
                            </div>
                            <button
                                onClick={handleRetryRefresh}
                                disabled={isSubmitting}
                                className="inline-flex items-center gap-1 rounded-lg border border-amber-300 bg-white px-3 py-1.5 text-xs font-semibold text-amber-800 hover:bg-amber-100 disabled:opacity-50"
                            >
                                <RefreshCw size={14} className={isSubmitting ? "animate-spin" : ""} />
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
                                    isAnswered={false}
                                    disabled={isSubmitting || isRefreshRequired}
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
    );
}
