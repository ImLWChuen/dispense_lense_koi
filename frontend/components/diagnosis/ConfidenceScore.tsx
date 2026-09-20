interface ConfidenceScoreProps {
    score: number;
    size?: "sm" | "md" | "lg";
    label?: string;
}

export default function ConfidenceScore({
    score,
    size = "md",
    label = "Evidence Support",
}: ConfidenceScoreProps) {
    const getColor = () => {
        if (score >= 80) return { bar: "bg-[#6d5dfc]", text: "text-[#5848e8]" };
        if (score >= 60) return { bar: "bg-amber-500", text: "text-amber-600" };
        return { bar: "bg-gray-400", text: "text-gray-500" };
    };

    const color = getColor();

    const sizeConfig = {
        sm: { height: "h-1.5", width: "w-16", text: "text-xs" },
        md: { height: "h-2", width: "w-24", text: "text-sm" },
        lg: { height: "h-2.5", width: "w-32", text: "text-base" },
    };

    const cfg = sizeConfig[size];
    const clampedScore = Math.max(0, Math.min(100, score));

    return (
        <div className="flex items-center gap-3">
            <div
                className={`${cfg.height} ${cfg.width} overflow-hidden rounded-full bg-gray-100`}
            >
                <div
                    className={`h-full rounded-full ${color.bar} transition-all duration-500`}
                    style={{ width: `${clampedScore}%` }}
                />
            </div>

            <span className={`${cfg.text} font-semibold ${color.text}`}>
                {score}/100
            </span>

            {label && (
                <span className="text-xs text-gray-500">{label}</span>
            )}
        </div>
    );
}
