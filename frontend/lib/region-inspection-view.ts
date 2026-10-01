/**
 * Dispense Lens - Region Inspection View Projections & Geometry Helpers (DLK-M3-041)
 *
 * Pure projection, coordinate mapping, and outline validation functions.
 * Shared between ImageUpload.tsx, ImageRoiEditor.tsx, RegionInspectionPanel.tsx,
 * and regression harnesses.
 */

import type {
    AggregateMeasurements,
    ImageAnalysisResponse,
    NormalizedPoint,
    NormalizedROI,
    RoiInspectionStatus,
    RoiMeasurement,
} from "@/types/image";
import type { Observation } from "@/types/api";

export type EffectiveRoiInspectionStatus =
    | "DETECTED"
    | "MISSING"
    | "UNASSESSED"
    | "UNAVAILABLE";

export interface ContentRect {
    left: number;
    top: number;
    width: number;
    height: number;
}

export interface NormalizedCoordsResult {
    x: number;
    y: number;
    isInside: boolean;
}

export interface OutlineValidationResult {
    isValid: boolean;
    points: NormalizedPoint[];
    reason?: string;
}

export interface RegionItemView {
    roi: NormalizedROI;
    measurement: RoiMeasurement | null;
    status: EffectiveRoiInspectionStatus;
    statusLabel: string;
    statusDescription: string;
    outlineResult: OutlineValidationResult;
    isSelected: boolean;
}

export interface CoverageSummaryProjection {
    expectedText: string;
    assessedText: string;
    statusText: string;
    isAvailable: boolean;
}

/**
 * Maps a single measurement to a truthful inspection status and label.
 * Never infers pass/fail or status from zero area or legacy is_missing.
 */
export function getEffectiveRoiStatus(
    measurement?: RoiMeasurement | null,
    isConfigured: boolean = true
): { status: EffectiveRoiInspectionStatus; label: string; description: string } {
    if (!measurement) {
        if (isConfigured) {
            return {
                status: "UNASSESSED",
                label: "Not assessed",
                description: "Configured expected site was not assessed or omitted from response.",
            };
        }
        return {
            status: "UNAVAILABLE",
            label: "Status unavailable",
            description: "Inspection status was not recorded in response.",
        };
    }

    const raw = measurement.inspection_status;
    if (raw === "DETECTED") {
        return {
            status: "DETECTED",
            label: "Material detected",
            description: "Fluid material was located at expected site (does not imply within process limits).",
        };
    }
    if (raw === "MISSING") {
        return {
            status: "MISSING",
            label: "Expected deposit missing",
            description: "No fluid deposit was detected at expected target site.",
        };
    }
    if (raw === "UNASSESSED") {
        return {
            status: "UNASSESSED",
            label: "Not assessed",
            description: "Site was not assessed or omitted from inspection.",
        };
    }

    // Older or unrecorded status: strictly mark unavailable
    return {
        status: "UNAVAILABLE",
        label: "Status unavailable",
        description: "Inspection status was not recorded in older or incomplete response.",
    };
}

/**
 * Matches a measurement strictly by roi_id string equality. Never uses array indices.
 */
export function matchMeasurementByRoiId(
    measurements: RoiMeasurement[] | undefined | null,
    roiId: string
): RoiMeasurement | null {
    if (!measurements || !Array.isArray(measurements)) return null;
    return measurements.find((m) => m && m.roi_id === roiId) ?? null;
}

/**
 * Validates deposit outline geometry against the accepted DLK-M3-034 contract:
 * - Only DETECTED sites can have outlines
 * - 3 to 128 finite normalized vertices in [0.0, 1.0]
 * - Vertices must be distinct (rejects duplicates)
 * Returns neutral reason when invalid or omitted.
 */
export function validateDepositOutline(
    outline?: NormalizedPoint[] | null,
    status?: RoiInspectionStatus | null
): OutlineValidationResult {
    if (status !== "DETECTED") {
        return {
            isValid: false,
            points: [],
            reason: "Outlines are only recorded for detected material.",
        };
    }

    if (!outline || !Array.isArray(outline) || outline.length === 0) {
        return {
            isValid: false,
            points: [],
            reason: "No outline contour recorded.",
        };
    }

    if (outline.length < 3) {
        return {
            isValid: false,
            points: [],
            reason: `Insufficient vertices (${outline.length}; minimum 3 required).`,
        };
    }

    if (outline.length > 128) {
        return {
            isValid: false,
            points: [],
            reason: `Exceeds vertex bound (${outline.length}; maximum 128 allowed).`,
        };
    }

    const seen = new Set<string>();
    for (let i = 0; i < outline.length; i++) {
        const p = outline[i];
        if (typeof p !== "object" || p === null) {
            return {
                isValid: false,
                points: [],
                reason: `Vertex ${i} is not a valid coordinate object.`,
            };
        }
        if (typeof p.x !== "number" || typeof p.y !== "number") {
            return {
                isValid: false,
                points: [],
                reason: `Vertex ${i} contains non-numeric coordinates.`,
            };
        }
        if (!Number.isFinite(p.x) || !Number.isFinite(p.y)) {
            return {
                isValid: false,
                points: [],
                reason: `Vertex ${i} contains non-finite coordinates.`,
            };
        }
        if (p.x < 0 || p.x > 1 || p.y < 0 || p.y > 1) {
            return {
                isValid: false,
                points: [],
                reason: `Vertex ${i} coordinates (${p.x.toFixed(4)}, ${p.y.toFixed(4)}) extend outside [0, 1].`,
            };
        }

        const key = `${p.x.toFixed(5)},${p.y.toFixed(5)}`;
        if (seen.has(key)) {
            return {
                isValid: false,
                points: [],
                reason: `Duplicate vertex detected at (${p.x.toFixed(4)}, ${p.y.toFixed(4)}).`,
            };
        }
        seen.add(key);
    }

    return {
        isValid: true,
        points: outline,
    };
}

/**
 * Computes exact content dimensions and letterbox padding for object-contain images.
 */
export function computeContentRect(
    containerWidth: number,
    containerHeight: number,
    naturalWidth: number,
    naturalHeight: number
): ContentRect {
    if (
        containerWidth <= 0 ||
        containerHeight <= 0 ||
        naturalWidth <= 0 ||
        naturalHeight <= 0
    ) {
        return {
            left: 0,
            top: 0,
            width: Math.max(0, containerWidth),
            height: Math.max(0, containerHeight),
        };
    }

    const scale = Math.min(
        containerWidth / naturalWidth,
        containerHeight / naturalHeight
    );
    const width = naturalWidth * scale;
    const height = naturalHeight * scale;
    const left = (containerWidth - width) / 2;
    const top = (containerHeight - height) / 2;

    return {
        left: Number(left.toFixed(2)),
        top: Number(top.toFixed(2)),
        width: Number(width.toFixed(2)),
        height: Number(height.toFixed(2)),
    };
}

/**
 * Converts browser client pointer coordinates to normalized [0, 1] relative to
 * the actual rendered image content rectangle, rejecting coordinates outside the image.
 */
export function clientToNormalizedCoords(
    clientX: number,
    clientY: number,
    containerBoundingRect: { left: number; top: number; width: number; height: number },
    contentRect: ContentRect
): NormalizedCoordsResult {
    const originX = containerBoundingRect.left + contentRect.left;
    const originY = containerBoundingRect.top + contentRect.top;
    const w = contentRect.width > 0 ? contentRect.width : 1;
    const h = contentRect.height > 0 ? contentRect.height : 1;

    const rawX = (clientX - originX) / w;
    const rawY = (clientY - originY) / h;

    const isInside = rawX >= 0 && rawX <= 1 && rawY >= 0 && rawY <= 1;

    return {
        x: Math.max(0, Math.min(1, rawX)),
        y: Math.max(0, Math.min(1, rawY)),
        isInside,
    };
}

/**
 * Formats a normalized point array into an SVG points string for viewBox="0 0 1000 1000".
 */
export function formatPolygonPoints(points: NormalizedPoint[]): string {
    return points
        .map((p) => `${(p.x * 1000).toFixed(1)},${(p.y * 1000).toFixed(1)}`)
        .join(" ");
}

/**
 * Projects every configured expected ROI into a comprehensive view model.
 * Unknown or duplicate response IDs do not create spurious extra expected sites.
 */
export function projectRegionItemViews(
    rois: NormalizedROI[],
    result: ImageAnalysisResponse | null | undefined,
    selectedRoiId: string | null | undefined
): RegionItemView[] {
    return rois.map((roi) => {
        const measurement = matchMeasurementByRoiId(
            result?.roi_measurements,
            roi.roi_id
        );
        const statusInfo = getEffectiveRoiStatus(measurement, true);
        const outlineResult = validateDepositOutline(
            measurement?.deposit_outline_normalized,
            measurement?.inspection_status
        );
        const isSelected = selectedRoiId === roi.roi_id;

        return {
            roi,
            measurement,
            status: statusInfo.status,
            statusLabel: statusInfo.label,
            statusDescription: statusInfo.description,
            outlineResult,
            isSelected,
        };
    });
}

/**
 * Finds all emitted diagnostic observations that include the given ROI ID in affected_roi_ids.
 * Identifies comparison-group findings (e.g. D03 inconsistent size) so technicians
 * understand it is an overall group finding rather than proof of individual failure.
 */
export function findEmittedObservationsForRoi(
    observations: Observation[] | undefined | null,
    roiId: string
): Array<{ observation: Observation; isGroupFinding: boolean }> {
    if (!observations || !Array.isArray(observations)) return [];

    const matched: Array<{ observation: Observation; isGroupFinding: boolean }> = [];
    for (const obs of observations) {
        const affected = obs.metadata?.affected_roi_ids;
        if (Array.isArray(affected) && affected.includes(roiId)) {
            const scope = obs.metadata?.region_evidence_scope;
            const isGroupFinding =
                scope === "comparison_group" ||
                obs.observation_type === "D03_INCONSISTENT_SIZE" ||
                obs.observation_type === "deposit_shape";
            matched.push({ observation: obs, isGroupFinding });
        }
    }
    return matched;
}

/**
 * Truthfully projects aggregate coverage metrics, returning "Not available" for
 * missing legacy responses rather than inventing counts.
 */
export function projectCoverageSummary(
    agg?: AggregateMeasurements | null
): CoverageSummaryProjection {
    if (
        agg &&
        agg.expected_roi_count !== null &&
        agg.expected_roi_count !== undefined &&
        agg.assessed_roi_count !== null &&
        agg.assessed_roi_count !== undefined
    ) {
        return {
            expectedText: String(agg.expected_roi_count),
            assessedText: String(agg.assessed_roi_count),
            statusText: agg.inspection_coverage_status || "Status unavailable",
            isAvailable: true,
        };
    }

    return {
        expectedText: "Not available",
        assessedText: "Not available",
        statusText: "Status unavailable",
        isAvailable: false,
    };
}

/**
 * Safely format a finite number or return a placeholder if null, undefined, or non-finite.
 */
export function formatMetricNumber(
    val: number | null | undefined,
    decimals = 1,
    suffix = "",
    fallback = "N/A"
): string {
    if (val === null || val === undefined || !Number.isFinite(val)) {
        return fallback;
    }
    return `${val.toFixed(decimals)}${suffix}`;
}

/**
 * Safely format a ratio as a percentage or return a placeholder if null, undefined, or non-finite.
 */
export function formatMetricPercent(
    val: number | null | undefined,
    decimals = 1,
    fallback = "N/A"
): string {
    if (val === null || val === undefined || !Number.isFinite(val)) {
        return fallback;
    }
    return `${(val * 100).toFixed(decimals)}%`;
}
