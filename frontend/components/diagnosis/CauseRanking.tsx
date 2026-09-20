import CauseCard from "./CauseCard";
import { CandidateCause } from "@/types/api";

interface CauseRankingProps {
    causes?: CandidateCause[];
    revision?: number;
}

export default function CauseRanking({ causes = [], revision = 1 }: CauseRankingProps) {
    if (causes.length === 0) {
        return (
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                <p className="text-sm text-gray-500">No causes identified yet.</p>
            </div>
        );
    }

    return (
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-base font-semibold text-gray-900">
                        Ranked Candidate Causes
                    </h2>

                    <p className="mt-1 text-xs text-gray-500">
                        Causes ranked by cumulative evidence score
                    </p>
                </div>

                <span className="rounded-full bg-[#eeebff] px-2.5 py-1 text-[10px] font-semibold text-[#5848e8]">
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
