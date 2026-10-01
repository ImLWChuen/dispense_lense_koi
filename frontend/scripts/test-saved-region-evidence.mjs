/**
 * Regression suite for Saved Region Evidence Projection (DLK-M3-043).
 *
 * Verifies:
 * 1. Multi-site evidence projection (distinct measurements, stable order, unique keys).
 * 2. Applied limits allowlist and formatting (only known keys, formatted units, finite values).
 * 3. Scope handling (individual_regions, comparison_group, canonical D03 fallback, unknown).
 * 4. Separate current and reference data (reference data explicitly null/not recorded when omitted).
 * 5. Robust untrusted metadata narrowing (malformed entries, non-finite scalars, non-array inputs).
 * 6. Affected IDs without snapshots (unmeasured sites distinguished from measured snapshots).
 * 7. Legacy observation fallback (legacy single-site summary preserved without multi-site masquerade).
 */

import assert from "node:assert/strict";
import {
    projectSavedRegionEvidence,
    parseScalarMeasurements,
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
                affected_roi_ids: ["dot-1", "dot-2"],
                applied_limits: {
                    min_coverage_ratio: 0.1,
                    max_coverage_ratio: 0.45,
                    max_bubble_count: 0,
                    unknown_unauthorized_key: 999, // Must be filtered out
                },
                region_evidence: [
                    {
                        roi_id: "dot-1",
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
                        roi_id: "dot-2",
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
        assert.deepEqual(view.affectedRoiIds, ["dot-1", "dot-2"]);
        assert.equal(view.hasSnapshots, true);
        assert.equal(view.isLegacyOnly, false);
        assert.equal(view.snapshots.length, 2);

        // Applied limits filtering
        assert.equal(view.appliedLimits.length, 3);
        const limitKeys = view.appliedLimits.map((l) => l.key);
        assert.ok(limitKeys.includes("min_coverage_ratio"));
        assert.ok(limitKeys.includes("max_coverage_ratio"));
        assert.ok(limitKeys.includes("max_bubble_count"));
        assert.ok(!limitKeys.includes("unknown_unauthorized_key"));

        // Snapshot measurements must be distinct
        const s1 = view.snapshots[0];
        const s2 = view.snapshots[1];
        assert.equal(s1.roi_id, "dot-1");
        assert.equal(s2.roi_id, "dot-2");
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
        console.log("✓ Test 1 Passed: Two distinct sites projected with correct limits, measurements, and unique keys.");
    }

    // --- 2. Reference Mode Measurements ---
    {
        const obs = {
            id: "obs-ref",
            observation_type: "deposit_size",
            value: "oversized",
            statement_type: "AI_INFERENCE",
            source: "IMAGE",
            metadata: {
                region_evidence_scope: "individual_regions",
                affected_roi_ids: ["r1"],
                applied_limits: {
                    tolerance_ratio: 0.15,
                },
                region_evidence: [
                    {
                        roi_id: "r1",
                        current_measurements: {
                            inspection_status: "DETECTED",
                            deposit_area_px: 500,
                            coverage_ratio: 0.25,
                        },
                        reference_measurements: {
                            inspection_status: "DETECTED",
                            deposit_area_px: 400,
                            coverage_ratio: 0.2,
                        },
                    },
                ],
            },
        };

        const view = projectSavedRegionEvidence(obs, 1);
        assert.equal(view.snapshots.length, 1);
        const s = view.snapshots[0];
        assert.equal(s.hasReference, true);
        assert.equal(s.referenceMeasurements?.deposit_area_px, 400);
        assert.equal(s.currentMeasurements?.deposit_area_px, 500);

        passed++;
        console.log("✓ Test 2 Passed: Reference measurements projected separately from current measurements.");
    }

    // --- 3. Scope Handling & Canonical D03 Fallback ---
    {
        // 3a: Explicit comparison_group
        const obsGroup = {
            id: "obs-grp",
            observation_type: "deposit_size",
            value: "inconsistent",
            metadata: {
                region_evidence_scope: "comparison_group",
            },
        };
        const viewGroup = projectSavedRegionEvidence(obsGroup, 2);
        assert.equal(viewGroup.scope, "comparison_group");
        assert.equal(viewGroup.scopeLabel, "Comparison Group");

        // 3b: Canonical D03 legacy fallback (scope missing, but type=deposit_size, value=inconsistent)
        const obsD03Legacy = {
            id: "obs-d03",
            observation_type: "deposit_size",
            value: "inconsistent",
            metadata: {},
        };
        const viewD03 = projectSavedRegionEvidence(obsD03Legacy, 3);
        assert.equal(viewD03.scope, "comparison_group");
        assert.ok(viewD03.scopeLabel.includes("Canonical D03"));

        // 3c: Missing scope for shape abnormality must NOT be mislabeled as group!
        const obsShape = {
            id: "obs-shape",
            observation_type: "deposit_shape",
            value: "abnormal",
            metadata: {},
        };
        const viewShape = projectSavedRegionEvidence(obsShape, 4);
        assert.equal(viewShape.scope, "unknown");
        assert.equal(viewShape.scopeLabel, "Not Recorded or Unknown");

        passed++;
        console.log("✓ Test 3 Passed: Scope handled accurately with canonical D03 fallback and shape protection.");
    }

    // --- 4. Legacy Observation Summary Fallback ---
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
                mode: "PROCESS_LIMITS",
                coverage_ratio: 0.12,
                overflow_ratio: 0.01,
                equivalent_diameter_px: 24.5,
                calibrated_diameter_mm: 0.49,
                segmentation_quality: 0.98,
                warnings: ["Legacy inspection warning"],
            },
        };

        const view = projectSavedRegionEvidence(obsLegacy, 5);
        assert.equal(view.hasSnapshots, false);
        assert.equal(view.isLegacyOnly, true);
        assert.notEqual(view.legacySummary, null);
        assert.equal(view.legacySummary?.status, "CALIBRATED");
        assert.equal(view.legacySummary?.roiId, "dot-legacy-1");
        assert.equal(view.legacySummary?.coverageRatio, 0.12);
        assert.equal(view.legacySummary?.calibratedDiameterMm, 0.49);
        assert.equal(view.warnings.length, 1);

        passed++;
        console.log("✓ Test 4 Passed: Legacy observation without region_evidence provides clean first-site summary.");
    }

    // --- 5. Untrusted Runtime Metadata Defense (Malformed & Extreme Inputs) ---
    {
        const obsMalformed = {
            id: "obs-malformed",
            observation_type: "deposit_presence",
            value: "missing",
            metadata: {
                region_evidence_scope: 12345, // invalid type
                affected_roi_ids: "not-an-array", // invalid type
                applied_limits: ["invalid-array"], // invalid type
                region_evidence: [
                    "not-a-dict", // malformed entry
                    {
                        roi_id: null, // missing ID
                        current_measurements: "corrupt-string", // invalid dict
                    },
                    {
                        roi_id: "dot-dup",
                        current_measurements: {
                            inspection_status: "INVALID_STATUS", // unknown enum
                            deposit_area_px: "not-a-number",
                            calibrated_diameter_mm: NaN, // non-finite
                            equivalent_diameter_px: Infinity, // non-finite
                        },
                    },
                    {
                        roi_id: "dot-dup", // duplicate ID
                        current_measurements: {
                            inspection_status: "DETECTED",
                            deposit_area_px: 100,
                        },
                    },
                ],
            },
        };

        const view = projectSavedRegionEvidence(obsMalformed, 6);
        assert.equal(view.scope, "unknown");
        assert.equal(view.appliedLimits.length, 0);
        assert.equal(view.snapshots.length, 4);

        // Entry 0 was string
        assert.equal(view.snapshots[0].isMalformed, true);
        assert.equal(view.snapshots[0].roi_id, "UNKNOWN");

        // Entry 1 had null ID and string measurements
        assert.equal(view.snapshots[1].isMalformed, true);
        assert.equal(view.snapshots[1].roi_id, "UNKNOWN");

        // Entry 2 had invalid status and non-finite scalars
        assert.equal(view.snapshots[2].roi_id, "dot-dup");
        assert.equal(
            view.snapshots[2].currentMeasurements?.inspection_status,
            "UNKNOWN"
        );
        assert.equal(view.snapshots[2].currentMeasurements?.deposit_area_px, null);
        assert.equal(
            view.snapshots[2].currentMeasurements?.calibrated_diameter_mm,
            null
        );
        assert.equal(
            view.snapshots[2].currentMeasurements?.equivalent_diameter_px,
            null
        );

        // Entry 3 had duplicate ID but must have unique React key
        assert.notEqual(view.snapshots[2].key, view.snapshots[3].key);
        assert.equal(view.snapshots[3].currentMeasurements?.deposit_area_px, 100);

        passed++;
        console.log("✓ Test 5 Passed: Malformed metadata safely narrowed without exceptions or duplicate keys.");
    }

    // --- 6. Unmeasured Affected ROI IDs ---
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

        const view = projectSavedRegionEvidence(obsPartial, 7);
        assert.deepEqual(view.unmeasuredAffectedIds, ["dot-unmeasured"]);
        assert.equal(view.snapshots.length, 2);

        passed++;
        console.log("✓ Test 6 Passed: Affected IDs without snapshots identified as unmeasured.");
    }

    // --- 7. Formatting Helpers ---
    {
        assert.equal(formatMetricPercent(0.1234), "12.3%");
        assert.equal(formatMetricPercent(null), "-");
        assert.equal(formatMetricPercent(NaN), "-");

        assert.equal(formatMetricNumber(123.456, 1, " px"), "123.5 px");
        assert.equal(formatMetricNumber(null), "-");

        assert.equal(formatPhysicalDiameter(0.399), "0.399 mm");
        assert.equal(formatPhysicalDiameter(null), "Not recorded");
        assert.equal(formatPhysicalDiameter(NaN), "Not recorded");

        assert.equal(formatLimitValue("min_coverage_ratio", 0.1), "0.1");
        assert.equal(formatLimitValue("tolerance_pct", 10), "10%");
        assert.equal(formatLimitValue("target_diameter_mm", 0.5), "0.5 mm");
        assert.equal(formatLimitValue("has_bubbles", false), "False");
        assert.equal(formatLimitValue("min_coverage_ratio", null), "-");

        // Verify parseScalarMeasurements and KNOWN_LIMIT_KEYS directly
        assert.ok(KNOWN_LIMIT_KEYS.has("min_coverage_ratio"));
        assert.ok(KNOWN_LIMIT_KEYS.has("target_diameter_mm"));
        const parsed = parseScalarMeasurements({ coverage_ratio: 0.85, deposit_area_px: 1500 });
        assert.equal(parsed?.coverage_ratio, 0.85);
        assert.equal(parsed?.deposit_area_px, 1500);

        passed++;
        console.log("✓ Test 7 Passed: Formatting helpers format numbers, percentages, physical units, and missing states.");
    }

    console.log(`\nAll ${passed} saved region evidence tests passed successfully.`);
}

runTests();
