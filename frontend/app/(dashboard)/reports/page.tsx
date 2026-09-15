import Link from "next/link";
import {
    FileText,
    CheckCircle2,
    Clock3,
    Plus,
} from "lucide-react";

import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";
import PageContainer from "@/components/layout/PageContainer";

const mockReports = [
    {
        id: "RPT-2026-0184",
        caseRef: "DSP-2026-0184",
        title: "Nozzle Restriction — Line A",
        date: "Sep 15, 2026",
        type: "Diagnostic Report",
        status: "Complete",
    },
    {
        id: "RPT-2026-0181",
        caseRef: "DSP-2026-0181",
        title: "Flow Rate Setting — Line C",
        date: "Sep 14, 2026",
        type: "Diagnostic Report",
        status: "Complete",
    },
    {
        id: "RPT-2026-0180",
        caseRef: "DSP-2026-0180",
        title: "Valve Issue — Line D",
        date: "Sep 14, 2026",
        type: "Diagnostic Report",
        status: "Complete",
    },
    {
        id: "RPT-2026-0178",
        caseRef: "DSP-2026-0178",
        title: "Temperature Issue — Line A",
        date: "Sep 13, 2026",
        type: "Diagnostic Report",
        status: "Complete",
    },
    {
        id: "RPT-2026-0177",
        caseRef: "DSP-2026-0177",
        title: "Nozzle Restriction — Line C",
        date: "Sep 12, 2026",
        type: "Diagnostic Report",
        status: "Complete",
    },
    {
        id: "RPT-SUMMARY-09",
        caseRef: "—",
        title: "September Monthly Summary",
        date: "Sep 15, 2026",
        type: "Summary Report",
        status: "Draft",
    },
];

export default function ReportsPage() {
    return (
        <div className="min-h-screen">
            <Sidebar />

            <div className="ml-64">
                <Header />

                <PageContainer>
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-sm font-medium text-[#6d5dfc]">
                                Documentation
                            </p>

                            <h1 className="mt-1 text-3xl font-bold tracking-tight text-gray-900">
                                Reports
                            </h1>

                            <p className="mt-2 text-sm text-gray-500">
                                View and manage generated diagnostic reports.
                            </p>
                        </div>

                        <button className="inline-flex items-center gap-2 rounded-xl bg-[#6d5dfc] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#5848e8]">
                            <Plus size={16} />
                            Generate Report
                        </button>
                    </div>

                    <div className="mt-8 rounded-2xl border border-gray-200 bg-white shadow-sm">
                        <table className="w-full">
                            <thead>
                                <tr className="border-b border-gray-100 text-left">
                                    <th className="px-6 py-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                        Report ID
                                    </th>

                                    <th className="px-6 py-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                        Title
                                    </th>

                                    <th className="px-6 py-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                        Case Ref
                                    </th>

                                    <th className="px-6 py-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                        Type
                                    </th>

                                    <th className="px-6 py-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                        Date
                                    </th>

                                    <th className="px-6 py-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                        Status
                                    </th>
                                </tr>
                            </thead>

                            <tbody>
                                {mockReports.map((report) => (
                                    <tr
                                        key={report.id}
                                        className="border-b border-gray-50 transition last:border-0 hover:bg-gray-50/70"
                                    >
                                        <td className="px-6 py-4">
                                            <Link
                                                href={`/reports/${report.id}`}
                                                className="flex items-center gap-2 text-sm font-semibold text-gray-900 hover:text-[#5848e8]"
                                            >
                                                <FileText
                                                    size={14}
                                                    className="text-gray-400"
                                                />
                                                {report.id}
                                            </Link>
                                        </td>

                                        <td className="px-6 py-4 text-sm font-medium text-gray-800">
                                            {report.title}
                                        </td>

                                        <td className="px-6 py-4 text-sm text-gray-600">
                                            {report.caseRef}
                                        </td>

                                        <td className="px-6 py-4">
                                            <span className="rounded-md bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-600">
                                                {report.type}
                                            </span>
                                        </td>

                                        <td className="px-6 py-4 text-xs text-gray-500">
                                            {report.date}
                                        </td>

                                        <td className="px-6 py-4">
                                            <span
                                                className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${
                                                    report.status === "Complete"
                                                        ? "bg-green-50 text-green-700"
                                                        : "bg-amber-50 text-amber-700"
                                                }`}
                                            >
                                                {report.status === "Complete" ? (
                                                    <CheckCircle2 size={12} />
                                                ) : (
                                                    <Clock3 size={12} />
                                                )}
                                                {report.status}
                                            </span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </PageContainer>
            </div>
        </div>
    );
}
