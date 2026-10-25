import ConfidenceScore from "./ConfidenceScore";
import {
    CheckCircle2,
    HelpCircle,
    AlertTriangle,
} from "lucide-react";

/**
 * Data structure representing a single candidate root cause.
 */
interface CauseCardData {
    /** Unique identifier of the failure cause (e.g., 'C01_AIR_BUBBLE') */
    id: string;
    /** Human-readable title of the cause */
    name: string;
    /** Technical explanation of how this root cause manifests */
    description: string;
    /** Normalized Bayesian likelihood percentage (0 - 100) */
    score: number;
    /** Current verification outcome assigned by logic or human sign-off */
    conclusion: "SUSPECTED" | "CONFIRMED" | "UNRESOLVED";
    /** Total number of pieces of evidence evaluated */
    evidenceCount: number;
    /** Number of pieces of evidence supporting this hypothesis */
    supportCount: number;
    /** Number of pieces of evidence refuting/contradicting this hypothesis */
    contradictCount: number;
}

/**
 * Props for CauseCard component.
 */
interface CauseCardProps {
    /** The candidate cause data object */
    cause: CauseCardData;
    /** 1-based rank position in the cause hierarchy */
    rank: number;
    /** Optional flag indicating whether the card's extended telemetry details are expanded */
    isExpanded?: boolean;
    /** Optional toggle handler for expanding/collapsing */
    onToggle?: () => void;
}

/**
 * Visual styling and iconography dictionary for each conclusion category.
 */
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

/**
 * CauseCard
 * 
 * Renders an individual root cause analysis card featuring rank order, title, description,
 * status badge, confidence gauge, and counts of supporting vs contradicting evidence points.
 */
export default function CauseCard({ cause, rank }: CauseCardProps) {
    // Select visual configuration corresponding to cause's conclusion state
    const conclusion = conclusionConfig[cause.conclusion];
    const ConclusionIcon = conclusion.icon;

    return (
        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-[#151d2d] p-5 transition hover:shadow-md dark:hover:border-gray-700">
            {/* Header: Rank badge, Cause Title & Description, and Conclusion Pill */}
            <div className="flex items-start justify-between">
                <div className="flex items-start gap-3">
                    {/* Rank index badge */}
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

                {/* Conclusion status badge */}
                <span
                    className={`inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold ${conclusion.className}`}
                >
                    <ConclusionIcon size={11} aria-hidden="true" />
                    {conclusion.label}
                </span>
            </div>

            {/* Footer: Confidence score meter and support vs contradiction tallies */}
            <div className="mt-4 flex items-center justify-between border-t border-gray-100 dark:border-gray-800 pt-3">
                <ConfidenceScore score={cause.score} size="sm" label="Evidence Support" />

                <div className="flex items-center gap-3 text-[10px]">
                    {/* Supporting evidence count */}
                    <span className="flex items-center gap-1 text-green-600 dark:text-emerald-400">
                        <CheckCircle2 size={11} aria-hidden="true" />
                        {cause.supportCount} supports
                    </span>

                    {/* Contradicting evidence count */}
                    <span className="flex items-center gap-1 text-red-500 dark:text-rose-400">
                        <AlertTriangle size={11} aria-hidden="true" />
                        {cause.contradictCount} contradicts
                    </span>
                </div>
            </div>
        </div>
    );
}
