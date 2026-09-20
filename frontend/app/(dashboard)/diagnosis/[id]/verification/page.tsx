"use client";

import { useState, useEffect, useCallback, use } from "react";
import Link from "next/link";
import { AlertCircle, RefreshCw } from "lucide-react";

import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";
import PageContainer from "@/components/layout/PageContainer";
import EngineerVerification from "@/components/diagnosis/EngineerVerification";
import DiagnosisSummary from "@/components/diagnosis/DiagnosisSummary";
import { casesApi } from "@/lib/api/cases";
import { DurableCaseResponse } from "@/types/api";

export default function VerificationPage({ params }: { params: Promise<{ id: string }> }) {
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

    const getCurrentRevision = (): number => {
        return (
            caseData?.current_revision ??
            caseData?.diagnosis?.analysis_revision?.revision_number ??
            1
        );
    };

    const handleConfirmCause = async (causeId: string, notes?: string) => {
        if (!caseData) return;
        setIsSubmitting(true);
        try {
            const revision = getCurrentRevision();
            await casesApi.submitCauseConfirmation(
                caseData.case_id,
                causeId,
                revision,
                "technician",
                notes
            );
            // R6: Fetch authoritative durable case after successful mutation
            const refreshed = await casesApi.getCase(caseData.case_id);
            setCaseData(refreshed);
            setError(null);
        } catch (err: unknown) {
            console.error("Failed to confirm cause", err);
            const message = err instanceof Error ? err.message : "Failed to confirm cause.";
            setError(message);
            // R1: Synchronize durable case without clearing mutation error
            try {
                const refreshed = await casesApi.getCase(caseData.case_id);
                setCaseData(refreshed);
            } catch (syncErr) {
                console.error("Failed to sync case state after mutation error", syncErr);
            }
            throw err;
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleSubmitRecoveryAction = async (recoveryDetails: string) => {
        if (!caseData) return;
        setIsSubmitting(true);
        try {
            const revision = getCurrentRevision();
            await casesApi.submitRecoveryAction(
                caseData.case_id,
                recoveryDetails,
                revision,
                "technician"
            );
            // R6: Fetch authoritative durable case after successful mutation
            const refreshed = await casesApi.getCase(caseData.case_id);
            setCaseData(refreshed);
            setError(null);
        } catch (err: unknown) {
            console.error("Failed to submit recovery action", err);
            const message = err instanceof Error ? err.message : "Failed to submit recovery action.";
            setError(message);
            // R1: Synchronize durable case without clearing mutation error
            try {
                const refreshed = await casesApi.getCase(caseData.case_id);
                setCaseData(refreshed);
            } catch (syncErr) {
                console.error("Failed to sync case state after mutation error", syncErr);
            }
            throw err;
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleSubmitRecoveryVerification = async (passed: boolean, details?: string) => {
        if (!caseData) return;
        setIsSubmitting(true);
        try {
            const revision = getCurrentRevision();
            await casesApi.verifyCase(
                caseData.case_id,
                passed,
                details || "",
                revision,
                "technician"
            );
            // R6: Fetch authoritative durable case after successful mutation
            const refreshed = await casesApi.getCase(caseData.case_id);
            setCaseData(refreshed);
            setError(null);
        } catch (err: unknown) {
            console.error("Failed to verify recovery", err);
            const message = err instanceof Error ? err.message : "Failed to verify recovery.";
            setError(message);
            // R1: Synchronize durable case without clearing mutation error
            try {
                const refreshed = await casesApi.getCase(caseData.case_id);
                setCaseData(refreshed);
            } catch (syncErr) {
                console.error("Failed to sync case state after mutation error", syncErr);
            }
            throw err;
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleSubmitRecurrence = async (details: string) => {
        if (!caseData) return;
        setIsSubmitting(true);
        try {
            const revision = getCurrentRevision();
            await casesApi.submitRecurrence(
                caseData.case_id,
                details,
                revision,
                "technician"
            );
            // R6: Fetch authoritative durable case after successful mutation
            const refreshed = await casesApi.getCase(caseData.case_id);
            setCaseData(refreshed);
            setError(null);
        } catch (err: unknown) {
            console.error("Failed to submit recurrence", err);
            const message = err instanceof Error ? err.message : "Failed to submit recurrence.";
            setError(message);
            // R1: Synchronize durable case without clearing mutation error
            try {
                const refreshed = await casesApi.getCase(caseData.case_id);
                setCaseData(refreshed);
            } catch (syncErr) {
                console.error("Failed to sync case state after mutation error", syncErr);
            }
            throw err;
        } finally {
            setIsSubmitting(false);
        }
    };

    // 1. Initial Loading
    if (isLoading && !caseData && !error) {
        return (
            <div className="min-h-screen">
                <Sidebar />
                <div className="ml-64">
                    <Header />
                    <PageContainer>
                        <div className="flex h-64 items-center justify-center">
                            <p className="text-gray-500">Loading case lifecycle data...</p>
                        </div>
                    </PageContainer>
                </div>
            </div>
        );
    }

    // 2. Dedicated Error (Initial request failure)
    if (!isLoading && error && !caseData) {
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
                                    Lifecycle Verification
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
                            <h3 className="text-lg font-semibold text-red-800">Failed to load case data</h3>
                            <p className="mt-2 text-sm text-red-700">
                                {error || "Unable to retrieve case lifecycle details."}
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

    // 3. Loaded state
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
                                Lifecycle Verification
                            </h1>

                            <p className="mt-2 text-sm text-gray-500">
                                Review candidate cause support, record recovery actions, and verify case lifecycle state.
                            </p>
                        </div>

                        <Link
                            href={`/diagnosis/${resolvedParams.id}`}
                            className="text-sm font-medium text-[#5848e8] hover:text-[#6d5dfc]"
                        >
                            ← Back to Diagnosis
                        </Link>
                    </div>

                    {/* Stale / Mutation Error Banner */}
                    {error && caseData && (
                        <div className="mt-4 flex items-center justify-between rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
                            <div>
                                <p className="font-semibold">Lifecycle Action Failed</p>
                                <p className="mt-0.5">{error}. Persisted case state has been re-synchronized.</p>
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
                        <div className="xl:col-span-2">
                            {caseData && (
                                <EngineerVerification
                                    caseData={caseData}
                                    onConfirmCause={handleConfirmCause}
                                    onSubmitRecoveryAction={handleSubmitRecoveryAction}
                                    onSubmitRecoveryVerification={handleSubmitRecoveryVerification}
                                    onSubmitRecurrence={handleSubmitRecurrence}
                                    isSubmitting={isSubmitting}
                                />
                            )}
                        </div>

                        <div>
                            {caseData && <DiagnosisSummary caseData={caseData} />}
                        </div>
                    </div>
                </PageContainer>
            </div>
        </div>
    );
}
