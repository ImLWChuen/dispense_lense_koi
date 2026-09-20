"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, ArrowLeft, Loader2 } from "lucide-react";

import CaseDetails from "@/components/cases/CaseDetails";
import SimilarCases from "@/components/cases/SimilarCases";
import PageContainer from "@/components/layout/PageContainer";
import { casesApi } from "@/lib/api/cases";
import type { DurableCaseResponse } from "@/types/api";

export default function CaseDetailPage({ params }: { params: Promise<{ id: string }> }) {
    const { id } = use(params);
    const [caseData, setCaseData] = useState<DurableCaseResponse | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const loadCase = useCallback(async () => {
        setIsLoading(true);
        setError(null);

        try {
            setCaseData(await casesApi.getCase(id));
        } catch (err: unknown) {
            console.error("Failed to load case details:", err);
            setCaseData(null);
            setError(err instanceof Error ? err.message : "Failed to load case details.");
        } finally {
            setIsLoading(false);
        }
    }, [id]);

    useEffect(() => {
        void loadCase();
    }, [loadCase]);

    return (
        <PageContainer>
            <Link
                href="/cases"
                className="inline-flex items-center gap-2 text-sm font-medium text-gray-500 transition hover:text-gray-900"
            >
                <ArrowLeft size={16} />
                Back to Cases
            </Link>

            <div className="mt-6">
                <p className="text-sm font-medium text-[#6d5dfc]">Case management</p>
                <h1 className="mt-1 text-3xl font-bold tracking-tight text-gray-900">Case Detail</h1>
                <p className="mt-2 text-sm text-gray-500">
                    Full lifecycle view of this diagnostic case.
                </p>
            </div>

            {isLoading ? (
                <div className="flex flex-col items-center justify-center py-24 text-gray-500">
                    <Loader2 className="mb-3 h-8 w-8 animate-spin text-[#6d5dfc]" />
                    <p className="text-sm font-medium">Loading case details...</p>
                </div>
            ) : error || !caseData ? (
                <div className="mt-8 rounded-2xl border border-rose-200 bg-white p-8 text-center shadow-sm">
                    <AlertCircle className="mx-auto mb-3 h-10 w-10 text-rose-500" />
                    <h2 className="text-base font-bold text-gray-900">Case Unavailable</h2>
                    <p className="mb-4 mt-1 text-sm text-gray-600">
                        {error || "The requested case could not be found."}
                    </p>
                    <button
                        type="button"
                        onClick={() => void loadCase()}
                        className="rounded-xl bg-[#6d5dfc] px-4 py-2 text-xs font-semibold text-white transition hover:bg-[#5848e8]"
                    >
                        Try Again
                    </button>
                </div>
            ) : (
                <div className="mt-8 grid grid-cols-1 gap-8 xl:grid-cols-3">
                    <div className="xl:col-span-2">
                        <CaseDetails caseData={caseData} />
                    </div>
                    <div>
                        <SimilarCases caseId={id} />
                    </div>
                </div>
            )}
        </PageContainer>
    );
}
