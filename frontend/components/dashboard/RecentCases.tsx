import Link from "next/link";
import {
    ArrowRight,
    CheckCircle2,
    Clock3,
    AlertTriangle,
} from "lucide-react";

interface CaseItem {
    id: string;
    caseNumber: string;
    defect: string;
    equipment: string;
    cause: string;
    status: "Resolved" | "In Progress" | "Needs Review";
    confidence: number;
    time: string;
}

const cases: CaseItem[] = [
    {
        id: "DSP-2026-0184",
        caseNumber: "DSP-2026-0184",
        defect: "Stringing",
        equipment: "Dispensing Line A",
        cause: "Material viscosity",
        status: "Resolved",
        confidence: 94,
        time: "12 min ago",
    },
    {
        id: "DSP-2026-0183",
        caseNumber: "DSP-2026-0183",
        defect: "Under-dispensing",
        equipment: "Dispensing Line B",
        cause: "Pressure instability",
        status: "In Progress",
        confidence: 87,
        time: "28 min ago",
    },
    {
        id: "DSP-2026-0182",
        caseNumber: "DSP-2026-0182",
        defect: "Inconsistent bead",
        equipment: "Dispensing Line A",
        cause: "Nozzle obstruction",
        status: "Needs Review",
        confidence: 76,
        time: "1 hr ago",
    },
    {
        id: "DSP-2026-0181",
        caseNumber: "DSP-2026-0181",
        defect: "Excess material",
        equipment: "Dispensing Line C",
        cause: "Flow rate setting",
        status: "Resolved",
        confidence: 91,
        time: "2 hrs ago",
    },
];

function StatusBadge({
                         status,
                     }: {
    status: CaseItem["status"];
}) {
    const config = {
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

    const current = config[status];
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

export default function RecentCases() {
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
                            Probable Cause
                        </th>

                        <th className="px-6 py-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
                            Confidence
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
                    {cases.map((item) => (
                        <tr
                            key={item.id}
                            className="border-b border-gray-50 transition last:border-0 hover:bg-gray-50/70"
                        >
                            <td className="px-6 py-4">
                                <Link
                                    href={`/cases/${item.id}`}
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
                                <div className="flex items-center gap-3">
                                    <div className="h-1.5 w-20 overflow-hidden rounded-full bg-gray-100">
                                        <div
                                            className="h-full rounded-full bg-[#6d5dfc]"
                                            style={{
                                                width: `${item.confidence}%`,
                                            }}
                                        />
                                    </div>

                                    <span className="text-xs font-semibold text-gray-700">
                      {item.confidence}%
                    </span>
                                </div>
                            </td>

                            <td className="px-6 py-4">
                                <StatusBadge status={item.status} />
                            </td>

                            <td className="px-6 py-4 text-xs text-gray-500">
                                {item.time}
                            </td>
                        </tr>
                    ))}
                    </tbody>
                </table>
            </div>
        </section>
    );
}