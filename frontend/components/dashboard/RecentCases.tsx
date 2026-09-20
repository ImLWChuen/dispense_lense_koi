import Link from "next/link";
import { ComponentType } from "react";
import {
    ArrowRight,
    CheckCircle2,
    Clock3,
    AlertTriangle,
} from "lucide-react";
import { RecentCaseRecord } from "@/lib/api/analytics";

function StatusBadge({
    status,
}: {
    status: string;
}) {
    const config: Record<string, { icon: ComponentType<{ size?: number }>; className: string }> = {
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

    const current = config[status] || config["In Progress"];
    const Icon = current.icon;

    return (
        <span
            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${current.className}`}
        >
            <Icon size={13} />
            {status}
        </span>
    );
}

interface RecentCasesProps {
    cases?: RecentCaseRecord[];
}

export default function RecentCases({ cases = [] }: RecentCasesProps) {
    const hasCases = cases && cases.length > 0;

    return (
        <section className="mt-6 rounded-2xl border border-gray-200 bg-white shadow-sm">
            <div className="flex items-center justify-between border-b border-gray-100 px-6 py-5">
                <div>
                    <h2 className="text-base font-semibold text-gray-900">
                        Recent Cases
                    </h2>

                    <p className="mt-1 text-xs text-gray-500">
                        Latest dispensing diagnostics and resolutions
                    </p>
                </div>

                <Link
                    href="/cases"
                    className="inline-flex items-center gap-1.5 text-sm font-medium text-[#5848e8] hover:text-[#6d5dfc]"
                >
                    View all
                    <ArrowRight size={15} />
                </Link>
            </div>

            <div className="overflow-x-auto">
                <table className="w-full min-w-[900px]">
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
                            Updated
                        </th>
                    </tr>
                    </thead>

                    <tbody>
                    {hasCases ? (
                        cases.map((item) => (
                            <tr
                                key={item.id}
                                className="border-b border-gray-50 transition last:border-0 hover:bg-gray-50/70"
                            >
                                <td className="px-6 py-4">
                                    <Link
                                        href={`/diagnosis/${item.id}`}
                                        className="text-sm font-semibold text-gray-900 hover:text-[#5848e8]"
                                    >
                                        {item.case_number}
                                    </Link>
                                </td>

                                <td className="px-6 py-4">
                                    <p className="text-sm font-medium text-gray-800">
                                        {item.defect}
                                    </p>
                                </td>

                                <td className="px-6 py-4">
                                    <p className="text-sm text-gray-600">
                                        {item.equipment}
                                    </p>
                                </td>

                                <td className="px-6 py-4">
                                    <p className="text-sm text-gray-600">
                                        {item.cause}
                                    </p>
                                </td>

                                <td className="px-6 py-4">
                                    {item.evidence_support != null ? (
                                        <div className="flex items-center gap-3">
                                            <div className="h-1.5 w-20 overflow-hidden rounded-full bg-gray-100">
                                                <div
                                                    className="h-full rounded-full bg-[#6d5dfc]"
                                                    style={{
                                                        width: `${Math.max(0, Math.min(100, item.evidence_support))}%`,
                                                    }}
                                                />
                                            </div>

                                            <span className="text-xs font-semibold text-gray-700">
                                                {item.evidence_support}/100
                                            </span>
                                        </div>
                                    ) : (
                                        <span className="text-xs text-gray-400">N/A</span>
                                    )}
                                </td>

                                <td className="px-6 py-4">
                                    <StatusBadge status={item.status} />
                                </td>

                                <td className="px-6 py-4 text-xs text-gray-500">
                                    {item.time}
                                </td>
                            </tr>
                        ))
                    ) : (
                        <tr>
                            <td colSpan={7} className="px-6 py-10 text-center text-xs text-gray-400">
                                No diagnostic cases recorded yet. Start a new diagnosis to begin!
                            </td>
                        </tr>
                    )}
                    </tbody>
                </table>
            </div>
        </section>
    );
}