/**
 * Props for QuestionProgress component.
 */
interface QuestionProgressProps {
    /** Number of diagnostic discriminator questions answered so far */
    current: number;
    /** Total number of questions in the diagnostic sequence */
    total: number;
}

/**
 * QuestionProgress
 * 
 * Progress card illustrating completion percentage for the interactive question loop.
 * Features a continuous percentage bar and segmented tick indicators.
 */
export default function QuestionProgress({
    current,
    total,
}: QuestionProgressProps) {
    // Calculate percentage, guarding against divide-by-zero
    const percentage = total > 0 ? Math.round((current / total) * 100) : 0;

    return (
        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
            {/* Header: Title, completed count, and percentage callout */}
            <div className="flex items-center justify-between">
                <div>
                    <p className="text-sm font-semibold text-gray-900">
                        Question Progress
                    </p>

                    <p className="mt-0.5 text-xs text-gray-500">
                        {current} of {total} questions answered
                    </p>
                </div>

                <span className="text-lg font-bold text-[#5848e8]">
                    {percentage}%
                </span>
            </div>

            {/* Continuous progress meter */}
            <div 
                className="mt-3 h-2 overflow-hidden rounded-full bg-gray-100"
                role="progressbar"
                aria-valuenow={percentage}
                aria-valuemin={0}
                aria-valuemax={100}
            >
                <div
                    className="h-full rounded-full bg-[#6d5dfc] transition-all duration-500"
                    style={{ width: `${percentage}%` }}
                />
            </div>

            {/* Segmented step ticks */}
            <div className="mt-3 flex gap-1" aria-hidden="true">
                {Array.from({ length: total }).map((_, i) => (
                    <div
                        key={i}
                        className={`h-1 flex-1 rounded-full transition ${
                            i < current ? "bg-[#6d5dfc]" : "bg-gray-200"
                        }`}
                    />
                ))}
            </div>
        </div>
    );
}
