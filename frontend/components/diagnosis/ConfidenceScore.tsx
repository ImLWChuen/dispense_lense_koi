"use client";

/**
 * Props for the ConfidenceScore component.
 */
interface ConfidenceScoreProps {
    /** Raw or normalized confidence/likelihood score (0 to 100) */
    score: number;
    /** Visual size profile for progress bar and typography */
    size?: "sm" | "md" | "lg";
    /** Optional descriptor label displayed adjacent to percentage */
    label?: string;
    /** Flag controlling whether the 5-star rating icon row is rendered */
    showStars?: boolean;
}

/**
 * Maps a numeric score (0-100) into discrete 1-to-5 star thresholds.
 * Thresholds align with standard industrial confidence tiers:
 * - >= 88: 5 Stars (High certainty)
 * - >= 68: 4 Stars (Strong correlation)
 * - >= 48: 3 Stars (Moderate evidence)
 * - >= 28: 2 Stars (Weak signal)
 * - > 8:   1 Star  (Minimal signal)
 * - <= 8:  0 Stars (Negligible)
 * 
 * @param score The confidence score between 0 and 100
 * @returns Number of active stars from 0 to 5
 */
export function getStarCount(score: number): number {
    if (score >= 88) return 5;
    if (score >= 68) return 4;
    if (score >= 48) return 3;
    if (score >= 28) return 2;
    if (score > 8) return 1;
    return 0;
}

/**
 * StarRating
 * 
 * Renders an accessible 5-star visual indicator with filled amber stars for
 * active tiers and muted stars for remaining capacity.
 */
export function StarRating({ score, className = "" }: { score: number; className?: string }) {
    const starCount = getStarCount(score);
    return (
        <span 
            className={`inline-flex items-center gap-0.5 ${className}`} 
            title={`Confidence: ${starCount} of 5 stars (${score}/100)`}
            aria-label={`Confidence rating: ${starCount} out of 5 stars`}
        >
            {[1, 2, 3, 4, 5].map((i) => (
                <span
                    key={i}
                    aria-hidden="true"
                    className={`text-sm ${
                        i <= starCount ? "text-amber-500 font-bold" : "text-gray-300 dark:text-gray-600"
                    }`}
                >
                    ★
                </span>
            ))}
        </span>
    );
}

/**
 * ConfidenceScore
 * 
 * Multi-element confidence indicator combining 5-star tier visualization,
 * animated smooth progress meter, and numeric percentage text.
 */
export default function ConfidenceScore({
    score,
    size = "md",
    label = "Evidence Support",
    showStars = true,
}: ConfidenceScoreProps) {
    // Dynamic color coding based on likelihood threshold
    const getColor = () => {
        if (score >= 80) return { bar: "bg-[#6d5dfc]", text: "text-[#5848e8] dark:text-[#a59bff]" };
        if (score >= 60) return { bar: "bg-amber-500", text: "text-amber-600 dark:text-amber-400" };
        return { bar: "bg-gray-400", text: "text-gray-500 dark:text-gray-400" };
    };

    const color = getColor();

    // Sizing dimension mappings
    const sizeConfig = {
        sm: { height: "h-1.5", width: "w-14", text: "text-xs" },
        md: { height: "h-2", width: "w-20", text: "text-sm" },
        lg: { height: "h-2.5", width: "w-28", text: "text-base" },
    };

    const cfg = sizeConfig[size];
    // Clamp score to valid [0, 100] bounds
    const clampedScore = Math.max(0, Math.min(100, Math.round(score)));

    return (
        <div className="flex flex-wrap items-center gap-2 sm:gap-3">
            {/* Optional Star Indicator */}
            {showStars && (
                <StarRating score={clampedScore} />
            )}

            {/* Linear Progress Bar */}
            <div
                className={`${cfg.height} ${cfg.width} overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800`}
                role="progressbar"
                aria-valuenow={clampedScore}
                aria-valuemin={0}
                aria-valuemax={100}
            >
                <div
                    className={`h-full rounded-full ${color.bar} transition-all duration-500`}
                    style={{ width: `${clampedScore}%` }}
                />
            </div>

            {/* Percentage Value */}
            <span className={`${cfg.text} font-semibold ${color.text}`}>
                {clampedScore}%
            </span>

            {/* Optional Descriptive Subtitle */}
            {label && (
                <span className="text-xs text-gray-500 dark:text-gray-400">{label}</span>
            )}
        </div>
    );
}
