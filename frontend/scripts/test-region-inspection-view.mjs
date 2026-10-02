/**
 * Deterministic regression suite for Region Inspection View Projections & Geometry (DLK-M3-041).
 *
 * Verifies:
 * 1. ROI ID matching strictly by roi_id string equality (ordering-independent, no array-index reliance).
 * 2. Truthful handling of omitted and legacy measurements (no pass/fail inference from zero area).
 * 3. Deposit outline geometry validation (3-128 finite distinct points in [0,1], DETECTED-only).
 * 4. Content rectangle computation and pointer coordinate normalization (letterbox rejection, aspect ratio safety).
 * 5. Overall inspection coverage projection (separate current/reference handling, legacy unavailable).
 * 6. Emitted observation mapping and comparison-group finding distinction.
 */

import assert from "node:assert/strict";
import {
    getEffectiveRoiStatus,
    matchMeasurementByRoiId,
    validateDepositOutline,
    computeContentRect,
    clientToNormalizedCoords,
    formatPolygonPoints,
    projectRegionItemViews,
    findEmittedObservationsForRoi,
    projectCoverageSummary,
} from "../lib/region-inspection-view.ts";

function runTests() {
    let testsPassed = 0;

    // --- 1. ID Matching Tests ---
    {
        const measurements = [
            { roi_id: "site_gamma", deposit_area_px: 100 },
            { roi_id: "site_alpha", deposit_area_px: 200 },
            { roi_id: "site_beta", deposit_area_px: 300 },
        ];

        // Must match by ID regardless of array order
        const alpha = matchMeasurementByRoiId(measurements, "site_alpha");
        assert.equal(alpha?.deposit_area_px, 200);

        const beta = matchMeasurementByRoiId(measurements, "site_beta");
        assert.equal(beta?.deposit_area_px, 300);

        const missing = matchMeasurementByRoiId(measurements, "site_delta");
        assert.equal(missing, null);

        // Projecting configured ROIs preserves configured ROI ordering and ignores extra response IDs
        const configuredRois = [
            { roi_id: "site_alpha", x: 0, y: 0, width: 0.5, height: 0.5 },
            { roi_id: "site_delta", x: 0.5, y: 0, width: 0.5, height: 0.5 },
        ];
        const views = projectRegionItemViews(
            configuredRois,
            {
                status: "CALIBRATED",
                mode: "PROCESS_LIMITS",
                image_dimensions: { width: 400, height: 400, channels: 3 },
                roi_measurements: [
                    { roi_id: "unknown_extra_site", deposit_area_px: 999, inspection_status: "DETECTED" },
                    { roi_id: "site_alpha", deposit_area_px: 200, inspection_status: "DETECTED" },
                ],
                aggregate_measurements: { mean_coverage: 0.5, size_cv: 0, missing_roi_ids: [], warnings: [] },
                observations: [],
                warnings: [],
            },
            "site_alpha"
        );

        assert.equal(views.length, 2, "Only configured ROIs must be projected, extra unknown IDs excluded");
        assert.equal(views[0].roi.roi_id, "site_alpha");
        assert.equal(views[0].status, "DETECTED");
        assert.equal(views[0].isSelected, true);
        assert.equal(views[1].roi.roi_id, "site_delta");
        assert.equal(views[1].status, "UNASSESSED"); // Omitted from response
        assert.equal(views[1].statusLabel, "Not assessed");
        assert.equal(views[1].isSelected, false);

        testsPassed++;
        console.log("✓ Test 1 Passed: ROI ID matching is strictly by ID and ignores extra response IDs.");
    }

    // --- 2. Missing & Legacy Status Projection ---
    {
        // Null measurement for configured site -> UNASSESSED ("Not assessed")
        const omittedStatus = getEffectiveRoiStatus(null, true);
        assert.equal(omittedStatus.status, "UNASSESSED");
        assert.equal(omittedStatus.label, "Not assessed");

        // Legacy measurement without inspection_status -> UNAVAILABLE ("Status unavailable")
        // Even if deposit_area_px is 0 or is_missing is true, we never invent pass/fail
        const legacyMissing = {
            roi_id: "site_old",
            deposit_area_px: 0,
            is_missing: true,
        };
        const legacyStatus = getEffectiveRoiStatus(legacyMissing, true);
        assert.equal(legacyStatus.status, "UNAVAILABLE");
        assert.equal(legacyStatus.label, "Status unavailable");

        // Explicit statuses
        const detected = getEffectiveRoiStatus({ roi_id: "s1", inspection_status: "DETECTED" });
        assert.equal(detected.status, "DETECTED");
        assert.equal(detected.label, "Material detected");

        const missingDeposit = getEffectiveRoiStatus({ roi_id: "s2", inspection_status: "MISSING" });
        assert.equal(missingDeposit.status, "MISSING");
        assert.equal(missingDeposit.label, "Expected deposit missing");

        const unassessed = getEffectiveRoiStatus({ roi_id: "s3", inspection_status: "UNASSESSED" });
        assert.equal(unassessed.status, "UNASSESSED");
        assert.equal(unassessed.label, "Not assessed");

        testsPassed++;
        console.log("✓ Test 2 Passed: Status projection truthfully distinguishes unassessed and legacy unavailable without guessing.");
    }

    // --- 3. Deposit Outline Validation ---
    {
        const validTriangle = [
            { x: 0.1, y: 0.1 },
            { x: 0.2, y: 0.1 },
            { x: 0.15, y: 0.2 },
        ];
        const resValid = validateDepositOutline(validTriangle, "DETECTED");
        assert.equal(resValid.isValid, true);
        assert.equal(resValid.points.length, 3);

        // Reject outline if status is not DETECTED (e.g. MISSING or UNASSESSED)
        const resMissing = validateDepositOutline(validTriangle, "MISSING");
        assert.equal(resMissing.isValid, false);
        assert.match(resMissing.reason, /only recorded for detected material/i);

        // Reject insufficient vertices (< 3)
        const resTwoPoints = validateDepositOutline([{ x: 0.1, y: 0.1 }, { x: 0.2, y: 0.2 }], "DETECTED");
        assert.equal(resTwoPoints.isValid, false);
        assert.match(resTwoPoints.reason, /minimum 3 required/i);

        // Reject excessive vertices (> 128)
        const manyPoints = Array.from({ length: 129 }, (_, i) => ({ x: i / 200, y: i / 200 }));
        const resTooMany = validateDepositOutline(manyPoints, "DETECTED");
        assert.equal(resTooMany.isValid, false);
        assert.match(resTooMany.reason, /maximum 128/i);

        // Reject duplicate vertices
        const duplicates = [
            { x: 0.1, y: 0.1 },
            { x: 0.2, y: 0.2 },
            { x: 0.1, y: 0.1 },
        ];
        const resDuplicates = validateDepositOutline(duplicates, "DETECTED");
        assert.equal(resDuplicates.isValid, false);
        assert.match(resDuplicates.reason, /duplicate vertex detected/i);

        // Reject out-of-bounds coordinates
        const outOfBounds = [
            { x: -0.05, y: 0.1 },
            { x: 0.2, y: 0.2 },
            { x: 0.15, y: 0.3 },
        ];
        const resOOB = validateDepositOutline(outOfBounds, "DETECTED");
        assert.equal(resOOB.isValid, false);
        assert.match(resOOB.reason, /extend outside \[0, 1\]/i);

        // Reject non-finite coordinates (NaN/Inf)
        const nonFinite = [
            { x: NaN, y: 0.1 },
            { x: 0.2, y: 0.2 },
            { x: 0.15, y: 0.3 },
        ];
        const resNonFinite = validateDepositOutline(nonFinite, "DETECTED");
        assert.equal(resNonFinite.isValid, false);
        assert.match(resNonFinite.reason, /non-finite/i);

        // Format points for SVG viewBox 0 0 1000 1000
        const svgPoints = formatPolygonPoints(validTriangle);
        assert.equal(svgPoints, "100.0,100.0 200.0,100.0 150.0,200.0");

        testsPassed++;
        console.log("✓ Test 3 Passed: Deposit outline validation enforces [3, 128] bounds, finite numbers, uniqueness, and DETECTED gating.");
    }

    // --- 4. Content Rectangle and Coordinate Mapping Tests ---
    {
        // 4.1 Landscape image (800x400) in square container (500x500):
        // Scale is min(500/800, 500/400) = 500/800 = 0.625.
        // Rendered width = 800 * 0.625 = 500.
        // Rendered height = 400 * 0.625 = 250.
        // Letterbox top = (500 - 250) / 2 = 125, left = 0.
        const landscapeRect = computeContentRect(500, 500, 800, 400);
        assert.equal(landscapeRect.width, 500);
        assert.equal(landscapeRect.height, 250);
        assert.equal(landscapeRect.left, 0);
        assert.equal(landscapeRect.top, 125);

        // Pointer click at top letterbox bar (e.g. Y = 50 inside container, top is 125)
        const containerBox = { left: 100, top: 100, width: 500, height: 500 };
        const clickInLetterbox = clientToNormalizedCoords(200, 150, containerBox, landscapeRect);
        // clientY is 150 -> container local Y is 50 -> outside contentRect (top is 125)
        assert.equal(clickInLetterbox.isInside, false, "Click in letterbox bar must be rejected as outside content");

        // Pointer click inside rendered image content (e.g. clientX = 350, clientY = 325)
        // local X = 250 -> normX = 250/500 = 0.5
        // local Y = 225 -> Y relative to content = 225 - 125 = 100 -> normY = 100/250 = 0.4
        const clickInContent = clientToNormalizedCoords(350, 325, containerBox, landscapeRect);
        assert.equal(clickInContent.isInside, true);
        assert.equal(clickInContent.x, 0.5);
        assert.equal(clickInContent.y, 0.4);

        // 4.2 Portrait image (400x800) in landscape container (600x400):
        // Scale is min(600/400, 400/800) = 400/800 = 0.5.
        // Rendered width = 400 * 0.5 = 200.
        // Rendered height = 800 * 0.5 = 400.
        // Pillarbox left = (600 - 200) / 2 = 200, top = 0.
        const portraitRect = computeContentRect(600, 400, 400, 800);
        assert.equal(portraitRect.width, 200);
        assert.equal(portraitRect.height, 400);
        assert.equal(portraitRect.left, 200);
        assert.equal(portraitRect.top, 0);

        testsPassed++;
        console.log("✓ Test 4 Passed: Content bounds accurately exclude letterboxing and reject outside pointer events.");
    }

    // --- 5. Overall Inspection Coverage Projection ---
    {
        // 5.1 Modern aggregate with counts and status
        const modernAgg = {
            mean_coverage: 0.85,
            size_cv: 0.10,
            missing_roi_ids: ["site_02"],
            unassessed_roi_ids: [],
            expected_roi_count: 5,
            assessed_roi_count: 4,
            inspection_coverage_status: "PARTIAL",
            warnings: [],
        };
        const projModern = projectCoverageSummary(modernAgg);
        assert.equal(projModern.isAvailable, true);
        assert.equal(projModern.expectedText, "5");
        assert.equal(projModern.assessedText, "4");
        assert.equal(projModern.statusText, "PARTIAL");

        // 5.2 Legacy aggregate missing counts
        const legacyAgg = {
            mean_coverage: 0.85,
            size_cv: 0.10,
            missing_roi_ids: [],
            warnings: [],
        };
        const projLegacy = projectCoverageSummary(legacyAgg);
        assert.equal(projLegacy.isAvailable, false);
        assert.equal(projLegacy.expectedText, "Not available");
        assert.equal(projLegacy.assessedText, "Not available");
        assert.equal(projLegacy.statusText, "Status unavailable");

        // 5.3 Null aggregate
        const projNull = projectCoverageSummary(null);
        assert.equal(projNull.isAvailable, false);
        assert.equal(projNull.statusText, "Status unavailable");

        testsPassed++;
        console.log("✓ Test 5 Passed: Inspection coverage projection handles modern counts and legacy unavailable states.");
    }

    // --- 6. Emitted Observations for ROI and Finding Semantics (R1) ---
    {
        const observations = [
            // Case 1: Individual deposit_size finding with explicit individual_regions scope
            {
                observation_type: "deposit_size",
                value: "undersized",
                metadata: {
                    region_evidence_scope: "individual_regions",
                    affected_roi_ids: ["site_01"],
                },
            },
            // Case 2: Realistic individual deposit_shape finding with explicit individual_regions scope
            {
                observation_type: "deposit_shape",
                value: "abnormal",
                metadata: {
                    region_evidence_scope: "individual_regions",
                    affected_roi_ids: ["site_01"],
                },
            },
            // Case 3: Realistic individual deposit_shape finding WITHOUT scope (legacy) -> must NOT infer group
            {
                observation_type: "deposit_shape",
                value: "tailing",
                metadata: {
                    affected_roi_ids: ["site_01"],
                },
            },
            // Case 4: Explicit comparison_group canonical D03 pair (deposit_size / inconsistent)
            {
                observation_type: "deposit_size",
                value: "inconsistent",
                metadata: {
                    region_evidence_scope: "comparison_group",
                    affected_roi_ids: ["site_01", "site_02"],
                },
            },
            // Case 5: Canonical legacy D03 pair WITHOUT scope (deposit_size / inconsistent) -> fallback to group
            {
                observation_type: "deposit_size",
                value: "inconsistent",
                metadata: {
                    affected_roi_ids: ["site_02"],
                },
            },
            // Case 6: Individual bubble presence without scope -> must NOT infer group
            {
                observation_type: "bubble_presence",
                value: "visible_bubbles",
                metadata: {
                    affected_roi_ids: ["site_02"],
                },
            },
        ];

        // Site 01 observations check
        const site1Obs = findEmittedObservationsForRoi(observations, "site_01");
        assert.equal(site1Obs.length, 4, "Site 01 has 4 matching observations");

        // 1) deposit_size=undersized (individual_regions scope)
        assert.equal(site1Obs[0].observation.observation_type, "deposit_size");
        assert.equal(site1Obs[0].isGroupFinding, false, "individual_regions scope is not a group finding");

        // 2) deposit_shape=abnormal (individual_regions scope) -> must be individual
        assert.equal(site1Obs[1].observation.observation_type, "deposit_shape");
        assert.equal(site1Obs[1].isGroupFinding, false, "deposit_shape with individual_regions is not a group finding");

        // 3) deposit_shape=tailing (no scope) -> must NEVER infer group
        assert.equal(site1Obs[2].observation.observation_type, "deposit_shape");
        assert.equal(site1Obs[2].isGroupFinding, false, "deposit_shape without scope must never infer group finding");

        // 4) deposit_size=inconsistent (comparison_group scope) -> group finding
        assert.equal(site1Obs[3].observation.observation_type, "deposit_size");
        assert.equal(site1Obs[3].isGroupFinding, true, "comparison_group scope is identified as group finding");

        // Site 02 observations check
        const site2Obs = findEmittedObservationsForRoi(observations, "site_02");
        assert.equal(site2Obs.length, 3, "Site 02 has 3 matching observations");

        // 1) deposit_size=inconsistent (comparison_group)
        assert.equal(site2Obs[0].isGroupFinding, true);

        // 2) deposit_size=inconsistent (legacy canonical D03 without scope) -> fallback to group finding
        assert.equal(site2Obs[1].observation.value, "inconsistent");
        assert.equal(site2Obs[1].isGroupFinding, true, "Legacy canonical D03 deposit_size=inconsistent without scope is identified as group finding");

        // 3) bubble_presence=visible_bubbles (no scope) -> must be individual
        assert.equal(site2Obs[2].observation.observation_type, "bubble_presence");
        assert.equal(site2Obs[2].isGroupFinding, false, "bubble_presence without scope is not a group finding");

        // Site 03 has no observations
        const site3Obs = findEmittedObservationsForRoi(observations, "site_03");
        assert.equal(site3Obs.length, 0);

        testsPassed++;
        console.log("✓ Test 6 Passed: Emitted observation lookup honors explicit scope, handles canonical legacy D03, and never mislabels shape findings.");
    }

    console.log(`\nAll ${testsPassed} region inspection view tests passed successfully.`);
}

runTests();
