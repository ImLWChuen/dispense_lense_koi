"use client";

import { useState } from "react";
import {
    CheckCircle2,
    AlertCircle,
    Layers,
    ChevronDown,
    ChevronUp,
    Sliders,
    Info,
} from "lucide-react";
import {
    SavedImageObservationView,
    SavedRegionSiteSnapshot,
    formatMetricPercent,
    formatMetricNumber,
    formatPhysicalDiameter,
} from "@/lib/saved-region-evidence";

interface SavedRegionEvidenceProps {
    observation: SavedImageObservationView;
}

export default function SavedRegionEvidence({ observation: obs }: SavedRegionEvidenceProps) {
    const [selectedSnapshotIndex, setSelectedSnapshotIndex] = useState<number>(0);
    const [showAllAffected, setShowAllAffected] = useState<boolean>(false);
    const [showAllSnapshots, setShowAllSnapshots] = useState<boolean>(false);

    const activeSnapshot: SavedRegionSiteSnapshot | null =
        obs.snapshots.length > 0
            ? obs.snapshots[Math.min(selectedSnapshotIndex, obs.snapshots.length - 1)]
            : null;

    const maxInitialAffected = 10;
    const hasManyAffected = obs.affectedRoiIds.length > maxInitialAffected;
    const displayedAffectedIds = showAllAffected
        ? obs.affectedRoiIds
        : obs.affectedRoiIds.slice(0, maxInitialAffected);

    const maxInitialSnapshots = 12;
    const hasManySnapshots = obs.snapshots.length > maxInitialSnapshots;
    const displayedSnapshots = showAllSnapshots
        ? obs.snapshots
        : obs.snapshots.slice(0, maxInitialSnapshots);

    const handleKeyDown = (e: React.KeyboardEvent, index: number) => {
        if (displayedSnapshots.length === 0) return;
        if (e.key === "ArrowRight") {
            e.preventDefault();
            const next = (index + 1) % displayedSnapshots.length;
            setSelectedSnapshotIndex(next);
        } else if (e.key === "ArrowLeft") {
            e.preventDefault();
            const prev = (index - 1 + displayedSnapshots.length) % displayedSnapshots.length;
            setSelectedSnapshotIndex(prev);
        } else if (e.key === "Home") {
            e.preventDefault();
            setSelectedSnapshotIndex(0);
        } else if (e.key === "End") {
            e.preventDefault();
            setSelectedSnapshotIndex(displayedSnapshots.length - 1);
        }
    };

    return (
        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-gray-50/40 dark:bg-gray-900/40 p-4 sm:p-5 text-xs space-y-4">
            {/* 1. Observation Header */}
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-200/80 dark:border-gray-800 pb-3">
                <div className="flex items-center gap-2 min-w-0">
                    <CheckCircle2 size={16} className="text-green-600 shrink-0" />
                    <span className="font-bold text-sm text-gray-900 dark:text-gray-100 truncate">
                        {obs.observationType.replace(/_/g, " ")}
                    </span>
                    <span className="rounded-full bg-[#eeebff] dark:bg-[#6d5dfc]/20 px-2.5 py-0.5 font-bold text-[#5848e8] dark:text-[#a397ff] shrink-0">
                        {obs.value}
                    </span>
                </div>

                <div className="flex items-center gap-1.5 shrink-0 flex-wrap">
                    {/* Scope Badge */}
                    <span
                        className={`rounded px-2 py-0.5 text-[10px] font-bold ${
                            obs.scope === "individual_regions"
                                ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300"
                                : obs.scope === "comparison_group"
                                ? "bg-purple-100 text-purple-800 dark:bg-purple-950/60 dark:text-purple-300"
                                : "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300"
                        }`}
                        title={obs.scopeDescription}
                    >
                        {obs.scopeLabel}
                    </span>

                    {obs.firstSeenRevision && (
                        <span className="rounded bg-gray-100 dark:bg-gray-800 px-2 py-0.5 text-[10px] font-medium text-gray-600 dark:text-gray-400">
                            Rev {obs.firstSeenRevision}
                        </span>
                    )}
                </div>
            </div>

            {/* Original Text / Statement Context */}
            {obs.originalText && (
                <p className="text-gray-600 dark:text-gray-400 italic">
                    &ldquo;{obs.originalText}&rdquo;
                </p>
            )}

            {/* Scope Explanation Note */}
            <div className="flex items-start gap-1.5 rounded-lg bg-white/70 dark:bg-gray-800/50 p-2.5 text-[11px] text-gray-600 dark:text-gray-400 border border-gray-100 dark:border-gray-800">
                <Info size={13} className="text-[#6d5dfc] shrink-0 mt-0.5" />
                <span className="leading-relaxed">{obs.scopeDescription}</span>
            </div>

            {/* 2. Affected Sites & Applied Limits Summary Bar */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {/* Affected Sites Card */}
                <div className="rounded-lg border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-800/40 p-3 space-y-2">
                    <div className="flex items-center justify-between">
                        <span className="font-semibold text-gray-800 dark:text-gray-200">
                            Recorded Affected Sites ({obs.affectedRoiIds.length})
                        </span>
                        {hasManyAffected && (
                            <button
                                type="button"
                                onClick={() => setShowAllAffected(!showAllAffected)}
                                className="text-[11px] font-medium text-[#5848e8] dark:text-[#a397ff] hover:underline"
                            >
                                {showAllAffected ? "Show less" : `Show all ${obs.affectedRoiIds.length}`}
                            </button>
                        )}
                    </div>

                    {obs.affectedRoiIds.length === 0 ? (
                        <p className="text-[11px] text-gray-400 italic">No specific site IDs recorded.</p>
                    ) : (
                        <div className="flex flex-wrap gap-1.5">
                            {displayedAffectedIds.map((id, idx) => (
                                <span
                                    key={`aff-${id}-${idx}`}
                                    className="rounded-md bg-gray-100 dark:bg-gray-700/60 px-2 py-0.5 text-[11px] font-mono text-gray-800 dark:text-gray-200 break-all"
                                >
                                    {id}
                                </span>
                            ))}
                        </div>
                    )}

                    {obs.unmeasuredAffectedIds.length > 0 && (
                        <p className="text-[10px] text-amber-600 dark:text-amber-400">
                            Note: Per-site snapshot not stored for: {obs.unmeasuredAffectedIds.join(", ")}
                        </p>
                    )}
                </div>

                {/* Applied Limits Snapshot Card */}
                <div className="rounded-lg border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-800/40 p-3 space-y-2">
                    <div className="flex items-center gap-1.5">
                        <Sliders size={13} className="text-[#6d5dfc] shrink-0" />
                        <span className="font-semibold text-gray-800 dark:text-gray-200">
                            Applied Limits Snapshot
                        </span>
                    </div>

                    {obs.appliedLimits.length === 0 ? (
                        <p className="text-[11px] text-gray-400 italic">
                            None recorded or not specified for this observation.
                        </p>
                    ) : (
                        <div className="grid grid-cols-2 gap-x-2 gap-y-1 text-[11px]">
                            {obs.appliedLimits.map((limit) => (
                                <div key={limit.key} className="flex items-baseline justify-between gap-1">
                                    <span className="text-gray-500 dark:text-gray-400 truncate" title={limit.label}>
                                        {limit.label}:
                                    </span>
                                    <span className="font-mono font-semibold text-gray-800 dark:text-gray-200 shrink-0">
                                        {limit.valueStr}
                                    </span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>

            {/* 3. Per-Region Evidence Snapshots */}
            {obs.hasSnapshots && (
                <div className="space-y-3 pt-1">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <Layers size={14} className="text-[#6d5dfc] shrink-0" />
                            <span className="font-semibold text-gray-900 dark:text-gray-100">
                                Persisted Per-Region Measurements ({obs.snapshots.length} sites)
                            </span>
                        </div>
                        {hasManySnapshots && (
                            <button
                                type="button"
                                onClick={() => setShowAllSnapshots(!showAllSnapshots)}
                                className="text-[11px] font-medium text-[#5848e8] dark:text-[#a397ff] hover:underline"
                            >
                                {showAllSnapshots ? "Show fewer tabs" : `Show all ${obs.snapshots.length} tabs`}
                            </button>
                        )}
                    </div>

                    {/* Site Selection Tabs */}
                    <div
                        role="tablist"
                        aria-label="Persisted Target Sites"
                        className="flex flex-wrap gap-1.5 p-1 bg-gray-200/60 dark:bg-gray-800/60 rounded-xl"
                    >
                        {displayedSnapshots.map((snap, idx) => {
                            const isSelected = idx === selectedSnapshotIndex;
                            const status = snap.currentMeasurements?.inspection_status || "UNKNOWN";
                            return (
                                <button
                                    key={snap.key}
                                    id={`saved-tab-${snap.roi_id}`}
                                    role="tab"
                                    type="button"
                                    aria-selected={isSelected}
                                    aria-controls={`saved-tabpanel-${snap.roi_id}`}
                                    tabIndex={0}
                                    onClick={() => setSelectedSnapshotIndex(idx)}
                                    onKeyDown={(e) => handleKeyDown(e, idx)}
                                    className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-semibold transition cursor-pointer ${
                                        isSelected
                                            ? "bg-white dark:bg-[#141b29] text-[#5848e8] dark:text-[#a397ff] shadow-xs ring-1 ring-black/5 dark:ring-white/10"
                                            : "text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 hover:bg-white/40"
                                    }`}
                                >
                                    <span className="font-bold truncate max-w-[120px]">{snap.roi_id}</span>
                                    <span
                                        className={`rounded px-1.5 py-0.2 text-[9px] font-bold ${
                                            status === "DETECTED"
                                                ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300"
                                                : status === "MISSING"
                                                ? "bg-red-100 text-red-800 dark:bg-red-950/60 dark:text-red-300"
                                                : status === "UNASSESSED"
                                                ? "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300"
                                                : "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300"
                                        }`}
                                    >
                                        {status}
                                    </span>
                                </button>
                            );
                        })}
                    </div>

                    {/* Active Site Details */}
                    {activeSnapshot && (
                        <div
                            role="tabpanel"
                            id={`saved-tabpanel-${activeSnapshot.roi_id}`}
                            aria-labelledby={`saved-tab-${activeSnapshot.roi_id}`}
                            className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-[#141b29] p-3.5 sm:p-4 space-y-3.5 shadow-2xs"
                        >
                            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-100 dark:border-gray-800 pb-2.5">
                                <div className="flex items-center gap-2">
                                    <span className="font-bold text-sm text-[#5848e8] dark:text-[#a397ff]">
                                        Site: {activeSnapshot.roi_id}
                                    </span>
                                    <span
                                        className={`rounded px-2 py-0.5 text-[10px] font-bold ${
                                            activeSnapshot.currentMeasurements?.inspection_status === "DETECTED"
                                                ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300"
                                                : activeSnapshot.currentMeasurements?.inspection_status === "MISSING"
                                                ? "bg-red-100 text-red-800 dark:bg-red-950/60 dark:text-red-300"
                                                : activeSnapshot.currentMeasurements?.inspection_status === "UNASSESSED"
                                                ? "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300"
                                                : "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300"
                                        }`}
                                    >
                                        {activeSnapshot.currentMeasurements?.inspection_status || "UNKNOWN"}
                                    </span>
                                </div>

                                <span className="text-[11px] text-gray-400 dark:text-gray-500">
                                    15-parameter scalar evidence snapshot
                                </span>
                            </div>

                            {activeSnapshot.isMalformed ? (
                                <div className="rounded-lg bg-amber-50 dark:bg-amber-950/40 p-3 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
                                    <p className="font-semibold">Malformed Snapshot Entry</p>
                                    <p className="mt-0.5 text-[11px]">
                                        {activeSnapshot.malformedReason || "Measurement record could not be parsed safely."}
                                    </p>
                                </div>
                            ) : (
                                <>
                                    {/* Primary 4-metric grid */}
                                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                                        <div className="rounded-lg border border-gray-100 dark:border-gray-800 bg-gray-50/80 dark:bg-gray-800/40 p-2.5">
                                            <span className="block text-[10px] font-medium text-gray-500">Coverage Ratio</span>
                                            <span className="text-xs sm:text-sm font-bold text-gray-900 dark:text-gray-100">
                                                {formatMetricPercent(activeSnapshot.currentMeasurements?.coverage_ratio, 1)}
                                            </span>
                                        </div>

                                        <div className="rounded-lg border border-gray-100 dark:border-gray-800 bg-gray-50/80 dark:bg-gray-800/40 p-2.5">
                                            <span className="block text-[10px] font-medium text-gray-500">Overflow Ratio</span>
                                            <span className="text-xs sm:text-sm font-bold text-gray-900 dark:text-gray-100">
                                                {formatMetricPercent(activeSnapshot.currentMeasurements?.overflow_ratio, 1)}
                                            </span>
                                        </div>

                                        <div className="rounded-lg border border-gray-100 dark:border-gray-800 bg-gray-50/80 dark:bg-gray-800/40 p-2.5">
                                            <span className="block text-[10px] font-medium text-gray-500">Equivalent Diameter</span>
                                            <span className="text-xs sm:text-sm font-bold text-gray-900 dark:text-gray-100">
                                                {formatMetricNumber(activeSnapshot.currentMeasurements?.equivalent_diameter_px, 1, " px")}
                                            </span>
                                        </div>

                                        <div className="rounded-lg border border-gray-100 dark:border-gray-800 bg-gray-50/80 dark:bg-gray-800/40 p-2.5">
                                            <span className="block text-[10px] font-medium text-gray-500">Physical Diameter</span>
                                            <span className="text-xs sm:text-sm font-bold text-[#5848e8] dark:text-[#a397ff]">
                                                {formatPhysicalDiameter(activeSnapshot.currentMeasurements?.calibrated_diameter_mm)}
                                            </span>
                                        </div>
                                    </div>

                                    {/* Secondary Morphology Details Table */}
                                    <div className="overflow-x-auto rounded-lg border border-gray-100 dark:border-gray-800">
                                        <table className="w-full text-left text-[11px] min-w-[500px]">
                                            <thead>
                                                <tr className="border-b border-gray-100 dark:border-gray-800 bg-gray-50/70 dark:bg-gray-800/40 text-gray-500">
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
                                                        {formatMetricNumber(activeSnapshot.currentMeasurements?.deposit_area_px, 0, " px²")} /{" "}
                                                        {formatMetricNumber(activeSnapshot.currentMeasurements?.target_area_px, 0, " px²")}
                                                    </td>
                                                    <td className="py-1.5 px-2.5">
                                                        {formatMetricPercent(activeSnapshot.currentMeasurements?.circularity, 0)}
                                                    </td>
                                                    <td className="py-1.5 px-2.5">
                                                        {formatMetricNumber(activeSnapshot.currentMeasurements?.aspect_ratio, 2)}
                                                    </td>
                                                    <td className="py-1.5 px-2.5">
                                                        {formatMetricPercent(activeSnapshot.currentMeasurements?.solidity, 0)}
                                                    </td>
                                                    <td className="py-1.5 px-2.5">
                                                        void={formatMetricPercent(activeSnapshot.currentMeasurements?.hole_void_ratio, 1)},{" "}
                                                        b={formatMetricNumber(activeSnapshot.currentMeasurements?.bubble_count, 0)}
                                                    </td>
                                                    <td className="py-1.5 px-2.5 font-semibold">
                                                        {formatMetricPercent(activeSnapshot.currentMeasurements?.segmentation_quality, 0)}
                                                    </td>
                                                </tr>
                                            </tbody>
                                        </table>
                                    </div>

                                    {/* Reference Measurements Section */}
                                    <div className="pt-1 border-t border-gray-100 dark:border-gray-800">
                                        <div className="flex items-center justify-between text-[11px]">
                                            <span className="font-semibold text-gray-700 dark:text-gray-300">
                                                Reference Measurements:
                                            </span>
                                            {activeSnapshot.hasReference ? (
                                                <span className="font-mono text-emerald-700 dark:text-emerald-400">
                                                    Recorded (Golden Reference Mode)
                                                </span>
                                            ) : (
                                                <span className="text-gray-400 italic">
                                                    Not recorded (single-image inspection or unmatched reference site)
                                                </span>
                                            )}
                                        </div>

                                        {activeSnapshot.hasReference && activeSnapshot.referenceMeasurements && (
                                            <div className="mt-2 grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] bg-slate-50 dark:bg-slate-900/40 p-2.5 rounded-lg border border-slate-200 dark:border-slate-800">
                                                <div>
                                                    <span className="text-gray-500">Ref Status: </span>
                                                    <span className="font-semibold">{activeSnapshot.referenceMeasurements.inspection_status}</span>
                                                </div>
                                                <div>
                                                    <span className="text-gray-500">Ref Area: </span>
                                                    <span className="font-semibold">{formatMetricNumber(activeSnapshot.referenceMeasurements.deposit_area_px, 0, " px²")}</span>
                                                </div>
                                                <div>
                                                    <span className="text-gray-500">Ref Coverage: </span>
                                                    <span className="font-semibold">{formatMetricPercent(activeSnapshot.referenceMeasurements.coverage_ratio, 1)}</span>
                                                </div>
                                                <div>
                                                    <span className="text-gray-500">Ref Equiv Diam: </span>
                                                    <span className="font-semibold">{formatMetricNumber(activeSnapshot.referenceMeasurements.equivalent_diameter_px, 1, " px")}</span>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </>
                            )}
                        </div>
                    )}
                </div>
            )}

            {/* 4. Legacy Only Observation Fallback */}
            {obs.isLegacyOnly && obs.legacySummary && (
                <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800/30 p-3.5 sm:p-4 space-y-2">
                    <div className="flex items-center justify-between border-b border-gray-100 dark:border-gray-800 pb-2">
                        <span className="font-semibold text-gray-800 dark:text-gray-200">
                            Legacy Evidence Summary (First Triggering Site Metadata)
                        </span>
                        <span className="rounded bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 px-1.5 py-0.5 text-[10px] font-bold">
                            Legacy Format
                        </span>
                    </div>

                    <p className="text-[11px] text-gray-500 italic">
                        This observation was saved prior to multi-site evidence snapshots. Measurements below represent the first triggering/affected site only.
                    </p>

                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-[11px] pt-1">
                        {obs.legacySummary.status && (
                            <div>
                                <span className="text-gray-400">Status: </span>
                                <span className="font-semibold text-gray-800 dark:text-gray-200">{obs.legacySummary.status}</span>
                            </div>
                        )}
                        {obs.legacySummary.roiId && (
                            <div>
                                <span className="text-gray-400">ROI Target: </span>
                                <span className="font-semibold text-[#5848e8] dark:text-[#a397ff]">{obs.legacySummary.roiId}</span>
                            </div>
                        )}
                        {obs.legacySummary.mode && (
                            <div>
                                <span className="text-gray-400">Mode: </span>
                                <span className="font-medium text-gray-800 dark:text-gray-200">{obs.legacySummary.mode}</span>
                            </div>
                        )}
                        {obs.legacySummary.coverageRatio !== null && (
                            <div>
                                <span className="text-gray-400">Coverage Ratio: </span>
                                <span className="font-medium text-gray-800 dark:text-gray-200">{formatMetricPercent(obs.legacySummary.coverageRatio, 1)}</span>
                            </div>
                        )}
                        {obs.legacySummary.equivDiameterPx !== null && (
                            <div>
                                <span className="text-gray-400">Equiv Diameter: </span>
                                <span className="font-medium text-gray-800 dark:text-gray-200">{formatMetricNumber(obs.legacySummary.equivDiameterPx, 1, " px")}</span>
                            </div>
                        )}
                        {obs.legacySummary.calibratedDiameterMm !== null && (
                            <div>
                                <span className="text-gray-400">Physical Diameter: </span>
                                <span className="font-semibold text-emerald-700 dark:text-emerald-400">{formatPhysicalDiameter(obs.legacySummary.calibratedDiameterMm)}</span>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* If neither snapshots nor legacy summary exist */}
            {!obs.hasSnapshots && !obs.isLegacyOnly && (
                <div className="rounded-lg bg-gray-100/60 dark:bg-gray-800/40 p-3 text-center text-gray-400 text-[11px] italic">
                    Detailed per-region evidence was not recorded for this observation.
                </div>
            )}

            {/* 5. Warnings */}
            {obs.warnings.length > 0 && (
                <div className="flex items-start gap-1.5 rounded-lg bg-amber-50/80 dark:bg-amber-950/30 p-2.5 text-[10px] text-amber-700 dark:text-amber-400 border border-amber-200/60 dark:border-amber-800/40">
                    <AlertCircle size={13} className="shrink-0 text-amber-600 dark:text-amber-400 mt-0.5" />
                    <div>{obs.warnings.join("; ")}</div>
                </div>
            )}
        </div>
    );
}
