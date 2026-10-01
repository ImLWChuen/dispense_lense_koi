/**
 * Dispense Lens - Portable Region Layout Contract & Validation (DLK-M3-046)
 *
 * Provides strict validation, pure parsing, allowlisted serialization,
 * and safe file helpers for exporting and importing geometry-only region layouts.
 *
 * Invariants:
 * - Version 1 schema with exact allowlisted keys.
 * - Rejects unknown keys at each level; no silent downgrade or arbitrary property retention.
 * - File size <= 256 KiB; 1 to 100 normalized rectangular ROIs.
 * - Nonblank strings, <= 100 chars, no control characters, unique trimmed IDs.
 * - Normalized coordinates strictly within [0, 1] with extents <= 1.00001.
 * - Never exports or imports images, calibration, limits, outcomes, or case IDs.
 */

import type { NormalizedROI } from "@/types/image";

export const REGION_LAYOUT_FORMAT = "dispense-region-layout" as const;
export const REGION_LAYOUT_VERSION = 1 as const;
export const MAX_LAYOUT_FILE_BYTES = 256 * 1024; // 256 KiB (262,144 bytes)
export const MAX_LAYOUT_ROIS = 100;
export const MAX_LAYOUT_NAME_LENGTH = 100;
export const MAX_ROI_ID_LENGTH = 100;
export const DEFAULT_LAYOUT_FILENAME = "dispense-region-layout.json" as const;

export interface RegionLayoutSourceImage {
    width: number;
    height: number;
}

export interface RegionLayoutFile {
    format: "dispense-region-layout";
    version: 1;
    name: string;
    source_image: RegionLayoutSourceImage;
    rois: NormalizedROI[];
}

export type RegionLayoutValidationResult =
    | { ok: true; layout: RegionLayoutFile }
    | { ok: false; error: string };

/**
 * Validates a parsed JavaScript object against the strict dispense-region-layout v1 contract.
 * Rejects unknown keys, invalid types, out-of-range dimensions, and non-normalized coordinates.
 */
export function validateRegionLayout(data: unknown): RegionLayoutValidationResult {
    if (!data || typeof data !== "object" || Array.isArray(data)) {
        return { ok: false, error: "Layout root must be a JSON object." };
    }

    const record = data as Record<string, unknown>;

    // 1. Root property strictness: exactly format, version, name, source_image, rois
    const rootKeys = Object.keys(record).sort();
    const expectedRootKeys = ["format", "name", "rois", "source_image", "version"];
    for (const k of rootKeys) {
        if (!expectedRootKeys.includes(k)) {
            return { ok: false, error: `Unrecognized root property '${k}' in layout file.` };
        }
    }
    for (const k of expectedRootKeys) {
        if (!rootKeys.includes(k)) {
            return { ok: false, error: `Missing required root property '${k}' in layout file.` };
        }
    }

    // 2. Format
    if (record.format !== REGION_LAYOUT_FORMAT) {
        return { ok: false, error: `Invalid layout format: expected '${REGION_LAYOUT_FORMAT}'.` };
    }

    // 3. Version (strict integer 1)
    if (record.version !== REGION_LAYOUT_VERSION) {
        return { ok: false, error: `Unsupported layout version: expected ${REGION_LAYOUT_VERSION}.` };
    }

    // 4. Name: string, nonblank, <= 100 chars, no control characters
    if (typeof record.name !== "string") {
        return { ok: false, error: "Layout 'name' must be a string." };
    }
    const trimmedName = record.name.trim();
    if (!trimmedName) {
        return { ok: false, error: "Layout 'name' cannot be empty or blank." };
    }
    if (record.name.length > MAX_LAYOUT_NAME_LENGTH) {
        return { ok: false, error: `Layout 'name' exceeds maximum length of ${MAX_LAYOUT_NAME_LENGTH} characters.` };
    }
    if (/[\x00-\x1F\x7F]/.test(record.name)) {
        return { ok: false, error: "Layout 'name' contains disallowed control characters." };
    }

    // 5. Source image dimensions
    if (!record.source_image || typeof record.source_image !== "object" || Array.isArray(record.source_image)) {
        return { ok: false, error: "Layout 'source_image' must be a JSON object." };
    }
    const srcImg = record.source_image as Record<string, unknown>;
    const srcKeys = Object.keys(srcImg).sort();
    if (srcKeys.length !== 2 || srcKeys[0] !== "height" || srcKeys[1] !== "width") {
        return { ok: false, error: "Layout 'source_image' must contain only 'width' and 'height'." };
    }
    const { width, height } = srcImg;
    if (typeof width !== "number" || !Number.isSafeInteger(width) || width <= 0) {
        return { ok: false, error: "Source image 'width' must be a positive safe integer." };
    }
    if (typeof height !== "number" || !Number.isSafeInteger(height) || height <= 0) {
        return { ok: false, error: "Source image 'height' must be a positive safe integer." };
    }

    // 6. ROIs array: 1 to 100 items
    if (!Array.isArray(record.rois)) {
        return { ok: false, error: "Layout 'rois' must be an array." };
    }
    if (record.rois.length === 0) {
        return { ok: false, error: "Layout must contain at least 1 region." };
    }
    if (record.rois.length > MAX_LAYOUT_ROIS) {
        return { ok: false, error: `Layout exceeds maximum of ${MAX_LAYOUT_ROIS} regions (contains ${record.rois.length}).` };
    }

    const parsedRois: NormalizedROI[] = [];
    const seenRoiIds = new Set<string>();

    for (let i = 0; i < record.rois.length; i++) {
        const item = record.rois[i];
        if (!item || typeof item !== "object" || Array.isArray(item)) {
            return { ok: false, error: `Region at index ${i} must be a JSON object.` };
        }
        const roiRecord = item as Record<string, unknown>;
        const roiKeys = Object.keys(roiRecord).sort();
        const expectedRoiKeys = ["height", "roi_id", "width", "x", "y"];
        if (roiKeys.length !== 5 || !roiKeys.every((k, idx) => k === expectedRoiKeys[idx])) {
            return { ok: false, error: `Region at index ${i} has invalid or unrecognized properties.` };
        }

        // Validate roi_id: string, <= 100 chars, no control chars, no leading/trailing whitespace
        if (typeof roiRecord.roi_id !== "string") {
            return { ok: false, error: `Region at index ${i} 'roi_id' must be a string.` };
        }
        if (!roiRecord.roi_id.trim()) {
            return { ok: false, error: `Region at index ${i} 'roi_id' cannot be empty or whitespace.` };
        }
        if (roiRecord.roi_id !== roiRecord.roi_id.trim()) {
            return { ok: false, error: `Region '${roiRecord.roi_id}' has leading or trailing whitespace.` };
        }
        if (roiRecord.roi_id.length > MAX_ROI_ID_LENGTH) {
            return { ok: false, error: `Region '${roiRecord.roi_id}' exceeds maximum length of ${MAX_ROI_ID_LENGTH} characters.` };
        }
        if (/[\x00-\x1F\x7F]/.test(roiRecord.roi_id)) {
            return { ok: false, error: `Region '${roiRecord.roi_id}' contains disallowed control characters.` };
        }
        if (seenRoiIds.has(roiRecord.roi_id)) {
            return { ok: false, error: `Duplicate ROI ID '${roiRecord.roi_id}' detected in layout.` };
        }
        seenRoiIds.add(roiRecord.roi_id);

        // Validate coordinates: finite numbers, bounds, extents
        const { x, y, width: rWidth, height: rHeight } = roiRecord;
        if (
            typeof x !== "number" || !Number.isFinite(x) ||
            typeof y !== "number" || !Number.isFinite(y) ||
            typeof rWidth !== "number" || !Number.isFinite(rWidth) ||
            typeof rHeight !== "number" || !Number.isFinite(rHeight)
        ) {
            return { ok: false, error: `Region '${roiRecord.roi_id}' coordinates must be finite numeric values.` };
        }
        if (x < 0 || x > 1 || y < 0 || y > 1) {
            return { ok: false, error: `Region '${roiRecord.roi_id}' coordinates (x, y) must be within [0, 1].` };
        }
        if (rWidth <= 0 || rWidth > 1 || rHeight <= 0 || rHeight > 1) {
            return { ok: false, error: `Region '${roiRecord.roi_id}' dimensions (width, height) must be within (0, 1].` };
        }
        if (x + rWidth > 1.00001 || y + rHeight > 1.00001) {
            return { ok: false, error: `Region '${roiRecord.roi_id}' extends beyond normalized image boundaries.` };
        }

        parsedRois.push({
            roi_id: roiRecord.roi_id,
            x,
            y,
            width: rWidth,
            height: rHeight,
        });
    }

    return {
        ok: true,
        layout: {
            format: REGION_LAYOUT_FORMAT,
            version: REGION_LAYOUT_VERSION,
            name: trimmedName,
            source_image: {
                width,
                height,
            },
            rois: parsedRois,
        },
    };
}

/**
 * Parses and validates raw JSON text from a layout file.
 * Rejects JSON syntax errors, oversized text payloads, and schema invalidity.
 */
export function parseRegionLayout(jsonStr: string): RegionLayoutValidationResult {
    // UTF-8 byte length safety check
    if (typeof jsonStr !== "string") {
        return { ok: false, error: "Input layout payload must be a string." };
    }
    const byteLength = new TextEncoder().encode(jsonStr).length;
    if (byteLength > MAX_LAYOUT_FILE_BYTES) {
        return {
            ok: false,
            error: `File payload (${(byteLength / 1024).toFixed(1)} KiB) exceeds maximum allowed size of 256 KiB.`,
        };
    }

    try {
        const parsed = JSON.parse(jsonStr);
        return validateRegionLayout(parsed);
    } catch {
        return { ok: false, error: "Failed to parse layout file: invalid JSON syntax." };
    }
}

/**
 * Constructs a validated RegionLayoutFile from memory values.
 */
export function createRegionLayout(
    name: string,
    dimensions: { width: number; height: number },
    rois: NormalizedROI[]
): RegionLayoutValidationResult {
    const candidate = {
        format: REGION_LAYOUT_FORMAT,
        version: REGION_LAYOUT_VERSION,
        name,
        source_image: {
            width: dimensions?.width,
            height: dimensions?.height,
        },
        rois: rois?.map((r) => ({
            roi_id: r.roi_id,
            x: r.x,
            y: r.y,
            width: r.width,
            height: r.height,
        })),
    };

    return validateRegionLayout(candidate);
}

/**
 * Serializes a validated RegionLayoutFile to allowlisted, formatted JSON.
 * Guarantees no extra metadata, analysis outcomes, or confidential fields leak.
 */
export function serializeRegionLayout(layout: RegionLayoutFile): string {
    const payload = {
        format: REGION_LAYOUT_FORMAT,
        version: REGION_LAYOUT_VERSION,
        name: layout.name.trim(),
        source_image: {
            width: layout.source_image.width,
            height: layout.source_image.height,
        },
        rois: layout.rois.map((r) => ({
            roi_id: r.roi_id,
            x: r.x,
            y: r.y,
            width: r.width,
            height: r.height,
        })),
    };

    return JSON.stringify(payload, null, 2);
}

/**
 * Triggers a browser download of the layout file and revokes the temporary URL immediately.
 */
export function triggerLayoutDownload(
    layout: RegionLayoutFile,
    filename: string = DEFAULT_LAYOUT_FILENAME
): void {
    const jsonStr = serializeRegionLayout(layout);
    const blob = new Blob([jsonStr], { type: "application/json" });
    const url = URL.createObjectURL(blob);

    try {
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = filename;
        anchor.style.display = "none";
        document.body.appendChild(anchor);
        anchor.click();
        document.body.removeChild(anchor);
    } finally {
        setTimeout(() => URL.revokeObjectURL(url), 100);
    }
}
