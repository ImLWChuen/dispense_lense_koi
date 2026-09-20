"use client";

import { useState, useEffect, useCallback, use } from "react";
import Link from "next/link";
import { CheckCircle2, ArrowRight } from "lucide-react";

import PageContainer from "@/components/layout/PageContainer";
import DiagnosticStepper from "@/components/diagnosis/DiagnosticStepper";
import TroubleshootingChecklist from "@/components/diagnosis/TroubleshootingChecklist";
import QuestionProgress from "@/components/diagnosis/QuestionProgress";
import { casesApi } from "@/lib/api/cases";
import { DurableCaseResponse } from "@/types/api";

export default function TroubleshootingPage({ params }: { params: Promise<{ id: string }> }) {
    const resolvedParams = use(params);
    const [caseData, setCaseData] = useState<DurableCaseResponse | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);
    


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

    const handleCheckSubmit = async (checkId: string, status: string, findingDetails: string, outcome: string) => {
        if (!caseData?.diagnosis?.analysis_revision) return;
        
        setIsSubmitting(true);
        try {
            await casesApi.submitCheckResult(
                caseData.case_id,
                checkId,
                status,
                outcome, // API uses finding for "NORMAL", "CONFIRMED", etc.
                caseData.diagnosis.analysis_revision.revision_number,
                undefined, // optional outcome text
                findingDetails
            );
            
            // Refresh to get the next check or transition to verification
            await fetchCase();
        } catch (err: unknown) {
            console.error("Failed to submit check result", err);
            const message = err instanceof Error ? err.message : "Failed to submit check result.";
            setError(message);
        } finally {
            setIsSubmitting(false);
        }
    };

    if (isLoading && !caseData) {
        return (
            <PageContainer>
                <div className="flex h-64 items-center justify-center">
                    <p className="text-gray-500">Loading troubleshooting checks...</p>
                </div>
            </PageContainer>
        );
    }

    const diagnosis = caseData?.diagnosis || caseData?.initial_diagnosis;
    const nextCheck = diagnosis?.next_check;
    const isDone = !nextCheck && !isLoading;

    const checks = caseData?.previous_check_results?.map(c => ({
        check_id: c.check_id,
        name: c.name || `Check ${c.check_id}`,
        description: c.description || `Finding: ${c.finding}`,
        procedure: c.procedure || "Historical check record.",
        effort_level: c.effort_level || "low",
        target_causes: c.target_causes || [],
        status: (c.execution_status === "COMPLETED" ? "completed" : 
                 c.execution_status === "BLOCKED" ? "blocked" : 
                 c.execution_status === "SKIPPED" ? "skipped" : "pending")
    })) || [];
    
    if (nextCheck) {
        checks.push({
            check_id: nextCheck.check_id,
            name: nextCheck.name,
            description: nextCheck.description || "Recommended troubleshooting check.",
            procedure: nextCheck.procedure || "Inspect according to standard operating procedure.",
            effort_level: nextCheck.effort_level || "medium",
            target_causes: nextCheck.target_causes || [],
            status: nextCheck.status || "pending",
        });
    }

    // Deduplicate checks by check_id (keep latest)
    const uniqueChecks = Array.from(new Map(checks.map(c => [c.check_id, c])).values());

    // Map checks to the UI component format
    const checklistActions = uniqueChecks.map(c => ({
        id: c.check_id,
        name: c.name,
        description: c.description,
        procedure: c.procedure,
        effortLevel: (c.effort_level === "low" || c.effort_level === "high" ? c.effort_level : "medium") as "low" | "medium" | "high",
        applicableCauses: c.target_causes || [],
        status: (c.status || "pending") as "pending" | "completed" | "blocked" | "skipped",
    }));

    return (
        <PageContainer>
            <DiagnosticStepper
                caseId={resolvedParams.id}
                activeStep="troubleshooting"
                caseData={caseData}
            />

            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-gray-900">
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
                    ← Back to Overview
                </Link>
            </div>

                    {error && (
                        <div className="mt-4 rounded-xl bg-red-50 p-4 text-sm text-red-700">
                            {error}
                        </div>
                    )}

                    <div className="mt-8 grid grid-cols-1 gap-8 xl:grid-cols-3">
                        <div className="xl:col-span-2 space-y-4">
                            {checklistActions.length > 0 && (
                                <TroubleshootingChecklist 
                                    actions={checklistActions} 
                                    onSubmit={handleCheckSubmit}
                                    isSubmitting={isSubmitting}
                                />
                            )}
                            
                            {isDone && (
                                <div className="mt-6 rounded-2xl border border-emerald-100 bg-emerald-50 p-6 text-center">
                                    <CheckCircle2 className="mx-auto mb-3 h-10 w-10 text-emerald-500" />
                                    <h3 className="text-lg font-semibold text-emerald-800">Checks Complete</h3>
                                    <p className="mt-2 text-sm text-emerald-700">
                                        The diagnostic engine has gathered sufficient physical evidence.
                                        You can now proceed to cause verification.
                                    </p>
                                    <Link
                                        href={`/diagnosis/${resolvedParams.id}/verification`}
                                        className="mt-5 inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-6 py-3 text-sm font-semibold text-white transition hover:bg-emerald-700"
                                    >
                                        Continue to Verification
                                        <ArrowRight size={16} />
                                    </Link>
                                </div>
                            )}

                            {!isDone && checklistActions.length > 0 && (
                                <div className="mt-6 flex justify-end">
                                    <Link
                                        href={`/diagnosis/${resolvedParams.id}/verification`}
                                        className="inline-flex items-center gap-2 rounded-xl bg-[#6d5dfc] px-6 py-3 text-sm font-semibold text-white transition hover:bg-[#5848e8]"
                                    >
                                        Skip to Verification →
                                    </Link>
                                </div>
                            )}
                        </div>

                        <div className="space-y-6">
                            <QuestionProgress current={checks.length - (nextCheck ? 1 : 0)} total={checks.length} />

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
    );
}
