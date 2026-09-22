import CauseCard from "./CauseCard";
import { CandidateCause } from "@/types/api";

interface CauseRankingProps {
    causes?: CandidateCause[];
    revision?: number;
}

export default function CauseRanking({ causes = [], revision = 1 }: CauseRankingProps) {
    if (causes.length === 0) {
        return (
            <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-6 shadow-sm">
                <p className="text-sm text-gray-500 dark:text-gray-400">No causes identified yet.</p>
            </div>
        );
    }

    return (
        <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-6 shadow-sm">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-base font-semibold text-gray-900 dark:text-white">
                        Ranked Candidate Causes
                    </h2>

                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                        Causes ranked by cumulative evidence score
                    </p>
                </div>

                <span className="rounded-full bg-[#eeebff] dark:bg-[#5848e8]/30 px-2.5 py-1 text-[10px] font-semibold text-[#5848e8] dark:text-[#a59bff]">
                    REVISION {revision}
                </span>
            </div>

            <div className="mt-5 space-y-3">
                {causes.map((cause, index) => {
                    const cardData = {
                        id: cause.cause_id,
                        name: cause.cause_name,
                        description: cause.description || "",
                        score: Math.round(cause.score),
                        conclusion: cause.conclusion,
                        evidenceCount: (cause.supporting_evidence?.length || 0) + (cause.contradicting_evidence?.length || 0) + (cause.neutral_evidence?.length || 0),
                        supportCount: cause.supporting_evidence?.length || 0,
                        contradictCount: cause.contradicting_evidence?.length || 0,
                    };
                    return (
                        <CauseCard
                            key={cause.cause_id}
                            cause={cardData}
                            rank={index + 1}
                        />
                    );
                })}
            </div>
        </div>
    );
}
