import Link from "next/link";

import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";
import PageContainer from "@/components/layout/PageContainer";
import EngineerVerification from "@/components/diagnosis/EngineerVerification";
import DiagnosisSummary from "@/components/diagnosis/DiagnosisSummary";

export default function VerificationPage() {
    return (
        <div className="min-h-screen">
            <Sidebar />

            <div className="ml-64">
                <Header />

                <PageContainer>
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-sm font-medium text-[#6d5dfc]">
                                Diagnostic workflow · DSP-2026-0185
                            </p>

                            <h1 className="mt-1 text-3xl font-bold tracking-tight text-gray-900">
                                Engineer Verification
                            </h1>

                            <p className="mt-2 text-sm text-gray-500">
                                Review the diagnostic conclusion and provide
                                your engineering verification.
                            </p>
                        </div>

                        <Link
                            href="/diagnosis/DSP-2026-0185"
                            className="text-sm font-medium text-[#5848e8] hover:text-[#6d5dfc]"
                        >
                            ← Back to Diagnosis
                        </Link>
                    </div>

                    <div className="mt-8 grid grid-cols-1 gap-8 xl:grid-cols-3">
                        <div className="xl:col-span-2">
                            <EngineerVerification />
                        </div>

                        <div>
                            <DiagnosisSummary status="Pending Verification" />
                        </div>
                    </div>
                </PageContainer>
            </div>
        </div>
    );
}
