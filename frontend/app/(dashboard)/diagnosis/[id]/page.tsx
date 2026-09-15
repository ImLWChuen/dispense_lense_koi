import Link from "next/link";
import {
    ArrowRight,
    MessageSquare,
    ClipboardCheck,
    UserCheck,
    BarChart3,
} from "lucide-react";

import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";
import PageContainer from "@/components/layout/PageContainer";
import DiagnosisSummary from "@/components/diagnosis/DiagnosisSummary";
import CauseRanking from "@/components/diagnosis/CauseRanking";
import EvidencePanel from "@/components/diagnosis/EvidencePanel";

const mockEvidence = [
    {
        observation: "Deposit Size",
        value: "undersized",
        relation: "SUPPORTS" as const,
        strength: "STRONG" as const,
        explanation:
            "A restricted nozzle directly reduces the amount of material that can pass through.",
    },
    {
        observation: "Frequency Pattern",
        value: "intermittent",
        relation: "SUPPORTS" as const,
        strength: "MODERATE" as const,
        explanation:
            "Intermittent occurrence suggests partial blockage that varies with flow conditions.",
    },
    {
        observation: "Location Pattern",
        value: "specific_nozzle",
        relation: "SUPPORTS" as const,
        strength: "STRONG" as const,
        explanation:
            "Issue isolated to a specific nozzle strongly indicates a localized restriction.",
    },
    {
        observation: "Visual Appearance",
        value: "thin_deposit",
        relation: "SUPPORTS" as const,
        strength: "MODERATE" as const,
        explanation:
            "Thin, flat deposits are consistent with reduced material flow through a restricted orifice.",
    },
    {
        observation: "Purge Response",
        value: "improves_temporarily",
        relation: "CONTRADICTS" as const,
        strength: "WEAK" as const,
        explanation:
            "Temporary improvement after purge may indicate trapped air rather than permanent restriction.",
    },
];

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

export default function DiagnosisDetailPage() {
    return (
        <div className="min-h-screen">
            <Sidebar />

            <div className="ml-64">
                <Header />

                <PageContainer>
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-sm font-medium text-[#6d5dfc]">
                                Diagnostic workflow
                            </p>

                            <h1 className="mt-1 text-3xl font-bold tracking-tight text-gray-900">
                                Diagnosis Detail
                            </h1>

                            <p className="mt-2 text-sm text-gray-500">
                                Review the diagnostic assessment and continue
                                the troubleshooting workflow.
                            </p>
                        </div>

                        <Link
                            href="/cases"
                            className="text-sm font-medium text-[#5848e8] hover:text-[#6d5dfc]"
                        >
                            ← Back to Cases
                        </Link>
                    </div>

                    <div className="mt-8 grid grid-cols-1 gap-8 xl:grid-cols-3">
                        {/* Left: Summary + Evidence */}
                        <div className="space-y-6 xl:col-span-2">
                            <CauseRanking />
                            <EvidencePanel
                                evidence={mockEvidence}
                                causeLabel="Nozzle Restriction"
                            />
                        </div>

                        {/* Right: Summary + Workflow */}
                        <div className="space-y-6">
                            <DiagnosisSummary />

                            {/* Workflow Actions */}
                            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                                <h2 className="text-base font-semibold text-gray-900">
                                    Next Steps
                                </h2>

                                <p className="mt-1 text-xs text-gray-500">
                                    Continue the diagnostic workflow
                                </p>

                                <div className="mt-5 space-y-2">
                                    {workflowSteps.map((step) => {
                                        const Icon = step.icon;

                                        return (
                                            <Link
                                                key={step.href}
                                                href={`/diagnosis/DSP-2026-0185/${step.href}`}
                                                className="group flex items-center gap-3 rounded-xl border border-gray-100 p-3 transition hover:border-[#6d5dfc]/30 hover:bg-[#faf9ff]"
                                            >
                                                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gray-100 text-gray-500 transition group-hover:bg-[#eeebff] group-hover:text-[#6d5dfc]">
                                                    <Icon size={17} />
                                                </div>

                                                <div className="min-w-0 flex-1">
                                                    <p className="text-sm font-medium text-gray-800 group-hover:text-[#5848e8]">
                                                        {step.label}
                                                    </p>

                                                    <p className="text-[10px] text-gray-500">
                                                        {step.description}
                                                    </p>
                                                </div>

                                                <ArrowRight
                                                    size={14}
                                                    className="shrink-0 text-gray-300 group-hover:text-[#6d5dfc]"
                                                />
                                            </Link>
                                        );
                                    })}
                                </div>
                            </div>
                        </div>
                    </div>
                </PageContainer>
            </div>
        </div>
    );
}
