interface QuestionProgressProps {
    current: number;
    total: number;
}

export default function QuestionProgress({
    current,
    total,
}: QuestionProgressProps) {
    const percentage = Math.round((current / total) * 100);

    return (
        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
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

            <div className="mt-3 h-2 overflow-hidden rounded-full bg-gray-100">
                <div
                    className="h-full rounded-full bg-[#6d5dfc] transition-all duration-500"
                    style={{ width: `${percentage}%` }}
                />
            </div>

            <div className="mt-3 flex gap-1">
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
