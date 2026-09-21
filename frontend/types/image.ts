/**
 * Dispense Lens - Calibrated Image Frontend Contracts
 *
 * Types for multipart image analysis, normalized rectangular ROIs,
 * process/reference calibration limits, and upload lifecycle snapshots.
 * Mirrors the authoritative backend schemas in app/schemas/image.py.
 */

import { Observation } from "./api";

export type ImageAnalysisMode = "FEATURES_ONLY" | "PROCESS_LIMITS" | "REFERENCE_IMAGE";

export type AnalysisStatus = "CALIBRATED" | "UNCALIBRATED" | "UNRELIABLE";

export interface NormalizedROI {
    roi_id: string;
    x: number;
    y: number;
    width: number;
    height: number;
}

export interface ProcessLimits {
    min_coverage_ratio?: number | null;
    max_coverage_ratio?: number | null;
    max_overflow_ratio?: number | null;
    max_size_cv?: number | null;
    min_presence_ratio?: number | null;
    min_circularity?: number | null;
    min_solidity?: number | null;
    min_convexity?: number | null;
    max_aspect_ratio?: number | null;
    min_aspect_ratio?: number | null;
    max_bubble_count?: number | null;
    max_void_ratio?: number | null;
}

export interface ReferenceLimits {
    min_reference_ratio?: number | null;
    max_reference_ratio?: number | null;
    tolerance_ratio?: number | null;
    min_circularity_ratio?: number | null;
    min_solidity_ratio?: number | null;
}

export interface AnalysisProfile {
    mode: ImageAnalysisMode;
    rois: NormalizedROI[];
    mm_per_pixel?: number | null;
    process_limits?: ProcessLimits | null;
    reference_limits?: ReferenceLimits | null;
}

export interface ImageDimensions {
    width: number;
    height: number;
    channels: number;
}

export interface RoiMeasurement {
    roi_id: string;
    deposit_area_px: number;
    target_area_px: number;
    coverage_ratio: number;
    overflow_ratio: number;
    equivalent_diameter_px: number;
    calibrated_diameter_mm: number | null;
    circularity: number;
    solidity: number;
    convexity?: number;
    aspect_ratio: number;
    hole_void_ratio: number;
    bubble_count?: number;
    has_bubbles?: boolean;
    is_abnormal_shape?: boolean;
    is_tailing?: boolean;
    bubble_details?: Array<{ x: number; y: number; radius: number; area: number; method: string }>;
    segmentation_quality: number;
    is_missing: boolean;
}

export interface AggregateMeasurements {
    mean_coverage: number | null;
    size_cv: number | null;
    missing_roi_ids: string[];
    warnings: string[];
}

export interface ImageAnalysisResponse {
    status: AnalysisStatus;
    mode: ImageAnalysisMode;
    image_dimensions: ImageDimensions;
    roi_measurements: RoiMeasurement[];
    aggregate_measurements: AggregateMeasurements;
    observations: Observation[];
    warnings: string[];
}

export type UploadLifecycleStatus = "ready" | "analyzing" | "analyzed" | "error";

export interface UploadItem {
    id: string;
    file: File;
    previewUrl: string;
    status: UploadLifecycleStatus;
    mode: ImageAnalysisMode;
    rois: NormalizedROI[];
    mmPerPixel?: number | null;
    processLimits?: ProcessLimits | null;
    referenceLimits?: ReferenceLimits | null;
    referenceFile?: File | null;
    referencePreviewUrl?: string | null;
    result?: ImageAnalysisResponse | null;
    errorMessage?: string | null;
    configRevision: number;
    activeRequestToken: number | null;
}

export type UploadSnapshot = Record<string, UploadItem>;
