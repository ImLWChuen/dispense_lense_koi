import PageContainer from "@/components/layout/PageContainer";
import CaseDetails from "@/components/cases/CaseDetails";
import SimilarCases from "@/components/cases/SimilarCases";

import { use } from "react";

export default function CaseDetailPage({ params }: { params: Promise<{ id: string }> }) {
    const resolvedParams = use(params);

    return (
        <PageContainer>
            <div>
                <p className="text-sm font-medium text-[#6d5dfc]">
                    Case management
                </p>

                <h1 className="mt-1 text-3xl font-bold tracking-tight text-gray-900">
                    Case Detail
                </h1>

                <p className="mt-2 text-sm text-gray-500">
                    Full lifecycle view of this diagnostic case.
                </p>
            </div>

            <div className="mt-8 grid grid-cols-1 gap-8 xl:grid-cols-3">
                <div className="xl:col-span-2">
                    <CaseDetails caseId={resolvedParams.id} />
                </div>

                <div>
                    <SimilarCases caseId={resolvedParams.id} />
                </div>
            </div>
        </PageContainer>
    );
}
