"use client";

import { useState, useRef } from "react";
import {
    Download,
    Upload,
    CheckCircle2,
    AlertTriangle,
    X,
    RotateCcw,
    Check,
    FileCode,
    Info,
} from "lucide-react";
import { UploadItem } from "@/types/image";
import {
    RegionLayoutFile,
    MAX_LAYOUT_FILE_BYTES,
    DEFAULT_LAYOUT_FILENAME,
    createRegionLayout,
    parseRegionLayout,
    triggerLayoutDownload,
} from "@/lib/region-layout";

interface RegionLayoutControlsProps {
    uploadItem: UploadItem;
    targetDimensions: { width: number; height: number } | null;
    isAnalyzing: boolean;
    onImportLayout: (layout: RegionLayoutFile) => void;
    onConfirmPlacement: () => void;
    onAbandonLayout: () => void;
    onLayoutError: (error: string | null) => void;
    layoutError?: string | null;
}

export default function RegionLayoutControls({
    uploadItem,
    targetDimensions,
    isAnalyzing,
    onImportLayout,
    onConfirmPlacement,
    onAbandonLayout,
    onLayoutError,
    layoutError,
}: RegionLayoutControlsProps) {
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [isSaveModalOpen, setIsSaveModalOpen] = useState(false);
    const [saveName, setSaveName] = useState(() => {
        const cleanBase = uploadItem.file?.name?.replace(/\.[^.]+$/, "") || "part";
        return `${cleanBase} layout`;
    });
    const [saveValidationError, setSaveValidationError] = useState<string | null>(null);

    const hasRois = uploadItem.rois && uploadItem.rois.length > 0;
    const hasValidDimensions =
        targetDimensions !== null &&
        targetDimensions.width > 0 &&
        targetDimensions.height > 0;

    const canExport = hasRois && hasValidDimensions && !isAnalyzing;

    // File export handler
    const handleOpenSaveModal = () => {
        if (!canExport) return;
        const cleanBase = uploadItem.file?.name?.replace(/\.[^.]+$/, "") || "part";
        setSaveName(`${cleanBase} layout`);
        setSaveValidationError(null);
        setIsSaveModalOpen(true);
    };

    const handleConfirmSave = () => {
        if (!hasValidDimensions || !targetDimensions) {
            setSaveValidationError("Target image dimensions unavailable.");
            return;
        }
        const trimmed = saveName.trim();
        if (!trimmed) {
            setSaveValidationError("Layout name cannot be blank.");
            return;
        }

        const res = createRegionLayout(trimmed, targetDimensions, uploadItem.rois);
        if (!res.ok) {
            setSaveValidationError(res.error);
            return;
        }

        triggerLayoutDownload(res.layout, DEFAULT_LAYOUT_FILENAME);
        setIsSaveModalOpen(false);
    };

    // File import handler
    const handleFileSelected = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        // Reset file input so re-selecting same file works
        e.target.value = "";
        if (!file) return;

        if (file.size > MAX_LAYOUT_FILE_BYTES) {
            onLayoutError(
                `File "${file.name}" rejected: payload (${(file.size / 1024).toFixed(1)} KiB) exceeds maximum 256 KiB limit.`
            );
            return;
        }

        const currentUploadId = uploadItem.id;
        const currentRevision = uploadItem.configRevision;

        const reader = new FileReader();
        reader.onload = (event) => {
            const content = event.target?.result;
            if (typeof content !== "string") {
                onLayoutError("Failed to read layout file content.");
                return;
            }

            // Stale check: verify upload revision still matches
            if (uploadItem.id !== currentUploadId || uploadItem.configRevision !== currentRevision) {
                // Obsolete read discarded
                return;
            }

            const parseRes = parseRegionLayout(content);
            if (!parseRes.ok) {
                onLayoutError(parseRes.error);
                return;
            }

            onLayoutError(null);
            onImportLayout(parseRes.layout);
        };

        reader.onerror = () => {
            onLayoutError("Failed to read the selected file from disk.");
        };

        reader.readAsText(file, "utf-8");
    };

    const imported = uploadItem.importedLayout;
    const isUnconfirmed = Boolean(imported && !imported.confirmed);
    const isConfirmed = Boolean(imported && imported.confirmed);

    const hasDimensionMismatch =
        imported &&
        targetDimensions &&
        targetDimensions.width > 0 &&
        targetDimensions.height > 0 &&
        (targetDimensions.width !== imported.sourceDimensions.width ||
            targetDimensions.height !== imported.sourceDimensions.height);

    return (
        <div className="space-y-3">
            {/* Top Toolbar: Save / Load Layout Action Buttons */}
            <div className="flex items-center justify-between gap-2 flex-wrap text-xs">
                <div className="flex items-center gap-2">
                    <span className="font-semibold text-gray-700 dark:text-gray-300">
                        Region Layout:
                    </span>
                    <button
                        type="button"
                        onClick={handleOpenSaveModal}
                        disabled={!canExport}
                        title={
                            !hasRois
                                ? "Draw at least one target region to save layout"
                                : !hasValidDimensions
                                ? "Image preview dimensions must be loaded before saving layout"
                                : isAnalyzing
                                ? "Analysis in progress"
                                : "Save current region positions to portable JSON file"
                        }
                        className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-2.5 py-1.5 font-medium text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 transition disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                    >
                        <Download size={13} className="text-[#6d5dfc]" />
                        <span>Save layout</span>
                    </button>

                    <button
                        type="button"
                        onClick={() => fileInputRef.current?.click()}
                        disabled={isAnalyzing}
                        title="Load region layout JSON from disk"
                        className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-2.5 py-1.5 font-medium text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 transition disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                    >
                        <Upload size={13} className="text-[#6d5dfc]" />
                        <span>Load layout</span>
                    </button>

                    <input
                        ref={fileInputRef}
                        type="file"
                        accept=".json,application/json"
                        onChange={handleFileSelected}
                        className="hidden"
                        aria-label="Upload portable region layout JSON"
                    />
                </div>

                {imported && (
                    <div className="flex items-center gap-1.5">
                        {isConfirmed ? (
                            <span className="inline-flex items-center gap-1 rounded-md bg-emerald-50 dark:bg-emerald-950/40 px-2 py-0.5 text-[11px] font-semibold text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                                <CheckCircle2 size={12} />
                                <span>Placement Confirmed</span>
                            </span>
                        ) : (
                            <span className="inline-flex items-center gap-1 rounded-md bg-amber-50 dark:bg-amber-950/40 px-2 py-0.5 text-[11px] font-semibold text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-800 animate-pulse">
                                <AlertTriangle size={12} />
                                <span>Unconfirmed Placement</span>
                            </span>
                        )}
                    </div>
                )}
            </div>

            {/* Error Message Banner */}
            {layoutError && (
                <div className="flex items-start justify-between gap-2 rounded-xl bg-red-50 dark:bg-red-950/30 p-3 text-xs text-red-700 dark:text-red-300 border border-red-200 dark:border-red-900/50">
                    <div className="flex items-start gap-2">
                        <AlertTriangle size={14} className="text-red-600 shrink-0 mt-0.5" />
                        <div>
                            <strong className="font-semibold">Layout Import Error:</strong>{" "}
                            <span>{layoutError}</span>
                        </div>
                    </div>
                    <button
                        type="button"
                        onClick={() => onLayoutError(null)}
                        className="text-red-500 hover:text-red-700 p-0.5"
                        title="Dismiss error"
                        aria-label="Dismiss error"
                    >
                        <X size={14} />
                    </button>
                </div>
            )}

            {/* Persistent Placement Confirmation Notice (When Imported Layout is Active) */}
            {imported && (
                <div
                    className={`rounded-xl border p-4 space-y-3 text-xs transition ${
                        isConfirmed
                            ? "bg-emerald-50/50 dark:bg-emerald-950/20 border-emerald-200/80 dark:border-emerald-800/60"
                            : "bg-amber-50/70 dark:bg-amber-950/30 border-amber-200 dark:border-amber-800/80 shadow-xs"
                    }`}
                >
                    {/* Header */}
                    <div className="flex items-start justify-between gap-3">
                        <div className="flex items-start gap-2.5">
                            {isConfirmed ? (
                                <CheckCircle2 size={18} className="text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
                            ) : (
                                <AlertTriangle size={18} className="text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                            )}
                            <div>
                                <h4 className="font-bold text-gray-900 dark:text-gray-100 text-sm">
                                    {isConfirmed
                                        ? "Region Placement Confirmed"
                                        : "Pending Region Placement Confirmation"}
                                </h4>
                                <p className="text-gray-600 dark:text-gray-400 mt-0.5">
                                    Imported layout: <strong className="text-gray-800 dark:text-gray-200">{imported.name}</strong> ({uploadItem.rois.length} regions)
                                </p>
                            </div>
                        </div>

                        {/* Abandon button */}
                        <button
                            type="button"
                            onClick={onAbandonLayout}
                            title="Discard imported layout and regions to draw manually"
                            className="inline-flex items-center gap-1 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-2 py-1 text-[11px] font-medium text-gray-600 dark:text-gray-300 hover:text-red-600 hover:border-red-200 dark:hover:border-red-800 transition cursor-pointer"
                        >
                            <RotateCcw size={11} />
                            <span>Abandon & Draw Manually</span>
                        </button>
                    </div>

                    {/* Dimensions Comparison */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs bg-white/70 dark:bg-gray-900/60 p-2.5 rounded-lg border border-gray-200/60 dark:border-gray-800">
                        <div>
                            <span className="text-gray-500 dark:text-gray-400">Layout Source Dimensions:</span>{" "}
                            <span className="font-mono font-medium text-gray-800 dark:text-gray-200">
                                {imported.sourceDimensions.width} × {imported.sourceDimensions.height} px
                            </span>
                        </div>
                        <div>
                            <span className="text-gray-500 dark:text-gray-400">Target Image Dimensions:</span>{" "}
                            <span className="font-mono font-medium text-gray-800 dark:text-gray-200">
                                {hasValidDimensions && targetDimensions
                                    ? `${targetDimensions.width} × ${targetDimensions.height} px`
                                    : "Reading dimensions..."}
                            </span>
                        </div>
                    </div>

                    {/* Dimension Mismatch Warning */}
                    {hasDimensionMismatch && (
                        <div className="flex items-start gap-2 rounded-lg bg-amber-100/70 dark:bg-amber-900/40 p-2 text-amber-900 dark:text-amber-200 text-xs border border-amber-300 dark:border-amber-700">
                            <Info size={14} className="shrink-0 text-amber-700 mt-0.5" />
                            <span>
                                <strong>Dimension mismatch detected:</strong> Target image dimensions differ from layout source. Normalized coordinates map to this aspect ratio. Verify positioning carefully. Note: matching dimensions do not guarantee physical part alignment.
                            </span>
                        </div>
                    )}

                    {!hasValidDimensions && (
                        <div className="rounded-lg bg-red-50 dark:bg-red-950/40 p-2 text-red-700 dark:text-red-300 text-xs border border-red-200 dark:border-red-800">
                            Target image dimensions are unreadable. Region placement confirmation is blocked until the image preview is loaded.
                        </div>
                    )}

                    {/* Technician Instructions & Scope Notice */}
                    <div className="space-y-1 text-[11px] text-gray-600 dark:text-gray-400 border-t border-gray-200/60 dark:border-gray-800/80 pt-2">
                        <p>
                            • Verify product orientation, camera framing, and all expected dispense sites.
                        </p>
                        {uploadItem.mode === "REFERENCE_IMAGE" && (
                            <p className="text-indigo-600 dark:text-indigo-400 font-medium">
                                • Reference image mode active: Ensure reference image corresponds accurately to this layout.
                            </p>
                        )}
                        <p>
                            • Calibration (scale mm/px), process limits, and thresholds are preserved separately and should be reviewed.
                        </p>
                        <p className="italic">
                            • Confirmation verifies region geometry placement only; it does not confirm process pass/fail or determine defect root cause.
                        </p>
                    </div>

                    {/* Action Row for Unconfirmed State */}
                    {isUnconfirmed && (
                        <div className="flex items-center justify-between gap-3 pt-1 border-t border-amber-200/80 dark:border-amber-800/60">
                            <span className="text-[11px] font-medium text-amber-900 dark:text-amber-300">
                                Analysis is blocked until region placement is confirmed.
                            </span>

                            <button
                                type="button"
                                onClick={onConfirmPlacement}
                                disabled={!hasValidDimensions || isAnalyzing}
                                title={
                                    !hasValidDimensions
                                        ? "Target dimensions unreadable"
                                        : "Confirm region positioning for this image"
                                }
                                className="inline-flex items-center gap-1.5 rounded-xl bg-[#6d5dfc] hover:bg-[#5848e8] text-white px-4 py-2 font-semibold shadow-xs transition disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                            >
                                <Check size={14} />
                                <span>Confirm region placement</span>
                            </button>
                        </div>
                    )}
                </div>
            )}

            {/* Save Layout Modal */}
            {isSaveModalOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
                    <div className="relative w-full max-w-md rounded-2xl border border-gray-200 bg-white dark:bg-gray-900 p-5 shadow-2xl space-y-4">
                        <div className="flex items-center justify-between border-b border-gray-100 dark:border-gray-800 pb-3">
                            <div className="flex items-center gap-2">
                                <FileCode size={18} className="text-[#6d5dfc]" />
                                <h3 className="font-bold text-gray-900 dark:text-gray-100 text-sm sm:text-base">
                                    Save Portable Region Layout
                                </h3>
                            </div>
                            <button
                                type="button"
                                onClick={() => setIsSaveModalOpen(false)}
                                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
                                aria-label="Close dialog"
                            >
                                <X size={16} />
                            </button>
                        </div>

                        <div className="space-y-3 text-xs text-gray-600 dark:text-gray-400">
                            <p>
                                Saves normalized geometry for {uploadItem.rois.length} region{uploadItem.rois.length === 1 ? "" : "s"} at current source dimensions ({targetDimensions?.width} × {targetDimensions?.height} px).
                            </p>
                            <p className="text-[11px] text-gray-500 bg-gray-50 dark:bg-gray-800 p-2 rounded-lg border border-gray-100 dark:border-gray-700">
                                <strong>Geometry only:</strong> Never exports images, file paths, calibration, process limits, reference images, or inspection results.
                            </p>

                            <div className="space-y-1.5">
                                <label
                                    htmlFor="layout-name-input"
                                    className="block font-semibold text-gray-700 dark:text-gray-300"
                                >
                                    Layout Name
                                </label>
                                <input
                                    id="layout-name-input"
                                    type="text"
                                    maxLength={100}
                                    value={saveName}
                                    onChange={(e) => {
                                        setSaveName(e.target.value);
                                        setSaveValidationError(null);
                                    }}
                                    placeholder="Enter descriptive layout name"
                                    className="w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-xs text-gray-900 dark:text-gray-100 focus:border-[#6d5dfc] focus:outline-hidden"
                                />
                                <span className="text-[10px] text-gray-400">
                                    Maximum 100 characters. Saved as <code className="font-mono">dispense-region-layout.json</code>.
                                </span>
                            </div>

                            {saveValidationError && (
                                <div className="rounded-lg bg-red-50 p-2 text-red-700 text-xs border border-red-200">
                                    {saveValidationError}
                                </div>
                            )}
                        </div>

                        <div className="flex items-center justify-end gap-2 border-t border-gray-100 dark:border-gray-800 pt-3 text-xs">
                            <button
                                type="button"
                                onClick={() => setIsSaveModalOpen(false)}
                                className="rounded-lg border border-gray-200 dark:border-gray-700 px-3 py-1.5 font-medium text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition"
                            >
                                Cancel
                            </button>
                            <button
                                type="button"
                                onClick={handleConfirmSave}
                                className="inline-flex items-center gap-1.5 rounded-lg bg-[#6d5dfc] hover:bg-[#5848e8] text-white px-3.5 py-1.5 font-semibold shadow-xs transition"
                            >
                                <Download size={13} />
                                <span>Save & Download JSON</span>
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
