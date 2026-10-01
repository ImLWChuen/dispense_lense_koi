"use client";

import { Scan } from "lucide-react";
import { CaseObservationResponse } from "@/types/api";
import { projectSavedRegionEvidence } from "@/lib/saved-region-evidence";
import SavedRegionEvidence from "./SavedRegionEvidence";

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
                <div className="mt-5 space-y-4">
                    {imageObservations.map((obs, idx) => {
                        const view = projectSavedRegionEvidence(obs, idx);
                        return <SavedRegionEvidence key={view.id} observation={view} />;
                    })}
                </div>
            )}

            <p className="mt-4 text-[10px] text-gray-400">
                Raw image files and polygon outlines are not retained in durable storage. Visual evidence is preserved as quantitative scalar defect measurements, target ROI identifiers, and threshold limit snapshots.
            </p>
        </div>
    );
}
