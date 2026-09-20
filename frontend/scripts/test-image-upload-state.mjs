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
import {
    validateAnalysisConfiguration,
    startAnalysis,
    commitSuccess,
    commitError,
    handleReconfigure,
    handleRemove,
    cleanupController,
} from "../lib/image-upload-state.ts";

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
            "ROI dot-1 extends beyond the image boundaries."
        );

        // Explicitly verify production boundary tolerance (1.00001)
        const itemWithinTolerance = { ...createMockUpload(), rois: [{ roi_id: "dot-1", x: 0.9, y: 0.1, width: 0.100005, height: 0.2 }] };
        assert.equal(
            validateAnalysisConfiguration(itemWithinTolerance),
            null
        );

        const itemExceedingTolerance = { ...createMockUpload(), rois: [{ roi_id: "dot-1", x: 0.9, y: 0.1, width: 0.10002, height: 0.2 }] };
        assert.equal(
            validateAnalysisConfiguration(itemExceedingTolerance),
            "ROI dot-1 extends beyond the image boundaries."
        );

        const itemNegativeScale = { ...createMockUpload(), mmPerPixel: -0.05 };
        assert.equal(
            validateAnalysisConfiguration(itemNegativeScale),
            "Scale (mm per pixel) must be a positive finite number greater than 0."
        );

        const itemInvalidCov = {
            ...createMockUpload(),
            mode: "PROCESS_LIMITS",
            processLimits: { min_coverage_ratio: 1.5 },
        };
        assert.equal(
            validateAnalysisConfiguration(itemInvalidCov),
            "Min coverage ratio must be a finite number between 0 and 1."
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
            "Min reference ratio must be a finite number greater than 0 (> 0)."
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
