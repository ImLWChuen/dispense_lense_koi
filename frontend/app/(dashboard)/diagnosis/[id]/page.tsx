"use client";

import { useEffect, useState, use } from "react";
import Link from "next/link";
import {
    ArrowRight,
    MessageSquare,
    ClipboardCheck,
    UserCheck,
    BarChart3,
    AlertTriangle,
} from "lucide-react";

import PageContainer from "@/components/layout/PageContainer";
import DiagnosticStepper from "@/components/diagnosis/DiagnosticStepper";
import DiagnosisSummary from "@/components/diagnosis/DiagnosisSummary";
import CauseRanking from "@/components/diagnosis/CauseRanking";
import EvidencePanel from "@/components/diagnosis/EvidencePanel";
import SimilarCases from "@/components/cases/SimilarCases";
import { casesApi } from "@/lib/api/cases";
import { DurableCaseResponse } from "@/types/api";

const workflowSteps = [
    {
        label: "Diagnostic Questions",
        href: "questions",
        icon: MessageSquare,
        description: "Answer targeted questions to refine diagnosis",
    },
    {
        label: "Troubleshooting Checks",
        href: "troubleshooting",
        icon: ClipboardCheck,
        description: "Perform physical checks and record findings",
    },
    {
        label: "Engineer Verification",
        href: "verification",
        icon: UserCheck,
        description: "Confirm cause and verify resolution",
    },
    {
        label: "Analysis Detail",
        href: "analysis",
        icon: BarChart3,
        description: "View scoring breakdown and revision history",
    },
];

export default function DiagnosisDetailPage({ params }: { params: Promise<{ id: string }> }) {
    const resolvedParams = use(params);
    const [caseData, setCaseData] = useState<DurableCaseResponse | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchCase = async () => {
            try {
                setIsLoading(true);
                const data = await casesApi.getCase(resolvedParams.id);
                setCaseData(data);
            } catch (err: any) {
                if (err?.status === 404) {
                    console.warn(`Case '${resolvedParams.id}' not found in database.`);
                    setError(`Case '${resolvedParams.id}' was not found in the database. It may have been removed or archived.`);
                } else {
                    console.error("Failed to fetch case", err);
                    setError(err.message || "Failed to load case data.");
                }
            } finally {
                setIsLoading(false);
            }
        };
        fetchCase();
    }, [resolvedParams.id]);

    if (isLoading) {
        return (
            <PageContainer>
                <div className="flex h-64 items-center justify-center">
                    <p className="text-gray-500">Loading case details...</p>
                </div>
            </PageContainer>
        );
    }

    if (error || !caseData) {
        return (
            <PageContainer>
                <div className="mx-auto max-w-lg py-16 text-center">
                    <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-amber-100 text-amber-600 shadow-sm mb-4">
                        <AlertTriangle size={28} />
                    </div>
                    <h2 className="text-xl font-bold text-gray-900 tracking-tight">
                        Diagnostic Case Not Found
                    </h2>
                    <p className="mt-2 text-sm text-gray-600 leading-relaxed">
                        {error || `Case '${resolvedParams.id}' was not found.`}
                    </p>
                    <div className="mt-6 flex items-center justify-center gap-3">
                        <Link
                            href="/cases"
                            className="rounded-xl bg-[#6d5dfc] px-4 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-[#5848e8] transition"
                        >
                            Browse All Cases
                        </Link>
                        <Link
                            href="/diagnosis/new"
                            className="rounded-xl border border-gray-200 bg-white px-4 py-2.5 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 transition"
                        >
                            New Diagnosis
                        </Link>
                    </div>
                </div>
            </PageContainer>
        );
    }

    const diagnosis = caseData.diagnosis || caseData.initial_diagnosis;
    const topCause = diagnosis?.ranked_causes?.[0];
    
    // Construct evidence for the top cause
    const evidenceList: any[] = [];
    if (topCause) {
        const addEvidence = (list: any[], relation: string) => {
            if (!list) return;
            list.forEach(item => {
                const obs = caseData.observations.find(o => o.observation_id === item.observation_id || o.id === item.observation_id);
                evidenceList.push({
                    observation: obs ? obs.observation_type : item.observation_id,
                    value: obs ? obs.value : "unknown",
                    relation,
                    strength: item.strength || "MODERATE",
                    explanation: item.explanation || "No explanation provided.",
                });
            });
        };
        addEvidence(topCause.supporting_evidence, "SUPPORTS");
        addEvidence(topCause.contradicting_evidence, "CONTRADICTS");
        addEvidence(topCause.neutral_evidence, "NEUTRAL");
    }

    return (
        <PageContainer>
            <DiagnosticStepper
                caseId={resolvedParams.id}
                activeStep="overview"
                caseData={caseData}
            />

            <div className="flex items-center justify-between">
                <div>
                    <p className="text-sm font-medium text-[#6d5dfc] dark:text-[#a59bff]">
                        Diagnostic workflow
                    </p>

                    <h1 className="mt-1 text-3xl font-bold tracking-tight text-gray-900 dark:text-white">
                        Diagnosis Detail
                    </h1>

                    <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
                        Review the diagnostic assessment and continue
                        the troubleshooting workflow.
                    </p>
                </div>

                <Link
                    href="/cases"
                    className="text-sm font-medium text-[#5848e8] dark:text-[#a59bff] hover:text-[#6d5dfc] dark:hover:text-white transition"
                >
                    ← Back to Cases
                </Link>
            </div>

            <div className="mt-8 grid grid-cols-1 gap-8 xl:grid-cols-3">
                {/* Left: Summary + Evidence */}
                <div className="space-y-6 xl:col-span-2">
                    <CauseRanking causes={diagnosis?.ranked_causes} revision={diagnosis?.analysis_revision?.revision_number || 1} />
                    
                    {evidenceList.length > 0 && topCause && (
                        <EvidencePanel
                            evidence={evidenceList}
                            causeLabel={topCause.cause_name}
                        />
                    )}
                </div>

                {/* Right: Summary + Workflow */}
                <div className="space-y-6">
                    <DiagnosisSummary caseData={caseData} />

                    {/* Workflow Actions */}
                    <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-6 shadow-sm">
                        <h2 className="text-base font-semibold text-gray-900 dark:text-white">
                            Next Steps
                        </h2>

                        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                            Continue the diagnostic workflow
                        </p>

                        <div className="mt-5 space-y-2">
                            {workflowSteps.map((step) => {
                                const Icon = step.icon;

                                return (
                                    <Link
                                        key={step.href}
                                        href={`/diagnosis/${caseData.case_id}/${step.href}`}
                                        className="group flex items-center gap-3 rounded-xl border border-gray-100 dark:border-gray-800 p-3 transition hover:border-[#6d5dfc]/30 hover:bg-[#faf9ff] dark:hover:bg-gray-800/60"
                                    >
                                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 transition group-hover:bg-[#eeebff] dark:group-hover:bg-[#5848e8]/25 group-hover:text-[#6d5dfc] dark:group-hover:text-[#a59bff]">
                                            <Icon size={17} />
                                        </div>

                                        <div className="min-w-0 flex-1">
                                            <p className="text-sm font-medium text-gray-800 dark:text-gray-200 group-hover:text-[#5848e8] dark:group-hover:text-[#a59bff]">
                                                {step.label}
                                            </p>

                                            <p className="text-[10px] text-gray-500 dark:text-gray-400">
                                                {step.description}
                                            </p>
                                        </div>

                                        <ArrowRight
                                            size={14}
                                            className="shrink-0 text-gray-300 dark:text-gray-600 group-hover:text-[#6d5dfc] dark:group-hover:text-[#a59bff]"
                                        />
                                    </Link>
                                );
                            })}
                        </div>
                    </div>

                            {/* Similar Historical Case Benchmarks */}
                            <SimilarCases caseId={resolvedParams.id} />
                        </div>
                    </div>
                </PageContainer>
    );
}
