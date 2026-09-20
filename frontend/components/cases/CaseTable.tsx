import Link from "next/link";
import {
    CheckCircle2,
    Clock3,
    AlertTriangle,
} from "lucide-react";

interface CaseRow {
    id: string;
    caseNumber: string;
    defect: string;
    equipment: string;
    cause: string;
    status: "Resolved" | "In Progress" | "Needs Review";
    evidenceSupport?: number | null;
    time: string;
    engineer: string;
}

const statusConfig = {
    Resolved: {
        icon: CheckCircle2,
        className: "bg-green-50 text-green-700",
    },
    "In Progress": {
        icon: Clock3,
        className: "bg-blue-50 text-blue-700",
    },
    "Needs Review": {
        icon: AlertTriangle,
        className: "bg-amber-50 text-amber-700",
    },
};

interface CaseTableProps {
    cases: CaseRow[];
}

export default function CaseTable({ cases }: CaseTableProps) {
    return (
        <div className="rounded-2xl border border-gray-200 bg-white shadow-sm">
            <div className="overflow-x-auto">
                <table className="w-full min-w-[1000px]">
                    <thead>
                        <tr className="border-b border-gray-100 text-left">
                            <th className="px-6 py-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                Case
                            </th>

                            <th className="px-6 py-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                Defect
                            </th>

                            <th className="px-6 py-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                Equipment
                            </th>

                            <th className="px-6 py-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                Identified Cause
                            </th>

                            <th className="px-6 py-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                Evidence Support
                            </th>

                            <th className="px-6 py-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                Status
                            </th>

                            <th className="px-6 py-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                Engineer
                            </th>

                            <th className="px-6 py-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                Updated
                            </th>
                        </tr>
                    </thead>

                    <tbody>
                        {cases.map((item) => {
                            const statusCfg = statusConfig[item.status] || statusConfig["In Progress"];
                            const Icon = statusCfg.icon;

                            return (
                                <tr
                                    key={item.id}
                                    className="border-b border-gray-50 transition last:border-0 hover:bg-gray-50/70"
                                >
                                    <td className="px-6 py-4">
                                        <Link
                                            href={`/diagnosis/${item.id}`}
                                            className="text-sm font-semibold text-gray-900 hover:text-[#5848e8]"
                                        >
                                            {item.caseNumber}
                                        </Link>
                                    </td>

                                    <td className="px-6 py-4">
                                        <p className="text-sm font-medium text-gray-800">
                                            {item.defect}
                                        </p>
                                    </td>

                                    <td className="px-6 py-4 text-sm text-gray-600">
                                        {item.equipment}
                                    </td>

                                    <td className="px-6 py-4 text-sm text-gray-600">
                                        {item.cause}
                                    </td>

                                    <td className="px-6 py-4">
                                        {item.evidenceSupport != null ? (
                                            <div className="flex items-center gap-3">
                                                <div className="h-1.5 w-20 overflow-hidden rounded-full bg-gray-100">
                                                    <div
                                                        className="h-full rounded-full bg-[#6d5dfc]"
                                                        style={{
                                                            width: `${Math.max(0, Math.min(100, item.evidenceSupport))}%`,
                                                        }}
                                                    />
                                                </div>

                                                <span className="text-xs font-semibold text-gray-700">
                                                    {item.evidenceSupport}/100
                                                </span>
                                            </div>
                                        ) : (
                                            <span className="text-xs text-gray-400">N/A</span>
                                        )}
                                    </td>

                                    <td className="px-6 py-4">
                                        <span
                                            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${statusCfg.className}`}
                                        >
                                            <Icon size={13} />
                                            {item.status}
                                        </span>
                                    </td>

                                    <td className="px-6 py-4 text-sm text-gray-600">
                                        {item.engineer}
                                    </td>

                                    <td className="px-6 py-4 text-xs text-gray-500">
                                        {item.time}
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>

            {/* Pagination */}
            <div className="flex items-center justify-between border-t border-gray-100 px-6 py-4">
                <p className="text-xs text-gray-500">
                    Showing {cases.length} of {cases.length} cases
                </p>

                <div className="flex gap-1">
                    <button className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-500 transition hover:bg-gray-50">
                        Previous
                    </button>

                    <button className="rounded-lg bg-[#6d5dfc] px-3 py-1.5 text-xs font-medium text-white">
                        1
                    </button>

                    <button className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-500 transition hover:bg-gray-50">
                        Next
                    </button>
                </div>
            </div>
        </div>
    );
}
