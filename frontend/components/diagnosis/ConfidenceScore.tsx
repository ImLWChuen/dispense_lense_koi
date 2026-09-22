"use client";

interface ConfidenceScoreProps {
    score: number;
    size?: "sm" | "md" | "lg";
    label?: string;
    showStars?: boolean;
}

export function getStarCount(score: number): number {
    if (score >= 88) return 5;
    if (score >= 68) return 4;
    if (score >= 48) return 3;
    if (score >= 28) return 2;
    if (score > 8) return 1;
    return 0;
}

export function StarRating({ score, className = "" }: { score: number; className?: string }) {
    const starCount = getStarCount(score);
    return (
        <span className={`inline-flex items-center gap-0.5 ${className}`} title={`Confidence: ${starCount} of 5 stars (${score}/100)`}>
            {[1, 2, 3, 4, 5].map((i) => (
                <span
                    key={i}
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

export default function ConfidenceScore({
    score,
    size = "md",
    label = "Evidence Support",
    showStars = true,
}: ConfidenceScoreProps) {
    const getColor = () => {
        if (score >= 80) return { bar: "bg-[#6d5dfc]", text: "text-[#5848e8] dark:text-[#a59bff]" };
        if (score >= 60) return { bar: "bg-amber-500", text: "text-amber-600 dark:text-amber-400" };
        return { bar: "bg-gray-400", text: "text-gray-500 dark:text-gray-400" };
    };

    const color = getColor();

    const sizeConfig = {
        sm: { height: "h-1.5", width: "w-14", text: "text-xs" },
        md: { height: "h-2", width: "w-20", text: "text-sm" },
        lg: { height: "h-2.5", width: "w-28", text: "text-base" },
    };

    const cfg = sizeConfig[size];
    const clampedScore = Math.max(0, Math.min(100, Math.round(score)));

    return (
        <div className="flex flex-wrap items-center gap-2 sm:gap-3">
            {showStars && (
                <StarRating score={clampedScore} />
            )}

            <div
                className={`${cfg.height} ${cfg.width} overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800`}
            >
                <div
                    className={`h-full rounded-full ${color.bar} transition-all duration-500`}
                    style={{ width: `${clampedScore}%` }}
                />
            </div>

            <span className={`${cfg.text} font-semibold ${color.text}`}>
                {clampedScore}%
            </span>

            {label && (
                <span className="text-xs text-gray-500 dark:text-gray-400">{label}</span>
            )}
        </div>
    );
}
