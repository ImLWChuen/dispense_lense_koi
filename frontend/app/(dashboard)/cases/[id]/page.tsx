"use client";

import { use, useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { ArrowLeft, Loader2, AlertCircle } from "lucide-react";
import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";
import PageContainer from "@/components/layout/PageContainer";
import CaseDetails from "@/components/cases/CaseDetails";
import { casesApi } from "@/lib/api/cases";
import type { DurableCaseResponse } from "@/types/api";

export default function CaseDetailPage({ params }: { params: Promise<{ id: string }> }) {
    const resolvedParams = use(params);
    const { id } = resolvedParams;

    const [caseData, setCaseData] = useState<DurableCaseResponse | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const reloadCase = useCallback(() => {
        if (!id) return;
        setIsLoading(true);
        setError(null);
        casesApi
            .getCase(id)
            .then((data) => {
                setCaseData(data);
                setError(null);
            })
            .catch((err: unknown) => {
                console.error("Failed to load case details:", err);
                setError(err instanceof Error ? err.message : "Failed to load case details.");
            })
            .finally(() => {
                setIsLoading(false);
            });
    }, [id]);

    useEffect(() => {
        if (!id) return;
        let isCurrent = true;

        casesApi
            .getCase(id)
            .then((data) => {
                if (isCurrent) {
                    setCaseData(data);
                    setError(null);
                    setIsLoading(false);
                }
            })
            .catch((err: unknown) => {
                if (isCurrent) {
                    console.error("Failed to load case details:", err);
                    setError(err instanceof Error ? err.message : "Failed to load case details.");
                    setIsLoading(false);
                }
            });

        return () => {
            isCurrent = false;
        };
    }, [id]);

    return (
        <div className="min-h-screen bg-[#f8fafc]">
            <Sidebar />

            <div className="ml-64">
                <Header />

                <PageContainer>
                    {/* Back Link */}
                    <div className="mb-6">
                        <Link
                            href="/cases"
                            className="inline-flex items-center gap-2 text-sm font-medium text-gray-500 hover:text-gray-900 transition"
                        >
                            <ArrowLeft size={16} />
                            Back to Cases
                        </Link>
                    </div>

                    {/* Mutually exclusive view states */}
                    {isLoading ? (
                        <div className="flex flex-col items-center justify-center py-24 text-gray-500">
                            <Loader2 className="h-8 w-8 animate-spin text-[#6d5dfc] mb-3" />
                            <p className="text-sm font-medium">Loading case details...</p>
                        </div>
                    ) : error || !caseData ? (
                        <div className="rounded-2xl border border-rose-200 bg-white p-8 text-center shadow-sm">
                            <AlertCircle className="h-10 w-10 text-rose-500 mx-auto mb-3" />
                            <h2 className="text-base font-bold text-gray-900">Case Unavailable</h2>
                            <p className="mt-1 text-sm text-gray-600 mb-4">
                                {error || "The requested case could not be found."}
                            </p>
                            <button
                                onClick={reloadCase}
                                className="rounded-xl bg-[#6d5dfc] px-4 py-2 text-xs font-semibold text-white hover:bg-[#5848e8] transition"
                            >
                                Try Again
                            </button>
                        </div>
                    ) : (
                        <div className="mt-2">
                            <CaseDetails caseData={caseData} />
                        </div>
                    )}
                </PageContainer>
            </div>
        </div>
    );
}
