"use client";

import { useState, useEffect, useCallback, use } from "react";
import Link from "next/link";
import { CheckCircle2, ArrowRight, AlertCircle, RefreshCw } from "lucide-react";

import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";
import PageContainer from "@/components/layout/PageContainer";
import TroubleshootingChecklist, {
    TroubleshootingAction,
    TroubleshootingCheckSubmitParams,
} from "@/components/diagnosis/TroubleshootingChecklist";
import QuestionProgress from "@/components/diagnosis/QuestionProgress";
import { casesApi } from "@/lib/api/cases";
import { DurableCaseResponse } from "@/types/api";
import {
    deriveTroubleshootingView,
    buildCheckResultPayload,
} from "@/lib/diagnostic-workflow-state";

export default function TroubleshootingPage({ params }: { params: Promise<{ id: string }> }) {
    const resolvedParams = use(params);
    const [caseData, setCaseData] = useState<DurableCaseResponse | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);

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

    const handleCheckSubmit = async (params: TroubleshootingCheckSubmitParams) => {
        if (!caseData?.diagnosis?.analysis_revision) return;

        setIsSubmitting(true);
        try {
            const payload = buildCheckResultPayload({
                check_id: params.check_id,
                execution_status: params.execution_status,
                finding: params.finding,
                outcome: params.outcome,
                finding_details: params.finding_details,
                expected_revision: caseData.diagnosis.analysis_revision.revision_number,
            });

            await casesApi.submitCheckResult(caseData.case_id, payload);
            // R6: Fetch authoritative durable case after successful mutation
            const refreshed = await casesApi.getCase(caseData.case_id);
            setCaseData(refreshed);
            setError(null);
        } catch (err: unknown) {
            console.error("Failed to submit check result", err);
            const message = err instanceof Error ? err.message : "Failed to submit check result.";
            setError(message);
            // R1: Synchronize durable case without clearing mutation error
            try {
                const refreshed = await casesApi.getCase(caseData.case_id);
                setCaseData(refreshed);
            } catch (syncErr) {
                console.error("Failed to sync case state after mutation error", syncErr);
            }
            // Re-throw so child form knows submission failed and preserves inputs
            throw err;
        } finally {
            setIsSubmitting(false);
        }
    };

    const diagnosis = caseData?.diagnosis || caseData?.initial_diagnosis;
    const nextCheck = diagnosis?.next_check;

    const derived = deriveTroubleshootingView({
        isLoading,
        error,
        caseData,
        hasNextCheck: Boolean(nextCheck),
    });

    // 1. Initial Loading
    if (derived.showInitialLoading) {
        return (
            <div className="min-h-screen">
                <Sidebar />
                <div className="ml-64">
                    <Header />
                    <PageContainer>
                        <div className="flex h-64 items-center justify-center">
                            <p className="text-gray-500">Loading troubleshooting checks...</p>
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
                                    Troubleshooting Checks
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
                            <h3 className="text-lg font-semibold text-red-800">Failed to load troubleshooting checks</h3>
                            <p className="mt-2 text-sm text-red-700">
                                {error || "Unable to retrieve troubleshooting checks for this case."}
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

    // Prepare checklist actions: previous completed/recorded checks + active next check
    const historicalChecks: TroubleshootingAction[] =
        caseData?.previous_check_results?.map((c) => {
            const rawStatus = (c.execution_status || "").toUpperCase();
            const status: TroubleshootingAction["status"] =
                rawStatus === "COMPLETED"
                    ? "completed"
                    : rawStatus === "BLOCKED"
                    ? "blocked"
                    : rawStatus === "SKIPPED"
                    ? "skipped"
                    : rawStatus === "FAILED"
                    ? "failed"
                    : rawStatus === "UNKNOWN"
                    ? "unknown"
                    : rawStatus === "NOT_APPLICABLE"
                    ? "not_applicable"
                    : "inconclusive";

            return {
                id: c.check_id,
                name: c.name || `Check ${c.check_id}`,
                description: c.description || `Finding: ${c.finding}`,
                procedure: c.procedure || "Historical check record.",
                effortLevel: (c.effort_level === "low" || c.effort_level === "high" ? c.effort_level : "medium") as "low" | "medium" | "high",
                applicableCauses: c.target_causes || [],
                status,
                finding: c.finding,
                outcome: c.outcome || undefined,
                findingDetails: c.finding_details || undefined,
            };
        }) || [];

    const checklistActions: TroubleshootingAction[] = [...historicalChecks];

    if (nextCheck) {
        checklistActions.push({
            id: nextCheck.check_id,
            name: nextCheck.name,
            description: nextCheck.description || "Recommended troubleshooting check.",
            procedure: nextCheck.procedure || "Inspect according to standard operating procedure.",
            effortLevel: (nextCheck.effort_level === "low" || nextCheck.effort_level === "high" ? nextCheck.effort_level : "medium") as "low" | "medium" | "high",
            applicableCauses: nextCheck.target_causes || [],
            status: "pending",
            possibleOutcomes: nextCheck.possible_outcomes || [],
        });
    }

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
                                Troubleshooting Checks
                            </h1>

                            <p className="mt-2 text-sm text-gray-500">
                                Perform the recommended checks to gather physical evidence and validate the diagnosis.
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
                        <div className="xl:col-span-2 space-y-4">
                            {/* Truthful Neutral Completion: No further checks recommended */}
                            {derived.showNoNextCheck && (
                                <div className="rounded-2xl border border-gray-200 bg-white p-6 text-center shadow-sm">
                                    <CheckCircle2 className="mx-auto mb-3 h-10 w-10 text-[#6d5dfc]" />
                                    <h3 className="text-lg font-semibold text-gray-900">No Additional Checks Available</h3>
                                    <p className="mt-2 text-sm text-gray-600">
                                        No additional physical troubleshooting checks are currently recommended by the diagnostic engine.
                                        You may review previous recorded findings below or proceed to verification.
                                    </p>
                                    <Link
                                        href={`/diagnosis/${resolvedParams.id}/verification`}
                                        className="mt-5 inline-flex items-center gap-2 rounded-xl bg-[#6d5dfc] px-6 py-3 text-sm font-semibold text-white transition hover:bg-[#5848e8]"
                                    >
                                        Proceed to Verification
                                        <ArrowRight size={16} />
                                    </Link>
                                </div>
                            )}

                            {/* Checklist: renders active form when pending check exists, and historical findings */}
                            {checklistActions.length > 0 && (
                                <TroubleshootingChecklist
                                    actions={checklistActions}
                                    activeCheckId={nextCheck?.check_id}
                                    onSubmit={handleCheckSubmit}
                                    isSubmitting={isSubmitting}
                                />
                            )}

                            {/* Shortcut to verification when active checks remain */}
                            {derived.showActiveCheck && (
                                <div className="mt-6 flex justify-end">
                                    <Link
                                        href={`/diagnosis/${resolvedParams.id}/verification`}
                                        className="inline-flex items-center gap-2 rounded-xl border border-gray-200 bg-white px-6 py-3 text-sm font-semibold text-gray-700 transition hover:bg-gray-50"
                                    >
                                        Skip to Verification →
                                    </Link>
                                </div>
                            )}
                        </div>

                        <div className="space-y-6">
                            <QuestionProgress
                                current={historicalChecks.length}
                                total={historicalChecks.length + (nextCheck ? 1 : 0)}
                            />

                            <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
                                <p className="text-sm font-semibold text-gray-900">
                                    Check Priority
                                </p>

                                <p className="mt-1 text-xs text-gray-500">
                                    Checks are ordered by diagnostic value
                                </p>

                                <div className="mt-4 space-y-3">
                                    <div className="flex items-center justify-between">
                                        <span className="text-xs text-gray-600">
                                            Low effort
                                        </span>

                                        <span className="rounded-full bg-green-50 px-2 py-0.5 text-[10px] font-medium text-green-700">
                                            Start here
                                        </span>
                                    </div>

                                    <div className="flex items-center justify-between">
                                        <span className="text-xs text-gray-600">
                                            Medium effort
                                        </span>

                                        <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-700">
                                            If needed
                                        </span>
                                    </div>

                                    <div className="flex items-center justify-between">
                                        <span className="text-xs text-gray-600">
                                            High effort
                                        </span>

                                        <span className="rounded-full bg-red-50 px-2 py-0.5 text-[10px] font-medium text-red-700">
                                            Last resort
                                        </span>
                                    </div>
                                </div>
                            </div>

                            <div className="rounded-2xl border border-[#ded9ff] bg-[#faf9ff] p-5">
                                <p className="text-sm font-semibold text-gray-900">
                                    Tip
                                </p>

                                <p className="mt-2 text-xs leading-5 text-gray-600">
                                    Complete low-effort checks first. Each
                                    finding automatically updates the cause
                                    ranking. You may not need to perform all
                                    checks if a clear cause emerges early.
                                </p>
                            </div>
                        </div>
                    </div>
                </PageContainer>
            </div>
        </div>
    );
}
