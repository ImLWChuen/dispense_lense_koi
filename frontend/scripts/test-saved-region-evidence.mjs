/**
 * Regression suite for Saved Region Evidence Projection (DLK-M3-043).
 *
 * Verifies R1, R2, and R3 requirements:
 * 1. Multi-site evidence projection (distinct measurements, stable order, unique keys, full untruncated IDs).
 * 2. Reference mode measurements with all 15 scalar fields separately exposed.
 * 3. Scope handling (individual_regions, comparison_group, canonical D03 fallback, explicit unknown stays unknown, non-canonical D03 rejected).
 * 4. Genuine legacy observation with all 12 legacy comparison fields.
 * 5. Distinguishing malformed and empty region evidence from genuine legacy (no age inference, no masking).
 * 6. Untrusted runtime metadata defense (empty measurement objects return null/malformed, non-finite scalars).
 * 7. Unmeasured affected ROI IDs identified and distinct.
 * 8. Applied limits allowlist, formatting (target_area_px with px²), and strict boolean rejection for numeric limits.
 */

import assert from "node:assert/strict";
import {
    projectSavedRegionEvidence,
    parseScalarMeasurements,
    parseLegacySummary,
    formatLimitValue,
    formatMetricPercent,
    formatMetricNumber,
    formatPhysicalDiameter,
    KNOWN_LIMIT_KEYS,
} from "../lib/saved-region-evidence.ts";

function runTests() {
    let passed = 0;

    // --- 1. Two Distinct Sites (Scenario A equivalent) ---
    {
        const longId1 = "dot-site-alpha-zone-1234567890-abcdef-full-identifier";
        const longId2 = "dot-site-beta-zone-1234567890-abcdef-full-identifier";

        const obs = {
            id: "obs-1",
            observation_id: "obs-1",
            observation_type: "deposit_size",
            value: "undersized",
            original_text: "Undersized deposits detected",
            statement_type: "AI_INFERENCE",
            source: "IMAGE",
            confidence: 0.9,
            timestamp: "2026-10-01T12:00:00Z",
            created_at: "2026-10-01T12:00:00Z",
            first_seen_revision: 1,
            metadata: {
                region_evidence_scope: "individual_regions",
                affected_roi_ids: [longId1, longId2],
                applied_limits: {
                    min_coverage_ratio: 0.1,
                    max_coverage_ratio: 0.45,
                    max_bubble_count: 0,
                    target_area_px: 35328,
                    unknown_unauthorized_key: 999, // Must be filtered out
                },
                region_evidence: [
                    {
                        roi_id: longId1,
                        current_measurements: {
                            inspection_status: "DETECTED",
                            deposit_area_px: 313,
                            target_area_px: 35328,
                            coverage_ratio: 0.0089,
                            overflow_ratio: 0.0,
                            equivalent_diameter_px: 19.96,
                            calibrated_diameter_mm: 0.399,
                            circularity: 1.0,
                            solidity: 1.0,
                            convexity: 0.977,
                            aspect_ratio: 1.0,
                            hole_void_ratio: 0.0,
                            bubble_count: 0,
                            has_bubbles: false,
                            segmentation_quality: 1.0,
                        },
                        reference_measurements: null,
                    },
                    {
                        roi_id: longId2,
                        current_measurements: {
                            inspection_status: "DETECTED",
                            deposit_area_px: 705,
                            target_area_px: 35328,
                            coverage_ratio: 0.02,
                            overflow_ratio: 0.0,
                            equivalent_diameter_px: 29.96,
                            calibrated_diameter_mm: 0.599,
                            circularity: 0.969,
                            solidity: 1.0,
                            convexity: 0.97,
                            aspect_ratio: 1.0,
                            hole_void_ratio: 0.0,
                            bubble_count: 0,
                            has_bubbles: false,
                            segmentation_quality: 1.0,
                        },
                        reference_measurements: null,
                    },
                ],
            },
        };

        const view = projectSavedRegionEvidence(obs, 0);

        assert.equal(view.id, "obs-1");
        assert.equal(view.observationType, "deposit_size");
        assert.equal(view.value, "undersized");
        assert.equal(view.scope, "individual_regions");
        // Verify full untruncated IDs retained
        assert.deepEqual(view.affectedRoiIds, [longId1, longId2]);
        assert.equal(view.hasSnapshots, true);
        assert.equal(view.isLegacyOnly, false);
        assert.equal(view.regionEvidenceState, "present");
        assert.equal(view.snapshots.length, 2);

        // Applied limits filtering & formatting
        assert.equal(view.appliedLimits.length, 4);
        const limitMap = Object.fromEntries(view.appliedLimits.map((l) => [l.key, l.valueStr]));
        assert.equal(limitMap.min_coverage_ratio, "0.1");
        assert.equal(limitMap.max_coverage_ratio, "0.45");
        assert.equal(limitMap.max_bubble_count, "0");
        assert.equal(limitMap.target_area_px, "35328 px²");
        assert.equal(limitMap.unknown_unauthorized_key, undefined);

        // Snapshot measurements must be distinct and retain full IDs
        const s1 = view.snapshots[0];
        const s2 = view.snapshots[1];
        assert.equal(s1.roi_id, longId1);
        assert.equal(s2.roi_id, longId2);
        assert.notEqual(s1.key, s2.key);
        assert.equal(s1.currentMeasurements?.deposit_area_px, 313);
        assert.equal(s2.currentMeasurements?.deposit_area_px, 705);
        assert.notEqual(
            s1.currentMeasurements?.coverage_ratio,
            s2.currentMeasurements?.coverage_ratio
        );
        assert.equal(s1.hasReference, false);
        assert.equal(s1.referenceMeasurements, null);
        assert.equal(view.unmeasuredAffectedIds.length, 0);

        passed++;
        console.log("✓ Test 1 Passed: Two distinct sites projected with full IDs, correct limits, and unique keys.");
    }

    // --- 2. Reference Mode Measurements (All 15 Scalar Fields) ---
    {
        const obs = {
            id: "obs-ref",
            observation_type: "deposit_shape",
            value: "irregular",
            statement_type: "AI_INFERENCE",
            source: "IMAGE",
            metadata: {
                region_evidence_scope: "individual_regions",
                affected_roi_ids: ["r1"],
                applied_limits: {
                    min_circularity_ratio: 0.8,
                    tolerance_ratio: 0.15,
                },
                region_evidence: [
                    {
                        roi_id: "r1",
                        current_measurements: {
                            inspection_status: "DETECTED",
                            deposit_area_px: 520,
                            target_area_px: 1000,
                            coverage_ratio: 0.52,
                            overflow_ratio: 0.05,
                            equivalent_diameter_px: 25.7,
                            calibrated_diameter_mm: 0.514,
                            circularity: 0.72,
                            solidity: 0.85,
                            convexity: 0.88,
                            aspect_ratio: 1.35,
                            hole_void_ratio: 0.04,
                            bubble_count: 2,
                            has_bubbles: true,
                            segmentation_quality: 0.95,
                        },
                        reference_measurements: {
                            inspection_status: "DETECTED",
                            deposit_area_px: 500,
                            target_area_px: 1000,
                            coverage_ratio: 0.50,
                            overflow_ratio: 0.01,
                            equivalent_diameter_px: 25.2,
                            calibrated_diameter_mm: 0.504,
                            circularity: 0.98,
                            solidity: 0.99,
                            convexity: 0.99,
                            aspect_ratio: 1.02,
                            hole_void_ratio: 0.0,
                            bubble_count: 0,
                            has_bubbles: false,
                            segmentation_quality: 0.99,
                        },
                    },
                ],
            },
        };

        const view = projectSavedRegionEvidence(obs, 1);
        assert.equal(view.snapshots.length, 1);
        const s = view.snapshots[0];
        assert.equal(s.hasReference, true);

        // Verify current measurements have all 15 fields
        const cm = s.currentMeasurements;
        assert.ok(cm);
        assert.equal(cm.inspection_status, "DETECTED");
        assert.equal(cm.deposit_area_px, 520);
        assert.equal(cm.target_area_px, 1000);
        assert.equal(cm.coverage_ratio, 0.52);
        assert.equal(cm.overflow_ratio, 0.05);
        assert.equal(cm.equivalent_diameter_px, 25.7);
        assert.equal(cm.calibrated_diameter_mm, 0.514);
        assert.equal(cm.circularity, 0.72);
        assert.equal(cm.solidity, 0.85);
        assert.equal(cm.convexity, 0.88);
        assert.equal(cm.aspect_ratio, 1.35);
        assert.equal(cm.hole_void_ratio, 0.04);
        assert.equal(cm.bubble_count, 2);
        assert.equal(cm.has_bubbles, true);
        assert.equal(cm.segmentation_quality, 0.95);

        // Verify reference measurements have all 15 fields
        const rm = s.referenceMeasurements;
        assert.ok(rm);
        assert.equal(rm.inspection_status, "DETECTED");
        assert.equal(rm.deposit_area_px, 500);
        assert.equal(rm.target_area_px, 1000);
        assert.equal(rm.coverage_ratio, 0.50);
        assert.equal(rm.overflow_ratio, 0.01);
        assert.equal(rm.equivalent_diameter_px, 25.2);
        assert.equal(rm.calibrated_diameter_mm, 0.504);
        assert.equal(rm.circularity, 0.98);
        assert.equal(rm.solidity, 0.99);
        assert.equal(rm.convexity, 0.99);
        assert.equal(rm.aspect_ratio, 1.02);
        assert.equal(rm.hole_void_ratio, 0.0);
        assert.equal(rm.bubble_count, 0);
        assert.equal(rm.has_bubbles, false);
        assert.equal(rm.segmentation_quality, 0.99);

        passed++;
        console.log("✓ Test 2 Passed: Reference measurements expose all 15 fields separately from current.");
    }

    // --- 3. Scope Handling & Canonical D03 Strictness ---
    {
        // 3a: Explicit individual_regions
        const obsInd = {
            id: "obs-ind",
            observation_type: "deposit_size",
            value: "oversized",
            metadata: { region_evidence_scope: "individual_regions" },
        };
        assert.equal(projectSavedRegionEvidence(obsInd, 2).scope, "individual_regions");

        // 3b: Explicit comparison_group
        const obsGroup = {
            id: "obs-grp",
            observation_type: "deposit_size",
            value: "inconsistent",
            metadata: { region_evidence_scope: "comparison_group" },
        };
        assert.equal(projectSavedRegionEvidence(obsGroup, 3).scope, "comparison_group");

        // 3c: Explicit unrecognized scope remains strictly unknown (does NOT fallback to group)
        const obsCustom = {
            id: "obs-custom",
            observation_type: "deposit_size",
            value: "inconsistent",
            metadata: { region_evidence_scope: "custom_unrecognized_scope" },
        };
        const viewCustom = projectSavedRegionEvidence(obsCustom, 4);
        assert.equal(viewCustom.scope, "unknown");
        assert.equal(viewCustom.scopeLabel, "Unknown Scope");
        assert.ok(viewCustom.scopeDescription.includes("custom_unrecognized_scope"));

        // 3d: Canonical D03 legacy fallback (scope absent AND deposit_size AND inconsistent)
        const obsD03 = {
            id: "obs-d03",
            observation_type: "deposit_size",
            value: "inconsistent",
            metadata: {},
        };
        const viewD03 = projectSavedRegionEvidence(obsD03, 5);
        assert.equal(viewD03.scope, "comparison_group");
        assert.ok(viewD03.scopeLabel.includes("Canonical D03"));

        // 3e: Non-canonical D03 (deposit_size_cv) must NOT get fallback
        const obsNonCanonical = {
            id: "obs-non-canonical",
            observation_type: "deposit_size_cv",
            value: "inconsistent",
            metadata: {},
        };
        const viewNonCanonical = projectSavedRegionEvidence(obsNonCanonical, 6);
        assert.equal(viewNonCanonical.scope, "unknown");

        // 3f: Other observation types without scope remain unknown
        const obsShape = {
            id: "obs-shape",
            observation_type: "deposit_shape",
            value: "abnormal",
            metadata: {},
        };
        const viewShape = projectSavedRegionEvidence(obsShape, 7);
        assert.equal(viewShape.scope, "unknown");

        passed++;
        console.log("✓ Test 3 Passed: Scope handling enforces strict canonical D03 fallback and preserves unknown scopes.");
    }

    // --- 4. Genuinely Legacy Observation with All 12 Legacy Fields ---
    {
        const obsLegacy = {
            id: "obs-legacy",
            observation_type: "deposit_size",
            value: "undersized",
            statement_type: "AI_INFERENCE",
            source: "IMAGE",
            metadata: {
                status: "CALIBRATED",
                roi_id: "dot-legacy-1",
                mode: "GOLDEN_TEMPLATE",
                coverage_ratio: 0.12,
                overflow_ratio: 0.015,
                current_coverage: 0.12,
                reference_coverage: 0.24,
                coverage_ratio_to_reference: 0.50,
                equivalent_diameter_px: 24.5,
                calibrated_diameter_mm: 0.49,
                segmentation_quality: 0.98,
                size_cv: 0.08,
                warnings: ["Legacy inspection warning"],
            },
        };

        const view = projectSavedRegionEvidence(obsLegacy, 8);
        assert.equal(view.regionEvidenceState, "absent");
        assert.equal(view.hasSnapshots, false);
        assert.equal(view.isLegacyOnly, true);
        assert.notEqual(view.legacySummary, null);

        const ls = view.legacySummary;
        assert.ok(ls);
        assert.equal(ls.status, "CALIBRATED");
        assert.equal(ls.roiId, "dot-legacy-1");
        assert.equal(ls.mode, "GOLDEN_TEMPLATE");
        assert.equal(ls.coverageRatio, 0.12);
        assert.equal(ls.overflowRatio, 0.015);
        assert.equal(ls.currentCoverage, 0.12);
        assert.equal(ls.referenceCoverage, 0.24);
        assert.equal(ls.coverageRatioToReference, 0.50);
        assert.equal(ls.equivDiameterPx, 24.5);
        assert.equal(ls.calibratedDiameterMm, 0.49);
        assert.equal(ls.segQuality, 0.98);
        assert.equal(ls.sizeCv, 0.08);

        const directLegacy = parseLegacySummary(obsLegacy.metadata);
        assert.ok(directLegacy);
        assert.equal(directLegacy.coverageRatioToReference, 0.50);

        passed++;
        console.log("✓ Test 4 Passed: Genuine legacy observation renders all 12 comparison fields.");
    }

    // --- 5. Distinguishing Malformed & Empty Region Evidence from Genuine Legacy ---
    {
        // 5a: String region_evidence with legacy fields -> MALFORMED, NOT legacy-only
        const obsString = {
            id: "obs-str",
            observation_type: "deposit_size",
            value: "undersized",
            metadata: {
                region_evidence: "corrupt_string_evidence",
                status: "CALIBRATED",
                roi_id: "site-1",
                coverage_ratio: 0.15,
            },
        };
        const viewString = projectSavedRegionEvidence(obsString, 9);
        assert.equal(viewString.regionEvidenceState, "malformed");
        assert.equal(viewString.isLegacyOnly, false); // Must NOT mask malformed evidence!
        assert.ok(viewString.warnings.some((w) => w.includes("malformed")));
        assert.notEqual(viewString.legacySummary, null); // Legacy fields preserved as fallback

        // 5b: Object region_evidence with legacy fields -> MALFORMED, NOT legacy-only
        const obsObj = {
            id: "obs-obj",
            observation_type: "deposit_size",
            value: "undersized",
            metadata: {
                region_evidence: { site1: "invalid_dict" },
                status: "CALIBRATED",
            },
        };
        const viewObj = projectSavedRegionEvidence(obsObj, 10);
        assert.equal(viewObj.regionEvidenceState, "malformed");
        assert.equal(viewObj.isLegacyOnly, false);
        assert.ok(viewObj.warnings.some((w) => w.includes("malformed")));

        // 5c: Empty array region_evidence with legacy fields -> EMPTY, NOT legacy-only
        const obsEmpty = {
            id: "obs-empty",
            observation_type: "deposit_size",
            value: "undersized",
            metadata: {
                region_evidence: [],
                status: "CALIBRATED",
            },
        };
        const viewEmpty = projectSavedRegionEvidence(obsEmpty, 11);
        assert.equal(viewEmpty.regionEvidenceState, "empty");
        assert.equal(viewEmpty.isLegacyOnly, false);
        assert.ok(viewEmpty.warnings.some((w) => w.includes("0 site snapshots")));

        // 5d: Absent region_evidence with NO legacy fields -> ABSENT, NOT legacy-only
        const obsNone = {
            id: "obs-none",
            observation_type: "deposit_size",
            value: "undersized",
            metadata: {},
        };
        const viewNone = projectSavedRegionEvidence(obsNone, 12);
        assert.equal(viewNone.regionEvidenceState, "absent");
        assert.equal(viewNone.isLegacyOnly, false);
        assert.equal(viewNone.legacySummary, null);

        passed++;
        console.log("✓ Test 5 Passed: Malformed and empty region evidence tracked distinctly from genuine legacy.");
    }

    // --- 6. Untrusted Runtime Metadata Defense & Empty Measurement Objects ---
    {
        // 6a: parseScalarMeasurements with empty object must return null
        assert.equal(parseScalarMeasurements({}), null);
        assert.equal(parseScalarMeasurements(null), null);
        assert.equal(parseScalarMeasurements(undefined), null);
        assert.equal(parseScalarMeasurements("string"), null);
        assert.equal(
            parseScalarMeasurements({
                inspection_status: "INVALID_STATUS",
                deposit_area_px: "not_a_num",
                coverage_ratio: NaN,
            }),
            null
        );

        // 6b: Observation with empty measurement object
        const obsEmptyMeasurements = {
            id: "obs-empty-meas",
            observation_type: "deposit_presence",
            value: "missing",
            metadata: {
                region_evidence: [
                    {
                        roi_id: "site-empty",
                        current_measurements: {}, // empty dict
                    },
                    {
                        roi_id: "site-valid",
                        current_measurements: {
                            inspection_status: "DETECTED",
                            deposit_area_px: 250,
                        },
                    },
                ],
            },
        };
        const viewEmptyMeas = projectSavedRegionEvidence(obsEmptyMeasurements, 13);
        assert.equal(viewEmptyMeas.snapshots.length, 2);
        assert.equal(viewEmptyMeas.snapshots[0].isMalformed, true);
        assert.equal(viewEmptyMeas.snapshots[0].currentMeasurements, null);
        assert.equal(viewEmptyMeas.snapshots[1].isMalformed, false);
        assert.equal(viewEmptyMeas.snapshots[1].currentMeasurements?.deposit_area_px, 250);

        // 6c: Duplicate ROI IDs within malformed input receive distinct keys
        const obsDups = {
            id: "obs-dups",
            observation_type: "deposit_size",
            value: "undersized",
            metadata: {
                region_evidence: [
                    { roi_id: "dup-id", current_measurements: { deposit_area_px: 100 } },
                    { roi_id: "dup-id", current_measurements: { deposit_area_px: 200 } },
                ],
            },
        };
        const viewDups = projectSavedRegionEvidence(obsDups, 14);
        assert.equal(viewDups.snapshots.length, 2);
        assert.notEqual(viewDups.snapshots[0].key, viewDups.snapshots[1].key);

        passed++;
        console.log("✓ Test 6 Passed: Empty measurement objects treated as unavailable/malformed, duplicate keys avoided.");
    }

    // --- 7. Unmeasured Affected ROI IDs ---
    {
        const obsPartial = {
            id: "obs-partial",
            observation_type: "deposit_size",
            value: "undersized",
            metadata: {
                affected_roi_ids: ["dot-1", "dot-2", "dot-unmeasured"],
                region_evidence: [
                    {
                        roi_id: "dot-1",
                        current_measurements: {
                            inspection_status: "DETECTED",
                            deposit_area_px: 200,
                        },
                    },
                    {
                        roi_id: "dot-2",
                        current_measurements: {
                            inspection_status: "DETECTED",
                            deposit_area_px: 300,
                        },
                    },
                ],
            },
        };

        const view = projectSavedRegionEvidence(obsPartial, 15);
        assert.deepEqual(view.unmeasuredAffectedIds, ["dot-unmeasured"]);
        assert.equal(view.snapshots.length, 2);

        passed++;
        console.log("✓ Test 7 Passed: Affected IDs without snapshots identified as unmeasured.");
    }

    // --- 8. Applied Limits Formatting & Strict Boolean Handling ---
    {
        // target_area_px has px²
        assert.equal(formatLimitValue("target_area_px", 35328), "35328 px²");

        // Numeric limits with boolean values must return "unavailable"
        assert.equal(formatLimitValue("min_coverage_ratio", true), "unavailable");
        assert.equal(formatLimitValue("min_coverage_ratio", false), "unavailable");
        assert.equal(formatLimitValue("target_area_px", true), "unavailable");
        assert.equal(formatLimitValue("max_bubble_count", true), "unavailable");

        // has_bubbles allows booleans
        assert.equal(formatLimitValue("has_bubbles", true), "True");
        assert.equal(formatLimitValue("has_bubbles", false), "False");

        // Normal numeric values
        assert.equal(formatLimitValue("min_coverage_ratio", 0.1), "0.1");
        assert.equal(formatLimitValue("tolerance_pct", 10), "10%");
        assert.equal(formatLimitValue("target_diameter_mm", 0.5), "0.5 mm");
        assert.equal(formatLimitValue("min_coverage_ratio", null), "-");

        // Metric formatting
        assert.equal(formatMetricPercent(0.1234), "12.3%");
        assert.equal(formatMetricPercent(null), "-");
        assert.equal(formatMetricPercent(NaN), "-");
        assert.equal(formatMetricNumber(123.456, 1, " px"), "123.5 px");
        assert.equal(formatPhysicalDiameter(0.399), "0.399 mm");
        assert.equal(formatPhysicalDiameter(null), "Not recorded");

        assert.ok(KNOWN_LIMIT_KEYS.has("target_area_px"));
        assert.ok(KNOWN_LIMIT_KEYS.has("min_coverage_ratio"));

        passed++;
        console.log("✓ Test 8 Passed: Limits formatting enforces px² and rejects booleans for numeric limits.");
    }

    console.log(`\nAll ${passed} saved region evidence tests passed successfully.`);
}

runTests();
