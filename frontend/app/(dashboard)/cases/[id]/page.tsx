import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";
import PageContainer from "@/components/layout/PageContainer";
import CaseDetails from "@/components/cases/CaseDetails";
import SimilarCases from "@/components/cases/SimilarCases";

export default function CaseDetailPage() {
    return (
        <div className="min-h-screen">
            <Sidebar />

            <div className="ml-64">
                <Header />

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
                            <CaseDetails />
                        </div>

                        <div>
                            <SimilarCases />
                        </div>
                    </div>
                </PageContainer>
            </div>
        </div>
    );
}
