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
} from "lucide-react";
import ImageRoiEditor from "./ImageRoiEditor";
import ImageCalibrationPanel from "./ImageCalibrationPanel";
import { imagesApi } from "@/lib/api/images";
import {
    AnalysisProfile,
    UploadItem,
    UploadSnapshot,
} from "@/types/image";

interface InFlightController {
    token: number;
    controller: AbortController;
}

export function validateAnalysisConfiguration(item: UploadItem): string | null {
    if (item.rois.length === 0) {
        return "At least one target ROI must be defined before running analysis.";
    }

    for (const roi of item.rois) {
        if (!roi.roi_id || !roi.roi_id.trim()) {
            return "All ROIs must have a valid non-empty identifier.";
        }
        if (
            !Number.isFinite(roi.x) || roi.x < 0 || roi.x > 1 ||
            !Number.isFinite(roi.y) || roi.y < 0 || roi.y > 1 ||
            !Number.isFinite(roi.width) || roi.width <= 0 || roi.width > 1 ||
            !Number.isFinite(roi.height) || roi.height <= 0 || roi.height > 1
        ) {
            return `ROI ${roi.roi_id} has invalid coordinates. Coordinates must be bounded within [0, 1].`;
        }
        if (roi.x + roi.width > 1.00001 || roi.y + roi.height > 1.00001) {
            return `ROI ${roi.roi_id} extends beyond the image boundaries.`;
        }
    }

    if (item.mmPerPixel !== null && item.mmPerPixel !== undefined) {
        if (!Number.isFinite(item.mmPerPixel) || item.mmPerPixel <= 0) {
            return "Scale (mm per pixel) must be a positive finite number greater than 0.";
        }
    }

    if (item.mode === "PROCESS_LIMITS") {
        const limits = item.processLimits;
        if (!limits) {
            return "PROCESS_LIMITS mode requires at least one process limit threshold.";
        }

        const hasAnyLimit =
            (limits.min_coverage_ratio !== null && limits.min_coverage_ratio !== undefined) ||
            (limits.max_coverage_ratio !== null && limits.max_coverage_ratio !== undefined) ||
            (limits.max_overflow_ratio !== null && limits.max_overflow_ratio !== undefined) ||
            (limits.max_size_cv !== null && limits.max_size_cv !== undefined) ||
            (limits.min_presence_ratio !== null && limits.min_presence_ratio !== undefined);

        if (!hasAnyLimit) {
            return "PROCESS_LIMITS mode requires at least one process limit threshold.";
        }

        if (limits.min_coverage_ratio !== null && limits.min_coverage_ratio !== undefined) {
            if (!Number.isFinite(limits.min_coverage_ratio) || limits.min_coverage_ratio < 0 || limits.min_coverage_ratio > 1) {
                return "Min coverage ratio must be a finite number between 0 and 1.";
            }
        }

        if (limits.max_coverage_ratio !== null && limits.max_coverage_ratio !== undefined) {
            if (!Number.isFinite(limits.max_coverage_ratio) || limits.max_coverage_ratio < 0 || limits.max_coverage_ratio > 1) {
                return "Max coverage ratio must be a finite number between 0 and 1.";
            }
        }

        if (
            limits.min_coverage_ratio !== null && limits.min_coverage_ratio !== undefined &&
            limits.max_coverage_ratio !== null && limits.max_coverage_ratio !== undefined
        ) {
            if (limits.min_coverage_ratio > limits.max_coverage_ratio) {
                return "Min coverage ratio cannot be greater than max coverage ratio.";
            }
        }

        if (limits.max_overflow_ratio !== null && limits.max_overflow_ratio !== undefined) {
            if (!Number.isFinite(limits.max_overflow_ratio) || limits.max_overflow_ratio < 0 || limits.max_overflow_ratio > 1) {
                return "Max overflow ratio must be a finite number between 0 and 1.";
            }
        }

        if (limits.max_size_cv !== null && limits.max_size_cv !== undefined) {
            if (!Number.isFinite(limits.max_size_cv) || limits.max_size_cv < 0) {
                return "Max size CV must be a non-negative finite number (>= 0).";
            }
        }

        if (limits.min_presence_ratio !== null && limits.min_presence_ratio !== undefined) {
            if (!Number.isFinite(limits.min_presence_ratio) || limits.min_presence_ratio < 0 || limits.min_presence_ratio > 1) {
                return "Min presence ratio must be a finite number between 0 and 1.";
            }
        }
    } else if (item.mode === "REFERENCE_IMAGE") {
        if (!item.referenceFile) {
            return "REFERENCE_IMAGE mode requires a reference image to be uploaded.";
        }

        const rLimits = item.referenceLimits;
        if (!rLimits) {
            return "REFERENCE_IMAGE mode requires at least one tolerance or reference ratio bound.";
        }

        const hasRefLimit =
            (rLimits.tolerance_ratio !== null && rLimits.tolerance_ratio !== undefined) ||
            (rLimits.min_reference_ratio !== null && rLimits.min_reference_ratio !== undefined) ||
            (rLimits.max_reference_ratio !== null && rLimits.max_reference_ratio !== undefined);

        if (!hasRefLimit) {
            return "REFERENCE_IMAGE mode requires at least one tolerance or reference ratio bound.";
        }

        if (rLimits.tolerance_ratio !== null && rLimits.tolerance_ratio !== undefined) {
            if (!Number.isFinite(rLimits.tolerance_ratio) || rLimits.tolerance_ratio < 0 || rLimits.tolerance_ratio > 1) {
                return "Tolerance ratio must be a finite number between 0 and 1.";
            }
        }

        if (rLimits.min_reference_ratio !== null && rLimits.min_reference_ratio !== undefined) {
            if (!Number.isFinite(rLimits.min_reference_ratio) || rLimits.min_reference_ratio <= 0) {
                return "Min reference ratio must be a finite number greater than 0 (> 0).";
            }
        }

        if (rLimits.max_reference_ratio !== null && rLimits.max_reference_ratio !== undefined) {
            if (!Number.isFinite(rLimits.max_reference_ratio) || rLimits.max_reference_ratio <= 0) {
                return "Max reference ratio must be a finite number greater than 0 (> 0).";
            }
        }

        if (
            rLimits.min_reference_ratio !== null && rLimits.min_reference_ratio !== undefined &&
            rLimits.max_reference_ratio !== null && rLimits.max_reference_ratio !== undefined
        ) {
            if (rLimits.min_reference_ratio > rLimits.max_reference_ratio) {
                return "Min reference ratio cannot be greater than max reference ratio.";
            }
        }
    }

    return null;
}

interface ImageUploadProps {
    onSnapshotChange?: (snapshot: UploadSnapshot) => void;
    // Retained for backward compatibility if callers expect it
    onAnalysisComplete?: (observations: unknown[]) => void;
}

export default function ImageUpload({
    onSnapshotChange,
    onAnalysisComplete,
}: ImageUploadProps) {
    const [uploads, setUploads] = useState<UploadSnapshot>({});
    const [expandedUploadId, setExpandedUploadId] = useState<string | null>(null);
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

        const newItem: UploadItem = {
            id: uploadId,
            file,
            previewUrl,
            status: "ready",
            mode: "FEATURES_ONLY",
            rois: [],
            mmPerPixel: null,
            processLimits: null,
            referenceLimits: null,
            referenceFile: null,
            referencePreviewUrl: null,
            result: null,
            errorMessage: null,
            configRevision: 1,
            activeRequestToken: null,
        };

        setUploads((prev) => ({ ...prev, [uploadId]: newItem }));
        setExpandedUploadId(uploadId);
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

        setUploads((prev) => {
            const item = prev[uploadId];
            if (item) {
                if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
                if (item.referencePreviewUrl) URL.revokeObjectURL(item.referencePreviewUrl);
            }
            const next = { ...prev };
            delete next[uploadId];
            return next;
        });

        if (expandedUploadId === uploadId) {
            setExpandedUploadId(null);
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

            setUploads((prev) => {
                const current = prev[uploadId];
                if (!current) return prev;

                // Invalidate existing result when configuration changes
                return {
                    ...prev,
                    [uploadId]: {
                        ...current,
                        ...updates,
                        status: "ready",
                        result: null,
                        errorMessage: null,
                        configRevision: current.configRevision + 1,
                        activeRequestToken: null,
                    },
                };
            });
        },
        []
    );

    const handleRunAnalysis = async (uploadId: string) => {
        const item = uploads[uploadId];
        if (!item || item.status === "analyzing") return;

        // Abort any existing in-flight request for this upload
        const existingReq = controllersRef.current[uploadId];
        if (existingReq) {
            delete controllersRef.current[uploadId];
            existingReq.controller.abort();
        }

        // Validate all numeric limits and schema constraints before sending request
        const validationError = validateAnalysisConfiguration(item);
        if (validationError) {
            setUploads((prev) => {
                const cur = prev[uploadId];
                if (!cur) return prev;
                return {
                    ...prev,
                    [uploadId]: {
                        ...cur,
                        status: "ready",
                        errorMessage: validationError,
                    },
                };
            });
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

        setUploads((prev) => {
            const cur = prev[uploadId];
            if (!cur) return prev;
            return {
                ...prev,
                [uploadId]: {
                    ...cur,
                    status: "analyzing",
                    errorMessage: null,
                    activeRequestToken: requestToken,
                },
            };
        });

        try {
            const response = await imagesApi.analyze(
                item.file,
                profile,
                item.referenceFile,
                controller.signal
            );

            // Commit result inside functional state update confirming upload exists,
            // configRevision matches, and request token matches
            setUploads((prev) => {
                const cur = prev[uploadId];
                if (!cur || cur.configRevision !== requestRevision || cur.activeRequestToken !== requestToken) {
                    return prev;
                }
                return {
                    ...prev,
                    [uploadId]: {
                        ...cur,
                        status: "analyzed",
                        result: response,
                        errorMessage: null,
                        activeRequestToken: null,
                    },
                };
            });
        } catch (err: unknown) {
            // Ignore abort exceptions
            if (err instanceof Error && err.name === "AbortError") {
                return;
            }

            const message = err instanceof Error ? err.message : "Image analysis failed.";
            setUploads((prev) => {
                const cur = prev[uploadId];
                if (!cur || cur.configRevision !== requestRevision || cur.activeRequestToken !== requestToken) {
                    return prev;
                }
                return {
                    ...prev,
                    [uploadId]: {
                        ...cur,
                        status: "error",
                        errorMessage: message,
                        activeRequestToken: null,
                    },
                };
            });
        } finally {
            // Delete controller only if stored controller still belongs to this request token
            if (controllersRef.current[uploadId]?.token === requestToken) {
                delete controllersRef.current[uploadId];
            }
        }
    };

    const uploadList = Object.values(uploads);

    return (
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
            <h2 className="text-base font-semibold text-gray-900">Image Evidence</h2>

            <p className="mt-1 text-xs text-gray-500">
                Upload dispensing deposit images, draw target ROIs, and configure calibration for visual defect analysis.
            </p>

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
                className={`mt-4 flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-8 transition ${
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
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#eeebff] text-[#6d5dfc]">
                    <Upload size={20} />
                </div>

                <p className="mt-3 text-sm font-medium text-gray-700">
                    Drag and drop images here, or click to browse
                </p>

                <p className="mt-1 text-xs text-gray-500">
                    JPEG or PNG format &middot; Maximum 10 MB per image
                </p>
            </div>

            {/* Uploaded Files List */}
            {uploadList.length > 0 && (
                <div className="mt-5 space-y-3">
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
                                <div className="flex items-center justify-between p-3.5">
                                    <div
                                        className="flex flex-1 cursor-pointer items-center gap-3 min-w-0"
                                        onClick={() =>
                                            setExpandedUploadId(isExpanded ? null : item.id)
                                        }
                                    >
                                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gray-100 text-gray-600">
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
                                            <div className="flex items-center gap-2">
                                                <p className="truncate text-sm font-semibold text-gray-800">
                                                    {item.file.name}
                                                </p>
                                                <span className="text-[11px] text-gray-400">
                                                    ({(item.file.size / 1024).toFixed(1)} KB)
                                                </span>
                                            </div>

                                            <div className="mt-0.5 flex flex-wrap items-center gap-2 text-xs">
                                                <span className="rounded bg-gray-100 px-1.5 py-0.5 font-medium text-gray-600">
                                                    Mode: {item.mode}
                                                </span>
                                                <span className="text-gray-500">
                                                    {item.rois.length} ROI{item.rois.length === 1 ? "" : "s"}
                                                </span>

                                                {item.status === "analyzed" && item.result && (
                                                    <span
                                                        className={`rounded px-1.5 py-0.5 font-bold ${
                                                            item.result.status === "CALIBRATED"
                                                                ? "bg-green-100 text-green-700"
                                                                : item.result.status === "UNCALIBRATED"
                                                                ? "bg-blue-100 text-blue-700"
                                                                : "bg-amber-100 text-amber-700"
                                                        }`}
                                                    >
                                                        {item.result.status}
                                                    </span>
                                                )}
                                                {item.status === "error" && (
                                                    <span className="text-red-600 font-medium">Error</span>
                                                )}
                                                {item.status === "ready" && (
                                                    <span className="text-gray-400">Ready to analyze</span>
                                                )}
                                            </div>
                                        </div>
                                    </div>

                                    <div className="flex items-center gap-2 shrink-0">
                                        <button
                                            type="button"
                                            disabled={isAnalyzing}
                                            onClick={() => handleRunAnalysis(item.id)}
                                            className="inline-flex items-center gap-1 rounded-lg bg-[#6d5dfc] px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition hover:bg-[#5848e8] disabled:opacity-50"
                                        >
                                            {isAnalyzing ? (
                                                <>
                                                    <Loader2 size={13} className="animate-spin" />
                                                    Analyzing...
                                                </>
                                            ) : (
                                                <>
                                                    <Play size={13} />
                                                    Analyze
                                                </>
                                            )}
                                        </button>

                                        <button
                                            type="button"
                                            onClick={() =>
                                                setExpandedUploadId(isExpanded ? null : item.id)
                                            }
                                            className="rounded-lg p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                                            title={isExpanded ? "Collapse" : "Expand"}
                                        >
                                            {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                                        </button>

                                        <button
                                            type="button"
                                            onClick={() => removeUpload(item.id)}
                                            className="rounded-lg p-1 text-gray-400 hover:bg-red-50 hover:text-red-600"
                                            title="Remove image"
                                        >
                                            <X size={16} />
                                        </button>
                                    </div>
                                </div>

                                {/* Error message banner if present */}
                                {item.errorMessage && (
                                    <div className="border-t border-red-100 bg-red-50 px-4 py-2 text-xs text-red-700">
                                        {item.errorMessage}
                                    </div>
                                )}

                                {/* Expanded Configuration & Inspection View */}
                                {isExpanded && (
                                    <div className="border-t border-gray-100 p-4 space-y-5 bg-white/90">
                                        {/* ROI Editor */}
                                        <ImageRoiEditor
                                            imageUrl={item.previewUrl}
                                            rois={item.rois}
                                            disabled={isAnalyzing}
                                            onChange={(newRois) =>
                                                updateUploadConfig(item.id, { rois: newRois })
                                            }
                                        />

                                        {/* Calibration Panel */}
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

                                        {/* Returned Analysis Results */}
                                        {item.result && (
                                            <div className="space-y-3 rounded-xl border border-gray-200 bg-gray-50/60 p-4">
                                                <div className="flex items-center justify-between">
                                                    <span className="text-xs font-semibold text-gray-800">
                                                        Analysis Results
                                                    </span>
                                                    <span
                                                        className={`rounded-full px-2 py-0.5 text-[11px] font-bold ${
                                                            item.result.status === "CALIBRATED"
                                                                ? "bg-green-100 text-green-800"
                                                                : item.result.status === "UNCALIBRATED"
                                                                ? "bg-blue-100 text-blue-800"
                                                                : "bg-amber-100 text-amber-800"
                                                        }`}
                                                    >
                                                        {item.result.status}
                                                    </span>
                                                </div>

                                                {item.result.status === "CALIBRATED" && (
                                                    <div className="flex items-center gap-1.5 rounded-lg bg-green-50 p-2 text-xs text-green-800">
                                                        <CheckCircle2 size={14} className="shrink-0 text-green-600" />
                                                        <span>
                                                            Calibrated evidence produced:{" "}
                                                            {item.result.observations.length} canonical observation(s)
                                                            ready to attach to diagnosis.
                                                        </span>
                                                    </div>
                                                )}

                                                {item.result.status === "UNCALIBRATED" && (
                                                    <div className="flex items-center gap-1.5 rounded-lg bg-blue-50 p-2 text-xs text-blue-800">
                                                        <Info size={14} className="shrink-0 text-blue-600" />
                                                        <span>
                                                            Pure geometric features extracted. No diagnostic observations
                                                            will be attached to case (FEATURES_ONLY mode).
                                                        </span>
                                                    </div>
                                                )}

                                                {item.result.status === "UNRELIABLE" && (
                                                    <div className="flex items-center gap-1.5 rounded-lg bg-amber-50 p-2 text-xs text-amber-800">
                                                        <AlertCircle size={14} className="shrink-0 text-amber-600" />
                                                        <span>
                                                            Ambiguous or unsegmentable image. Results are kept as measurements
                                                            only and emit 0 diagnostic observations.
                                                        </span>
                                                    </div>
                                                )}

                                                {/* ROI Measurements Table */}
                                                <div className="overflow-x-auto">
                                                    <table className="w-full text-left text-xs">
                                                        <thead>
                                                            <tr className="border-b border-gray-200 text-gray-500">
                                                                <th className="pb-1.5 font-medium">ROI</th>
                                                                <th className="pb-1.5 font-medium">Coverage</th>
                                                                <th className="pb-1.5 font-medium">Overflow</th>
                                                                <th className="pb-1.5 font-medium">Equiv Dia</th>
                                                                {item.mmPerPixel && (
                                                                    <th className="pb-1.5 font-medium">Calibrated Dia</th>
                                                                )}
                                                                <th className="pb-1.5 font-medium">Quality</th>
                                                            </tr>
                                                        </thead>
                                                        <tbody className="divide-y divide-gray-100 text-gray-700">
                                                            {item.result.roi_measurements.map((rm) => (
                                                                <tr key={rm.roi_id}>
                                                                    <td className="py-1.5 font-semibold text-[#5848e8]">
                                                                        {rm.roi_id}
                                                                    </td>
                                                                    <td className="py-1.5">
                                                                        {(rm.coverage_ratio * 100).toFixed(1)}%
                                                                    </td>
                                                                    <td className="py-1.5">
                                                                        {(rm.overflow_ratio * 100).toFixed(1)}%
                                                                    </td>
                                                                    <td className="py-1.5">
                                                                        {rm.equivalent_diameter_px.toFixed(1)} px
                                                                    </td>
                                                                    {item.mmPerPixel && (
                                                                        <td className="py-1.5">
                                                                            {rm.calibrated_diameter_mm !== null &&
                                                                            rm.calibrated_diameter_mm !== undefined
                                                                                ? `${rm.calibrated_diameter_mm.toFixed(3)} mm`
                                                                                : "—"}
                                                                        </td>
                                                                    )}
                                                                    <td className="py-1.5">
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
        </div>
    );
}
