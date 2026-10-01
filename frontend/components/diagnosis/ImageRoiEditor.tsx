"use client";

import { useState, useRef, useCallback, useEffect, useMemo } from "react";
import { Trash2, RotateCcw, AlertCircle, Crosshair, Maximize2, MousePointer, Plus } from "lucide-react";
import { NormalizedROI, ImageAnalysisResponse } from "@/types/image";
import {
    computeContentRect,
    clientToNormalizedCoords,
    validateDepositOutline,
    formatPolygonPoints,
    matchMeasurementByRoiId,
    getEffectiveRoiStatus,
} from "@/lib/region-inspection-view";

export type RoiInteractionMode = "inspect" | "draw";

interface ImageRoiEditorProps {
    imageUrl: string;
    rois: NormalizedROI[];
    onChange: (rois: NormalizedROI[]) => void;
    disabled?: boolean;
    onExpandStudio?: () => void;
    isStudioMode?: boolean;
    selectedRoiId?: string | null;
    onSelectRoi?: (roiId: string | null) => void;
    result?: ImageAnalysisResponse | null;
    interactionMode?: RoiInteractionMode;
    onInteractionModeChange?: (mode: RoiInteractionMode) => void;
}

export default function ImageRoiEditor({
    imageUrl,
    rois,
    onChange,
    disabled = false,
    onExpandStudio,
    isStudioMode = false,
    selectedRoiId,
    onSelectRoi,
    result,
    interactionMode: propInteractionMode,
    onInteractionModeChange: propOnInteractionModeChange,
}: ImageRoiEditorProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const imgRef = useRef<HTMLImageElement>(null);

    const [naturalSize, setNaturalSize] = useState<{ width: number; height: number }>({ width: 0, height: 0 });
    const [containerSize, setContainerSize] = useState<{ width: number; height: number }>({ width: 0, height: 0 });

    const [internalMode, setInternalMode] = useState<RoiInteractionMode>(() => {
        if (rois.length === 0) return "draw";
        if (result) return "inspect";
        return "draw";
    });

    const activeMode = propInteractionMode ?? internalMode;
    const setInteractionMode = useCallback(
        (nextMode: RoiInteractionMode) => {
            if (propOnInteractionModeChange) {
                propOnInteractionModeChange(nextMode);
            } else {
                setInternalMode(nextMode);
            }
        },
        [propOnInteractionModeChange]
    );

    // Auto-switch to draw mode if rois becomes empty (e.g. after reset)
    useEffect(() => {
        if (rois.length === 0 && activeMode !== "draw") {
            setInteractionMode("draw");
        }
    }, [rois.length, activeMode, setInteractionMode]);

    const [isDrawing, setIsDrawing] = useState(false);
    const [startPoint, setStartPoint] = useState<{ x: number; y: number } | null>(null);
    const [currentPoint, setCurrentPoint] = useState<{ x: number; y: number } | null>(null);

    const isDrawingRef = useRef(false);
    const startPointRef = useRef<{ x: number; y: number } | null>(null);
    const currentPointRef = useRef<{ x: number; y: number } | null>(null);

    // Track container dimensions with ResizeObserver
    useEffect(() => {
        if (!containerRef.current) return;
        const el = containerRef.current;
        const updateSize = () => {
            setContainerSize({
                width: el.clientWidth,
                height: el.clientHeight,
            });
        };
        updateSize();

        const observer = new ResizeObserver((entries) => {
            for (const entry of entries) {
                setContainerSize({
                    width: entry.contentRect.width,
                    height: entry.contentRect.height,
                });
            }
        });
        observer.observe(el);
        return () => observer.disconnect();
    }, []);

    // Sync natural dimensions from image element when URL changes
    useEffect(() => {
        if (imgRef.current && imgRef.current.naturalWidth > 0) {
            setNaturalSize({
                width: imgRef.current.naturalWidth,
                height: imgRef.current.naturalHeight,
            });
        }
    }, [imageUrl]);

    // Letterbox/pillarbox content rectangle
    const contentRect = useMemo(() => {
        return computeContentRect(
            containerSize.width,
            containerSize.height,
            naturalSize.width,
            naturalSize.height
        );
    }, [containerSize.width, containerSize.height, naturalSize.width, naturalSize.height]);

    // Normalized pointer coordinates relative to image content rect
    const getNormalizedCoords = useCallback(
        (e: React.PointerEvent<HTMLDivElement>) => {
            if (!containerRef.current) return { x: 0, y: 0, isInside: false };
            const rect = containerRef.current.getBoundingClientRect();
            const currContentRect = computeContentRect(
                rect.width,
                rect.height,
                naturalSize.width || (imgRef.current?.naturalWidth ?? 0),
                naturalSize.height || (imgRef.current?.naturalHeight ?? 0)
            );
            return clientToNormalizedCoords(
                e.clientX,
                e.clientY,
                { left: rect.left, top: rect.top, width: rect.width, height: rect.height },
                currContentRect
            );
        },
        [naturalSize]
    );

    const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
        if (disabled) return;
        // Only accept primary button
        if (e.button !== 0) return;

        // In Inspect mode: clicking empty space on the image deselects the current ROI; never draws
        if (activeMode === "inspect") {
            onSelectRoi?.(null);
            return;
        }

        const coords = getNormalizedCoords(e);
        // Reject drags starting outside rendered image content in empty letterbox space
        if (!coords.isInside) {
            return;
        }

        try {
            (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
        } catch {
            // Ignore capture failure on synthetic/unsupported pointer devices
        }
        isDrawingRef.current = true;
        startPointRef.current = { x: coords.x, y: coords.y };
        currentPointRef.current = { x: coords.x, y: coords.y };
        setStartPoint({ x: coords.x, y: coords.y });
        setCurrentPoint({ x: coords.x, y: coords.y });
        setIsDrawing(true);
    };

    const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
        if (activeMode !== "draw") return;
        if (!isDrawingRef.current || !startPointRef.current || disabled) return;
        const coords = getNormalizedCoords(e);
        currentPointRef.current = { x: coords.x, y: coords.y };
        setCurrentPoint({ x: coords.x, y: coords.y });
    };

    const handlePointerUp = () => {
        if (activeMode !== "draw") return;
        const isDrawingVal = isDrawingRef.current;
        const startPt = startPointRef.current;
        const currentPt = currentPointRef.current;

        isDrawingRef.current = false;
        startPointRef.current = null;
        currentPointRef.current = null;
        setIsDrawing(false);
        setStartPoint(null);
        setCurrentPoint(null);

        if (!isDrawingVal || !startPt || !currentPt || disabled) {
            return;
        }

        const x = Math.min(startPt.x, currentPt.x);
        const y = Math.min(startPt.y, currentPt.y);
        const width = Math.abs(currentPt.x - startPt.x);
        const height = Math.abs(currentPt.y - startPt.y);

        // Minimum size threshold to prevent accidental clicks
        if (width >= 0.02 && height >= 0.02) {
            // Find next available dot index
            const existingIndices = rois
                .map((r) => {
                    const match = r.roi_id.match(/^dot-(\d+)$/);
                    return match ? parseInt(match[1], 10) : 0;
                })
                .filter((n) => n > 0);
            const nextIndex = existingIndices.length > 0 ? Math.max(...existingIndices) + 1 : rois.length + 1;
            const newRoiId = `dot-${nextIndex}`;
            const newRoi: NormalizedROI = {
                roi_id: newRoiId,
                x: Number(x.toFixed(4)),
                y: Number(y.toFixed(4)),
                width: Number(width.toFixed(4)),
                height: Number(height.toFixed(4)),
            };
            onChange([...rois, newRoi]);
            onSelectRoi?.(newRoiId);
        }
    };

    const handleRemoveRoi = (roiId: string) => {
        if (disabled) return;
        if (selectedRoiId === roiId) {
            onSelectRoi?.(null);
        }
        onChange(rois.filter((r) => r.roi_id !== roiId));
    };

    const handleResetAll = () => {
        if (disabled) return;
        onSelectRoi?.(null);
        onChange([]);
        setInteractionMode("draw");
    };

    // Calculate active drawing box
    const activeBox =
        isDrawing && startPoint && currentPoint
            ? {
                  left: `${Math.min(startPoint.x, currentPoint.x) * 100}%`,
                  top: `${Math.min(startPoint.y, currentPoint.y) * 100}%`,
                  width: `${Math.abs(currentPoint.x - startPoint.x) * 100}%`,
                  height: `${Math.abs(currentPoint.y - startPoint.y) * 100}%`,
              }
            : null;

    const isDrawMode = activeMode === "draw";

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between gap-3 flex-wrap">
                <div className="flex items-center gap-2 min-w-0">
                    <Crosshair size={16} className="text-[#6d5dfc] shrink-0" />
                    <span className="text-sm font-bold text-gray-900 whitespace-nowrap">
                        Regions of Interest (ROIs)
                    </span>
                    <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600 shrink-0">
                        {rois.length} {rois.length === 1 ? "defined" : "defined"}
                    </span>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                    {/* Explicit Draw / Inspect Mode Toggle */}
                    <div
                        role="radiogroup"
                        aria-label="ROI Interaction Mode"
                        className="inline-flex items-center rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-100 dark:bg-gray-800 p-0.5 text-xs font-semibold"
                    >
                        <button
                            type="button"
                            role="radio"
                            aria-checked={activeMode === "inspect"}
                            onClick={() => setInteractionMode("inspect")}
                            disabled={disabled || rois.length === 0}
                            title={rois.length === 0 ? "Draw an ROI first before inspecting" : "Inspect and select target regions"}
                            className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 transition cursor-pointer ${
                                activeMode === "inspect"
                                    ? "bg-white dark:bg-[#141b29] text-[#5848e8] dark:text-[#a397ff] shadow-xs"
                                    : "text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100"
                            } ${disabled || rois.length === 0 ? "opacity-50 cursor-not-allowed" : ""}`}
                        >
                            <MousePointer size={12} />
                            <span>Inspect</span>
                        </button>
                        <button
                            type="button"
                            role="radio"
                            aria-checked={activeMode === "draw"}
                            onClick={() => setInteractionMode("draw")}
                            disabled={disabled}
                            title="Draw new rectangular target ROIs"
                            className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 transition cursor-pointer ${
                                activeMode === "draw"
                                    ? "bg-white dark:bg-[#141b29] text-[#5848e8] dark:text-[#a397ff] shadow-xs"
                                    : "text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100"
                            } ${disabled ? "opacity-50 cursor-not-allowed" : ""}`}
                        >
                            <Plus size={12} />
                            <span>Draw ROI</span>
                        </button>
                    </div>

                    {rois.length > 0 && !disabled && (
                        <button
                            type="button"
                            onClick={handleResetAll}
                            className="inline-flex items-center gap-1.5 text-xs font-medium text-gray-500 hover:text-red-600 transition"
                        >
                            <RotateCcw size={12} />
                            <span>Reset ROIs</span>
                        </button>
                    )}
                </div>
            </div>

            {/* Interactive Image Container */}
            <div
                ref={containerRef}
                onPointerDown={handlePointerDown}
                onPointerMove={handlePointerMove}
                onPointerUp={handlePointerUp}
                onPointerCancel={handlePointerUp}
                className={`relative select-none overflow-hidden rounded-xl border border-gray-300 bg-gray-950 flex items-center justify-center ${
                    disabled
                        ? "cursor-not-allowed opacity-75"
                        : isDrawMode
                        ? "cursor-crosshair"
                        : "cursor-default"
                }`}
                style={{ touchAction: "none" }}
            >
                {/* Expand Studio Floating Action Button */}
                {onExpandStudio && !isStudioMode && (
                    <button
                        type="button"
                        onClick={(e) => {
                            e.stopPropagation();
                            onExpandStudio();
                        }}
                        className="absolute top-2.5 right-2.5 z-30 inline-flex items-center gap-1.5 rounded-lg bg-black/75 hover:bg-black/90 backdrop-blur-xs px-2.5 py-1.5 text-xs font-semibold text-white shadow-md transition"
                        title="Open Full Computer Vision Studio"
                    >
                        <Maximize2 size={13} />
                        <span>Expand Studio</span>
                    </button>
                )}

                {/* Safe natural-dimension local preview */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                    ref={imgRef}
                    src={imageUrl}
                    alt="Deposit target"
                    onLoad={(e) => {
                        setNaturalSize({
                            width: e.currentTarget.naturalWidth,
                            height: e.currentTarget.naturalHeight,
                        });
                    }}
                    className={`block w-full object-contain pointer-events-none select-none ${
                        isStudioMode ? "max-h-[600px]" : "max-h-[440px] xl:max-h-[480px]"
                    }`}
                    draggable={false}
                />

                {/* Helper prompt overlay when 0 ROIs */}
                {rois.length === 0 && !isDrawing && (
                    <div className="pointer-events-none absolute bottom-2 left-2 right-2 z-20 flex items-center justify-center gap-1.5 rounded-lg bg-black/60 backdrop-blur-xs px-2.5 py-1 text-[11px] font-medium text-white/90">
                        <Crosshair size={13} className="text-amber-400 shrink-0" />
                        <span className="truncate">Drag box over deposit to define target ROI</span>
                    </div>
                )}

                {/* Overlay layer strictly mapped to rendered image contentRect (excluding letterbox padding) */}
                <div
                    className="absolute pointer-events-none"
                    style={{
                        left: `${contentRect.left}px`,
                        top: `${contentRect.top}px`,
                        width: `${contentRect.width}px`,
                        height: `${contentRect.height}px`,
                    }}
                >
                    {/* SVG Deposit Outlines Layer for DETECTED regions */}
                    <svg
                        className="pointer-events-none absolute inset-0 h-full w-full"
                        viewBox="0 0 1000 1000"
                        preserveAspectRatio="none"
                    >
                        {rois.map((roi) => {
                            const measurement = result
                                ? matchMeasurementByRoiId(result.roi_measurements, roi.roi_id)
                                : null;
                            const outlineVal = validateDepositOutline(
                                measurement?.deposit_outline_normalized,
                                measurement?.inspection_status
                            );
                            if (!outlineVal.isValid || !outlineVal.points) return null;
                            const isSelected = roi.roi_id === selectedRoiId;
                            const pointsStr = formatPolygonPoints(outlineVal.points);

                            return (
                                <polygon
                                    key={`outline-${roi.roi_id}`}
                                    points={pointsStr}
                                    className={
                                        isSelected
                                            ? "fill-emerald-400/35 stroke-emerald-300 stroke-[3]"
                                            : "fill-emerald-500/20 stroke-emerald-400 stroke-[1.5]"
                                    }
                                    style={{
                                        filter: isSelected
                                            ? "drop-shadow(0 0 4px rgba(52, 211, 153, 0.8))"
                                            : undefined,
                                    }}
                                />
                            );
                        })}
                    </svg>

                    {/* Existing ROIs overlay */}
                    {rois.map((roi) => {
                        const isSelected = roi.roi_id === selectedRoiId;
                        const measurement = result
                            ? matchMeasurementByRoiId(result.roi_measurements, roi.roi_id)
                            : null;
                        const statusInfo = getEffectiveRoiStatus(measurement, Boolean(result));

                        // Color coding based on inspection status
                        let borderClass = "border-2 border-[#6d5dfc] bg-[#6d5dfc]/15";
                        let tagBgClass = "bg-[#6d5dfc]";
                        if (result) {
                            switch (statusInfo.status) {
                                case "DETECTED":
                                    borderClass = "border-2 border-emerald-500 bg-emerald-500/15";
                                    tagBgClass = "bg-emerald-600";
                                    break;
                                case "MISSING":
                                    borderClass = "border-2 border-dashed border-rose-500 bg-rose-500/15";
                                    tagBgClass = "bg-rose-600";
                                    break;
                                case "UNASSESSED":
                                    borderClass = "border-2 border-dashed border-amber-500 bg-amber-500/15";
                                    tagBgClass = "bg-amber-600";
                                    break;
                                case "UNAVAILABLE":
                                default:
                                    borderClass = "border-2 border-gray-400 bg-gray-400/15";
                                    tagBgClass = "bg-gray-600";
                                    break;
                            }
                        }

                        return (
                            <div
                                key={roi.roi_id}
                                tabIndex={isDrawMode ? -1 : 0}
                                role="button"
                                aria-label={`Select region ${roi.roi_id}: ${statusInfo.label}`}
                                onClick={
                                    isDrawMode
                                        ? undefined
                                        : (e) => {
                                              e.stopPropagation();
                                              onSelectRoi?.(isSelected ? null : roi.roi_id);
                                          }
                                }
                                onKeyDown={
                                    isDrawMode
                                        ? undefined
                                        : (e) => {
                                              if (e.key === "Enter" || e.key === " ") {
                                                  e.preventDefault();
                                                  e.stopPropagation();
                                                  onSelectRoi?.(isSelected ? null : roi.roi_id);
                                              }
                                          }
                                }
                                className={`absolute transition-all ${
                                    isDrawMode
                                        ? "pointer-events-none"
                                        : "pointer-events-auto cursor-pointer focus:outline-hidden"
                                } ${borderClass} ${
                                    isSelected
                                        ? "ring-2 ring-offset-2 ring-[#6d5dfc] dark:ring-[#a397ff] z-20 shadow-md"
                                        : "hover:border-opacity-100 z-10"
                                }`}
                                style={{
                                    left: `${roi.x * 100}%`,
                                    top: `${roi.y * 100}%`,
                                    width: `${roi.width * 100}%`,
                                    height: `${roi.height * 100}%`,
                                }}
                            >
                                <div
                                    className={`absolute -top-6 left-0 flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-semibold text-white shadow-xs pointer-events-auto ${tagBgClass}`}
                                >
                                    <span>{roi.roi_id}</span>
                                    {result && (
                                        <span className="text-[9px] opacity-90 font-normal">
                                            ({statusInfo.label})
                                        </span>
                                    )}
                                    {!disabled && (
                                        <button
                                            type="button"
                                            onPointerDown={(e) => e.stopPropagation()}
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                handleRemoveRoi(roi.roi_id);
                                            }}
                                            className="ml-1 hover:text-red-200 cursor-pointer"
                                            title={`Remove ${roi.roi_id}`}
                                            aria-label={`Remove ${roi.roi_id}`}
                                        >
                                            ×
                                        </button>
                                    )}
                                </div>
                            </div>
                        );
                    })}

                    {/* Active drawing rectangle */}
                    {activeBox && (
                        <div
                            className="pointer-events-none absolute border-2 border-dashed border-amber-400 bg-amber-400/20 z-30"
                            style={{
                                left: activeBox.left,
                                top: activeBox.top,
                                width: activeBox.width,
                                height: activeBox.height,
                            }}
                        />
                    )}
                </div>
            </div>

            {/* Helper guidance */}
            {rois.length === 0 && (
                <div className="flex items-center gap-2 rounded-lg bg-amber-50 dark:bg-amber-950/40 p-2.5 text-xs text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
                    <AlertCircle size={14} className="shrink-0 text-amber-600" />
                    <span>
                        Draw at least one rectangular target ROI over the image by clicking and dragging.
                    </span>
                </div>
            )}

            {rois.length > 0 && isDrawMode && (
                <div className="flex items-center justify-between gap-2 rounded-lg bg-indigo-50/70 dark:bg-indigo-950/30 p-2.5 text-xs text-[#5848e8] dark:text-[#a397ff] border border-indigo-100 dark:border-indigo-900/50">
                    <div className="flex items-center gap-2">
                        <Crosshair size={14} className="shrink-0 text-[#6d5dfc]" />
                        <span>
                            <strong>Draw Mode active:</strong> Drag anywhere on the image to add a new ROI. You can start drawing inside existing regions.
                        </span>
                    </div>
                    <button
                        type="button"
                        onClick={() => setInteractionMode("inspect")}
                        className="text-[11px] font-semibold underline hover:text-[#4335c4] cursor-pointer shrink-0"
                    >
                        Switch to Inspect
                    </button>
                </div>
            )}

            {rois.length > 0 && (
                <div className="space-y-3 pt-2">
                    <div className="flex items-center justify-between">
                        <p className="text-xs font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                            Saved Target Regions
                        </p>
                        <span className="text-xs text-gray-400 font-medium">
                            {rois.length} target{rois.length === 1 ? "" : "s"}
                        </span>
                    </div>
                    <div className="max-h-56 overflow-y-auto space-y-2.5 rounded-xl border border-gray-200/80 dark:border-gray-800 bg-gray-50/60 dark:bg-gray-800/40 p-3 text-xs">
                        {rois.map((roi) => {
                            const isSelected = roi.roi_id === selectedRoiId;
                            const measurement = result
                                ? matchMeasurementByRoiId(result.roi_measurements, roi.roi_id)
                                : null;
                            const statusInfo = getEffectiveRoiStatus(measurement, Boolean(result));

                            return (
                                <div
                                    key={roi.roi_id}
                                    tabIndex={0}
                                    role="button"
                                    aria-label={`Select ${roi.roi_id}`}
                                    onClick={() => onSelectRoi?.(isSelected ? null : roi.roi_id)}
                                    onKeyDown={(e) => {
                                        if (e.key === "Enter" || e.key === " ") {
                                            e.preventDefault();
                                            onSelectRoi?.(isSelected ? null : roi.roi_id);
                                        }
                                    }}
                                    className={`flex items-center justify-between gap-4 rounded-xl border p-3 text-xs transition cursor-pointer focus:outline-hidden ${
                                        isSelected
                                            ? "border-[#6d5dfc] bg-[#eeebff]/30 dark:bg-[#6d5dfc]/10 ring-1 ring-[#6d5dfc] shadow-xs"
                                            : "border-gray-200 dark:border-gray-700 bg-white dark:bg-[#141b29] hover:border-gray-300 dark:hover:border-gray-600"
                                    }`}
                                >
                                    <div className="min-w-0 flex-1">
                                        <div className="flex items-center gap-2 flex-wrap">
                                            <span className="font-bold text-xs sm:text-sm text-[#5848e8] dark:text-[#a397ff]">
                                                {roi.roi_id}
                                            </span>
                                            {result ? (
                                                <span
                                                    className={`rounded-md px-2 py-0.5 text-[10px] font-semibold ${
                                                        statusInfo.status === "DETECTED"
                                                            ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800"
                                                            : statusInfo.status === "MISSING"
                                                            ? "bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300 border border-rose-200 dark:border-rose-800"
                                                            : statusInfo.status === "UNASSESSED"
                                                            ? "bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300 border border-amber-200 dark:border-amber-800"
                                                            : "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300 border border-gray-200 dark:border-gray-700"
                                                    }`}
                                                >
                                                    {statusInfo.label}
                                                </span>
                                            ) : (
                                                <span className="rounded-md bg-indigo-50 dark:bg-[#6d5dfc]/20 px-2 py-0.5 text-[10px] sm:text-xs font-semibold text-[#5848e8] dark:text-[#a397ff]">
                                                    Target ROI
                                                </span>
                                            )}
                                            {isSelected && (
                                                <span className="rounded-md bg-[#6d5dfc] text-white px-1.5 py-0.5 text-[9px] font-semibold">
                                                    Selected
                                                </span>
                                            )}
                                        </div>
                                        <div className="mt-2 grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono text-gray-700 dark:text-gray-300">
                                            <span className="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-md px-2 py-1 text-center">
                                                X: {(roi.x * 100).toFixed(1)}%
                                            </span>
                                            <span className="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-md px-2 py-1 text-center">
                                                Y: {(roi.y * 100).toFixed(1)}%
                                            </span>
                                            <span className="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-md px-2 py-1 text-center">
                                                W: {(roi.width * 100).toFixed(1)}%
                                            </span>
                                            <span className="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-md px-2 py-1 text-center">
                                                H: {(roi.height * 100).toFixed(1)}%
                                            </span>
                                        </div>
                                    </div>
                                    {!disabled && (
                                        <button
                                            type="button"
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                handleRemoveRoi(roi.roi_id);
                                            }}
                                            className="rounded-lg p-2 text-gray-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/50 transition shrink-0"
                                            title={`Delete ${roi.roi_id}`}
                                            aria-label={`Delete ${roi.roi_id}`}
                                        >
                                            <Trash2 size={16} />
                                        </button>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
}
