import { CheckCircle2, AlertTriangle, Minus } from "lucide-react";

/**
 * Individual evidence observation and its causal relationship to a root cause.
 */
interface EvidenceItem {
    /** Observation name / feature key (e.g., 'Dispense Pressure Drop') */
    observation: string;
    /** Current sensor value or categorical measurement (e.g., '0.18 MPa') */
    value: string;
    /** Nature of Bayesian correlation: SUPPORTS hypothesis, CONTRADICTS it, or NEUTRAL */
    relation: "SUPPORTS" | "CONTRADICTS" | "NEUTRAL";
    /** Severity or weight magnitude of the evidence item */
    strength: "STRONG" | "MODERATE" | "WEAK";
    /** Technical rationale explaining why this observation supports or contradicts the cause */
    explanation: string;
}

/**
 * Props for the EvidencePanel component.
 */
interface EvidencePanelProps {
    /** List of evidence items associated with the evaluated cause */
    evidence: EvidenceItem[];
    /** Optional label identifying the focused root cause */
    causeLabel?: string;
}

/**
 * Visual styling and iconography dictionary for evidence relation types.
 */
const relationConfig = {
    SUPPORTS: {
        icon: CheckCircle2,
        className: "bg-green-50 text-green-700 border border-green-300 dark:bg-emerald-500/20 dark:text-emerald-300 dark:border-emerald-500/40",
        label: "Supports",
    },
    CONTRADICTS: {
        icon: AlertTriangle,
        className: "bg-red-50 text-red-700 border border-red-300 dark:bg-rose-500/20 dark:text-rose-300 dark:border-rose-500/40",
        label: "Contradicts",
    },
    NEUTRAL: {
        icon: Minus,
        className: "bg-gray-100 text-gray-700 border border-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:border-gray-700",
        label: "Neutral",
    },
};

/**
 * Numeric mapping for strength dot indicator.
 */
const strengthDots = {
    STRONG: 3,
    MODERATE: 2,
    WEAK: 1,
};

/**
 * EvidencePanel
 * 
 * Detailed itemized list of evaluated physical measurements, sensor feeds, and questions,
 * displaying how each individual data point affects the candidate cause's likelihood score.
 */
export default function EvidencePanel({
    evidence,
    causeLabel,
}: EvidencePanelProps) {
    return (
        <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-6 shadow-sm">
            {/* Header: Title and optional cause context label */}
            <div>
                <h2 className="text-base font-semibold text-gray-900 dark:text-white">
                    Evidence
                </h2>

                {causeLabel && (
                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                        Evidence relevance for{" "}
                        <span className="font-medium text-gray-700 dark:text-gray-200">
                            {causeLabel}
                        </span>
                    </p>
                )}
            </div>

            {/* Evidence Items List */}
            <div className="mt-5 space-y-3">
                {evidence.map((item, index) => {
                    const rel = relationConfig[item.relation];
                    const Icon = rel.icon;
                    const dots = strengthDots[item.strength];

                    return (
                        <div
                            key={index}
                            className="rounded-xl border border-gray-100 dark:border-gray-800 bg-gray-50/50 dark:bg-[#151d2d] p-4"
                        >
                            <div className="flex items-start justify-between gap-3">
                                {/* Observation text, recorded value, and engineering rationale */}
                                <div className="flex-1">
                                    <div className="flex items-center gap-2">
                                        <span className="text-sm font-medium text-gray-800 dark:text-gray-200">
                                            {item.observation}
                                        </span>

                                        <span className="rounded-md bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 text-[10px] font-medium text-gray-600 dark:text-gray-300 border border-transparent dark:border-gray-700 font-mono">
                                            {item.value}
                                        </span>
                                    </div>

                                    <p className="mt-1.5 text-xs leading-5 text-gray-500 dark:text-gray-400">
                                        {item.explanation}
                                    </p>
                                </div>

                                {/* Strength Dots and Relationship Badge */}
                                <div className="flex shrink-0 items-center gap-2">
                                    {/* 3-dot strength meter */}
                                    <div 
                                        className="flex gap-0.5" 
                                        title={`Evidence weight: ${item.strength}`}
                                        aria-label={`Evidence weight: ${item.strength}`}
                                    >
                                        {[1, 2, 3].map((d) => (
                                            <span
                                                key={d}
                                                aria-hidden="true"
                                                className={`h-1.5 w-1.5 rounded-full ${
                                                    d <= dots
                                                        ? "bg-[#6d5dfc]"
                                                        : "bg-gray-200 dark:bg-gray-700"
                                                }`}
                                            />
                                        ))}
                                    </div>

                                    {/* Supports / Contradicts badge */}
                                    <span
                                        className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold ${rel.className}`}
                                    >
                                        <Icon size={11} aria-hidden="true" />
                                        {rel.label}
                                    </span>
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
