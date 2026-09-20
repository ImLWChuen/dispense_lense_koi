export default function ReportPreview() {
    return (
        <div className="rounded-2xl border border-gray-200 bg-white p-8 shadow-sm">
            {/* Report Header */}
            <div className="border-b border-gray-200 pb-6">
                <div className="flex items-center justify-between">
                    <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-[#6d5dfc]">
                            Dispense Lens Diagnostic Report
                        </p>

                        <h2 className="mt-2 text-xl font-bold text-gray-900">
                            DSP-2026-0184
                        </h2>
                    </div>

                    <div className="text-right text-xs text-gray-500">
                        <p>Generated: Sep 15, 2026</p>
                        <p>Engineer: Sarah Mitchell</p>
                    </div>
                </div>
            </div>

            {/* Problem Summary */}
            <div className="mt-6">
                <h3 className="text-sm font-semibold text-gray-900">
                    Problem Summary
                </h3>

                <p className="mt-2 text-sm leading-6 text-gray-600">
                    Dispensed dots on Dispensing Line A were consistently
                    undersized (measured 0.8mm vs. 1.2mm target). The defect
                    was observed intermittently, worsening after prolonged
                    operation, and was isolated to a specific nozzle position.
                </p>
            </div>

            {/* Diagnosis */}
            <div className="mt-6">
                <h3 className="text-sm font-semibold text-gray-900">
                    Diagnostic Findings
                </h3>

                <div className="mt-2 rounded-lg bg-gray-50 p-4">
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <p className="text-[10px] font-semibold uppercase tracking-wide text-gray-400">
                                Defect Type
                            </p>

                            <p className="mt-1 text-sm font-medium text-gray-800">
                                Too Little Material (D01)
                            </p>
                        </div>

                        <div>
                            <p className="text-[10px] font-semibold uppercase tracking-wide text-gray-400">
                                Confirmed Root Cause
                            </p>

                            <p className="mt-1 text-sm font-medium text-gray-800">
                                Nozzle Restriction
                            </p>
                        </div>

                        <div>
                            <p className="text-[10px] font-semibold uppercase tracking-wide text-gray-400">
                                Confidence
                            </p>

                            <p className="mt-1 text-sm font-medium text-[#5848e8]">
                                87%
                            </p>
                        </div>

                        <div>
                            <p className="text-[10px] font-semibold uppercase tracking-wide text-gray-400">
                                Diagnostic Revisions
                            </p>

                            <p className="mt-1 text-sm font-medium text-gray-800">
                                3
                            </p>
                        </div>
                    </div>
                </div>
            </div>

            {/* Evidence */}
            <div className="mt-6">
                <h3 className="text-sm font-semibold text-gray-900">
                    Key Evidence
                </h3>

                <ul className="mt-2 space-y-1.5">
                    {[
                        "Undersized deposits (SUPPORTS nozzle restriction - STRONG)",
                        "Issue isolated to specific nozzle (SUPPORTS - STRONG)",
                        "Intermittent occurrence (SUPPORTS - MODERATE)",
                        "Visual inspection confirmed partial blockage at nozzle tip",
                    ].map((item, i) => (
                        <li
                            key={i}
                            className="flex items-start gap-2 text-sm text-gray-600"
                        >
                            <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[#6d5dfc]" />
                            {item}
                        </li>
                    ))}
                </ul>
            </div>

            {/* Actions Taken */}
            <div className="mt-6">
                <h3 className="text-sm font-semibold text-gray-900">
                    Actions Taken
                </h3>

                <ul className="mt-2 space-y-1.5">
                    {[
                        "Nozzle removed and inspected - dried material buildup found at tip",
                        "Nozzle cleaned with approved solvent",
                        "O-ring seal replaced due to minor wear",
                        "Test shots performed - 20/20 within specification",
                    ].map((item, i) => (
                        <li
                            key={i}
                            className="flex items-start gap-2 text-sm text-gray-600"
                        >
                            <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-green-500" />
                            {item}
                        </li>
                    ))}
                </ul>
            </div>

            {/* Resolution */}
            <div className="mt-6 rounded-lg bg-green-50 p-4">
                <h3 className="text-sm font-semibold text-green-800">
                    Resolution
                </h3>

                <p className="mt-1 text-sm text-green-700">
                    Issue resolved. Dispensing verified normal across 20
                    consecutive shots. Case closed by Sarah Mitchell on Sep 15,
                    2026 at 11:35 AM.
                </p>
            </div>

            {/* Recommendations */}
            <div className="mt-6">
                <h3 className="text-sm font-semibold text-gray-900">
                    Recommendations
                </h3>

                <ul className="mt-2 space-y-1.5">
                    {[
                        "Implement weekly nozzle inspection schedule for Line A",
                        "Review material pot life management procedures",
                        "Consider nozzle tip replacement interval reduction from 30 to 21 days",
                    ].map((item, i) => (
                        <li
                            key={i}
                            className="flex items-start gap-2 text-sm text-gray-600"
                        >
                            <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500" />
                            {item}
                        </li>
                    ))}
                </ul>
            </div>
        </div>
    );
}
