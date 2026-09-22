"use client";

import { useState, useRef, useCallback } from "react";
import { Trash2, RotateCcw, AlertCircle, Crosshair, Maximize2 } from "lucide-react";
import { NormalizedROI } from "@/types/image";

interface ImageRoiEditorProps {
    imageUrl: string;
    rois: NormalizedROI[];
    onChange: (rois: NormalizedROI[]) => void;
    disabled?: boolean;
    onExpandStudio?: () => void;
    isStudioMode?: boolean;
}

export default function ImageRoiEditor({
    imageUrl,
    rois,
    onChange,
    disabled = false,
    onExpandStudio,
    isStudioMode = false,
}: ImageRoiEditorProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const [isDrawing, setIsDrawing] = useState(false);
    const [startPoint, setStartPoint] = useState<{ x: number; y: number } | null>(null);
    const [currentPoint, setCurrentPoint] = useState<{ x: number; y: number } | null>(null);

    const getNormalizedCoords = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
        if (!containerRef.current) return { x: 0, y: 0 };
        const rect = containerRef.current.getBoundingClientRect();
        const rawX = (e.clientX - rect.left) / rect.width;
        const rawY = (e.clientY - rect.top) / rect.height;
        return {
            x: Math.max(0, Math.min(1, rawX)),
            y: Math.max(0, Math.min(1, rawY)),
        };
    }, []);

    const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
        if (disabled) return;
        // Only accept primary button
        if (e.button !== 0) return;
        (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
        const coords = getNormalizedCoords(e);
        setStartPoint(coords);
        setCurrentPoint(coords);
        setIsDrawing(true);
    };

    const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
        if (!isDrawing || !startPoint || disabled) return;
        const coords = getNormalizedCoords(e);
        setCurrentPoint(coords);
    };

    const handlePointerUp = () => {
        if (!isDrawing || !startPoint || !currentPoint || disabled) {
            setIsDrawing(false);
            setStartPoint(null);
            setCurrentPoint(null);
            return;
        }

        const x = Math.min(startPoint.x, currentPoint.x);
        const y = Math.min(startPoint.y, currentPoint.y);
        const width = Math.abs(currentPoint.x - startPoint.x);
        const height = Math.abs(currentPoint.y - startPoint.y);

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
            const newRoi: NormalizedROI = {
                roi_id: `dot-${nextIndex}`,
                x: Number(x.toFixed(4)),
                y: Number(y.toFixed(4)),
                width: Number(width.toFixed(4)),
                height: Number(height.toFixed(4)),
            };
            onChange([...rois, newRoi]);
        }

        setIsDrawing(false);
        setStartPoint(null);
        setCurrentPoint(null);
    };

    const handleRemoveRoi = (roiId: string) => {
        if (disabled) return;
        onChange(rois.filter((r) => r.roi_id !== roiId));
    };

    const handleResetAll = () => {
        if (disabled) return;
        onChange([]);
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

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between gap-3">
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
                className={`relative select-none overflow-hidden rounded-xl border border-gray-300 bg-gray-950 ${
                    disabled ? "cursor-not-allowed opacity-75" : "cursor-crosshair"
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
                        className="absolute top-2.5 right-2.5 z-20 inline-flex items-center gap-1.5 rounded-lg bg-black/75 hover:bg-black/90 backdrop-blur-xs px-2.5 py-1.5 text-xs font-semibold text-white shadow-md transition"
                        title="Open Full Computer Vision Studio"
                    >
                        <Maximize2 size={13} />
                        <span>Expand Studio</span>
                    </button>
                )}

                {/* Safe natural-dimension local preview */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                    src={imageUrl}
                    alt="Deposit target"
                    className={`block w-full object-contain pointer-events-none ${
                        isStudioMode ? "max-h-[600px]" : "max-h-[440px] xl:max-h-[480px]"
                    }`}
                    draggable={false}
                />

                {/* Helper prompt overlay when 0 ROIs */}
                {rois.length === 0 && !isDrawing && (
                    <div className="pointer-events-none absolute bottom-2 left-2 right-2 flex items-center justify-center gap-1.5 rounded-lg bg-black/60 backdrop-blur-xs px-2.5 py-1 text-[11px] font-medium text-white/90">
                        <Crosshair size={13} className="text-amber-400 shrink-0" />
                        <span className="truncate">Drag box over deposit to define target ROI</span>
                    </div>
                )}

                {/* Existing ROIs overlay */}
                {rois.map((roi) => (
                    <div
                        key={roi.roi_id}
                        className="absolute border-2 border-[#6d5dfc] bg-[#6d5dfc]/15 transition-all"
                        style={{
                            left: `${roi.x * 100}%`,
                            top: `${roi.y * 100}%`,
                            width: `${roi.width * 100}%`,
                            height: `${roi.height * 100}%`,
                        }}
                    >
                        <div className="absolute -top-6 left-0 flex items-center gap-1 rounded bg-[#6d5dfc] px-1.5 py-0.5 text-[10px] font-semibold text-white shadow-xs">
                            <span>{roi.roi_id}</span>
                            {!disabled && (
                                <button
                                    type="button"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        handleRemoveRoi(roi.roi_id);
                                    }}
                                    className="ml-1 hover:text-red-200"
                                    title={`Remove ${roi.roi_id}`}
                                >
                                    ×
                                </button>
                            )}
                        </div>
                    </div>
                ))}

                {/* Active drawing rectangle */}
                {activeBox && (
                    <div
                        className="pointer-events-none absolute border-2 border-dashed border-amber-400 bg-amber-400/20"
                        style={{
                            left: activeBox.left,
                            top: activeBox.top,
                            width: activeBox.width,
                            height: activeBox.height,
                        }}
                    />
                )}
            </div>

            {/* Helper guidance */}
            {rois.length === 0 ? (
                <div className="flex items-center gap-2 rounded-lg bg-amber-50 p-2.5 text-xs text-amber-800">
                    <AlertCircle size={14} className="shrink-0 text-amber-600" />
                    <span>
                        Draw at least one rectangular target ROI over the image by clicking and dragging.
                    </span>
                </div>
            ) : (
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
                        {rois.map((roi) => (
                            <div
                                key={roi.roi_id}
                                className="flex items-center justify-between gap-4 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-[#141b29] p-3 text-xs shadow-2xs hover:border-gray-300 dark:hover:border-gray-600 transition"
                            >
                                <div className="min-w-0 flex-1">
                                    <div className="flex items-center gap-2">
                                        <span className="font-bold text-xs sm:text-sm text-[#5848e8] dark:text-[#a397ff]">{roi.roi_id}</span>
                                        <span className="rounded-md bg-indigo-50 dark:bg-[#6d5dfc]/20 px-2 py-0.5 text-[10px] sm:text-xs font-semibold text-[#5848e8] dark:text-[#a397ff]">Target ROI</span>
                                    </div>
                                    <div className="mt-2 grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono text-gray-700 dark:text-gray-300">
                                        <span className="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-md px-2 py-1 text-center">X: {(roi.x * 100).toFixed(1)}%</span>
                                        <span className="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-md px-2 py-1 text-center">Y: {(roi.y * 100).toFixed(1)}%</span>
                                        <span className="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-md px-2 py-1 text-center">W: {(roi.width * 100).toFixed(1)}%</span>
                                        <span className="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-md px-2 py-1 text-center">H: {(roi.height * 100).toFixed(1)}%</span>
                                    </div>
                                </div>
                                {!disabled && (
                                    <button
                                        type="button"
                                        onClick={() => handleRemoveRoi(roi.roi_id)}
                                        className="rounded-lg p-2 text-gray-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/50 transition shrink-0"
                                        title={`Delete ${roi.roi_id}`}
                                    >
                                        <Trash2 size={16} />
                                    </button>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
