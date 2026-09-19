"use client";

import { Scan, CheckCircle2, AlertCircle } from "lucide-react";
import { CaseObservationResponse } from "@/types/api";

interface ImageAnalysisProps {
    observations?: CaseObservationResponse[];
}

export default function ImageAnalysis({ observations = [] }: ImageAnalysisProps) {
    const imageObservations = observations.filter((obs) => obs.source === "IMAGE");

    return (
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
            <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#eeebff] text-[#6d5dfc]">
                    <Scan size={20} />
                </div>

                <div>
                    <h2 className="text-base font-semibold text-gray-900">
                        Image Analysis Evidence
                    </h2>

                    <p className="text-xs text-gray-500">
                        Persisted calibrated visual defect observations
                    </p>
                </div>
            </div>

            {imageObservations.length === 0 ? (
                <div className="mt-5 rounded-xl border border-dashed border-gray-200 bg-gray-50/50 p-6 text-center">
                    <p className="text-xs text-gray-500 italic">
                        No image-derived evidence recorded for this case.
                    </p>
                </div>
            ) : (
                <div className="mt-5 space-y-3">
                    {imageObservations.map((obs) => {
                        const meta = (obs.metadata || {}) as Record<string, unknown>;
                        const roiId = typeof meta.roi_id === "string" ? meta.roi_id : null;
                        const mode = typeof meta.mode === "string" ? meta.mode : null;
                        const coverageRatio = typeof meta.coverage_ratio === "number" ? meta.coverage_ratio : null;
                        const overflowRatio = typeof meta.overflow_ratio === "number" ? meta.overflow_ratio : null;
                        const referenceRatio = typeof meta.reference_ratio === "number" ? meta.reference_ratio : null;
                        const equivDiameterPx = typeof meta.equivalent_diameter_px === "number" ? meta.equivalent_diameter_px : null;
                        const calibratedDiameterMm =
                            typeof meta.calibrated_diameter_mm === "number" && isFinite(meta.calibrated_diameter_mm)
                                ? meta.calibrated_diameter_mm
                                : null;
                        const segQuality = typeof meta.segmentation_quality === "number" ? meta.segmentation_quality : null;
                        const sizeCv = typeof meta.size_cv === "number" ? meta.size_cv : null;
                        const warnings = Array.isArray(meta.warnings)
                            ? (meta.warnings.filter((w) => typeof w === "string") as string[])
                            : [];

                        return (
                            <div
                                key={obs.id || obs.observation_id}
                                className="rounded-xl border border-gray-200 bg-gray-50/40 p-4 text-xs space-y-2.5"
                            >
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <CheckCircle2 size={15} className="text-green-600 shrink-0" />
                                        <span className="font-semibold text-gray-900">
                                            {obs.observation_type.replace(/_/g, " ")}
                                        </span>
                                    </div>

                                    <span className="rounded-full bg-[#eeebff] px-2.5 py-0.5 font-bold text-[#5848e8]">
                                        {obs.value}
                                    </span>
                                </div>

                                {obs.original_text && (
                                    <p className="text-gray-600 italic">
                                        &ldquo;{obs.original_text}&rdquo;
                                    </p>
                                )}

                                {/* Metadata Breakdown */}
                                <div className="grid grid-cols-2 gap-2 rounded-lg border border-gray-100 bg-white p-2.5 text-[11px] text-gray-700">
                                    {roiId && (
                                        <div>
                                            <span className="text-gray-400">ROI Target: </span>
                                            <span className="font-semibold text-[#5848e8]">{roiId}</span>
                                        </div>
                                    )}

                                    {mode && (
                                        <div>
                                            <span className="text-gray-400">Mode: </span>
                                            <span className="font-medium text-gray-800">{mode}</span>
                                        </div>
                                    )}

                                    {coverageRatio !== null && (
                                        <div>
                                            <span className="text-gray-400">Coverage Ratio: </span>
                                            <span className="font-medium text-gray-800">
                                                {(coverageRatio * 100).toFixed(1)}%
                                            </span>
                                        </div>
                                    )}

                                    {overflowRatio !== null && (
                                        <div>
                                            <span className="text-gray-400">Overflow Ratio: </span>
                                            <span className="font-medium text-gray-800">
                                                {(overflowRatio * 100).toFixed(1)}%
                                            </span>
                                        </div>
                                    )}

                                    {referenceRatio !== null && (
                                        <div>
                                            <span className="text-gray-400">Ref Ratio: </span>
                                            <span className="font-medium text-gray-800">
                                                {referenceRatio.toFixed(3)}
                                            </span>
                                        </div>
                                    )}

                                    {equivDiameterPx !== null && (
                                        <div>
                                            <span className="text-gray-400">Equiv Diameter: </span>
                                            <span className="font-medium text-gray-800">
                                                {equivDiameterPx.toFixed(1)} px
                                            </span>
                                        </div>
                                    )}

                                    {calibratedDiameterMm !== null && (
                                        <div>
                                            <span className="text-gray-400">Physical Diameter: </span>
                                            <span className="font-semibold text-green-700">
                                                {calibratedDiameterMm.toFixed(3)} mm
                                            </span>
                                        </div>
                                    )}

                                    {segQuality !== null && (
                                        <div>
                                            <span className="text-gray-400">Seg Quality: </span>
                                            <span className="font-medium text-gray-800">
                                                {(segQuality * 100).toFixed(0)}%
                                            </span>
                                        </div>
                                    )}

                                    {sizeCv !== null && (
                                        <div>
                                            <span className="text-gray-400">Size CV: </span>
                                            <span className="font-medium text-gray-800">
                                                {(sizeCv * 100).toFixed(1)}%
                                            </span>
                                        </div>
                                    )}
                                </div>

                                {warnings.length > 0 && (
                                    <div className="flex items-start gap-1.5 text-[10px] text-amber-700">
                                        <AlertCircle size={12} className="shrink-0 text-amber-600 mt-0.5" />
                                        <div>{warnings.join("; ")}</div>
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}

            <p className="mt-4 text-[10px] text-gray-400">
                Raw image files are not retained in durable storage. Visual evidence is preserved losslessly as resolution-independent geometric metadata.
            </p>
        </div>
    );
}
