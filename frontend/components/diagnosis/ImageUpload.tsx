"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import {
    Upload,
    X,
    Image as ImageIcon,
    Loader2,
    CheckCircle2,
    AlertCircle,
    Info,
    ChevronDown,
    ChevronUp,
    Play,
    Maximize2,
    Scan,
} from "lucide-react";
import ImageRoiEditor from "./ImageRoiEditor";
import ImageCalibrationPanel from "./ImageCalibrationPanel";
import { imagesApi } from "@/lib/api/images";
import {
    AnalysisProfile,
    UploadItem,
    UploadSnapshot,
} from "@/types/image";

import {
    validateAnalysisConfiguration,
    startUploadAnalysis,
    setUploadValidationError,
    commitUploadSuccess,
    commitUploadError,
    reconfigureUpload,
    removeUploadItem,
    cleanupControllerEntry,
    type InFlightController,
} from "@/lib/image-upload-state";

export { validateAnalysisConfiguration } from "@/lib/image-upload-state";

interface ImageUploadProps {
    onSnapshotChange?: (snapshot: UploadSnapshot) => void;
    // Retained for backward compatibility if callers expect it
    onAnalysisComplete?: (observations: unknown[]) => void;
    isFullWidth?: boolean;
}

export default function ImageUpload({
    onSnapshotChange,
    onAnalysisComplete,
    isFullWidth = false,
}: ImageUploadProps) {
    const [uploads, setUploads] = useState<UploadSnapshot>({});
    const [expandedUploadId, setExpandedUploadId] = useState<string | null>(null);
    const [studioUploadId, setStudioUploadId] = useState<string | null>(null);
    const [isDragging, setIsDragging] = useState(false);
    const [globalError, setGlobalError] = useState<string | null>(null);

    const fileInputRef = useRef<HTMLInputElement>(null);
    const controllersRef = useRef<Record<string, InFlightController>>({});
    const nextTokenRef = useRef<number>(1);
    const uploadsRef = useRef<UploadSnapshot>({});

    // Keep uploadsRef updated outside of render
    useEffect(() => {
        uploadsRef.current = uploads;
    }, [uploads]);

    // Sync snapshot to parent whenever uploads change
    useEffect(() => {
        onSnapshotChange?.(uploads);

        if (onAnalysisComplete) {
            const allObs: unknown[] = [];
            Object.values(uploads).forEach((u) => {
                if (u.status === "analyzed" && u.result?.status === "CALIBRATED") {
                    allObs.push(...u.result.observations);
                }
            });
            onAnalysisComplete(allObs);
        }
    }, [uploads, onSnapshotChange, onAnalysisComplete]);

    // Cleanup all object URLs and abort pending requests on unmount
    useEffect(() => {
        return () => {
            Object.values(controllersRef.current).forEach((req) => req.controller.abort());
            controllersRef.current = {};
            Object.values(uploadsRef.current).forEach((item) => {
                if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
                if (item.referencePreviewUrl) URL.revokeObjectURL(item.referencePreviewUrl);
            });
        };
    }, []);

    const executeAnalysis = async (item: UploadItem) => {
        const uploadId = item.id;
        if (item.status === "analyzing") return;

        // Abort any existing in-flight request for this upload
        const existingReq = controllersRef.current[uploadId];
        if (existingReq) {
            delete controllersRef.current[uploadId];
            existingReq.controller.abort();
        }

        // Validate all numeric limits and schema constraints before sending request
        const validationError = validateAnalysisConfiguration(item);
        if (validationError) {
            setUploads((prev) => setUploadValidationError(prev, uploadId, validationError));
            return;
        }

        // Build typed AnalysisProfile
        const profile: AnalysisProfile = {
            mode: item.mode,
            rois: item.rois,
            mm_per_pixel: item.mmPerPixel || null,
            process_limits: item.mode === "PROCESS_LIMITS" ? item.processLimits || null : null,
            reference_limits: item.mode === "REFERENCE_IMAGE" ? item.referenceLimits || null : null,
        };

        const requestToken = nextTokenRef.current++;
        const requestRevision = item.configRevision;
        const controller = new AbortController();

        controllersRef.current[uploadId] = {
            token: requestToken,
            controller,
        };

        setUploads((prev) => startUploadAnalysis(prev, uploadId, requestToken));

        try {
            const response = await imagesApi.analyze(
                item.file,
                profile,
                item.referenceFile,
                controller.signal
            );

            // Commit result inside functional state update confirming upload exists,
            // configRevision matches, and request token matches
            setUploads((prev) =>
                commitUploadSuccess(prev, uploadId, requestToken, requestRevision, response)
            );
        } catch (err: unknown) {
            // Ignore abort exceptions
            if (err instanceof Error && err.name === "AbortError") {
                return;
            }

            const message = err instanceof Error ? err.message : "Image analysis failed.";
            setUploads((prev) =>
                commitUploadError(prev, uploadId, requestToken, requestRevision, message)
            );
        } finally {
            // Delete controller only if stored controller still belongs to this request token
            cleanupControllerEntry(controllersRef.current, uploadId, requestToken);
        }
    };

    const handleRunAnalysis = async (uploadId: string) => {
        const item = uploadsRef.current[uploadId] || uploads[uploadId];
        if (!item) return;
        await executeAnalysis(item);
    };

    const processAddedFile = (file: File) => {
        setGlobalError(null);
        // Pre-validation: JPEG/PNG only
        const isValidType =
            ["image/jpeg", "image/png"].includes(file.type) || /\.(jpe?g|png)$/i.test(file.name);
        if (!isValidType) {
            setGlobalError(`File "${file.name}" rejected: Only JPEG and PNG images are supported.`);
            return;
        }

        // Pre-validation: 10 MiB limit
        if (file.size > 10 * 1024 * 1024) {
            setGlobalError(`File "${file.name}" rejected: File size exceeds 10 MB limit.`);
            return;
        }

        // Generate unique upload ID
        const uploadId = `upload_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
        const previewUrl = URL.createObjectURL(file);

        // Initialize with calibrated defaults so visual defect evidence is ready immediately
        const newItem: UploadItem = {
            id: uploadId,
            file,
            previewUrl,
            status: "ready",
            mode: "PROCESS_LIMITS",
            rois: [
                {
                    roi_id: "roi_1",
                    x: 0.15,
                    y: 0.15,
                    width: 0.70,
                    height: 0.70,
                },
            ],
            mmPerPixel: 0.02,
            processLimits: {
                min_coverage_ratio: 0.15,
                max_coverage_ratio: 0.45,
                max_overflow_ratio: 0.20,
                min_presence_ratio: 0.05,
                min_circularity: 0.75,
                max_aspect_ratio: 1.35,
                max_bubble_count: 0,
            },
            referenceLimits: null,
            referenceFile: null,
            referencePreviewUrl: null,
            result: null,
            errorMessage: null,
            configRevision: 1,
            activeRequestToken: null,
        };

        uploadsRef.current = { ...uploadsRef.current, [uploadId]: newItem };
        setUploads((prev) => ({ ...prev, [uploadId]: newItem }));
        setExpandedUploadId(uploadId);

        // Auto-run calibrated OpenCV analysis immediately
        executeAnalysis(newItem);
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
        const droppedFiles = Array.from(e.dataTransfer.files);
        droppedFiles.forEach(processAddedFile);
    };

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files) {
            const selectedFiles = Array.from(e.target.files);
            selectedFiles.forEach(processAddedFile);
        }
        // Clear input value so re-uploading the same file triggers onChange
        if (fileInputRef.current) {
            fileInputRef.current.value = "";
        }
    };

    const removeUpload = (uploadId: string) => {
        // Synchronously invalidate and abort running request
        const pending = controllersRef.current[uploadId];
        if (pending) {
            delete controllersRef.current[uploadId];
            pending.controller.abort();
        }

        const item = uploads[uploadId];
        if (item) {
            if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
            if (item.referencePreviewUrl) URL.revokeObjectURL(item.referencePreviewUrl);
        }

        setUploads((prev) => removeUploadItem(prev, uploadId));

        if (expandedUploadId === uploadId) {
            setExpandedUploadId(null);
        }
        if (studioUploadId === uploadId) {
            setStudioUploadId(null);
        }
    };

    // Helper to update upload configuration and invalidate stale results
    const updateUploadConfig = useCallback(
        (uploadId: string, updates: Partial<UploadItem>) => {
            // Synchronously invalidate and abort running request
            const pending = controllersRef.current[uploadId];
            if (pending) {
                delete controllersRef.current[uploadId];
                pending.controller.abort();
            }

            setUploads((prev) => reconfigureUpload(prev, uploadId, updates));
        },
        []
    );

    const uploadList = Object.values(uploads);

    const studioItem = studioUploadId ? uploads[studioUploadId] : null;

    return (
        <div className="rounded-2xl border border-gray-200 bg-white p-4 sm:p-5 lg:p-6 shadow-xs">
            <div className="flex items-center justify-between gap-2">
                <div>
                    <h2 className="text-sm sm:text-base font-semibold text-gray-900">Image Evidence</h2>
                    <p className="mt-0.5 text-xs text-gray-500">
                        Upload dispensing deposit images, draw target ROIs, and configure calibration for visual defect analysis.
                    </p>
                </div>
            </div>

            {globalError && (
                <div className="mt-3 flex items-center justify-between rounded-xl bg-red-50 p-3 text-xs text-red-700">
                    <span>{globalError}</span>
                    <button
                        type="button"
                        onClick={() => setGlobalError(null)}
                        className="text-red-500 hover:text-red-800"
                    >
                        ×
                    </button>
                </div>
            )}

            {/* Drag and Drop Zone */}
            <div
                onDragOver={(e) => {
                    e.preventDefault();
                    setIsDragging(true);
                }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={`mt-4 flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-4 py-6 sm:py-8 transition text-center ${
                    isDragging
                        ? "border-[#6d5dfc] bg-[#eeebff]"
                        : "border-gray-300 bg-gray-50 hover:border-gray-400"
                }`}
            >
                <input
                    type="file"
                    className="hidden"
                    ref={fileInputRef}
                    onChange={handleFileChange}
                    accept="image/jpeg,image/png"
                    multiple
                />
                <div className="flex h-10 w-10 sm:h-11 sm:w-11 items-center justify-center rounded-xl bg-[#eeebff] text-[#6d5dfc]">
                    <Upload size={18} />
                </div>

                <p className="mt-2.5 text-xs sm:text-sm font-medium text-gray-700">
                    Drag and drop images here, or click to browse
                </p>

                <p className="mt-1 text-[11px] text-gray-500">
                    JPEG or PNG format &middot; Maximum 10 MB per image
                </p>
            </div>

            {/* Uploaded Files List */}
            {uploadList.length > 0 && (
                <div className="mt-4 space-y-3">
                    {uploadList.map((item) => {
                        const isExpanded = expandedUploadId === item.id;
                        const isAnalyzing = item.status === "analyzing";

                        return (
                            <div
                                key={item.id}
                                className={`rounded-xl border transition-all ${
                                    item.status === "error"
                                        ? "border-red-200 bg-red-50/20"
                                        : item.result?.status === "CALIBRATED"
                                        ? "border-green-200 bg-green-50/20"
                                        : item.result?.status === "UNRELIABLE"
                                        ? "border-amber-200 bg-amber-50/20"
                                        : "border-gray-200 bg-white"
                                }`}
                            >
                                {/* Header / Summary Bar */}
                                <div className="p-4 sm:p-5">
                                    <div className="flex items-start justify-between gap-3">
                                        <div
                                            className="flex flex-1 cursor-pointer items-start gap-3 min-w-0"
                                            onClick={() =>
                                                setExpandedUploadId(isExpanded ? null : item.id)
                                            }
                                        >
                                            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gray-100 dark:bg-gray-800 text-gray-600 mt-0.5 shadow-2xs">
                                                {isAnalyzing ? (
                                                    <Loader2 size={18} className="animate-spin text-[#6d5dfc]" />
                                                ) : item.status === "error" ? (
                                                    <AlertCircle size={18} className="text-red-500" />
                                                ) : item.result?.status === "CALIBRATED" ? (
                                                    <CheckCircle2 size={18} className="text-green-600" />
                                                ) : (
                                                    <ImageIcon size={18} className="text-[#6d5dfc]" />
                                                )}
                                            </div>

                                            <div className="min-w-0 flex-1">
                                                <div className="flex items-center gap-2 min-w-0">
                                                    <p className="truncate text-sm sm:text-base font-semibold text-gray-900 dark:text-gray-100" title={item.file.name}>
                                                        {item.file.name}
                                                    </p>
                                                    <span className="text-xs text-gray-400 shrink-0">
                                                        ({(item.file.size / 1024).toFixed(1)} KB)
                                                    </span>
                                                </div>

                                                <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs">
                                                    <span className="rounded-md bg-gray-100 dark:bg-gray-800 px-2 py-0.5 font-medium text-gray-700 dark:text-gray-300">
                                                        Mode: {item.mode === "FEATURES_ONLY" ? "Features" : item.mode === "PROCESS_LIMITS" ? "Limits" : "Golden Ref"}
                                                    </span>
                                                    <span className="rounded-md bg-gray-50 dark:bg-gray-800/60 px-2 py-0.5 font-medium text-gray-500">
                                                        {item.rois.length} ROI{item.rois.length === 1 ? "" : "s"}
                                                    </span>

                                                    {item.status === "analyzed" && item.result && (
                                                        <span
                                                            className={`rounded-md px-2 py-0.5 font-bold ${
                                                                item.result.status === "CALIBRATED"
                                                                    ? "bg-green-100 text-green-700 dark:bg-green-950/50 dark:text-green-300"
                                                                    : item.result.status === "UNCALIBRATED"
                                                                    ? "bg-blue-100 text-blue-700 dark:bg-blue-950/50 dark:text-blue-300"
                                                                    : "bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300"
                                                            }`}
                                                        >
                                                            {item.result.status}
                                                        </span>
                                                    )}
                                                    {item.status === "error" && (
                                                        <span className="rounded-md bg-red-100 px-2 py-0.5 font-medium text-red-600">Error</span>
                                                    )}
                                                    {item.status === "ready" && (
                                                        <span className="rounded-md bg-gray-100 px-2 py-0.5 font-medium text-gray-500">Ready</span>
                                                    )}
                                                </div>
                                            </div>
                                        </div>

                                        {/* Quick Actions Top-Right */}
                                        <div className="flex items-center gap-1.5 shrink-0">
                                            <button
                                                type="button"
                                                onClick={() => setStudioUploadId(item.id)}
                                                className="rounded-lg p-1.5 text-gray-500 hover:bg-[#eeebff] hover:text-[#5848e8] dark:hover:bg-gray-800 transition"
                                                title="Expand Studio Canvas"
                                            >
                                                <Maximize2 size={16} />
                                            </button>

                                            <button
                                                type="button"
                                                onClick={() =>
                                                    setExpandedUploadId(isExpanded ? null : item.id)
                                                }
                                                className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-600 transition"
                                                title={isExpanded ? "Collapse" : "Expand"}
                                            >
                                                {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                                            </button>

                                            <button
                                                type="button"
                                                onClick={() => removeUpload(item.id)}
                                                className="rounded-lg p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/50 transition"
                                                title="Remove image"
                                            >
                                                <X size={16} />
                                            </button>
                                        </div>
                                    </div>

                                    {/* Action Row */}
                                    <div className="mt-3 flex items-center justify-between gap-3 border-t border-gray-100 dark:border-gray-800 pt-2.5">
                                        <button
                                            type="button"
                                            disabled={isAnalyzing}
                                            onClick={() => handleRunAnalysis(item.id)}
                                            className="inline-flex items-center gap-2 rounded-xl bg-[#6d5dfc] px-4 py-2 text-xs sm:text-sm font-semibold text-white shadow-xs transition hover:bg-[#5848e8] disabled:opacity-50"
                                        >
                                            {isAnalyzing ? (
                                                <>
                                                    <Loader2 size={14} className="animate-spin" />
                                                    <span>Analyzing...</span>
                                                </>
                                            ) : (
                                                <>
                                                    <Play size={14} />
                                                    <span>Analyze</span>
                                                </>
                                            )}
                                        </button>

                                        {item.result?.observations && item.result.observations.length > 0 && (
                                            <span className="inline-flex items-center gap-1.5 rounded-lg bg-[#eeebff] dark:bg-[#6d5dfc]/20 px-2.5 py-1 text-xs font-semibold text-[#5848e8] dark:text-[#a397ff] border border-[#dcd6ff] dark:border-[#6d5dfc]/40">
                                                <span className="h-1.5 w-1.5 rounded-full bg-[#6d5dfc] animate-pulse" />
                                                {item.result.observations.length} OpenCV Evidence
                                            </span>
                                        )}
                                    </div>
                                </div>

                                {/* Error message banner if present */}
                                {item.errorMessage && (
                                    <div className="border-t border-red-100 bg-red-50 px-4 py-2.5 text-xs text-red-700">
                                        {item.errorMessage}
                                    </div>
                                )}

                                {/* Expanded Configuration & Inspection View */}
                                {isExpanded && (
                                    <div className="border-t border-gray-200/80 dark:border-gray-800 p-4 sm:p-6 lg:p-7 space-y-7 bg-slate-50/40 dark:bg-slate-900/20">
                                        <div className={isFullWidth ? "grid grid-cols-1 xl:grid-cols-12 gap-8 items-start" : "space-y-6"}>
                                            {/* ROI Editor */}
                                            <div className={isFullWidth ? "xl:col-span-7 space-y-5" : "space-y-5"}>
                                                <ImageRoiEditor
                                                    imageUrl={item.previewUrl}
                                                    rois={item.rois}
                                                    disabled={isAnalyzing}
                                                    onChange={(newRois) =>
                                                        updateUploadConfig(item.id, { rois: newRois })
                                                    }
                                                    onExpandStudio={() => setStudioUploadId(item.id)}
                                                />
                                            </div>

                                            {/* Calibration Panel */}
                                            <div className={isFullWidth ? "xl:col-span-5 space-y-5" : "space-y-5"}>
                                                <ImageCalibrationPanel
                                                    mode={item.mode}
                                                    disabled={isAnalyzing}
                                                    onModeChange={(newMode) =>
                                                        updateUploadConfig(item.id, { mode: newMode })
                                                    }
                                                    mmPerPixel={item.mmPerPixel}
                                                    onMmPerPixelChange={(val) =>
                                                        updateUploadConfig(item.id, { mmPerPixel: val })
                                                    }
                                                    processLimits={item.processLimits}
                                                    onProcessLimitsChange={(limits) =>
                                                        updateUploadConfig(item.id, { processLimits: limits })
                                                    }
                                                    referenceLimits={item.referenceLimits}
                                                    onReferenceLimitsChange={(limits) =>
                                                        updateUploadConfig(item.id, { referenceLimits: limits })
                                                    }
                                                    referenceFile={item.referenceFile}
                                                    referencePreviewUrl={item.referencePreviewUrl}
                                                    onReferenceFileChange={(refFile) => {
                                                        if (item.referencePreviewUrl) {
                                                            URL.revokeObjectURL(item.referencePreviewUrl);
                                                        }
                                                        const refUrl = refFile ? URL.createObjectURL(refFile) : null;
                                                        updateUploadConfig(item.id, {
                                                            referenceFile: refFile,
                                                            referencePreviewUrl: refUrl,
                                                        });
                                                    }}
                                                />
                                            </div>
                                        </div>

                                        {/* Returned Analysis Results */}
                                        {item.result && (
                                            <div className="space-y-3 rounded-xl border border-gray-200 bg-gray-50/70 p-3 sm:p-4">
                                                <div className="flex items-center justify-between gap-2">
                                                    <span className="text-xs font-semibold text-gray-800">
                                                        Analysis Results
                                                    </span>
                                                    <div className="flex items-center gap-1.5">
                                                        <span
                                                            className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                                                                item.result.status === "CALIBRATED"
                                                                    ? "bg-green-100 text-green-800"
                                                                    : item.result.status === "UNCALIBRATED"
                                                                    ? "bg-blue-100 text-blue-800"
                                                                    : "bg-amber-100 text-amber-800"
                                                            }`}
                                                        >
                                                            {item.result.status}
                                                        </span>
                                                        <button
                                                            type="button"
                                                            onClick={() => setStudioUploadId(item.id)}
                                                            className="rounded p-1 text-gray-500 hover:text-[#6d5dfc] hover:bg-white transition"
                                                            title="View in CV Studio"
                                                        >
                                                            <Maximize2 size={13} />
                                                        </button>
                                                    </div>
                                                </div>

                                                {item.result.status === "CALIBRATED" && (
                                                    <div className="flex items-start gap-1.5 rounded-lg bg-green-50 p-2 text-xs text-green-800">
                                                        <CheckCircle2 size={14} className="shrink-0 text-green-600 mt-0.5" />
                                                        <span>
                                                            Calibrated evidence produced:{" "}
                                                            {item.result.observations.length} canonical observation(s)
                                                            ready to attach to diagnosis.
                                                        </span>
                                                    </div>
                                                )}

                                                {item.result.status === "UNCALIBRATED" && (
                                                    <div className="flex items-start gap-1.5 rounded-lg bg-blue-50 p-2 text-xs text-blue-800">
                                                        <Info size={14} className="shrink-0 text-blue-600 mt-0.5" />
                                                        <span>
                                                            Pure geometric features extracted. No diagnostic observations
                                                            will be attached to case (FEATURES_ONLY mode).
                                                        </span>
                                                    </div>
                                                )}

                                                {item.result.status === "UNRELIABLE" && (
                                                    <div className="flex items-start gap-1.5 rounded-lg bg-amber-50 p-2 text-xs text-amber-800">
                                                        <AlertCircle size={14} className="shrink-0 text-amber-600 mt-0.5" />
                                                        <span>
                                                            Ambiguous or unsegmentable image. Results are kept as measurements
                                                            only and emit 0 diagnostic observations.
                                                        </span>
                                                    </div>
                                                )}

                                                {/* Quick summary metric cards for compact view */}
                                                {item.result.roi_measurements.length > 0 && (
                                                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                                                        <div className="rounded-lg border border-gray-200 bg-white p-2">
                                                            <span className="block text-[10px] font-medium text-gray-500">Coverage</span>
                                                            <span className="text-xs sm:text-sm font-bold text-gray-900">
                                                                {(item.result.roi_measurements[0].coverage_ratio * 100).toFixed(1)}%
                                                            </span>
                                                        </div>
                                                        <div className="rounded-lg border border-gray-200 bg-white p-2">
                                                            <span className="block text-[10px] font-medium text-gray-500">Overflow</span>
                                                            <span className="text-xs sm:text-sm font-bold text-gray-900">
                                                                {(item.result.roi_measurements[0].overflow_ratio * 100).toFixed(1)}%
                                                            </span>
                                                        </div>
                                                        <div className="rounded-lg border border-gray-200 bg-white p-2">
                                                            <span className="block text-[10px] font-medium text-gray-500">
                                                                {item.mmPerPixel ? "Calibrated Dia" : "Equiv Dia"}
                                                            </span>
                                                            <span className="text-xs sm:text-sm font-bold text-[#5848e8]">
                                                                {item.mmPerPixel && item.result.roi_measurements[0].calibrated_diameter_mm !== null && item.result.roi_measurements[0].calibrated_diameter_mm !== undefined
                                                                    ? `${item.result.roi_measurements[0].calibrated_diameter_mm.toFixed(3)} mm`
                                                                    : `${item.result.roi_measurements[0].equivalent_diameter_px.toFixed(1)} px`}
                                                            </span>
                                                        </div>
                                                        <div className="rounded-lg border border-gray-200 bg-white p-2">
                                                            <span className="block text-[10px] font-medium text-gray-500">Quality</span>
                                                            <span className="text-xs sm:text-sm font-bold text-emerald-600">
                                                                {(item.result.roi_measurements[0].segmentation_quality * 100).toFixed(0)}%
                                                            </span>
                                                        </div>
                                                    </div>
                                                )}

                                                {/* ROI Measurements Table with Clean Horizontal Scroll */}
                                                <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-2xs">
                                                    <table className="w-full text-left text-xs min-w-[540px]">
                                                        <thead>
                                                            <tr className="border-b border-gray-200 bg-gray-50/70 text-gray-500">
                                                                <th className="py-2 px-2.5 font-medium">ROI</th>
                                                                <th className="py-2 px-2.5 font-medium">Coverage</th>
                                                                <th className="py-2 px-2.5 font-medium">Overflow</th>
                                                                <th className="py-2 px-2.5 font-medium">Equiv Dia</th>
                                                                {item.mmPerPixel && (
                                                                    <th className="py-2 px-2.5 font-medium">Calibrated Dia</th>
                                                                )}
                                                                <th className="py-2 px-2.5 font-medium">Shape (Circ / AR)</th>
                                                                <th className="py-2 px-2.5 font-medium">Bubbles</th>
                                                                <th className="py-2 px-2.5 font-medium">Quality</th>
                                                            </tr>
                                                        </thead>
                                                        <tbody className="divide-y divide-gray-100 text-gray-700">
                                                            {item.result.roi_measurements.map((rm) => (
                                                                <tr key={rm.roi_id} className="hover:bg-gray-50/50">
                                                                    <td className="py-1.5 px-2.5 font-semibold text-[#5848e8]">
                                                                        {rm.roi_id}
                                                                    </td>
                                                                    <td className="py-1.5 px-2.5">
                                                                        {(rm.coverage_ratio * 100).toFixed(1)}%
                                                                    </td>
                                                                    <td className="py-1.5 px-2.5">
                                                                        {(rm.overflow_ratio * 100).toFixed(1)}%
                                                                    </td>
                                                                    <td className="py-1.5 px-2.5">
                                                                        {rm.equivalent_diameter_px.toFixed(1)} px
                                                                    </td>
                                                                    {item.mmPerPixel && (
                                                                        <td className="py-1.5 px-2.5">
                                                                            {rm.calibrated_diameter_mm !== null &&
                                                                            rm.calibrated_diameter_mm !== undefined
                                                                                ? `${rm.calibrated_diameter_mm.toFixed(3)} mm`
                                                                                : "-"}
                                                                        </td>
                                                                    )}
                                                                    <td className="py-1.5 px-2.5">
                                                                        <span>
                                                                            {(rm.circularity * 100).toFixed(0)}% circ · {rm.aspect_ratio.toFixed(2)} AR
                                                                        </span>
                                                                        {rm.is_tailing ? (
                                                                            <span className="ml-1 rounded bg-amber-100 px-1 py-0.5 text-[10px] font-medium text-amber-800">
                                                                                Tailing
                                                                            </span>
                                                                        ) : rm.is_abnormal_shape ? (
                                                                            <span className="ml-1 rounded bg-rose-100 px-1 py-0.5 text-[10px] font-medium text-rose-800">
                                                                                Abnormal
                                                                            </span>
                                                                        ) : null}
                                                                    </td>
                                                                    <td className="py-1.5 px-2.5">
                                                                        {(rm.bubble_count ?? 0) > 0 || rm.has_bubbles ? (
                                                                            <span className="rounded bg-rose-100 px-1.5 py-0.5 text-[10px] font-medium text-rose-700">
                                                                                {rm.bubble_count ?? 1} void(s)
                                                                            </span>
                                                                        ) : (
                                                                            <span className="text-gray-400">0</span>
                                                                        )}
                                                                    </td>
                                                                    <td className="py-1.5 px-2.5">
                                                                        {(rm.segmentation_quality * 100).toFixed(0)}%
                                                                    </td>
                                                                </tr>
                                                            ))}
                                                        </tbody>
                                                    </table>
                                                </div>

                                                {/* Warnings */}
                                                {item.result.warnings.length > 0 && (
                                                    <div className="space-y-1 text-[11px] text-amber-700">
                                                        {item.result.warnings.map((w, idx) => (
                                                            <div key={idx} className="flex items-start gap-1">
                                                                <span>&bull;</span>
                                                                <span>{w}</span>
                                                            </div>
                                                        ))}
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}

            {/* Computer Vision Defect Studio Modal */}
            {studioItem && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-3 sm:p-6 overflow-y-auto">
                    <div className="relative flex flex-col max-h-[92vh] w-full max-w-6xl rounded-2xl border border-gray-200 bg-white shadow-2xl overflow-hidden">
                        {/* Studio Header */}
                        <div className="flex items-center justify-between border-b border-gray-200 px-5 sm:px-6 py-3.5 bg-gray-50/80 shrink-0">
                            <div className="flex items-center gap-3 min-w-0">
                                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#eeebff] text-[#6d5dfc]">
                                    <Scan size={20} />
                                </div>
                                <div className="min-w-0">
                                    <div className="flex items-center gap-2">
                                        <h2 className="text-sm sm:text-base font-bold text-gray-900 truncate">
                                            Computer Vision Defect Studio
                                        </h2>
                                        <span className="rounded bg-gray-200 px-2 py-0.5 text-xs font-semibold text-gray-700 truncate max-w-[180px]">
                                            {studioItem.file.name}
                                        </span>
                                    </div>
                                    <p className="text-xs text-gray-500 hidden sm:block">
                                        High-precision ROI annotation, calibration tuning, and OpenCV defect extraction
                                    </p>
                                </div>
                            </div>

                            <div className="flex items-center gap-2 shrink-0">
                                <button
                                    type="button"
                                    disabled={studioItem.status === "analyzing"}
                                    onClick={() => handleRunAnalysis(studioItem.id)}
                                    className="inline-flex items-center gap-1.5 rounded-xl bg-[#6d5dfc] px-3 sm:px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-[#5848e8] transition disabled:opacity-50"
                                >
                                    {studioItem.status === "analyzing" ? (
                                        <>
                                            <Loader2 size={13} className="animate-spin" />
                                            <span>Analyzing...</span>
                                        </>
                                    ) : (
                                        <>
                                            <Play size={13} />
                                            <span>Run CV Analysis</span>
                                        </>
                                    )}
                                </button>
                                <button
                                    type="button"
                                    onClick={() => setStudioUploadId(null)}
                                    className="rounded-xl p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-700 transition"
                                    title="Close Studio"
                                >
                                    <X size={18} />
                                </button>
                            </div>
                        </div>

                        {/* Studio Body */}
                        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
                            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                                {/* Left: Interactive Canvas */}
                                <div className="lg:col-span-7 space-y-4">
                                    <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-xs">
                                        <ImageRoiEditor
                                            imageUrl={studioItem.previewUrl}
                                            rois={studioItem.rois}
                                            disabled={studioItem.status === "analyzing"}
                                            onChange={(newRois) => updateUploadConfig(studioItem.id, { rois: newRois })}
                                            isStudioMode={true}
                                        />
                                    </div>
                                </div>

                                {/* Right: Calibration & Output */}
                                <div className="lg:col-span-5 space-y-4">
                                    <ImageCalibrationPanel
                                        mode={studioItem.mode}
                                        disabled={studioItem.status === "analyzing"}
                                        onModeChange={(newMode) => updateUploadConfig(studioItem.id, { mode: newMode })}
                                        mmPerPixel={studioItem.mmPerPixel}
                                        onMmPerPixelChange={(val) => updateUploadConfig(studioItem.id, { mmPerPixel: val })}
                                        processLimits={studioItem.processLimits}
                                        onProcessLimitsChange={(limits) => updateUploadConfig(studioItem.id, { processLimits: limits })}
                                        referenceLimits={studioItem.referenceLimits}
                                        onReferenceLimitsChange={(limits) => updateUploadConfig(studioItem.id, { referenceLimits: limits })}
                                        referenceFile={studioItem.referenceFile}
                                        referencePreviewUrl={studioItem.referencePreviewUrl}
                                        onReferenceFileChange={(refFile) => {
                                            if (studioItem.referencePreviewUrl) URL.revokeObjectURL(studioItem.referencePreviewUrl);
                                            const refUrl = refFile ? URL.createObjectURL(refFile) : null;
                                            updateUploadConfig(studioItem.id, {
                                                referenceFile: refFile,
                                                referencePreviewUrl: refUrl,
                                            });
                                        }}
                                    />

                                    {/* Analysis results in Studio view */}
                                    {studioItem.result && (
                                        <div className="space-y-3 rounded-xl border border-gray-200 bg-gray-50/70 p-4">
                                            <div className="flex items-center justify-between">
                                                <span className="text-xs font-semibold text-gray-800">
                                                    OpenCV Defect Findings
                                                </span>
                                                <span
                                                    className={`rounded-full px-2 py-0.5 text-xs font-bold ${
                                                        studioItem.result.status === "CALIBRATED"
                                                            ? "bg-green-100 text-green-800"
                                                            : studioItem.result.status === "UNCALIBRATED"
                                                            ? "bg-blue-100 text-blue-800"
                                                            : "bg-amber-100 text-amber-800"
                                                    }`}
                                                >
                                                    {studioItem.result.status}
                                                </span>
                                            </div>

                                            {studioItem.result.observations.length > 0 && (
                                                <div className="space-y-1.5">
                                                    <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider">
                                                        Canonical Diagnostic Observations
                                                    </p>
                                                    <div className="flex flex-wrap gap-1.5">
                                                        {studioItem.result.observations.map((obs, idx) => (
                                                            <span
                                                                key={idx}
                                                                className="inline-flex items-center gap-1.5 rounded-lg bg-[#eeebff] px-2.5 py-1 text-xs font-semibold text-[#5848e8] border border-[#dcd6ff]"
                                                            >
                                                                <span className="h-1.5 w-1.5 rounded-full bg-[#6d5dfc]" />
                                                                {obs.observation_type} = {obs.value}
                                                            </span>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>
                            </div>

                            {/* Measurements Full Table in Studio View */}
                            {studioItem.result && (
                                <div className="rounded-xl border border-gray-200 bg-white p-4 space-y-3 shadow-xs">
                                    <h4 className="text-xs font-semibold text-gray-900">
                                        Comprehensive ROI Measurements & Morphology
                                    </h4>
                                    <div className="overflow-x-auto rounded-lg border border-gray-100">
                                        <table className="w-full text-left text-xs min-w-[650px]">
                                            <thead>
                                                <tr className="border-b border-gray-200 bg-gray-50 text-gray-600">
                                                    <th className="py-2 px-3 font-semibold">ROI ID</th>
                                                    <th className="py-2 px-3 font-semibold">Coverage</th>
                                                    <th className="py-2 px-3 font-semibold">Overflow</th>
                                                    <th className="py-2 px-3 font-semibold">Equiv Dia (px)</th>
                                                    {studioItem.mmPerPixel && (
                                                        <th className="py-2 px-3 font-semibold">Calibrated Dia (mm)</th>
                                                    )}
                                                    <th className="py-2 px-3 font-semibold">Circularity</th>
                                                    <th className="py-2 px-3 font-semibold">Aspect Ratio</th>
                                                    <th className="py-2 px-3 font-semibold">Tailing / Shape</th>
                                                    <th className="py-2 px-3 font-semibold">Voids / Bubbles</th>
                                                    <th className="py-2 px-3 font-semibold">Segmentation Quality</th>
                                                </tr>
                                            </thead>
                                            <tbody className="divide-y divide-gray-100 text-gray-700">
                                                {studioItem.result.roi_measurements.map((rm) => (
                                                    <tr key={rm.roi_id} className="hover:bg-gray-50">
                                                        <td className="py-2 px-3 font-bold text-[#5848e8]">
                                                            {rm.roi_id}
                                                        </td>
                                                        <td className="py-2 px-3">
                                                            {(rm.coverage_ratio * 100).toFixed(1)}%
                                                        </td>
                                                        <td className="py-2 px-3">
                                                            {(rm.overflow_ratio * 100).toFixed(1)}%
                                                        </td>
                                                        <td className="py-2 px-3">
                                                            {rm.equivalent_diameter_px.toFixed(1)} px
                                                        </td>
                                                        {studioItem.mmPerPixel && (
                                                            <td className="py-2 px-3 font-semibold text-gray-900">
                                                                {rm.calibrated_diameter_mm !== null && rm.calibrated_diameter_mm !== undefined
                                                                    ? `${rm.calibrated_diameter_mm.toFixed(3)} mm`
                                                                    : "-"}
                                                            </td>
                                                        )}
                                                        <td className="py-2 px-3">
                                                            {(rm.circularity * 100).toFixed(1)}%
                                                        </td>
                                                        <td className="py-2 px-3">
                                                            {rm.aspect_ratio.toFixed(2)}
                                                        </td>
                                                        <td className="py-2 px-3">
                                                            {rm.is_tailing ? (
                                                                <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[11px] font-semibold text-amber-800">
                                                                    Tailing Detected
                                                                </span>
                                                            ) : rm.is_abnormal_shape ? (
                                                                <span className="rounded bg-rose-100 px-1.5 py-0.5 text-[11px] font-semibold text-rose-800">
                                                                    Abnormal
                                                                </span>
                                                            ) : (
                                                                <span className="text-emerald-700 font-medium">Normal</span>
                                                            )}
                                                        </td>
                                                        <td className="py-2 px-3">
                                                            {(rm.bubble_count ?? 0) > 0 || rm.has_bubbles ? (
                                                                <span className="rounded bg-rose-100 px-1.5 py-0.5 text-[11px] font-semibold text-rose-700">
                                                                    {rm.bubble_count ?? 1} void(s)
                                                                </span>
                                                            ) : (
                                                                <span className="text-gray-400">0</span>
                                                            )}
                                                        </td>
                                                        <td className="py-2 px-3 font-medium text-emerald-700">
                                                            {(rm.segmentation_quality * 100).toFixed(0)}%
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Studio Footer */}
                        <div className="flex items-center justify-between border-t border-gray-200 px-6 py-3 bg-gray-50 text-xs text-gray-500 shrink-0">
                            <div className="flex items-center gap-2">
                                <CheckCircle2 size={14} className="text-green-600" />
                                <span>Edits sync automatically with the diagnostic case workflow.</span>
                            </div>
                            <button
                                type="button"
                                onClick={() => setStudioUploadId(null)}
                                className="rounded-lg bg-gray-900 px-4 py-1.5 text-xs font-semibold text-white hover:bg-gray-800 transition"
                            >
                                Done & Close Studio
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
