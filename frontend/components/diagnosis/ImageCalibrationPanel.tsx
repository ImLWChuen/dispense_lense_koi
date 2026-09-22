"use client";

import { useRef } from "react";
import { Sliders, Ruler, Image as ImageIcon, X, AlertTriangle } from "lucide-react";
import {
    ImageAnalysisMode,
    ProcessLimits,
    ReferenceLimits,
} from "@/types/image";

interface ImageCalibrationPanelProps {
    mode: ImageAnalysisMode;
    onModeChange: (mode: ImageAnalysisMode) => void;
    mmPerPixel?: number | null;
    onMmPerPixelChange: (val: number | null) => void;
    processLimits?: ProcessLimits | null;
    onProcessLimitsChange: (limits: ProcessLimits | null) => void;
    referenceLimits?: ReferenceLimits | null;
    onReferenceLimitsChange: (limits: ReferenceLimits | null) => void;
    referenceFile?: File | null;
    onReferenceFileChange: (file: File | null) => void;
    referencePreviewUrl?: string | null;
    disabled?: boolean;
}

export default function ImageCalibrationPanel({
    mode,
    onModeChange,
    mmPerPixel,
    onMmPerPixelChange,
    processLimits,
    onProcessLimitsChange,
    referenceLimits,
    onReferenceLimitsChange,
    referenceFile,
    onReferenceFileChange,
    referencePreviewUrl,
    disabled = false,
}: ImageCalibrationPanelProps) {
    const refFileInputRef = useRef<HTMLInputElement>(null);

    const handleModeSelect = (newMode: ImageAnalysisMode) => {
        if (disabled) return;
        onModeChange(newMode);
    };

    const updateProcessLimit = (key: keyof ProcessLimits, rawVal: string) => {
        if (disabled) return;
        const numVal = rawVal.trim() === "" ? null : parseFloat(rawVal);
        const next: ProcessLimits = {
            ...(processLimits || {}),
            [key]: numVal !== null && !isNaN(numVal) ? numVal : null,
        };
        // Clean empty values
        const hasAny = Object.values(next).some((v) => v !== null && v !== undefined);
        onProcessLimitsChange(hasAny ? next : null);
    };

    const updateReferenceLimit = (key: keyof ReferenceLimits, rawVal: string) => {
        if (disabled) return;
        const numVal = rawVal.trim() === "" ? null : parseFloat(rawVal);
        const next: ReferenceLimits = {
            ...(referenceLimits || {}),
            [key]: numVal !== null && !isNaN(numVal) ? numVal : null,
        };
        const hasAny = Object.values(next).some((v) => v !== null && v !== undefined);
        onReferenceLimitsChange(hasAny ? next : null);
    };

    const handleRefFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (disabled || !e.target.files?.[0]) return;
        const file = e.target.files[0];
        // Client-side pre-validation: JPEG or PNG, <= 10 MiB
        const isValidType = ["image/jpeg", "image/png"].includes(file.type) || /\.(jpe?g|png)$/i.test(file.name);
        if (!isValidType) {
            alert("Invalid reference file type. Only JPEG and PNG images are supported.");
            e.target.value = "";
            return;
        }
        if (file.size > 10 * 1024 * 1024) {
            alert("Reference file exceeds 10 MB limit.");
            e.target.value = "";
            return;
        }
        onReferenceFileChange(file);
    };

    const handleRemoveRefFile = () => {
        if (disabled) return;
        if (refFileInputRef.current) refFileInputRef.current.value = "";
        onReferenceFileChange(null);
    };

    const coverageMin = processLimits?.min_coverage_ratio ?? null;
    const coverageMax = processLimits?.max_coverage_ratio ?? null;
    const hasCoverageError =
        coverageMin !== null && coverageMax !== null && coverageMin > coverageMax;

    const refMin = referenceLimits?.min_reference_ratio ?? null;
    const refMax = referenceLimits?.max_reference_ratio ?? null;
    const hasRefLimitError = refMin !== null && refMax !== null && refMin > refMax;

    return (
        <div className="space-y-5 rounded-2xl border border-gray-200/80 dark:border-gray-800 bg-gray-50/90 dark:bg-gray-800/30 p-4 sm:p-5 shadow-2xs">
            <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2 min-w-0">
                    <Sliders size={16} className="text-[#6d5dfc] shrink-0" />
                    <h3 className="text-xs sm:text-sm font-semibold text-gray-900 dark:text-gray-100 truncate">
                        Analysis Mode & Calibration
                    </h3>
                </div>
                <span className="rounded-md bg-white dark:bg-gray-800 px-2.5 py-1 text-[11px] font-semibold text-[#5848e8] dark:text-[#a397ff] border border-gray-200 dark:border-gray-700 shrink-0">
                    {mode === "FEATURES_ONLY" ? "Features" : mode === "PROCESS_LIMITS" ? "Limits" : "Golden Ref"}
                </span>
            </div>

            {/* Mode Selector */}
            <div className="flex flex-col sm:flex-row gap-1.5 p-1.5 bg-gray-200/70 dark:bg-gray-800/70 rounded-xl">
                <button
                    type="button"
                    disabled={disabled}
                    onClick={() => handleModeSelect("FEATURES_ONLY")}
                    className={`flex-1 rounded-lg px-3 py-2 text-xs transition text-center ${
                        mode === "FEATURES_ONLY"
                            ? "bg-white dark:bg-gray-700 text-[#5848e8] dark:text-white shadow-xs font-semibold"
                            : "text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 hover:bg-white/50"
                    }`}
                >
                    Features Only
                </button>
                <button
                    type="button"
                    disabled={disabled}
                    onClick={() => handleModeSelect("PROCESS_LIMITS")}
                    className={`flex-1 rounded-lg px-3 py-2 text-xs transition text-center ${
                        mode === "PROCESS_LIMITS"
                            ? "bg-white dark:bg-gray-700 text-[#5848e8] dark:text-white shadow-xs font-semibold"
                            : "text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 hover:bg-white/50"
                    }`}
                >
                    Process Limits
                </button>
                <button
                    type="button"
                    disabled={disabled}
                    onClick={() => handleModeSelect("REFERENCE_IMAGE")}
                    className={`flex-1 rounded-lg px-3 py-2 text-xs transition text-center ${
                        mode === "REFERENCE_IMAGE"
                            ? "bg-white dark:bg-gray-700 text-[#5848e8] dark:text-white shadow-xs font-semibold"
                            : "text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 hover:bg-white/50"
                    }`}
                >
                    Reference Image
                </button>
            </div>

            {/* Mode Descriptions */}
            {mode === "FEATURES_ONLY" && (
                <p className="text-xs text-gray-500 dark:text-gray-400 leading-relaxed px-1">
                    Extracts resolution-independent geometric features without threshold evaluation. Returns status{" "}
                    <code className="rounded bg-gray-200/80 dark:bg-gray-700 px-1.5 py-0.5 text-[11px] font-mono">UNCALIBRATED</code> with no diagnostic observations.
                </p>
            )}

            {mode === "PROCESS_LIMITS" && (
                <div className="space-y-3 rounded-xl border border-gray-200 bg-white p-3">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-gray-800">Process Thresholds</span>
                        <span className="text-[11px] text-gray-500">At least 1 limit required</span>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
                        <div>
                            <label className="block text-[11px] font-medium text-gray-600">
                                Min Coverage Ratio
                            </label>
                            <input
                                type="number"
                                step="0.01"
                                min="0"
                                max="1"
                                disabled={disabled}
                                value={processLimits?.min_coverage_ratio ?? ""}
                                onChange={(e) => updateProcessLimit("min_coverage_ratio", e.target.value)}
                                placeholder="e.g. 0.15"
                                className="mt-1 w-full rounded-md border border-gray-200 px-2.5 py-1.5 text-xs outline-none focus:border-[#6d5dfc]"
                            />
                        </div>

                        <div>
                            <label className="block text-[11px] font-medium text-gray-600">
                                Max Coverage Ratio
                            </label>
                            <input
                                type="number"
                                step="0.01"
                                min="0"
                                max="1"
                                disabled={disabled}
                                value={processLimits?.max_coverage_ratio ?? ""}
                                onChange={(e) => updateProcessLimit("max_coverage_ratio", e.target.value)}
                                placeholder="e.g. 0.35"
                                className="mt-1 w-full rounded-md border border-gray-200 px-2.5 py-1.5 text-xs outline-none focus:border-[#6d5dfc]"
                            />
                        </div>

                        <div>
                            <label className="block text-[11px] font-medium text-gray-600">
                                Max Overflow Ratio
                            </label>
                            <input
                                type="number"
                                step="0.01"
                                min="0"
                                max="1"
                                disabled={disabled}
                                value={processLimits?.max_overflow_ratio ?? ""}
                                onChange={(e) => updateProcessLimit("max_overflow_ratio", e.target.value)}
                                placeholder="e.g. 0.05"
                                className="mt-1 w-full rounded-md border border-gray-200 px-2.5 py-1.5 text-xs outline-none focus:border-[#6d5dfc]"
                            />
                        </div>

                        <div>
                            <label className="block text-[11px] font-medium text-gray-600">
                                Max Size CV
                            </label>
                            <input
                                type="number"
                                step="0.01"
                                min="0"
                                disabled={disabled}
                                value={processLimits?.max_size_cv ?? ""}
                                onChange={(e) => updateProcessLimit("max_size_cv", e.target.value)}
                                placeholder="e.g. 0.10"
                                className="mt-1 w-full rounded-md border border-gray-200 px-2.5 py-1.5 text-xs outline-none focus:border-[#6d5dfc]"
                            />
                        </div>

                        <div>
                            <label className="block text-[11px] font-medium text-gray-600">
                                Min Presence Ratio
                            </label>
                            <input
                                type="number"
                                step="0.01"
                                min="0"
                                max="1"
                                disabled={disabled}
                                value={processLimits?.min_presence_ratio ?? ""}
                                onChange={(e) => updateProcessLimit("min_presence_ratio", e.target.value)}
                                placeholder="e.g. 0.05"
                                className="mt-1 w-full rounded-md border border-gray-200 px-2.5 py-1.5 text-xs outline-none focus:border-[#6d5dfc]"
                            />
                        </div>
                    </div>

                    {hasCoverageError && (
                        <div className="flex items-center gap-1.5 text-[11px] text-red-600">
                            <AlertTriangle size={12} className="shrink-0" />
                            <span>Min coverage ratio cannot be greater than max coverage ratio.</span>
                        </div>
                    )}
                </div>
            )}

            {mode === "REFERENCE_IMAGE" && (
                <div className="space-y-3 rounded-xl border border-gray-200 bg-white p-3">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-gray-800">Golden Reference Image</span>
                        <span className="text-[11px] text-amber-700 font-medium">Required for Reference mode</span>
                    </div>

                    <input
                        ref={refFileInputRef}
                        type="file"
                        accept="image/jpeg,image/png"
                        onChange={handleRefFileSelect}
                        disabled={disabled}
                        className="hidden"
                    />

                    {referenceFile && referencePreviewUrl ? (
                        <div className="flex items-center justify-between gap-2 rounded-lg border border-gray-200 p-2 text-xs">
                            <div className="flex items-center gap-2 min-w-0 flex-1">
                                {/* eslint-disable-next-line @next/next/no-img-element */}
                                <img
                                    src={referencePreviewUrl}
                                    alt="Reference"
                                    className="h-10 w-10 shrink-0 rounded object-cover border"
                                />
                                <div className="min-w-0 flex-1">
                                    <p className="font-medium text-gray-800 truncate">
                                        {referenceFile.name}
                                    </p>
                                    <p className="text-[11px] text-gray-500">
                                        {(referenceFile.size / 1024).toFixed(1)} KB
                                    </p>
                                </div>
                            </div>
                            {!disabled && (
                                <button
                                    type="button"
                                    onClick={handleRemoveRefFile}
                                    className="shrink-0 rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-700"
                                    title="Remove reference image"
                                >
                                    <X size={14} />
                                </button>
                            )}
                        </div>
                    ) : (
                        <button
                            type="button"
                            disabled={disabled}
                            onClick={() => refFileInputRef.current?.click()}
                            className="flex w-full items-center justify-center gap-2 rounded-lg border-2 border-dashed border-gray-300 py-2.5 px-2 text-xs font-medium text-gray-600 hover:border-gray-400 hover:bg-gray-50 transition"
                        >
                            <ImageIcon size={15} className="shrink-0" />
                            <span className="truncate">Upload Reference Image (PNG/JPEG &le; 10 MB)</span>
                        </button>
                    )}

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-1">
                        <div>
                            <label className="block text-[11px] font-medium text-gray-600 truncate">
                                Tolerance Ratio
                            </label>
                            <input
                                type="number"
                                step="0.01"
                                min="0"
                                max="1"
                                disabled={disabled}
                                value={referenceLimits?.tolerance_ratio ?? ""}
                                onChange={(e) => updateReferenceLimit("tolerance_ratio", e.target.value)}
                                placeholder="e.g. 0.10"
                                className="mt-1 w-full rounded-md border border-gray-200 px-2.5 py-1.5 text-xs outline-none focus:border-[#6d5dfc]"
                            />
                        </div>

                        <div>
                            <label className="block text-[11px] font-medium text-gray-600 truncate">
                                Min Ref Ratio
                            </label>
                            <input
                                type="number"
                                step="0.01"
                                min="0"
                                disabled={disabled}
                                value={referenceLimits?.min_reference_ratio ?? ""}
                                onChange={(e) => updateReferenceLimit("min_reference_ratio", e.target.value)}
                                placeholder="e.g. 0.85"
                                className="mt-1 w-full rounded-md border border-gray-200 px-2.5 py-1.5 text-xs outline-none focus:border-[#6d5dfc]"
                            />
                        </div>

                        <div>
                            <label className="block text-[11px] font-medium text-gray-600 truncate">
                                Max Ref Ratio
                            </label>
                            <input
                                type="number"
                                step="0.01"
                                min="0"
                                disabled={disabled}
                                value={referenceLimits?.max_reference_ratio ?? ""}
                                onChange={(e) => updateReferenceLimit("max_reference_ratio", e.target.value)}
                                placeholder="e.g. 1.15"
                                className="mt-1 w-full rounded-md border border-gray-200 px-2.5 py-1.5 text-xs outline-none focus:border-[#6d5dfc]"
                            />
                        </div>
                    </div>

                    {hasRefLimitError && (
                        <div className="flex items-center gap-1.5 text-[11px] text-red-600">
                            <AlertTriangle size={12} className="shrink-0" />
                            <span>Min reference ratio cannot be greater than max reference ratio.</span>
                        </div>
                    )}
                </div>
            )}

            {/* Optional Scale (mm_per_pixel) */}
            <div className="border-t border-gray-200/80 dark:border-gray-800 pt-4">
                <div className="flex items-center gap-2">
                    <Ruler size={15} className="text-gray-500 dark:text-gray-400 shrink-0" />
                    <label className="text-xs sm:text-sm font-semibold text-gray-800 dark:text-gray-200">
                        Physical Scale (mm per pixel)
                    </label>
                    <span className="rounded-md bg-gray-200/70 dark:bg-gray-800 px-2 py-0.5 text-[10px] font-medium text-gray-600 dark:text-gray-400">
                        Optional
                    </span>
                </div>
                <div className="mt-2 flex flex-col sm:flex-row sm:items-center gap-2.5">
                    <input
                        type="number"
                        step="0.0001"
                        min="0"
                        disabled={disabled}
                        value={mmPerPixel ?? ""}
                        onChange={(e) => {
                            const val = e.target.value.trim() === "" ? null : parseFloat(e.target.value);
                            onMmPerPixelChange(val !== null && !isNaN(val) && val > 0 ? val : null);
                        }}
                        placeholder="e.g. 0.005"
                        className="w-full sm:w-40 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-[#141b29] px-3 py-2 text-xs sm:text-sm font-mono outline-none focus:border-[#6d5dfc] transition"
                    />
                    <span className="text-xs text-gray-500 dark:text-gray-400 leading-normal">
                        Required to calculate physical diameter in millimeters (mm).
                    </span>
                </div>
            </div>
        </div>
    );
}
