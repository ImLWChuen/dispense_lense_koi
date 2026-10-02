"use client";

import { useState, useRef, useId, useEffect } from "react";
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
    SavedScalarMeasurements,
    formatMetricPercent,
    formatMetricNumber,
    formatPhysicalDiameter,
} from "@/lib/saved-region-evidence";

interface SavedRegionEvidenceProps {
    observation: SavedImageObservationView;
}

function ScalarMetricsView({
    measurements: m,
    variant = "current",
}: {
    measurements: SavedScalarMeasurements | null;
    variant?: "current" | "reference";
}) {
    if (!m) {
        return (
            <p className="text-[11px] text-gray-400 italic">
                {variant === "reference"
                    ? "No reference measurement recorded for this site."
                    : "No scalar measurements recorded."}
            </p>
        );
    }

    const isRef = variant === "reference";

    return (
        <div className="space-y-2.5">
            {/* Primary 4-metric grid */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                <div
                    className={`rounded-lg border p-2.5 ${
                        isRef
                            ? "border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50"
                            : "border-gray-100 dark:border-gray-800 bg-gray-50/80 dark:bg-gray-800/40"
                    }`}
                >
                    <span className="block text-[10px] font-medium text-gray-500">Coverage Ratio</span>
                    <span className="text-xs sm:text-sm font-bold text-gray-900 dark:text-gray-100">
                        {formatMetricPercent(m.coverage_ratio, 1)}
                    </span>
                </div>

                <div
                    className={`rounded-lg border p-2.5 ${
                        isRef
                            ? "border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50"
                            : "border-gray-100 dark:border-gray-800 bg-gray-50/80 dark:bg-gray-800/40"
                    }`}
                >
                    <span className="block text-[10px] font-medium text-gray-500">Overflow Ratio</span>
                    <span className="text-xs sm:text-sm font-bold text-gray-900 dark:text-gray-100">
                        {formatMetricPercent(m.overflow_ratio, 1)}
                    </span>
                </div>

                <div
                    className={`rounded-lg border p-2.5 ${
                        isRef
                            ? "border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50"
                            : "border-gray-100 dark:border-gray-800 bg-gray-50/80 dark:bg-gray-800/40"
                    }`}
                >
                    <span className="block text-[10px] font-medium text-gray-500">Equivalent Diameter</span>
                    <span className="text-xs sm:text-sm font-bold text-gray-900 dark:text-gray-100">
                        {formatMetricNumber(m.equivalent_diameter_px, 1, " px")}
                    </span>
                </div>

                <div
                    className={`rounded-lg border p-2.5 ${
                        isRef
                            ? "border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50"
                            : "border-gray-100 dark:border-gray-800 bg-gray-50/80 dark:bg-gray-800/40"
                    }`}
                >
                    <span className="block text-[10px] font-medium text-gray-500">Physical Diameter</span>
                    <span className="text-xs sm:text-sm font-bold text-[#5848e8] dark:text-[#a397ff]">
                        {formatPhysicalDiameter(m.calibrated_diameter_mm)}
                    </span>
                </div>
            </div>

            {/* Secondary Morphology & Quality Details Table */}
            <div
                className={`overflow-x-auto rounded-lg border ${
                    isRef
                        ? "border-slate-200 dark:border-slate-700"
                        : "border-gray-100 dark:border-gray-800"
                }`}
            >
                <table className="w-full text-left text-[11px] min-w-[520px]">
                    <thead>
                        <tr
                            className={`border-b text-gray-500 ${
                                isRef
                                    ? "border-slate-200 dark:border-slate-700 bg-slate-100/60 dark:bg-slate-800/60"
                                    : "border-gray-100 dark:border-gray-800 bg-gray-50/70 dark:bg-gray-800/40"
                            }`}
                        >
                            <th className="py-1.5 px-2.5 font-medium">Area (Deposit / Tgt)</th>
                            <th className="py-1.5 px-2.5 font-medium">Circularity</th>
                            <th className="py-1.5 px-2.5 font-medium">Aspect Ratio</th>
                            <th className="py-1.5 px-2.5 font-medium">Solidity</th>
                            <th className="py-1.5 px-2.5 font-medium">Convexity</th>
                            <th className="py-1.5 px-2.5 font-medium">Voids / Bubbles</th>
                            <th className="py-1.5 px-2.5 font-medium">Seg Quality</th>
                        </tr>
                    </thead>
                    <tbody
                        className={`divide-y text-gray-700 dark:text-gray-300 ${
                            isRef
                                ? "divide-slate-200 dark:divide-slate-700 bg-white/60 dark:bg-slate-900/30"
                                : "divide-gray-100 dark:divide-gray-800"
                        }`}
                    >
                        <tr>
                            <td className="py-1.5 px-2.5">
                                {formatMetricNumber(m.deposit_area_px, 0, " px²")} /{" "}
                                {formatMetricNumber(m.target_area_px, 0, " px²")}
                            </td>
                            <td className="py-1.5 px-2.5">
                                {formatMetricPercent(m.circularity, 0)}
                            </td>
                            <td className="py-1.5 px-2.5">
                                {formatMetricNumber(m.aspect_ratio, 2)}
                            </td>
                            <td className="py-1.5 px-2.5">
                                {formatMetricPercent(m.solidity, 0)}
                            </td>
                            <td className="py-1.5 px-2.5">
                                {formatMetricPercent(m.convexity, 0)}
                            </td>
                            <td className="py-1.5 px-2.5">
                                void={formatMetricPercent(m.hole_void_ratio, 1)},{" "}
                                bubbles={formatMetricNumber(m.bubble_count, 0)}
                                {m.has_bubbles !== null && (
                                    <span className="ml-1 text-[10px] text-gray-400">
                                        ({m.has_bubbles ? "bubbles" : "no bubbles"})
                                    </span>
                                )}
                            </td>
                            <td className="py-1.5 px-2.5 font-semibold">
                                {formatMetricPercent(m.segmentation_quality, 0)}
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    );
}

export default function SavedRegionEvidence({ observation: obs }: SavedRegionEvidenceProps) {
    const instanceId = useId().replace(/:/g, "");
    const [selectedSnapshotIndex, setSelectedSnapshotIndex] = useState<number>(0);
    const [showAllAffected, setShowAllAffected] = useState<boolean>(false);
    const [showAllSnapshots, setShowAllSnapshots] = useState<boolean>(false);
    const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

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

    // Keep selection and tabRefs coherent if snapshot count changes
    useEffect(() => {
        if (displayedSnapshots.length === 0) return;
        if (selectedSnapshotIndex >= displayedSnapshots.length) {
            const clamped = displayedSnapshots.length - 1;
            setSelectedSnapshotIndex(clamped);
            tabRefs.current[clamped]?.focus();
        }
    }, [displayedSnapshots.length, selectedSnapshotIndex]);

    const activeSnapshot: SavedRegionSiteSnapshot | null =
        displayedSnapshots.length > 0
            ? displayedSnapshots[Math.min(selectedSnapshotIndex, displayedSnapshots.length - 1)]
            : null;

    const handleKeyDown = (e: React.KeyboardEvent, index: number) => {
        if (displayedSnapshots.length === 0) return;
        let nextIndex = index;
        if (e.key === "ArrowRight") {
            e.preventDefault();
            nextIndex = (index + 1) % displayedSnapshots.length;
        } else if (e.key === "ArrowLeft") {
            e.preventDefault();
            nextIndex = (index - 1 + displayedSnapshots.length) % displayedSnapshots.length;
        } else if (e.key === "Home") {
            e.preventDefault();
            nextIndex = 0;
        } else if (e.key === "End") {
            e.preventDefault();
            nextIndex = displayedSnapshots.length - 1;
        } else {
            return;
        }
        setSelectedSnapshotIndex(nextIndex);
        tabRefs.current[nextIndex]?.focus();
    };

    const handleToggleShowSnapshots = () => {
        if (showAllSnapshots) {
            // Collapsing back to maxInitialSnapshots
            if (selectedSnapshotIndex >= maxInitialSnapshots) {
                const clamped = maxInitialSnapshots - 1;
                setSelectedSnapshotIndex(clamped);
                setTimeout(() => {
                    tabRefs.current[clamped]?.focus();
                }, 0);
            }
            setShowAllSnapshots(false);
        } else {
            setShowAllSnapshots(true);
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
                                className="text-[11px] font-medium text-[#5848e8] dark:text-[#a397ff] hover:underline cursor-pointer"
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

            {/* Malformed or Empty Region Evidence Banner */}
            {obs.regionEvidenceState === "malformed" && (
                <div className="rounded-lg bg-amber-50 dark:bg-amber-950/40 p-3 text-amber-800 dark:text-amber-200 border border-amber-300 dark:border-amber-800 space-y-1">
                    <div className="flex items-center gap-1.5 font-semibold">
                        <AlertCircle size={14} className="shrink-0 text-amber-600 dark:text-amber-400" />
                        <span>Malformed Region Evidence</span>
                    </div>
                    <p className="text-[11px] text-amber-700 dark:text-amber-300">
                        Region evidence metadata is not a valid list of site snapshots.
                    </p>
                </div>
            )}

            {obs.regionEvidenceState === "empty" && (
                <div className="rounded-lg bg-gray-100 dark:bg-gray-800/60 p-3 text-gray-600 dark:text-gray-400 border border-gray-200 dark:border-gray-700 space-y-1">
                    <div className="flex items-center gap-1.5 font-semibold text-gray-700 dark:text-gray-300">
                        <Info size={14} className="shrink-0 text-gray-500" />
                        <span>Empty Region Evidence</span>
                    </div>
                    <p className="text-[11px]">
                        Region evidence was recorded as an empty list (0 site snapshots).
                    </p>
                </div>
            )}

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
                                onClick={handleToggleShowSnapshots}
                                className="text-[11px] font-medium text-[#5848e8] dark:text-[#a397ff] hover:underline cursor-pointer"
                            >
                                {showAllSnapshots ? "Show fewer tabs" : `Show all ${obs.snapshots.length} tabs`}
                            </button>
                        )}
                    </div>

                    {/* Site Selection Tabs with Roving Tabindex & Instance Unique DOM IDs */}
                    <div
                        role="tablist"
                        aria-label="Persisted Target Sites"
                        className="flex flex-wrap gap-1.5 p-1 bg-gray-200/60 dark:bg-gray-800/60 rounded-xl"
                    >
                        {displayedSnapshots.map((snap, idx) => {
                            const isSelected = idx === selectedSnapshotIndex;
                            const status = snap.currentMeasurements?.inspection_status || "UNKNOWN";
                            const tabId = `${instanceId}-tab-${idx}-${snap.key}`;
                            const panelId = `${instanceId}-panel-${idx}-${snap.key}`;

                            return (
                                <button
                                    key={snap.key}
                                    ref={(el) => {
                                        tabRefs.current[idx] = el;
                                    }}
                                    id={tabId}
                                    role="tab"
                                    type="button"
                                    aria-selected={isSelected}
                                    aria-controls={panelId}
                                    tabIndex={isSelected ? 0 : -1}
                                    onClick={() => {
                                        setSelectedSnapshotIndex(idx);
                                        tabRefs.current[idx]?.focus();
                                    }}
                                    onKeyDown={(e) => handleKeyDown(e, idx)}
                                    className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-semibold transition cursor-pointer ${
                                        isSelected
                                            ? "bg-white dark:bg-[#141b29] text-[#5848e8] dark:text-[#a397ff] shadow-xs ring-1 ring-black/5 dark:ring-white/10"
                                            : "text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 hover:bg-white/40"
                                    }`}
                                >
                                    <span className="font-bold truncate max-w-[120px]" title={snap.roi_id}>
                                        {snap.roi_id}
                                    </span>
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
                            id={`${instanceId}-panel-${Math.min(selectedSnapshotIndex, displayedSnapshots.length - 1)}-${activeSnapshot.key}`}
                            aria-labelledby={`${instanceId}-tab-${Math.min(selectedSnapshotIndex, displayedSnapshots.length - 1)}-${activeSnapshot.key}`}
                            tabIndex={0}
                            className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-[#141b29] p-3.5 sm:p-4 space-y-3.5 shadow-2xs focus:outline-hidden"
                        >
                            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-100 dark:border-gray-800 pb-2.5">
                                <div className="flex items-center gap-2">
                                    <span className="font-bold text-sm text-[#5848e8] dark:text-[#a397ff] break-all">
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
                                    {/* Current Measurements: Shared 15-parameter view */}
                                    <div className="space-y-1.5">
                                        <div className="text-[11px] font-semibold text-gray-700 dark:text-gray-300">
                                            Current Site Measurements
                                        </div>
                                        <ScalarMetricsView
                                            measurements={activeSnapshot.currentMeasurements}
                                            variant="current"
                                        />
                                    </div>

                                    {/* Reference Measurements Section: Shared 15-parameter view */}
                                    <div className="pt-2 border-t border-gray-100 dark:border-gray-800 space-y-2">
                                        <div className="flex items-center justify-between text-[11px]">
                                            <span className="font-semibold text-gray-700 dark:text-gray-300">
                                                Reference Measurements:
                                            </span>
                                            {activeSnapshot.hasReference ? (
                                                <span className="font-mono font-medium text-emerald-700 dark:text-emerald-400">
                                                    Recorded (Golden Reference Mode)
                                                </span>
                                            ) : (
                                                <span className="text-gray-400 italic">
                                                    Not recorded (single-image inspection or unmatched reference site)
                                                </span>
                                            )}
                                        </div>

                                        {activeSnapshot.hasReference && (
                                            <div className="p-2.5 rounded-lg bg-slate-50/70 dark:bg-slate-900/40 border border-slate-200 dark:border-slate-800">
                                                <ScalarMetricsView
                                                    measurements={activeSnapshot.referenceMeasurements}
                                                    variant="reference"
                                                />
                                            </div>
                                        )}
                                    </div>
                                </>
                            )}
                        </div>
                    )}
                </div>
            )}

            {/* 4. Legacy Observation Summary (Genuinely Legacy or Legacy Fallback Fields) */}
            {obs.legacySummary && (obs.isLegacyOnly || obs.regionEvidenceState === "malformed" || obs.regionEvidenceState === "empty") && (
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
                        {obs.isLegacyOnly
                            ? "This observation contains legacy single-site or summary metrics recorded without multi-site snapshots."
                            : "Legacy summary fields recorded on this observation alongside malformed or empty multi-site evidence."}
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
                                <span className="font-semibold text-[#5848e8] dark:text-[#a397ff] break-all">{obs.legacySummary.roiId}</span>
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
                        {obs.legacySummary.overflowRatio !== null && (
                            <div>
                                <span className="text-gray-400">Overflow Ratio: </span>
                                <span className="font-medium text-gray-800 dark:text-gray-200">{formatMetricPercent(obs.legacySummary.overflowRatio, 1)}</span>
                            </div>
                        )}
                        {obs.legacySummary.currentCoverage !== null && (
                            <div>
                                <span className="text-gray-400">Current Coverage: </span>
                                <span className="font-medium text-gray-800 dark:text-gray-200">{formatMetricPercent(obs.legacySummary.currentCoverage, 1)}</span>
                            </div>
                        )}
                        {obs.legacySummary.referenceCoverage !== null && (
                            <div>
                                <span className="text-gray-400">Reference Coverage: </span>
                                <span className="font-medium text-gray-800 dark:text-gray-200">{formatMetricPercent(obs.legacySummary.referenceCoverage, 1)}</span>
                            </div>
                        )}
                        {obs.legacySummary.coverageRatioToReference !== null && (
                            <div>
                                <span className="text-gray-400">Coverage vs Ref: </span>
                                <span className="font-medium text-gray-800 dark:text-gray-200">{formatMetricNumber(obs.legacySummary.coverageRatioToReference, 2)}</span>
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
                        {obs.legacySummary.segQuality !== null && (
                            <div>
                                <span className="text-gray-400">Seg Quality: </span>
                                <span className="font-medium text-gray-800 dark:text-gray-200">{formatMetricPercent(obs.legacySummary.segQuality, 0)}</span>
                            </div>
                        )}
                        {obs.legacySummary.sizeCv !== null && (
                            <div>
                                <span className="text-gray-400">Size CV: </span>
                                <span className="font-medium text-gray-800 dark:text-gray-200">{formatMetricPercent(obs.legacySummary.sizeCv, 1)}</span>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* If neither snapshots nor legacy summary exist */}
            {!obs.hasSnapshots && !obs.isLegacyOnly && !obs.legacySummary && obs.regionEvidenceState === "absent" && (
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
