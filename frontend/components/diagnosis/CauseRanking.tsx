import CauseCard from "./CauseCard";

const mockCauses = [
    {
        id: "nozzle_restriction",
        name: "Nozzle Restriction",
        description:
            "Partial or complete blockage of the dispensing nozzle reduces or blocks material flow.",
        score: 87,
        conclusion: "SUSPECTED" as const,
        evidenceCount: 5,
        supportCount: 4,
        contradictCount: 1,
    },
    {
        id: "air_supply_issue",
        name: "Air / Supply Issue",
        description:
            "Trapped air or inconsistent air pressure in the material supply path causes erratic dispensing.",
        score: 72,
        conclusion: "SUSPECTED" as const,
        evidenceCount: 4,
        supportCount: 3,
        contradictCount: 1,
    },
    {
        id: "material_condition",
        name: "Material Condition",
        description:
            "Material properties are outside acceptable range, causing unpredictable dispensing behaviour.",
        score: 58,
        conclusion: "UNRESOLVED" as const,
        evidenceCount: 3,
        supportCount: 2,
        contradictCount: 1,
    },
    {
        id: "pressure_instability",
        name: "Pressure Instability",
        description:
            "Inconsistent dispensing pressure from the supply system or regulator causes volume variation.",
        score: 41,
        conclusion: "UNRESOLVED" as const,
        evidenceCount: 3,
        supportCount: 1,
        contradictCount: 2,
    },
    {
        id: "parameter_issue",
        name: "Parameter Issue",
        description:
            "Dispensing parameters (time, pressure, speed) are incorrectly configured.",
        score: 29,
        conclusion: "UNRESOLVED" as const,
        evidenceCount: 2,
        supportCount: 1,
        contradictCount: 1,
    },
];

export default function CauseRanking() {
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
                    REVISION 1
                </span>
            </div>

            <div className="mt-5 space-y-3">
                {mockCauses.map((cause, index) => (
                    <CauseCard
                        key={cause.id}
                        cause={cause}
                        rank={index + 1}
                    />
                ))}
            </div>
        </div>
    );
}
