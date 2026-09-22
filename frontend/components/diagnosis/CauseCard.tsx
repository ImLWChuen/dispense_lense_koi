import ConfidenceScore from "./ConfidenceScore";
import {
    CheckCircle2,
    HelpCircle,
    AlertTriangle,
} from "lucide-react";

interface CauseCardData {
    id: string;
    name: string;
    description: string;
    score: number;
    conclusion: "SUSPECTED" | "CONFIRMED" | "UNRESOLVED";
    evidenceCount: number;
    supportCount: number;
    contradictCount: number;
}

interface CauseCardProps {
    cause: CauseCardData;
    rank: number;
    isExpanded?: boolean;
    onToggle?: () => void;
}

const conclusionConfig = {
    SUSPECTED: {
        icon: HelpCircle,
        className: "bg-amber-50 text-amber-800 border border-amber-300 dark:bg-amber-500/20 dark:text-amber-300 dark:border-amber-500/40",
        label: "Suspected",
    },
    CONFIRMED: {
        icon: CheckCircle2,
        className: "bg-green-50 text-green-700 border border-green-300 dark:bg-emerald-500/20 dark:text-emerald-300 dark:border-emerald-500/40",
        label: "Confirmed",
    },
    UNRESOLVED: {
        icon: AlertTriangle,
        className: "bg-gray-100 text-gray-700 border border-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:border-gray-700",
        label: "Unresolved",
    },
};

export default function CauseCard({ cause, rank }: CauseCardProps) {
    const conclusion = conclusionConfig[cause.conclusion];
    const ConclusionIcon = conclusion.icon;

    return (
        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-[#151d2d] p-5 transition hover:shadow-md dark:hover:border-gray-700">
            <div className="flex items-start justify-between">
                <div className="flex items-start gap-3">
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-[#eeebff] dark:bg-[#5848e8]/25 text-xs font-bold text-[#5848e8] dark:text-[#a59bff]">
                        {rank}
                    </span>

                    <div>
                        <p className="text-sm font-semibold text-gray-900 dark:text-white">
                            {cause.name}
                        </p>

                        <p className="mt-1 text-xs leading-5 text-gray-500 dark:text-gray-400">
                            {cause.description}
                        </p>
                    </div>
                </div>

                <span
                    className={`inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold ${conclusion.className}`}
                >
                    <ConclusionIcon size={11} />
                    {conclusion.label}
                </span>
            </div>

            <div className="mt-4 flex items-center justify-between border-t border-gray-100 dark:border-gray-800 pt-3">
                <ConfidenceScore score={cause.score} size="sm" label="Evidence Support" />

                <div className="flex items-center gap-3 text-[10px]">
                    <span className="flex items-center gap-1 text-green-600 dark:text-emerald-400">
                        <CheckCircle2 size={11} />
                        {cause.supportCount} supports
                    </span>

                    <span className="flex items-center gap-1 text-red-500 dark:text-rose-400">
                        <AlertTriangle size={11} />
                        {cause.contradictCount} contradicts
                    </span>
                </div>
            </div>
        </div>
    );
}
