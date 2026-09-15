import Link from "next/link";
import { Plus } from "lucide-react";

import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";
import PageContainer from "@/components/layout/PageContainer";
import CaseFilters from "@/components/cases/CaseFilters";
import CaseTable from "@/components/cases/CaseTable";

const mockCases = [
    {
        id: "DSP-2026-0184",
        caseNumber: "DSP-2026-0184",
        defect: "Stringing",
        equipment: "Dispensing Line A",
        cause: "Material viscosity",
        status: "Resolved" as const,
        confidence: 94,
        time: "12 min ago",
        engineer: "Sarah M.",
    },
    {
        id: "DSP-2026-0183",
        caseNumber: "DSP-2026-0183",
        defect: "Under-dispensing",
        equipment: "Dispensing Line B",
        cause: "Pressure instability",
        status: "In Progress" as const,
        confidence: 87,
        time: "28 min ago",
        engineer: "James K.",
    },
    {
        id: "DSP-2026-0182",
        caseNumber: "DSP-2026-0182",
        defect: "Inconsistent bead",
        equipment: "Dispensing Line A",
        cause: "Nozzle obstruction",
        status: "Needs Review" as const,
        confidence: 76,
        time: "1 hr ago",
        engineer: "Sarah M.",
    },
    {
        id: "DSP-2026-0181",
        caseNumber: "DSP-2026-0181",
        defect: "Excess material",
        equipment: "Dispensing Line C",
        cause: "Flow rate setting",
        status: "Resolved" as const,
        confidence: 91,
        time: "2 hrs ago",
        engineer: "Li W.",
    },
    {
        id: "DSP-2026-0180",
        caseNumber: "DSP-2026-0180",
        defect: "Missing dots",
        equipment: "Dispensing Line D",
        cause: "Valve issue",
        status: "Resolved" as const,
        confidence: 88,
        time: "3 hrs ago",
        engineer: "James K.",
    },
    {
        id: "DSP-2026-0179",
        caseNumber: "DSP-2026-0179",
        defect: "Bubbles",
        equipment: "Dispensing Line B",
        cause: "Air supply issue",
        status: "In Progress" as const,
        confidence: 65,
        time: "5 hrs ago",
        engineer: "Sarah M.",
    },
    {
        id: "DSP-2026-0178",
        caseNumber: "DSP-2026-0178",
        defect: "Spreading",
        equipment: "Dispensing Line A",
        cause: "Temperature issue",
        status: "Resolved" as const,
        confidence: 82,
        time: "8 hrs ago",
        engineer: "Li W.",
    },
    {
        id: "DSP-2026-0177",
        caseNumber: "DSP-2026-0177",
        defect: "Under-dispensing",
        equipment: "Dispensing Line C",
        cause: "Nozzle restriction",
        status: "Resolved" as const,
        confidence: 95,
        time: "1 day ago",
        engineer: "James K.",
    },
];

export default function CasesPage() {
    return (
        <div className="min-h-screen">
            <Sidebar />

            <div className="ml-64">
                <Header />

                <PageContainer>
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-sm font-medium text-[#6d5dfc]">
                                Case management
                            </p>

                            <h1 className="mt-1 text-3xl font-bold tracking-tight text-gray-900">
                                Cases
                            </h1>

                            <p className="mt-2 text-sm text-gray-500">
                                Browse and manage all diagnostic cases across
                                your dispensing lines.
                            </p>
                        </div>

                        <Link
                            href="/diagnosis/new"
                            className="inline-flex items-center gap-2 rounded-xl bg-[#6d5dfc] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#5848e8]"
                        >
                            <Plus size={16} />
                            New Diagnosis
                        </Link>
                    </div>

                    <div className="mt-8 space-y-4">
                        <CaseFilters />
                        <CaseTable cases={mockCases} />
                    </div>
                </PageContainer>
            </div>
        </div>
    );
}
