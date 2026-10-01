/**
 * Saved Region Evidence Projection Helper (DLK-M3-043)
 *
 * Pure projection and normalization logic for rendering persisted multi-site
 * image observations on saved diagnosis cases.
 *
 * Design principles:
 * 1. Untrusted runtime metadata defense: safely narrows unknown objects, arrays,
 *    scalars, booleans, and enum statuses. Never throws or renders raw objects.
 * 2. Truthful scope distinction: distinguishes individual region findings from
 *    comparison group findings (e.g. D03 inconsistent size). Unknown scope stays unknown.
 * 3. Exact allowlisted limits: evaluates supplied limits against KNOWN_LIMIT_KEYS.
 * 4. Separate current and reference data: reference data is explicitly labeled
 *    as "Not recorded" rather than zero when omitted.
 * 5. Distinct unmeasured affected IDs: affected IDs without snapshots are not
 *    falsely decorated with another site's measurements.
 * 6. Legacy fallback preservation: observations recorded prior to multi-site
 *    snapshots retain a clearly labeled first-site legacy summary.
 */

import type { CaseObservationResponse } from "@/types/api";

export type InspectionStatus = "DETECTED" | "MISSING" | "UNASSESSED" | "UNKNOWN";

export type RegionEvidenceScope = "individual_regions" | "comparison_group" | "unknown";

export const ALLOWED_INSPECTION_STATUSES = new Set<string>([
    "DETECTED",
    "MISSING",
    "UNASSESSED",
]);

export const KNOWN_LIMIT_KEYS = new Set<string>([
    // Process limits
    "min_coverage_ratio",
    "max_coverage_ratio",
    "max_overflow_ratio",
    "max_size_cv",
    "min_presence_ratio",
    "min_circularity",
    "min_solidity",
    "min_convexity",
    "max_aspect_ratio",
    "min_aspect_ratio",
    "max_bubble_count",
    "max_void_ratio",
    // Reference limits
    "min_reference_ratio",
    "max_reference_ratio",
    "tolerance_ratio",
    "min_circularity_ratio",
    "min_solidity_ratio",
    // Profile/calibration limits
    "target_area_px",
    "tolerance_pct",
    "target_diameter_mm",
    "tolerance_pct_diameter",
]);

export const LIMIT_LABELS: Record<string, string> = {
    min_coverage_ratio: "Min Coverage Ratio",
    max_coverage_ratio: "Max Coverage Ratio",
    max_overflow_ratio: "Max Overflow Ratio",
    max_size_cv: "Max Size CV",
    min_presence_ratio: "Min Presence Ratio",
    min_circularity: "Min Circularity",
    min_solidity: "Min Solidity",
    min_convexity: "Min Convexity",
    max_aspect_ratio: "Max Aspect Ratio",
    min_aspect_ratio: "Min Aspect Ratio",
    max_bubble_count: "Max Bubble Count",
    max_void_ratio: "Max Void Ratio",
    min_reference_ratio: "Min Reference Ratio",
    max_reference_ratio: "Max Reference Ratio",
    tolerance_ratio: "Tolerance Ratio",
    min_circularity_ratio: "Min Circularity Ratio",
    min_solidity_ratio: "Min Solidity Ratio",
    target_area_px: "Target Area (px²)",
    tolerance_pct: "Tolerance (%)",
    target_diameter_mm: "Target Diameter (mm)",
    tolerance_pct_diameter: "Diameter Tolerance (%)",
};

export interface SavedScalarMeasurements {
    inspection_status: InspectionStatus;
    deposit_area_px: number | null;
    target_area_px: number | null;
    coverage_ratio: number | null;
    overflow_ratio: number | null;
    equivalent_diameter_px: number | null;
    calibrated_diameter_mm: number | null;
    circularity: number | null;
    solidity: number | null;
    convexity: number | null;
    aspect_ratio: number | null;
    hole_void_ratio: number | null;
    bubble_count: number | null;
    has_bubbles: boolean | null;
    segmentation_quality: number | null;
}

export interface SavedRegionSiteSnapshot {
    key: string;
    roi_id: string;
    isMalformed: boolean;
    malformedReason?: string;
    currentMeasurements: SavedScalarMeasurements | null;
    referenceMeasurements: SavedScalarMeasurements | null;
    hasReference: boolean;
}

export interface SavedAppliedLimit {
    key: string;
    label: string;
    valueStr: string;
}

export interface LegacyObservationSummary {
    status: string | null;
    roiId: string | null;
    mode: string | null;
    coverageRatio: number | null;
    overflowRatio: number | null;
    currentCoverage: number | null;
    referenceCoverage: number | null;
    coverageRatioToReference: number | null;
    equivDiameterPx: number | null;
    calibratedDiameterMm: number | null;
    segQuality: number | null;
    sizeCv: number | null;
}

export interface SavedImageObservationView {
    id: string;
    observationType: string;
    value: string;
    source: string;
    statementType: string;
    firstSeenRevision: string | null;
    originalText: string | null;
    scope: RegionEvidenceScope;
    scopeLabel: string;
    scopeDescription: string;
    affectedRoiIds: string[];
    appliedLimits: SavedAppliedLimit[];
    snapshots: SavedRegionSiteSnapshot[];
    unmeasuredAffectedIds: string[];
    hasSnapshots: boolean;
    regionEvidenceState: "present" | "absent" | "empty" | "malformed";
    isLegacyOnly: boolean;
    legacySummary: LegacyObservationSummary | null;
    warnings: string[];
}

function truncateStr(val: string, maxLen = 200): string {
    if (val.length <= maxLen) return val;
    return val.slice(0, maxLen) + "...";
}

export function isFiniteNumber(val: unknown): val is number {
    return typeof val === "number" && Number.isFinite(val);
}

export function formatMetricPercent(val: number | null | undefined, decimals = 1): string {
    if (val === null || val === undefined || !isFiniteNumber(val)) return "-";
    return `${(val * 100).toFixed(decimals)}%`;
}

export function formatMetricNumber(
    val: number | null | undefined,
    decimals = 1,
    unit = ""
): string {
    if (val === null || val === undefined || !isFiniteNumber(val)) return "-";
    return `${val.toFixed(decimals)}${unit}`;
}

export function formatPhysicalDiameter(val: number | null | undefined): string {
    if (val === null || val === undefined || !isFiniteNumber(val)) return "Not recorded";
    return `${val.toFixed(3)} mm`;
}

export function formatLimitValue(key: string, val: unknown): string {
    if (val === null || val === undefined) return "-";
    if (typeof val === "boolean") {
        if (key === "has_bubbles") return val ? "True" : "False";
        return "unavailable";
    }
    if (isFiniteNumber(val)) {
        if (key === "target_area_px") {
            return `${val} px²`;
        }
        if (key === "tolerance_pct" || key === "tolerance_pct_diameter") {
            return `${val}%`;
        }
        if (key === "target_diameter_mm" || key.includes("mm")) {
            return `${val} mm`;
        }
        if (key.includes("px")) {
            return `${val} px`;
        }
        if (
            key.includes("ratio") ||
            key.includes("cv") ||
            key.includes("circularity") ||
            key.includes("solidity") ||
            key.includes("convexity")
        ) {
            return String(val);
        }
        return String(val);
    }
    return "unavailable";
}

export function parseScalarMeasurements(raw: unknown): SavedScalarMeasurements | null {
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
        return null;
    }
    const r = raw as Record<string, unknown>;

    let inspection_status: InspectionStatus = "UNKNOWN";
    if (typeof r.inspection_status === "string" && ALLOWED_INSPECTION_STATUSES.has(r.inspection_status)) {
        inspection_status = r.inspection_status as InspectionStatus;
    }

    const parseNum = (k: string): number | null => {
        const v = r[k];
        return isFiniteNumber(v) ? v : null;
    };

    const parseBool = (k: string): boolean | null => {
        const v = r[k];
        return typeof v === "boolean" ? v : null;
    };

    const deposit_area_px = parseNum("deposit_area_px");
    const target_area_px = parseNum("target_area_px");
    const coverage_ratio = parseNum("coverage_ratio");
    const overflow_ratio = parseNum("overflow_ratio");
    const equivalent_diameter_px = parseNum("equivalent_diameter_px");
    const calibrated_diameter_mm = parseNum("calibrated_diameter_mm");
    const circularity = parseNum("circularity");
    const solidity = parseNum("solidity");
    const convexity = parseNum("convexity");
    const aspect_ratio = parseNum("aspect_ratio");
    const hole_void_ratio = parseNum("hole_void_ratio");
    const bubble_count = parseNum("bubble_count");
    const has_bubbles = parseBool("has_bubbles");
    const segmentation_quality = parseNum("segmentation_quality");

    const hasUsableStatus = inspection_status !== "UNKNOWN";
    const hasUsableScalar =
        deposit_area_px !== null ||
        target_area_px !== null ||
        coverage_ratio !== null ||
        overflow_ratio !== null ||
        equivalent_diameter_px !== null ||
        calibrated_diameter_mm !== null ||
        circularity !== null ||
        solidity !== null ||
        convexity !== null ||
        aspect_ratio !== null ||
        hole_void_ratio !== null ||
        bubble_count !== null ||
        segmentation_quality !== null;
    const hasUsableBool = has_bubbles !== null;

    if (!hasUsableStatus && !hasUsableScalar && !hasUsableBool) {
        return null;
    }

    return {
        inspection_status,
        deposit_area_px,
        target_area_px,
        coverage_ratio,
        overflow_ratio,
        equivalent_diameter_px,
        calibrated_diameter_mm,
        circularity,
        solidity,
        convexity,
        aspect_ratio,
        hole_void_ratio,
        bubble_count,
        has_bubbles,
        segmentation_quality,
    };
}

export function parseLegacySummary(meta: Record<string, unknown>): LegacyObservationSummary | null {
    const hasAnyLegacyField =
        meta.status !== undefined ||
        meta.roi_id !== undefined ||
        meta.mode !== undefined ||
        meta.coverage_ratio !== undefined ||
        meta.overflow_ratio !== undefined ||
        meta.current_coverage !== undefined ||
        meta.reference_coverage !== undefined ||
        meta.coverage_ratio_to_reference !== undefined ||
        meta.equivalent_diameter_px !== undefined ||
        meta.calibrated_diameter_mm !== undefined ||
        meta.segmentation_quality !== undefined ||
        meta.size_cv !== undefined;

    if (!hasAnyLegacyField) return null;

    const parseNum = (k: string): number | null => {
        const v = meta[k];
        return isFiniteNumber(v) ? v : null;
    };

    return {
        status: typeof meta.status === "string" ? truncateStr(meta.status) : null,
        roiId: typeof meta.roi_id === "string" ? String(meta.roi_id) : null,
        mode: typeof meta.mode === "string" ? truncateStr(meta.mode) : null,
        coverageRatio: parseNum("coverage_ratio"),
        overflowRatio: parseNum("overflow_ratio"),
        currentCoverage: parseNum("current_coverage"),
        referenceCoverage: parseNum("reference_coverage"),
        coverageRatioToReference: parseNum("coverage_ratio_to_reference"),
        equivDiameterPx: parseNum("equivalent_diameter_px"),
        calibratedDiameterMm: parseNum("calibrated_diameter_mm"),
        segQuality: parseNum("segmentation_quality"),
        sizeCv: parseNum("size_cv"),
    };
}

export function projectSavedRegionEvidence(
    obs: CaseObservationResponse,
    obsIndex: number
): SavedImageObservationView {
    const obsId = obs.id || obs.observation_id || `obs_${obsIndex}`;
    const meta = (obs.metadata && typeof obs.metadata === "object" && !Array.isArray(obs.metadata))
        ? (obs.metadata as Record<string, unknown>)
        : {};

    // 1. Resolve Scope
    const rawScope = meta.region_evidence_scope;
    let scope: RegionEvidenceScope = "unknown";
    let scopeLabel = "Not Recorded or Unknown";
    let scopeDescription = "Region evidence scope was not recorded or is unknown.";

    if (rawScope === "individual_regions") {
        scope = "individual_regions";
        scopeLabel = "Individual Regions";
        scopeDescription = "Individual region defect findings: each listed region was evaluated and independently triggered defect criteria.";
    } else if (rawScope === "comparison_group") {
        scope = "comparison_group";
        scopeLabel = "Comparison Group";
        scopeDescription = "Group comparison finding: listed regions are eligible comparison participants evaluated for group variation, not individually confirmed failures.";
    } else if (typeof rawScope === "string" && rawScope.trim() !== "") {
        // Explicit unrecognized scope remains strictly unknown
        scope = "unknown";
        scopeLabel = "Unknown Scope";
        scopeDescription = `Unrecognized region evidence scope: "${rawScope.trim()}".`;
    } else if (
        (rawScope === undefined || rawScope === null) &&
        obs.observation_type === "deposit_size" &&
        obs.value === "inconsistent"
    ) {
        // Canonical legacy D03 fallback strictly when scope is absent and observation_type is canonical deposit_size
        scope = "comparison_group";
        scopeLabel = "Comparison Group (Canonical D03)";
        scopeDescription = "Group comparison finding: listed regions are eligible comparison participants evaluated for group variation, not individually confirmed failures.";
    }

    // 2. Affected ROI IDs (retain full, untruncated string for identity and matching)
    const affectedRoiIds: string[] = [];
    const rawAffected = meta.affected_roi_ids;
    if (Array.isArray(rawAffected)) {
        for (const item of rawAffected) {
            if (typeof item === "string" || typeof item === "number") {
                affectedRoiIds.push(String(item));
            } else {
                affectedRoiIds.push("unavailable");
            }
        }
    } else if (meta.roi_id !== undefined && meta.roi_id !== null) {
        if (typeof meta.roi_id === "string" || typeof meta.roi_id === "number") {
            affectedRoiIds.push(String(meta.roi_id));
        } else {
            affectedRoiIds.push("unavailable");
        }
    }

    // 3. Applied Limits (Allowlisted keys only)
    const appliedLimits: SavedAppliedLimit[] = [];
    const rawLimits = meta.applied_limits;
    if (rawLimits && typeof rawLimits === "object" && !Array.isArray(rawLimits)) {
        for (const [k, v] of Object.entries(rawLimits as Record<string, unknown>)) {
            if (!KNOWN_LIMIT_KEYS.has(k)) continue;
            appliedLimits.push({
                key: k,
                label: LIMIT_LABELS[k] || k,
                valueStr: formatLimitValue(k, v),
            });
        }
    }

    // 4. Region Evidence State and Snapshots
    const rawEvidence = meta.region_evidence;
    let regionEvidenceState: "present" | "absent" | "empty" | "malformed" = "absent";
    if (rawEvidence === undefined || rawEvidence === null) {
        regionEvidenceState = "absent";
    } else if (!Array.isArray(rawEvidence)) {
        regionEvidenceState = "malformed";
    } else if (rawEvidence.length === 0) {
        regionEvidenceState = "empty";
    } else {
        regionEvidenceState = "present";
    }

    const snapshots: SavedRegionSiteSnapshot[] = [];
    if (Array.isArray(rawEvidence)) {
        rawEvidence.forEach((entry, idx) => {
            const uniqueKey = `${obsId}-snap-${idx}`;
            if (!entry || typeof entry !== "object" || Array.isArray(entry)) {
                snapshots.push({
                    key: uniqueKey,
                    roi_id: "UNKNOWN",
                    isMalformed: true,
                    malformedReason: "Malformed region evidence entry (expected dictionary record).",
                    currentMeasurements: null,
                    referenceMeasurements: null,
                    hasReference: false,
                });
                return;
            }

            const e = entry as Record<string, unknown>;
            const rawRoiId = e.roi_id;
            let roiIdStr = "UNKNOWN";
            if (typeof rawRoiId === "string" || typeof rawRoiId === "number") {
                roiIdStr = String(rawRoiId);
            }

            const currentMeasurements = parseScalarMeasurements(e.current_measurements);
            const refMeasurements = parseScalarMeasurements(e.reference_measurements);
            const hasRef = refMeasurements !== null;

            snapshots.push({
                key: `${uniqueKey}-${roiIdStr}`,
                roi_id: roiIdStr,
                isMalformed: currentMeasurements === null,
                malformedReason: currentMeasurements === null ? "Missing or malformed current measurement scalar data." : undefined,
                currentMeasurements,
                referenceMeasurements: refMeasurements,
                hasReference: hasRef,
            });
        });
    }

    // 5. Unmeasured Affected IDs (matching full IDs)
    const measuredIds = new Set(
        snapshots
            .filter((s) => !s.isMalformed && s.roi_id !== "UNKNOWN")
            .map((s) => s.roi_id)
    );
    const unmeasuredAffectedIds = affectedRoiIds.filter((id) => !measuredIds.has(id));

    // 6. Legacy Only Check (strictly when region_evidence is absent and legacy fields exist)
    const hasSnapshots = snapshots.length > 0;
    const legacySummary = parseLegacySummary(meta);
    const isLegacyOnly = regionEvidenceState === "absent" && !hasSnapshots && legacySummary !== null;

    // 7. Warnings and notices
    const warnings: string[] = [];
    if (regionEvidenceState === "malformed") {
        warnings.push(`Region evidence metadata is malformed (expected an array of site snapshots, received ${typeof rawEvidence}).`);
    } else if (regionEvidenceState === "empty") {
        warnings.push("Region evidence array is empty (0 site snapshots recorded).");
    }

    if (Array.isArray(meta.warnings)) {
        for (const w of meta.warnings) {
            if (typeof w === "string") warnings.push(truncateStr(w));
        }
    }

    return {
        id: obsId,
        observationType: truncateStr(obs.observation_type || "unknown"),
        value: truncateStr(obs.value || "unknown"),
        source: truncateStr(obs.source || "IMAGE"),
        statementType: truncateStr(obs.statement_type || "AI_INFERENCE"),
        firstSeenRevision: obs.first_seen_revision !== undefined && obs.first_seen_revision !== null
            ? String(obs.first_seen_revision)
            : null,
        originalText: typeof obs.original_text === "string" ? truncateStr(obs.original_text) : null,
        scope,
        scopeLabel,
        scopeDescription,
        affectedRoiIds,
        appliedLimits,
        snapshots,
        unmeasuredAffectedIds,
        hasSnapshots,
        regionEvidenceState,
        isLegacyOnly,
        legacySummary,
        warnings,
    };
}
