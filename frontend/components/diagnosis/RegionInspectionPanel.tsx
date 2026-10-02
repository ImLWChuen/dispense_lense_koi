"use client";

import React from "react";
import {
    CheckCircle2,
    XCircle,
    AlertTriangle,
    HelpCircle,
    ShieldAlert,
    Layers,
    Info,
    Activity,
    Maximize2,
} from "lucide-react";
import type {
    ImageAnalysisMode,
    ImageAnalysisResponse,
    NormalizedROI,
    RoiInspectionStatus,
} from "@/types/image";
import {
    getEffectiveRoiStatus,
    matchMeasurementByRoiId,
    validateDepositOutline,
    findEmittedObservationsForRoi,
    projectCoverageSummary,
    formatMetricNumber,
    formatMetricPercent,
    type EffectiveRoiInspectionStatus,
} from "@/lib/region-inspection-view";

interface RegionInspectionPanelProps {
    rois: NormalizedROI[];
    result: ImageAnalysisResponse | null | undefined;
    selectedRoiId: string | null;
    onSelectRoi: (roiId: string | null) => void;
    mode: ImageAnalysisMode;
    mmPerPixel?: number | null;
    isStudioMode?: boolean;
    onOpenStudio?: () => void;
}

function StatusBadge({
    status,
    label,
}: {
    status: EffectiveRoiInspectionStatus;
    label: string;
}) {
    switch (status) {
        case "DETECTED":
            return (
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 dark:bg-emerald-950/40 px-2 py-0.5 text-xs font-semibold text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                    <CheckCircle2 size={12} className="text-emerald-600 shrink-0" />
                    <span>{label}</span>
                </span>
            );
        case "MISSING":
            return (
                <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 dark:bg-rose-950/40 px-2 py-0.5 text-xs font-semibold text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-800">
                    <XCircle size={12} className="text-rose-600 shrink-0" />
                    <span>{label}</span>
                </span>
            );
        case "UNASSESSED":
            return (
                <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 dark:bg-amber-950/40 px-2 py-0.5 text-xs font-semibold text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
                    <AlertTriangle size={12} className="text-amber-600 shrink-0" />
                    <span>{label}</span>
                </span>
            );
        case "UNAVAILABLE":
        default:
            return (
                <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 dark:bg-gray-800 px-2 py-0.5 text-xs font-semibold text-gray-600 dark:text-gray-300 border border-gray-200 dark:border-gray-700">
                    <HelpCircle size={12} className="text-gray-500 shrink-0" />
                    <span>{label}</span>
                </span>
            );
    }
}

export default function RegionInspectionPanel({
    rois,
    result,
    selectedRoiId,
    onSelectRoi,
    mode,
    mmPerPixel,
    isStudioMode = false,
    onOpenStudio,
}: RegionInspectionPanelProps) {
    if (!result) return null;

    const currentCoverage = projectCoverageSummary(result.aggregate_measurements);
    const referenceCoverage =
        mode === "REFERENCE_IMAGE" && result.reference_aggregate_measurements
            ? projectCoverageSummary(result.reference_aggregate_measurements)
            : null;

    // Active selected ROI object (fallback to first configured ROI if selection invalid)
    const effectiveSelectedId =
        selectedRoiId && rois.some((r) => r.roi_id === selectedRoiId)
            ? selectedRoiId
            : rois.length > 0
            ? rois[0].roi_id
            : null;

    const selectedRoi = rois.find((r) => r.roi_id === effectiveSelectedId) || null;
    const selectedMeasurement = selectedRoi
        ? matchMeasurementByRoiId(result.roi_measurements, selectedRoi.roi_id)
        : null;

    const selectedStatusInfo = getEffectiveRoiStatus(selectedMeasurement, true);
    const outlineResult = validateDepositOutline(
        selectedMeasurement?.deposit_outline_normalized,
        selectedMeasurement?.inspection_status
    );

    const emittedObservations = selectedRoi
        ? findEmittedObservationsForRoi(result.observations, selectedRoi.roi_id)
        : [];

    return (
        <div className="space-y-4 rounded-xl border border-gray-200 dark:border-gray-800 bg-gray-50/70 dark:bg-gray-900/40 p-3 sm:p-5">
            {/* Header: Title, Analysis Mode, and Studio Link */}
            <div className="flex items-center justify-between gap-2 border-b border-gray-200/80 dark:border-gray-800 pb-3">
                <div className="flex items-center gap-2">
                    <Activity size={16} className="text-[#6d5dfc] shrink-0" />
                    <span className="text-xs sm:text-sm font-bold text-gray-900 dark:text-gray-100">
                        Region Inspection Workbench
                    </span>
                    <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                            result.status === "CALIBRATED"
                                ? "bg-green-100 text-green-800 dark:bg-green-950/60 dark:text-green-300"
                                : result.status === "UNCALIBRATED"
                                ? "bg-blue-100 text-blue-800 dark:bg-blue-950/60 dark:text-blue-300"
                                : "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300"
                        }`}
                    >
                        {result.status}
                    </span>
                </div>

                {!isStudioMode && onOpenStudio && (
                    <button
                        type="button"
                        onClick={onOpenStudio}
                        className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-semibold text-[#5848e8] dark:text-[#a397ff] hover:bg-[#eeebff] dark:hover:bg-gray-800 transition"
                        title="Expand in Studio"
                    >
                        <Maximize2 size={13} />
                        <span>Studio</span>
                    </button>
                )}
            </div>

            {/* Analysis Gating & UNRELIABLE Status Notice */}
            {result.status === "UNRELIABLE" && (
                <div className="flex items-start gap-2 rounded-lg bg-amber-50 dark:bg-amber-950/50 p-3 text-xs text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
                    <ShieldAlert size={16} className="text-amber-600 shrink-0 mt-0.5" />
                    <div>
                        <p className="font-semibold">Inspection Quality Gate: UNRELIABLE</p>
                        <p className="mt-0.5 text-[11px] leading-relaxed">
                            Image contrast, lighting, or segmentation was ambiguous. Per-region inspection measurements are displayed below for technician review, but 0 score-bearing diagnostic observations are emitted for case creation.
                        </p>
                    </div>
                </div>
            )}

            {/* Top-Level Warnings */}
            {result.warnings.length > 0 && (
                <div className="space-y-1 rounded-lg bg-amber-50/60 dark:bg-amber-950/30 p-2.5 text-[11px] text-amber-800 dark:text-amber-300 border border-amber-200/60 dark:border-amber-800/40">
                    <p className="font-semibold text-amber-900 dark:text-amber-200">Analysis Warnings:</p>
                    {result.warnings.map((w, idx) => (
                        <div key={idx} className="flex items-start gap-1">
                            <span>&bull;</span>
                            <span>{w}</span>
                        </div>
                    ))}
                </div>
            )}

            {/* Coverage Summary Cards (Current vs Reference Separately) */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {/* Current Image Coverage Card */}
                <div className="rounded-lg border border-gray-200 dark:border-gray-800 bg-white dark:bg-[#141b29] p-3 text-xs shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="font-bold text-gray-800 dark:text-gray-200">
                            Current Image Inspection Coverage
                        </span>
                        <span
                            className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${
                                currentCoverage.statusText === "COMPLETE"
                                    ? "bg-green-100 text-green-800 dark:bg-green-950/50 dark:text-green-300"
                                    : currentCoverage.statusText === "PARTIAL"
                                    ? "bg-amber-100 text-amber-800 dark:bg-amber-950/50 dark:text-amber-300"
                                    : currentCoverage.statusText === "NONE"
                                    ? "bg-rose-100 text-rose-800 dark:bg-rose-950/50 dark:text-rose-300"
                                    : "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400"
                            }`}
                        >
                            {currentCoverage.statusText}
                        </span>
                    </div>
                    <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
                        <div className="rounded bg-gray-50 dark:bg-gray-800/60 p-2 text-center">
                            <span className="block text-[10px] text-gray-500">Expected Sites</span>
                            <span className="font-bold text-gray-900 dark:text-gray-100">
                                {currentCoverage.expectedText}
                            </span>
                        </div>
                        <div className="rounded bg-gray-50 dark:bg-gray-800/60 p-2 text-center">
                            <span className="block text-[10px] text-gray-500">Assessed Sites</span>
                            <span className="font-bold text-gray-900 dark:text-gray-100">
                                {currentCoverage.assessedText}
                            </span>
                        </div>
                    </div>
                    <p className="mt-1.5 text-[10px] text-gray-500 dark:text-gray-400">
                        COMPLETE coverage indicates all expected sites were evaluated; it does not assert within-specification material.
                    </p>
                </div>

                {/* Reference Image Coverage Card (Only in Reference Mode) */}
                {referenceCoverage ? (
                    <div className="rounded-lg border border-indigo-200 dark:border-indigo-900 bg-white dark:bg-[#141b29] p-3 text-xs shadow-2xs">
                        <div className="flex items-center justify-between">
                            <span className="font-bold text-indigo-950 dark:text-indigo-200">
                                Reference Image Coverage
                            </span>
                            <span
                                className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${
                                    referenceCoverage.statusText === "COMPLETE"
                                        ? "bg-green-100 text-green-800 dark:bg-green-950/50 dark:text-green-300"
                                        : referenceCoverage.statusText === "PARTIAL"
                                        ? "bg-amber-100 text-amber-800 dark:bg-amber-950/50 dark:text-amber-300"
                                        : referenceCoverage.statusText === "NONE"
                                        ? "bg-rose-100 text-rose-800 dark:bg-rose-950/50 dark:text-rose-300"
                                        : "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400"
                                }`}
                            >
                                {referenceCoverage.statusText}
                            </span>
                        </div>
                        <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
                            <div className="rounded bg-indigo-50/60 dark:bg-indigo-950/30 p-2 text-center">
                                <span className="block text-[10px] text-gray-500">Ref Expected</span>
                                <span className="font-bold text-indigo-900 dark:text-indigo-200">
                                    {referenceCoverage.expectedText}
                                </span>
                            </div>
                            <div className="rounded bg-indigo-50/60 dark:bg-indigo-950/30 p-2 text-center">
                                <span className="block text-[10px] text-gray-500">Ref Assessed</span>
                                <span className="font-bold text-indigo-900 dark:text-indigo-200">
                                    {referenceCoverage.assessedText}
                                </span>
                            </div>
                        </div>
                        <p className="mt-1.5 text-[10px] text-gray-500 dark:text-gray-400">
                            Evaluated independently on reference golden image; never reuses current image counts.
                        </p>
                    </div>
                ) : (
                    <div className="rounded-lg border border-gray-200 dark:border-gray-800 bg-white dark:bg-[#141b29] p-3 text-xs shadow-2xs flex flex-col justify-center">
                        <span className="font-bold text-gray-800 dark:text-gray-200">Aggregate Summary</span>
                        <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-center">
                            <div className="rounded bg-gray-50 dark:bg-gray-800/60 p-2">
                                <span className="block text-[10px] text-gray-500">Mean Coverage</span>
                                <span className="font-bold text-gray-900 dark:text-gray-100">
                                    {formatMetricPercent(result.aggregate_measurements.mean_coverage, 1, "Not available")}
                                </span>
                            </div>
                            <div className="rounded bg-gray-50 dark:bg-gray-800/60 p-2">
                                <span className="block text-[10px] text-gray-500">Size CV</span>
                                <span className="font-bold text-gray-900 dark:text-gray-100">
                                    {formatMetricPercent(result.aggregate_measurements.size_cv, 1, "Not available")}
                                </span>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* Selectable Expected Sites List / Selector */}
            <div className="space-y-2">
                <div className="flex items-center justify-between">
                    <span className="text-xs font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                        Expected Target Sites ({rois.length})
                    </span>
                    <span className="text-[11px] text-gray-400">Select site to view detailed inspection</span>
                </div>

                <div
                    role="tablist"
                    aria-label="Expected Target Sites"
                    className="flex flex-wrap gap-2"
                >
                    {rois.map((roi) => {
                        const m = matchMeasurementByRoiId(result.roi_measurements, roi.roi_id);
                        const statusInfo = getEffectiveRoiStatus(m, true);
                        const isSelected = roi.roi_id === effectiveSelectedId;

                        return (
                            <button
                                key={roi.roi_id}
                                role="tab"
                                type="button"
                                aria-selected={isSelected}
                                onClick={() => onSelectRoi(roi.roi_id)}
                                className={`inline-flex items-center gap-2 rounded-xl px-3 py-2 text-xs font-semibold transition cursor-pointer ${
                                    isSelected
                                        ? "bg-white dark:bg-[#1a2336] text-[#5848e8] dark:text-[#a397ff] border-2 border-[#5848e8] dark:border-[#a397ff] shadow-sm ring-2 ring-[#5848e8]/20"
                                        : "bg-white dark:bg-[#141b29] text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-800 hover:border-gray-300 dark:hover:border-gray-700"
                                }`}
                            >
                                <span className="font-bold">{roi.roi_id}</span>
                                <StatusBadge status={statusInfo.status} label={statusInfo.label} />
                            </button>
                        );
                    })}
                </div>
            </div>

            {/* Selected Site Details */}
            {selectedRoi && (
                <div className="space-y-3 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-[#141b29] p-3.5 sm:p-4 shadow-xs">
                    {/* Selected Site Header */}
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-100 dark:border-gray-800 pb-2.5">
                        <div className="flex items-center gap-2">
                            <span className="font-bold text-sm text-[#5848e8] dark:text-[#a397ff]">
                                {selectedRoi.roi_id}
                            </span>
                            <StatusBadge
                                status={selectedStatusInfo.status}
                                label={selectedStatusInfo.label}
                            />
                        </div>

                        {/* Deposit Outline Status Notice */}
                        <div className="text-[11px] font-medium">
                            {outlineResult.isValid ? (
                                <span className="inline-flex items-center gap-1 text-emerald-700 dark:text-emerald-400">
                                    <Layers size={13} />
                                    <span>Deposit Outline ({outlineResult.points.length} vertices rendered)</span>
                                </span>
                            ) : (
                                <span className="text-gray-400 dark:text-gray-500">
                                    Outline: {outlineResult.reason || "Unavailable"}
                                </span>
                            )}
                        </div>
                    </div>

                    <p className="text-[11px] text-gray-500 dark:text-gray-400 leading-relaxed">
                        {selectedStatusInfo.description}
                    </p>

                    {/* Measurements Display */}
                    {selectedMeasurement ? (
                        <div className="space-y-3 pt-1">
                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                                <div className="rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-800/40 p-2">
                                    <span className="block text-[10px] font-medium text-gray-500">Coverage Ratio</span>
                                    <span className="text-xs sm:text-sm font-bold text-gray-900 dark:text-gray-100">
                                        {formatMetricPercent(selectedMeasurement.coverage_ratio, 1)}
                                    </span>
                                </div>
                                <div className="rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-800/40 p-2">
                                    <span className="block text-[10px] font-medium text-gray-500">Overflow Ratio</span>
                                    <span className="text-xs sm:text-sm font-bold text-gray-900 dark:text-gray-100">
                                        {formatMetricPercent(selectedMeasurement.overflow_ratio, 1)}
                                    </span>
                                </div>
                                <div className="rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-800/40 p-2">
                                    <span className="block text-[10px] font-medium text-gray-500">Physical Diameter</span>
                                    <span className="text-xs sm:text-sm font-bold text-[#5848e8] dark:text-[#a397ff]">
                                        {selectedMeasurement.calibrated_diameter_mm !== null &&
                                        selectedMeasurement.calibrated_diameter_mm !== undefined &&
                                        Number.isFinite(selectedMeasurement.calibrated_diameter_mm)
                                            ? `${selectedMeasurement.calibrated_diameter_mm.toFixed(3)} mm`
                                            : "Not recorded"}
                                    </span>
                                </div>
                                <div className="rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-800/40 p-2">
                                    <span className="block text-[10px] font-medium text-gray-500">Equivalent Diameter</span>
                                    <span className="text-xs sm:text-sm font-bold text-gray-900 dark:text-gray-100">
                                        {formatMetricNumber(selectedMeasurement.equivalent_diameter_px, 1, " px")}
                                    </span>
                                </div>
                            </div>

                            {/* Secondary Geometric Morphology Table */}
                            <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-800">
                                <table className="w-full text-left text-xs min-w-[500px]">
                                    <thead>
                                        <tr className="border-b border-gray-200 dark:border-gray-800 bg-gray-50/70 dark:bg-gray-800/40 text-gray-500">
                                            <th className="py-1.5 px-2.5 font-medium">Area (Deposit / Tgt)</th>
                                            <th className="py-1.5 px-2.5 font-medium">Circularity</th>
                                            <th className="py-1.5 px-2.5 font-medium">Aspect Ratio</th>
                                            <th className="py-1.5 px-2.5 font-medium">Solidity</th>
                                            <th className="py-1.5 px-2.5 font-medium">Voids / Bubbles</th>
                                            <th className="py-1.5 px-2.5 font-medium">Seg Quality</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-gray-100 dark:divide-gray-800 text-gray-700 dark:text-gray-300">
                                        <tr>
                                            <td className="py-1.5 px-2.5">
                                                {formatMetricNumber(selectedMeasurement.deposit_area_px, 0, " px²")} / {formatMetricNumber(selectedMeasurement.target_area_px, 0, " px²")}
                                            </td>
                                            <td className="py-1.5 px-2.5">
                                                {formatMetricPercent(selectedMeasurement.circularity, 0)}
                                            </td>
                                            <td className="py-1.5 px-2.5 font-mono">
                                                {formatMetricNumber(selectedMeasurement.aspect_ratio, 2)}
                                            </td>
                                            <td className="py-1.5 px-2.5">
                                                {formatMetricPercent(selectedMeasurement.solidity, 0)}
                                            </td>
                                            <td className="py-1.5 px-2.5">
                                                void={formatMetricPercent(selectedMeasurement.hole_void_ratio, 1)}, b={(selectedMeasurement.bubble_count ?? 0)}
                                            </td>
                                            <td className="py-1.5 px-2.5 font-semibold text-emerald-600 dark:text-emerald-400">
                                                {formatMetricPercent(selectedMeasurement.segmentation_quality, 0)}
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>

                            {/* Inspection Warnings for Selected Site */}
                            {selectedMeasurement.inspection_warnings && selectedMeasurement.inspection_warnings.length > 0 && (
                                <div className="space-y-1 rounded-lg bg-amber-50 dark:bg-amber-950/40 p-2 text-xs text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
                                    <p className="font-semibold">Site Inspection Warnings:</p>
                                    {selectedMeasurement.inspection_warnings.map((w, idx) => (
                                        <div key={idx} className="flex items-start gap-1 text-[11px]">
                                            <span>&bull;</span>
                                            <span>{w}</span>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="rounded-lg bg-amber-50/60 dark:bg-amber-950/30 p-3 text-xs text-amber-800 dark:text-amber-300 border border-amber-200/60 dark:border-amber-800/40">
                            No measurement record was returned by the image analysis pipeline for expected site{" "}
                            <span className="font-semibold">{selectedRoi.roi_id}</span>.
                        </div>
                    )}

                    {/* Emitted Observations Affecting Selected Site */}
                    <div className="space-y-1.5 border-t border-gray-100 dark:border-gray-800 pt-2.5">
                        <span className="block text-[11px] font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                            Diagnostic Observations Affecting {selectedRoi.roi_id} ({emittedObservations.length})
                        </span>
                        {emittedObservations.length > 0 ? (
                            <div className="space-y-1.5">
                                {emittedObservations.map(({ observation, isGroupFinding }, idx) => (
                                    <div
                                        key={idx}
                                        className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-indigo-50/60 dark:bg-indigo-950/30 p-2 text-xs border border-indigo-100 dark:border-indigo-900"
                                    >
                                        <div className="flex items-center gap-2">
                                            <span className="font-bold text-[#5848e8] dark:text-[#a397ff]">
                                                {observation.observation_type} = {observation.value}
                                            </span>
                                            <span className="rounded bg-white dark:bg-gray-800 px-1.5 py-0.5 text-[10px] font-medium text-gray-600 dark:text-gray-300">
                                                conf: {observation.confidence != null ? `${(observation.confidence * 100).toFixed(0)}%` : "N/A"}
                                            </span>
                                        </div>
                                        {isGroupFinding ? (
                                            <span className="text-[11px] text-amber-800 dark:text-amber-300 font-medium">
                                                (Group comparison finding: listed regions are eligible; not an assertion of individual site failure)
                                            </span>
                                        ) : (
                                            <span className="text-[11px] text-emerald-700 dark:text-emerald-300 font-medium">
                                                (Individual region finding)
                                            </span>
                                        )}
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <p className="text-xs text-gray-400 italic">
                                No diagnostic defect findings emitted for this region.
                            </p>
                        )}
                    </div>
                </div>
            )}

            {/* Terminology and Semantic Legend */}
            <div className="rounded-lg bg-gray-100/70 dark:bg-gray-800/50 p-2.5 text-[11px] text-gray-600 dark:text-gray-400 space-y-1 border border-gray-200/60 dark:border-gray-700/60">
                <div className="flex items-center gap-1 font-semibold text-gray-800 dark:text-gray-300">
                    <Info size={13} className="text-[#6d5dfc]" />
                    <span>Inspection Semantic Reference:</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-0.5 text-[10px]">
                    <div>
                        <span className="font-semibold text-emerald-700 dark:text-emerald-400">Material detected:</span>{" "}
                        Deposit located at site; does not imply within process limits.
                    </div>
                    <div>
                        <span className="font-semibold text-rose-700 dark:text-rose-400">Expected deposit missing:</span>{" "}
                        Zero material detected within the expected boundary.
                    </div>
                    <div>
                        <span className="font-semibold text-amber-700 dark:text-amber-400">Not assessed:</span>{" "}
                        Expected site omitted or not assessed by inspection pipeline.
                    </div>
                    <div>
                        <span className="font-semibold text-green-700 dark:text-green-400">COMPLETE coverage:</span>{" "}
                        All expected sites were assessed; not an assertion of zero defects.
                    </div>
                </div>
            </div>
        </div>
    );
}
