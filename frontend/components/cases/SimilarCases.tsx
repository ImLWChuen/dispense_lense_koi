import Link from "next/link";
import { ArrowRight } from "lucide-react";

interface SimilarCase {
    id: string;
    defect: string;
    cause: string;
    similarity: number;
    status: string;
}

const mockSimilar: SimilarCase[] = [
    {
        id: "DSP-2026-0171",
        defect: "Too Little Material",
        cause: "Nozzle Restriction",
        similarity: 92,
        status: "Resolved",
    },
    {
        id: "DSP-2026-0158",
        defect: "Inconsistent Size",
        cause: "Nozzle Restriction",
        similarity: 78,
        status: "Resolved",
    },
    {
        id: "DSP-2026-0143",
        defect: "Too Little Material",
        cause: "Air / Supply Issue",
        similarity: 71,
        status: "Resolved",
    },
];

export default function SimilarCases() {
    return (
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
            <h2 className="text-base font-semibold text-gray-900">
                Similar Cases
            </h2>

            <p className="mt-1 text-xs text-gray-500">
                Historical cases with similar symptoms
            </p>

            <div className="mt-5 space-y-3">
                {mockSimilar.map((item) => (
                    <Link
                        key={item.id}
                        href={`/cases/${item.id}`}
                        className="group flex items-center justify-between rounded-xl border border-gray-100 p-3 transition hover:border-[#6d5dfc]/30 hover:bg-[#faf9ff]"
                    >
                        <div>
                            <p className="text-sm font-semibold text-gray-900 group-hover:text-[#5848e8]">
                                {item.id}
                            </p>

                            <p className="mt-0.5 text-xs text-gray-500">
                                {item.defect} · {item.cause}
                            </p>
                        </div>

                        <div className="flex items-center gap-3">
                            <div className="text-right">
                                <span className="text-xs font-semibold text-[#5848e8]">
                                    {item.similarity}%
                                </span>

                                <p className="text-[10px] text-gray-400">
                                    match
                                </p>
                            </div>

                            <ArrowRight
                                size={14}
                                className="text-gray-300 group-hover:text-[#6d5dfc]"
                            />
                        </div>
                    </Link>
                ))}
            </div>
        </div>
    );
}
