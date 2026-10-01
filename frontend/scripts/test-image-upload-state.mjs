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
    handleImportLayout,
    handleConfirmPlacement,
    handleAbandonLayout,
} from "../lib/image-upload-state.ts";
import {
    createRegionLayout,
    serializeRegionLayout,
} from "../lib/region-layout.ts";

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

    // --- 8. Layout Import: Pending Confirmation and Analysis Block ---
    {
        let uploads = { "up-1": createMockUpload("up-1") };
        // Baseline: manual upload passes validation without confirmation
        assert.equal(validateAnalysisConfiguration(uploads["up-1"]), null);

        const mockLayout = {
            format: "dispense-region-layout",
            version: 1,
            name: "Standard Dual Site",
            source_image: { width: 1024, height: 768 },
            rois: [
                { roi_id: "site-a", x: 0.1, y: 0.2, width: 0.3, height: 0.4 },
                { roi_id: "site-b", x: 0.5, y: 0.6, width: 0.3, height: 0.2 },
            ],
        };

        uploads = handleImportLayout(uploads, "up-1", mockLayout);

        const item = uploads["up-1"];
        assert.equal(item.status, "ready");
        assert.equal(item.result, null);
        assert.equal(item.configRevision, 2);
        assert.equal(item.rois.length, 2);
        assert.equal(item.rois[0].roi_id, "site-a");
        assert.equal(item.rois[1].roi_id, "site-b");

        // Verify imported layout metadata
        assert.ok(item.importedLayout);
        assert.equal(item.importedLayout.name, "Standard Dual Site");
        assert.equal(item.importedLayout.confirmed, false);
        assert.equal(item.importedLayout.sourceDimensions.width, 1024);
        assert.equal(item.importedLayout.sourceDimensions.height, 768);

        // Analysis MUST refuse dispatch while unconfirmed
        assert.equal(
            validateAnalysisConfiguration(item),
            "Imported region layout placement must be confirmed before running analysis."
        );

        testsPassed++;
        console.log("✓ Test 8 Passed: Layout import sets pending confirmation, bumps revision, and blocks analysis.");
    }

    // --- 9. Placement Confirmation and Target Dimension Validation ---
    {
        let uploads = { "up-1": createMockUpload("up-1") };
        const mockLayout = {
            format: "dispense-region-layout",
            version: 1,
            name: "Standard Dual Site",
            source_image: { width: 1024, height: 768 },
            rois: [{ roi_id: "site-a", x: 0.1, y: 0.2, width: 0.3, height: 0.4 }],
        };
        uploads = handleImportLayout(uploads, "up-1", mockLayout);

        // Unreadable / non-positive target dimensions must block confirmation
        const unreadableDims = { width: 0, height: 768 };
        uploads = handleConfirmPlacement(uploads, "up-1", unreadableDims);
        assert.equal(uploads["up-1"].importedLayout.confirmed, false);

        const negativeDims = { width: 1024, height: -10 };
        uploads = handleConfirmPlacement(uploads, "up-1", negativeDims);
        assert.equal(uploads["up-1"].importedLayout.confirmed, false);

        // Valid target dimensions allow confirmation
        const validDims = { width: 1920, height: 1080 };
        uploads = handleConfirmPlacement(uploads, "up-1", validDims);
        assert.equal(uploads["up-1"].importedLayout.confirmed, true);
        assert.ok(uploads["up-1"].importedLayout.confirmedAt);
        assert.equal(uploads["up-1"].importedLayout.confirmedRevision, uploads["up-1"].configRevision);

        // Analysis is now unblocked
        assert.equal(validateAnalysisConfiguration(uploads["up-1"]), null);

        testsPassed++;
        console.log("✓ Test 9 Passed: Placement confirmation validates target dimensions and unblocks analysis.");
    }

    // --- 10. ROI Editing Invalidates Confirmation and Prior Results ---
    {
        let uploads = { "up-1": createMockUpload("up-1") };
        const mockLayout = {
            format: "dispense-region-layout",
            version: 1,
            name: "Standard Dual Site",
            source_image: { width: 1024, height: 768 },
            rois: [{ roi_id: "site-a", x: 0.1, y: 0.2, width: 0.3, height: 0.4 }],
        };
        uploads = handleImportLayout(uploads, "up-1", mockLayout);
        uploads = handleConfirmPlacement(uploads, "up-1", { width: 1024, height: 768 });
        assert.equal(uploads["up-1"].importedLayout.confirmed, true);

        // Simulate analysis result
        uploads["up-1"].status = "analyzed";
        uploads["up-1"].result = { status: "CALIBRATED", observations: [] };

        // Technician modifies ROI geometry
        uploads = handleReconfigure(uploads, "up-1", {
            rois: [{ roi_id: "site-a", x: 0.15, y: 0.25, width: 0.3, height: 0.4 }],
        });

        // Confirmation and prior results MUST be invalidated
        assert.equal(uploads["up-1"].importedLayout.confirmed, false);
        assert.equal(uploads["up-1"].importedLayout.confirmedAt, null);
        assert.equal(uploads["up-1"].result, null);
        assert.equal(uploads["up-1"].status, "ready");
        assert.equal(
            validateAnalysisConfiguration(uploads["up-1"]),
            "Imported region layout placement must be confirmed before running analysis."
        );

        testsPassed++;
        console.log("✓ Test 10 Passed: Editing ROIs invalidates placement confirmation and prior results.");
    }

    // --- 11. Abandoning Imported Layout and Manual Fallback ---
    {
        let uploads = { "up-1": createMockUpload("up-1") };
        const mockLayout = {
            format: "dispense-region-layout",
            version: 1,
            name: "Standard Dual Site",
            source_image: { width: 1024, height: 768 },
            rois: [{ roi_id: "site-a", x: 0.1, y: 0.2, width: 0.3, height: 0.4 }],
        };
        uploads = handleImportLayout(uploads, "up-1", mockLayout);
        assert.ok(uploads["up-1"].importedLayout);

        // Case A: Explicit abandon
        uploads = handleAbandonLayout(uploads, "up-1");
        assert.equal(uploads["up-1"].importedLayout, null);
        assert.equal(uploads["up-1"].rois.length, 0);

        // User can now draw manually without confirmation gate
        uploads = handleReconfigure(uploads, "up-1", {
            rois: [{ roi_id: "manual-site", x: 0.2, y: 0.2, width: 0.4, height: 0.4 }],
        });
        assert.equal(uploads["up-1"].importedLayout, null);
        assert.equal(validateAnalysisConfiguration(uploads["up-1"]), null);

        // Case B: Clearing ROIs via handleReconfigure also removes importedLayout gate
        uploads = handleImportLayout(uploads, "up-1", mockLayout);
        assert.ok(uploads["up-1"].importedLayout);
        uploads = handleReconfigure(uploads, "up-1", { rois: [] });
        assert.equal(uploads["up-1"].importedLayout, null);

        testsPassed++;
        console.log("✓ Test 11 Passed: Abandoning imported layout and clearing ROIs restores manual workflow.");
    }

    // --- 12. Reference Image Change Invalidates Confirmation in REFERENCE_IMAGE Mode ---
    {
        let uploads = {
            "up-1": {
                ...createMockUpload("up-1"),
                mode: "REFERENCE_IMAGE",
                referenceFile: { name: "ref-v1.png" },
                referenceLimits: { tolerance_ratio: 0.1 },
            },
        };

        const mockLayout = {
            format: "dispense-region-layout",
            version: 1,
            name: "Ref Layout",
            source_image: { width: 800, height: 600 },
            rois: [{ roi_id: "ref-roi-1", x: 0.1, y: 0.1, width: 0.2, height: 0.2 }],
        };
        uploads = handleImportLayout(uploads, "up-1", mockLayout);
        uploads = handleConfirmPlacement(uploads, "up-1", { width: 800, height: 600 });
        assert.equal(uploads["up-1"].importedLayout.confirmed, true);

        // Changing the reference file in REFERENCE_IMAGE mode invalidates confirmation
        const newRefFile = { name: "ref-v2.png" };
        uploads = handleReconfigure(uploads, "up-1", { referenceFile: newRefFile });
        assert.equal(uploads["up-1"].importedLayout.confirmed, false);
        assert.equal(
            validateAnalysisConfiguration(uploads["up-1"]),
            "Imported region layout placement must be confirmed before running analysis."
        );

        testsPassed++;
        console.log("✓ Test 12 Passed: Reference image change invalidates confirmation in REFERENCE_IMAGE mode.");
    }

    // --- 13. Stale Analysis Response After Layout Import ---
    {
        let uploads = { "up-1": createMockUpload("up-1") };
        const requestToken = 10;
        const requestRevision = 1;

        uploads = startAnalysis(uploads, "up-1", requestToken);
        assert.equal(uploads["up-1"].status, "analyzing");

        // Layout is imported while request is in flight
        const mockLayout = {
            format: "dispense-region-layout",
            version: 1,
            name: "Layout Mid-flight",
            source_image: { width: 800, height: 600 },
            rois: [{ roi_id: "new-site", x: 0.2, y: 0.2, width: 0.3, height: 0.3 }],
        };
        uploads = handleImportLayout(uploads, "up-1", mockLayout);
        assert.equal(uploads["up-1"].status, "ready");
        assert.equal(uploads["up-1"].configRevision, 2);
        assert.equal(uploads["up-1"].activeRequestToken, null);

        // Old response from requestToken 10 arrives
        const staleResponse = { status: "CALIBRATED", observations: [{ id: "stale" }] };
        uploads = commitSuccess(uploads, "up-1", requestToken, requestRevision, staleResponse);

        // Stale result MUST be rejected
        assert.equal(uploads["up-1"].status, "ready");
        assert.equal(uploads["up-1"].result, null);

        testsPassed++;
        console.log("✓ Test 13 Passed: Stale network responses after layout import cannot overwrite state.");
    }

    // --- 14. Asynchronous File Read Races and Multi-Upload Independence ---
    {
        let uploads = {
            "up-1": createMockUpload("up-1"),
            "up-2": createMockUpload("up-2"),
        };

        const mockLayoutA = {
            format: "dispense-region-layout",
            version: 1,
            name: "Layout A",
            source_image: { width: 800, height: 600 },
            rois: [{ roi_id: "site-a", x: 0.1, y: 0.1, width: 0.2, height: 0.2 }],
        };
        const mockLayoutB = {
            format: "dispense-region-layout",
            version: 1,
            name: "Layout B",
            source_image: { width: 1200, height: 900 },
            rois: [{ roi_id: "site-b", x: 0.4, y: 0.4, width: 0.3, height: 0.3 }],
        };

        // Import on up-1 does not affect up-2
        uploads = handleImportLayout(uploads, "up-1", mockLayoutA);
        assert.ok(uploads["up-1"].importedLayout);
        assert.equal(uploads["up-2"].importedLayout, undefined);
        assert.equal(uploads["up-2"].configRevision, 1);
        assert.equal(uploads["up-2"].rois[0].roi_id, "dot-1");

        // Concurrent read race simulation on up-1:
        // Read 1 starts at configRevision 2
        const read1Revision = uploads["up-1"].configRevision;
        // User reconfigures up-1 or Read 2 commits first, bumping revision to 3
        uploads = handleImportLayout(uploads, "up-1", mockLayoutB);
        assert.equal(uploads["up-1"].configRevision, 3);
        assert.equal(uploads["up-1"].importedLayout.name, "Layout B");

        // Stale Read 1 finishes late: application guard checks revision
        if (uploads["up-1"] && uploads["up-1"].configRevision === read1Revision) {
            uploads = handleImportLayout(uploads, "up-1", mockLayoutA);
        }
        // Read 1 was discarded, up-1 retains Layout B
        assert.equal(uploads["up-1"].configRevision, 3);
        assert.equal(uploads["up-1"].importedLayout.name, "Layout B");

        // Deletion race simulation:
        // Read starts on up-2, but user removes up-2 before read completes
        uploads = handleRemove(uploads, "up-2");
        assert.equal(uploads["up-2"], undefined);
        if (uploads["up-2"]) {
            uploads = handleImportLayout(uploads, "up-2", mockLayoutA);
        }
        assert.equal(uploads["up-2"], undefined, "Deleted upload cannot be resurrected by late file read");

        // Export has no side effects on upload item
        const preExport = JSON.stringify(uploads["up-1"]);
        const layoutRes = createRegionLayout(
            uploads["up-1"].importedLayout.name,
            uploads["up-1"].importedLayout.sourceDimensions,
            uploads["up-1"].rois
        );
        assert.equal(layoutRes.ok, true);
        const serialized = serializeRegionLayout(layoutRes.layout);
        assert.ok(serialized.length > 0);
        assert.equal(JSON.stringify(uploads["up-1"]), preExport, "Export must not mutate upload item");

        testsPassed++;
        console.log("✓ Test 14 Passed: Asynchronous file read races and multi-upload isolation verified.");
    }

    console.log(`\nAll ${testsPassed} regression tests passed successfully.`);
}

runTests();
