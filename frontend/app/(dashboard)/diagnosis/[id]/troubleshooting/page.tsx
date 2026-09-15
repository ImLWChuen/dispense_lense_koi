import Link from "next/link";

import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";
import PageContainer from "@/components/layout/PageContainer";
import TroubleshootingChecklist from "@/components/diagnosis/TroubleshootingChecklist";
import QuestionProgress from "@/components/diagnosis/QuestionProgress";

const mockActions = [
    {
        id: "ACT01",
        name: "Inspect Nozzle",
        description:
            "Visually inspect the dispensing nozzle for blockage, dried material, damage, or contamination.",
        procedure:
            "1. Stop dispensing operation.\n2. Remove the nozzle from the dispense head.\n3. Inspect the nozzle tip under magnification for blockage or damage.\n4. Check for dried material buildup at the tip face.\n5. Verify the nozzle bore is clear by visual or light-pass inspection.\n6. Document findings.",
        effortLevel: "low" as const,
        applicableCauses: ["nozzle_restriction", "nozzle_condition"],
    },
    {
        id: "ACT02",
        name: "Check Material Supply Condition",
        description:
            "Inspect the dispensing material syringe or reservoir for air bubbles, separation, contamination, or depletion.",
        procedure:
            "1. Visually inspect the syringe/reservoir for trapped air bubbles.\n2. Check material level — note if nearly depleted.\n3. Look for phase separation or settling.\n4. Verify the material is within its specified pot life.\n5. Check for contamination or discoloration.\n6. Document findings.",
        effortLevel: "low" as const,
        applicableCauses: ["material_condition", "air_supply_issue"],
    },
    {
        id: "ACT03",
        name: "Perform Test Shots",
        description:
            "Dispense a series of test dots and measure volume/size consistency to quantify the defect.",
        procedure:
            "1. Set up standard test substrate.\n2. Dispense 10-20 test shots at current parameters.\n3. Measure dot diameter or weight for each shot.\n4. Calculate mean, standard deviation, and coefficient of variation.\n5. Record any visible anomalies per shot.\n6. Compare against specification limits.\n7. Document results.",
        effortLevel: "medium" as const,
        applicableCauses: [
            "pressure_instability",
            "parameter_issue",
            "equipment_condition",
        ],
    },
    {
        id: "ACT04",
        name: "Verify Pressure Settings",
        description:
            "Check and verify the dispensing pressure settings and supply pressure consistency.",
        procedure:
            "1. Record current pressure setpoint.\n2. Monitor actual pressure gauge during dispensing.\n3. Note any fluctuation or drift.\n4. Verify regulator is functioning correctly.\n5. Check for pneumatic leaks in supply lines.\n6. Document findings.",
        effortLevel: "medium" as const,
        applicableCauses: ["pressure_instability", "parameter_issue"],
    },
    {
        id: "ACT05",
        name: "Inspect Valve Assembly",
        description:
            "Check the dispensing valve for wear, misalignment, or malfunction.",
        procedure:
            "1. Remove valve assembly for inspection.\n2. Check valve seat for wear or damage.\n3. Verify proper seating and seal integrity.\n4. Check actuator response time.\n5. Look for material leakage around seals.\n6. Document findings.",
        effortLevel: "high" as const,
        applicableCauses: ["valve_issue", "equipment_condition"],
    },
];

export default function TroubleshootingPage() {
    return (
        <div className="min-h-screen">
            <Sidebar />

            <div className="ml-64">
                <Header />

                <PageContainer>
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-sm font-medium text-[#6d5dfc]">
                                Diagnostic workflow · DSP-2026-0185
                            </p>

                            <h1 className="mt-1 text-3xl font-bold tracking-tight text-gray-900">
                                Troubleshooting Checks
                            </h1>

                            <p className="mt-2 text-sm text-gray-500">
                                Perform the recommended checks to gather
                                physical evidence and validate the diagnosis.
                            </p>
                        </div>

                        <Link
                            href="/diagnosis/DSP-2026-0185"
                            className="text-sm font-medium text-[#5848e8] hover:text-[#6d5dfc]"
                        >
                            ← Back to Diagnosis
                        </Link>
                    </div>

                    <div className="mt-8 grid grid-cols-1 gap-8 xl:grid-cols-3">
                        <div className="xl:col-span-2">
                            <TroubleshootingChecklist actions={mockActions} />

                            <div className="mt-6 flex justify-end">
                                <Link
                                    href="/diagnosis/DSP-2026-0185/verification"
                                    className="inline-flex items-center gap-2 rounded-xl bg-[#6d5dfc] px-6 py-3 text-sm font-semibold text-white transition hover:bg-[#5848e8]"
                                >
                                    Continue to Verification →
                                </Link>
                            </div>
                        </div>

                        <div className="space-y-6">
                            <QuestionProgress current={3} total={5} />

                            <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
                                <p className="text-sm font-semibold text-gray-900">
                                    Check Priority
                                </p>

                                <p className="mt-1 text-xs text-gray-500">
                                    Checks are ordered by diagnostic value
                                </p>

                                <div className="mt-4 space-y-3">
                                    <div className="flex items-center justify-between">
                                        <span className="text-xs text-gray-600">
                                            Low effort
                                        </span>

                                        <span className="rounded-full bg-green-50 px-2 py-0.5 text-[10px] font-medium text-green-700">
                                            Start here
                                        </span>
                                    </div>

                                    <div className="flex items-center justify-between">
                                        <span className="text-xs text-gray-600">
                                            Medium effort
                                        </span>

                                        <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-700">
                                            If needed
                                        </span>
                                    </div>

                                    <div className="flex items-center justify-between">
                                        <span className="text-xs text-gray-600">
                                            High effort
                                        </span>

                                        <span className="rounded-full bg-red-50 px-2 py-0.5 text-[10px] font-medium text-red-700">
                                            Last resort
                                        </span>
                                    </div>
                                </div>
                            </div>

                            <div className="rounded-2xl border border-[#ded9ff] bg-[#faf9ff] p-5">
                                <p className="text-sm font-semibold text-gray-900">
                                    Tip
                                </p>

                                <p className="mt-2 text-xs leading-5 text-gray-600">
                                    Complete low-effort checks first. Each
                                    finding automatically updates the cause
                                    ranking. You may not need to perform all
                                    checks if a clear cause emerges early.
                                </p>
                            </div>
                        </div>
                    </div>
                </PageContainer>
            </div>
        </div>
    );
}
