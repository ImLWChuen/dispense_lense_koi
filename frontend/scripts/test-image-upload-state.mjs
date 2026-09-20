/**
 * Deterministic regression suite for ImageUpload request-state machine
 * and client-side analysis configuration validation (DLK-M3-027).
 *
 * Verifies:
 * 1. Client-side configuration validation (ROIs, bounds, process & reference limits, scale).
 * 2. Current request success (atomic commit with activeRequestToken).
 * 3. Current request error (atomic commit with activeRequestToken).
 * 4. Removal during in-flight analysis (request aborted, late result rejected, upload not recreated).
 * 5. Reconfiguration during in-flight analysis (request aborted, revision bumped, late result rejected).
 * 6. Supersession (new request started while older in-flight; older result rejected, newer succeeds).
 * 7. Old request finishing after newer request starts (old finally block preserves newer controller).
 * 8. Deferred React updater timing (updater commits even if finally ran first).
 */

import assert from "node:assert/strict";

// ============================================================================
// Extracted Validation Logic (mirrors ImageUpload.tsx validateAnalysisConfiguration)
// ============================================================================

export function validateAnalysisConfiguration(item) {
    if (!item.rois || item.rois.length === 0) {
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
            return `ROI "${roi.roi_id}" coordinates must be within [0.0, 1.0].`;
        }
        if (roi.x + roi.width > 1.0001) {
            return `ROI "${roi.roi_id}" exceeds image width boundary.`;
        }
        if (roi.y + roi.height > 1.0001) {
            return `ROI "${roi.roi_id}" exceeds image height boundary.`;
        }
    }

    if (item.mmPerPixel !== null && item.mmPerPixel !== undefined) {
        if (!Number.isFinite(item.mmPerPixel) || item.mmPerPixel <= 0) {
            return "Scale factor mm_per_pixel must be a positive number.";
        }
    }

    if (item.mode === "PROCESS_LIMITS") {
        const limits = item.processLimits;
        if (!limits) {
            return "Process limits mode requires at least one process limit to be defined.";
        }

        const hasMinCov = limits.min_coverage_ratio !== null && limits.min_coverage_ratio !== undefined;
        const hasMaxCov = limits.max_coverage_ratio !== null && limits.max_coverage_ratio !== undefined;
        const hasMaxOverflow = limits.max_overflow_ratio !== null && limits.max_overflow_ratio !== undefined;
        const hasMaxSizeCv = limits.max_size_cv !== null && limits.max_size_cv !== undefined;
        const hasMinPresence = limits.min_presence_ratio !== null && limits.min_presence_ratio !== undefined;

        if (!hasMinCov && !hasMaxCov && !hasMaxOverflow && !hasMaxSizeCv && !hasMinPresence) {
            return "Process limits mode requires at least one process limit to be defined.";
        }

        const validateRatio = (val, name) => {
            if (val !== null && val !== undefined) {
                if (!Number.isFinite(val) || val < 0.0 || val > 1.0) {
                    return `${name} must be a number between 0.0 and 1.0.`;
                }
            }
            return null;
        };

        const covErr = validateRatio(limits.min_coverage_ratio, "Min coverage ratio") ||
                       validateRatio(limits.max_coverage_ratio, "Max coverage ratio") ||
                       validateRatio(limits.max_overflow_ratio, "Max overflow ratio") ||
                       validateRatio(limits.min_presence_ratio, "Min presence ratio");
        if (covErr) return covErr;

        if (hasMaxSizeCv) {
            if (!Number.isFinite(limits.max_size_cv) || limits.max_size_cv < 0.0) {
                return "Max size CV must be a non-negative number.";
            }
        }

        if (hasMinCov && hasMaxCov) {
            if (limits.min_coverage_ratio > limits.max_coverage_ratio) {
                return "Min coverage ratio cannot be greater than max coverage ratio.";
            }
        }
    }

    if (item.mode === "REFERENCE_IMAGE") {
        if (!item.referenceFile) {
            return "Reference image mode requires a reference image file.";
        }

        const rLimits = item.referenceLimits;
        if (!rLimits) {
            return "Reference image mode requires comparison tolerances to be defined.";
        }

        const hasMinRef = rLimits.min_reference_ratio !== null && rLimits.min_reference_ratio !== undefined;
        const hasMaxRef = rLimits.max_reference_ratio !== null && rLimits.max_reference_ratio !== undefined;
        const hasTolerance = rLimits.tolerance_ratio !== null && rLimits.tolerance_ratio !== undefined;

        if (!hasMinRef && !hasMaxRef && !hasTolerance) {
            return "Reference image mode requires at least one of min reference ratio, max reference ratio, or tolerance ratio.";
        }

        if (hasTolerance) {
            if (!Number.isFinite(rLimits.tolerance_ratio) || rLimits.tolerance_ratio < 0.0 || rLimits.tolerance_ratio > 1.0) {
                return "Tolerance ratio must be a number between 0.0 and 1.0.";
            }
        }

        if (hasMinRef) {
            if (!Number.isFinite(rLimits.min_reference_ratio) || rLimits.min_reference_ratio <= 0.0) {
                return "Min reference ratio must be greater than 0.0.";
            }
        }

        if (hasMaxRef) {
            if (!Number.isFinite(rLimits.max_reference_ratio) || rLimits.max_reference_ratio <= 0.0) {
                return "Max reference ratio must be greater than 0.0.";
            }
        }

        if (hasMinRef && hasMaxRef) {
            if (rLimits.min_reference_ratio > rLimits.max_reference_ratio) {
                return "Min reference ratio cannot be greater than max reference ratio.";
            }
        }
    }

    return null;
}

// ============================================================================
// Extracted Request State Transitions (mirrors ImageUpload.tsx atomic logic)
// ============================================================================

export function startAnalysis(prevUploads, uploadId, requestToken) {
    const cur = prevUploads[uploadId];
    if (!cur) return prevUploads;
    return {
        ...prevUploads,
        [uploadId]: {
            ...cur,
            status: "analyzing",
            errorMessage: null,
            activeRequestToken: requestToken,
        },
    };
}

export function commitSuccess(prevUploads, uploadId, requestToken, requestRevision, response) {
    const cur = prevUploads[uploadId];
    if (!cur || cur.configRevision !== requestRevision || cur.activeRequestToken !== requestToken) {
        return prevUploads;
    }
    return {
        ...prevUploads,
        [uploadId]: {
            ...cur,
            status: "analyzed",
            result: response,
            errorMessage: null,
            activeRequestToken: null,
        },
    };
}

export function commitError(prevUploads, uploadId, requestToken, requestRevision, errorMessage) {
    const cur = prevUploads[uploadId];
    if (!cur || cur.configRevision !== requestRevision || cur.activeRequestToken !== requestToken) {
        return prevUploads;
    }
    return {
        ...prevUploads,
        [uploadId]: {
            ...cur,
            status: "error",
            errorMessage,
            activeRequestToken: null,
        },
    };
}

export function handleReconfigure(prevUploads, uploadId, updates) {
    const cur = prevUploads[uploadId];
    if (!cur) return prevUploads;
    return {
        ...prevUploads,
        [uploadId]: {
            ...cur,
            ...updates,
            status: "ready",
            result: null,
            errorMessage: null,
            configRevision: cur.configRevision + 1,
            activeRequestToken: null,
        },
    };
}

export function handleRemove(prevUploads, uploadId) {
    if (!prevUploads[uploadId]) return prevUploads;
    const next = { ...prevUploads };
    delete next[uploadId];
    return next;
}

export function cleanupController(controllers, uploadId, requestToken) {
    if (controllers[uploadId]?.token === requestToken) {
        delete controllers[uploadId];
    }
}

// ============================================================================
// Test Suite Execution
// ============================================================================

function createMockUpload(id = "up-1") {
    return {
        id,
        status: "ready",
        mode: "FEATURES_ONLY",
        rois: [{ roi_id: "dot-1", x: 0.1, y: 0.1, width: 0.2, height: 0.2 }],
        mmPerPixel: null,
        processLimits: null,
        referenceLimits: null,
        referenceFile: null,
        result: null,
        errorMessage: null,
        configRevision: 1,
        activeRequestToken: null,
    };
}

function runTests() {
    let testsPassed = 0;

    // --- 1. Client-Side Validation Tests ---
    {
        const itemNoRois = { ...createMockUpload(), rois: [] };
        assert.equal(
            validateAnalysisConfiguration(itemNoRois),
            "At least one target ROI must be defined before running analysis."
        );

        const itemBlankRoi = { ...createMockUpload(), rois: [{ roi_id: "   ", x: 0.1, y: 0.1, width: 0.2, height: 0.2 }] };
        assert.equal(
            validateAnalysisConfiguration(itemBlankRoi),
            "All ROIs must have a valid non-empty identifier."
        );

        const itemOutOfBounds = { ...createMockUpload(), rois: [{ roi_id: "dot-1", x: 0.9, y: 0.1, width: 0.2, height: 0.2 }] };
        assert.equal(
            validateAnalysisConfiguration(itemOutOfBounds),
            'ROI "dot-1" exceeds image width boundary.'
        );

        const itemNegativeScale = { ...createMockUpload(), mmPerPixel: -0.05 };
        assert.equal(
            validateAnalysisConfiguration(itemNegativeScale),
            "Scale factor mm_per_pixel must be a positive number."
        );

        const itemInvalidCov = {
            ...createMockUpload(),
            mode: "PROCESS_LIMITS",
            processLimits: { min_coverage_ratio: 1.5 },
        };
        assert.equal(
            validateAnalysisConfiguration(itemInvalidCov),
            "Min coverage ratio must be a number between 0.0 and 1.0."
        );

        const itemInvertedCov = {
            ...createMockUpload(),
            mode: "PROCESS_LIMITS",
            processLimits: { min_coverage_ratio: 0.8, max_coverage_ratio: 0.3 },
        };
        assert.equal(
            validateAnalysisConfiguration(itemInvertedCov),
            "Min coverage ratio cannot be greater than max coverage ratio."
        );

        const itemInvalidRefMin = {
            ...createMockUpload(),
            mode: "REFERENCE_IMAGE",
            referenceFile: {},
            referenceLimits: { min_reference_ratio: -0.2 },
        };
        assert.equal(
            validateAnalysisConfiguration(itemInvalidRefMin),
            "Min reference ratio must be greater than 0.0."
        );

        testsPassed++;
        console.log("✓ Test 1 Passed: Client-side configuration validation catches invalid limits and boundaries.");
    }

    // --- 2. Current Request Success ---
    {
        let uploads = { "up-1": createMockUpload("up-1") };
        const controllers = {};
        const mockController = { abort: () => {} };
        const requestToken = 1;
        const requestRevision = 1;

        controllers["up-1"] = { token: requestToken, controller: mockController };
        uploads = startAnalysis(uploads, "up-1", requestToken);

        assert.equal(uploads["up-1"].status, "analyzing");
        assert.equal(uploads["up-1"].activeRequestToken, 1);

        const mockResponse = { status: "CALIBRATED", observations: [{ id: "obs-1" }] };
        uploads = commitSuccess(uploads, "up-1", requestToken, requestRevision, mockResponse);
        cleanupController(controllers, "up-1", requestToken);

        assert.equal(uploads["up-1"].status, "analyzed");
        assert.equal(uploads["up-1"].result, mockResponse);
        assert.equal(uploads["up-1"].activeRequestToken, null);
        assert.equal(controllers["up-1"], undefined);

        testsPassed++;
        console.log("✓ Test 2 Passed: Current request success commits atomically and cleans up request token.");
    }

    // --- 3. Current Request Error ---
    {
        let uploads = { "up-1": createMockUpload("up-1") };
        const controllers = {};
        const mockController = { abort: () => {} };
        const requestToken = 1;
        const requestRevision = 1;

        controllers["up-1"] = { token: requestToken, controller: mockController };
        uploads = startAnalysis(uploads, "up-1", requestToken);

        uploads = commitError(uploads, "up-1", requestToken, requestRevision, "Backend unavailable");
        cleanupController(controllers, "up-1", requestToken);

        assert.equal(uploads["up-1"].status, "error");
        assert.equal(uploads["up-1"].errorMessage, "Backend unavailable");
        assert.equal(uploads["up-1"].activeRequestToken, null);
        assert.equal(uploads["up-1"].result, null);
        assert.equal(controllers["up-1"], undefined);

        testsPassed++;
        console.log("✓ Test 3 Passed: Current request error commits atomically and records error message.");
    }

    // --- 4. Removal During In-Flight Analysis ---
    {
        let uploads = { "up-1": createMockUpload("up-1") };
        const controllers = {};
        let aborted = false;
        const mockController = { abort: () => { aborted = true; } };
        const requestToken = 1;
        const requestRevision = 1;

        controllers["up-1"] = { token: requestToken, controller: mockController };
        uploads = startAnalysis(uploads, "up-1", requestToken);

        // User removes the upload while request is in flight
        if (controllers["up-1"]) {
            controllers["up-1"].controller.abort();
            delete controllers["up-1"];
        }
        uploads = handleRemove(uploads, "up-1");

        assert.equal(aborted, true);
        assert.equal(uploads["up-1"], undefined);
        assert.equal(controllers["up-1"], undefined);

        // Late response arrives from the network
        const mockResponse = { status: "CALIBRATED", observations: [] };
        uploads = commitSuccess(uploads, "up-1", requestToken, requestRevision, mockResponse);

        // Confirm upload was NOT resurrected
        assert.equal(uploads["up-1"], undefined);

        testsPassed++;
        console.log("✓ Test 4 Passed: Removal aborts controller and late response does not recreate upload.");
    }

    // --- 5. Reconfiguration During In-Flight Analysis ---
    {
        let uploads = { "up-1": createMockUpload("up-1") };
        const controllers = {};
        let aborted = false;
        const mockController = { abort: () => { aborted = true; } };
        const requestToken = 1;
        const requestRevision = 1;

        controllers["up-1"] = { token: requestToken, controller: mockController };
        uploads = startAnalysis(uploads, "up-1", requestToken);

        // User reconfigures ROIs while request is in flight
        if (controllers["up-1"]) {
            controllers["up-1"].controller.abort();
            delete controllers["up-1"];
        }
        uploads = handleReconfigure(uploads, "up-1", {
            rois: [{ roi_id: "dot-2", x: 0.3, y: 0.3, width: 0.2, height: 0.2 }],
        });

        assert.equal(aborted, true);
        assert.equal(uploads["up-1"].status, "ready");
        assert.equal(uploads["up-1"].configRevision, 2);
        assert.equal(uploads["up-1"].activeRequestToken, null);

        // Old response arrives with revision 1 and token 1
        const mockResponse = { status: "CALIBRATED", observations: [{ id: "stale-obs" }] };
        uploads = commitSuccess(uploads, "up-1", requestToken, requestRevision, mockResponse);

        // Confirm stale result was discarded
        assert.equal(uploads["up-1"].status, "ready");
        assert.equal(uploads["up-1"].result, null);

        testsPassed++;
        console.log("✓ Test 5 Passed: Reconfiguration bumps revision, clears token, and rejects stale response.");
    }

    // --- 6. Supersession (New Request Started While Older Is In-Flight) ---
    {
        let uploads = { "up-1": createMockUpload("up-1") };
        const controllers = {};
        let req1Aborted = false;
        const mockController1 = { abort: () => { req1Aborted = true; } };
        const mockController2 = { abort: () => {} };

        // Request 1 starts
        controllers["up-1"] = { token: 1, controller: mockController1 };
        uploads = startAnalysis(uploads, "up-1", 1);

        // Request 2 supersedes Request 1
        controllers["up-1"].controller.abort();
        delete controllers["up-1"];
        controllers["up-1"] = { token: 2, controller: mockController2 };
        uploads = startAnalysis(uploads, "up-1", 2);

        assert.equal(req1Aborted, true);
        assert.equal(uploads["up-1"].activeRequestToken, 2);
        assert.equal(controllers["up-1"].token, 2);

        // Request 1 finishes late and tries to commit
        const mockResponse1 = { status: "CALIBRATED", observations: [{ id: "obs-from-req-1" }] };
        uploads = commitSuccess(uploads, "up-1", 1, 1, mockResponse1);

        // Request 1's finally block runs
        cleanupController(controllers, "up-1", 1);

        // Confirm Request 1 could not commit and did NOT delete Request 2's controller
        assert.equal(uploads["up-1"].status, "analyzing");
        assert.equal(uploads["up-1"].result, null);
        assert.equal(controllers["up-1"].token, 2);

        // Request 2 completes successfully
        const mockResponse2 = { status: "CALIBRATED", observations: [{ id: "obs-from-req-2" }] };
        uploads = commitSuccess(uploads, "up-1", 2, 1, mockResponse2);
        cleanupController(controllers, "up-1", 2);

        assert.equal(uploads["up-1"].status, "analyzed");
        assert.equal(uploads["up-1"].result, mockResponse2);
        assert.equal(uploads["up-1"].activeRequestToken, null);
        assert.equal(controllers["up-1"], undefined);

        testsPassed++;
        console.log("✓ Test 6 Passed: Superseded request cannot commit result or delete newer controller.");
    }

    // --- 7. Deferred React Updater Timing Simulation ---
    {
        let uploads = { "up-1": createMockUpload("up-1") };
        const controllers = {};
        const mockController = { abort: () => {} };
        const requestToken = 1;
        const requestRevision = 1;

        controllers["up-1"] = { token: requestToken, controller: mockController };
        uploads = startAnalysis(uploads, "up-1", requestToken);

        // Simulate finally block executing BEFORE React commits the queued updater callback
        cleanupController(controllers, "up-1", requestToken);
        assert.equal(controllers["up-1"], undefined, "Controller deleted in finally before state updater runs");

        // React executes the deferred functional updater
        const mockResponse = { status: "CALIBRATED", observations: [{ id: "obs-deferred" }] };
        uploads = commitSuccess(uploads, "up-1", requestToken, requestRevision, mockResponse);

        // Because activeRequestToken is stored in UploadItem state, the commit succeeds
        assert.equal(uploads["up-1"].status, "analyzed");
        assert.equal(uploads["up-1"].result, mockResponse);
        assert.equal(uploads["up-1"].activeRequestToken, null);

        testsPassed++;
        console.log("✓ Test 7 Passed: Deferred state updater commits reliably even when finally runs first.");
    }

    console.log(`\nAll ${testsPassed} regression tests passed successfully.`);
}

runTests();
