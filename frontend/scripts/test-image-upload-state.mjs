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
    ImportCoordinator,
    beginRegionLayoutImport,
    beginRegionLayoutFileSelection,
    clearRegionLayoutImport,
    startCoordinatedImport,
} from "../lib/image-upload-state.ts";
import {
    createRegionLayout,
    serializeRegionLayout,
    parseRegionLayout,
    MAX_LAYOUT_FILE_BYTES,
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

        // Unconditional target dimension validation (R2):
        // 1. Omitted targetDimensions argument
        uploads = handleConfirmPlacement(uploads, "up-1");
        assert.equal(uploads["up-1"].importedLayout.confirmed, false);
        assert.equal(validateAnalysisConfiguration(uploads["up-1"]), "Imported region layout placement must be confirmed before running analysis.");

        // 2. Explicit null targetDimensions
        uploads = handleConfirmPlacement(uploads, "up-1", null);
        assert.equal(uploads["up-1"].importedLayout.confirmed, false);
        assert.equal(validateAnalysisConfiguration(uploads["up-1"]), "Imported region layout placement must be confirmed before running analysis.");

        // 3. Explicit undefined targetDimensions
        uploads = handleConfirmPlacement(uploads, "up-1", undefined);
        assert.equal(uploads["up-1"].importedLayout.confirmed, false);
        assert.equal(validateAnalysisConfiguration(uploads["up-1"]), "Imported region layout placement must be confirmed before running analysis.");

        // 4. Zero dimensions
        uploads = handleConfirmPlacement(uploads, "up-1", { width: 0, height: 768 });
        assert.equal(uploads["up-1"].importedLayout.confirmed, false);

        // 5. Negative dimensions
        uploads = handleConfirmPlacement(uploads, "up-1", { width: 1024, height: -10 });
        assert.equal(uploads["up-1"].importedLayout.confirmed, false);

        // 6. Floating point / non-integer dimensions
        uploads = handleConfirmPlacement(uploads, "up-1", { width: 1024.5, height: 768 });
        assert.equal(uploads["up-1"].importedLayout.confirmed, false);

        // 7. NaN dimensions
        uploads = handleConfirmPlacement(uploads, "up-1", { width: NaN, height: 768 });
        assert.equal(uploads["up-1"].importedLayout.confirmed, false);

        // 8. Infinity dimensions
        uploads = handleConfirmPlacement(uploads, "up-1", { width: Infinity, height: 768 });
        assert.equal(uploads["up-1"].importedLayout.confirmed, false);

        // 9. Non-number dimensions / malformed objects
        uploads = handleConfirmPlacement(uploads, "up-1", { width: "1024", height: 768 });
        assert.equal(uploads["up-1"].importedLayout.confirmed, false);
        uploads = handleConfirmPlacement(uploads, "up-1", {});
        assert.equal(uploads["up-1"].importedLayout.confirmed, false);

        // 10. Valid target dimensions allow confirmation and unblock analysis
        const validDims = { width: 1920, height: 1080 };
        uploads = handleConfirmPlacement(uploads, "up-1", validDims);
        assert.equal(uploads["up-1"].importedLayout.confirmed, true);
        assert.ok(uploads["up-1"].importedLayout.confirmedAt);
        assert.equal(uploads["up-1"].importedLayout.confirmedRevision, uploads["up-1"].configRevision);

        // Analysis is now unblocked
        assert.equal(validateAnalysisConfiguration(uploads["up-1"]), null);

        testsPassed++;
        console.log("✓ Test 9 Passed: Placement confirmation unconditionally validates target dimensions (omitted, null, invalid, valid).");
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

    // --- 14. Multi-Upload Independence and Non-Mutating Export ---
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

        // Import on up-1 does not affect up-2
        uploads = handleImportLayout(uploads, "up-1", mockLayoutA);
        assert.ok(uploads["up-1"].importedLayout);
        assert.equal(uploads["up-2"].importedLayout, undefined);
        assert.equal(uploads["up-2"].configRevision, 1);
        assert.equal(uploads["up-2"].rois[0].roi_id, "dot-1");

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
        console.log("✓ Test 14 Passed: Multi-upload isolation and non-mutating export verified.");
    }

    // --- 15. Asynchronous Import Coordination: A/B Out-of-Order Completion ---
    {
        let uploads = { "up-1": createMockUpload("up-1") };
        const coordinator = new ImportCoordinator();

        let readerAAborted = false;
        let readerACallback = null;
        let readerBCallback = null;
        let pendingBCommit = null;

        const mockLayoutA = {
            format: "dispense-region-layout",
            version: 1,
            name: "Layout A (Slow)",
            source_image: { width: 800, height: 600 },
            rois: [{ roi_id: "site-a", x: 0.1, y: 0.1, width: 0.2, height: 0.2 }],
        };
        const mockLayoutB = {
            format: "dispense-region-layout",
            version: 1,
            name: "Layout B (Fast)",
            source_image: { width: 1200, height: 900 },
            rois: [{ roi_id: "site-b", x: 0.3, y: 0.3, width: 0.4, height: 0.4 }],
        };

        // 1. Technician selects File A
        const tokenA = startCoordinatedImport(
            coordinator,
            "up-1",
            uploads["up-1"].configRevision,
            (onSuccess) => {
                readerACallback = () => onSuccess(JSON.stringify(mockLayoutA));
                return () => { readerAAborted = true; };
            },
            {
                getCurrentUpload: () => uploads["up-1"],
                onStart: (token, expectedRevision) => {
                    uploads = beginRegionLayoutImport(uploads, "up-1", token, expectedRevision);
                },
                onCommit: () => {},
                onError: () => {},
                parseLayout: parseRegionLayout,
            }
        );

        assert.equal(tokenA, 1);
        assert.equal(coordinator.isTokenActive("up-1", tokenA), true);

        // 2. Before File A finishes reading, technician selects File B (newer request)
        const tokenB = startCoordinatedImport(
            coordinator,
            "up-1",
            uploads["up-1"].configRevision,
            (onSuccess) => {
                readerBCallback = () => onSuccess(JSON.stringify(mockLayoutB));
                return () => {};
            },
            {
                getCurrentUpload: () => uploads["up-1"],
                onStart: (token, expectedRevision) => {
                    uploads = beginRegionLayoutImport(uploads, "up-1", token, expectedRevision);
                },
                onCommit: (token, layout, expectedRevision, startedAt) => {
                    pendingBCommit = { token, layout, expectedRevision, startedAt };
                },
                onError: () => {},
                parseLayout: parseRegionLayout,
            }
        );

        assert.equal(tokenB, 2);
        assert.equal(readerAAborted, true, "Reader A must be aborted when superseded by Reader B");
        assert.equal(coordinator.isTokenActive("up-1", tokenA), false, "Token A is no longer active");
        assert.equal(coordinator.isTokenActive("up-1", tokenB), true, "Token B is active");

        // 3. Stale Reader A finishes late and invokes its callback
        readerACallback();
        // State must remain unmutated (still default dot-1, no Layout A)
        assert.equal(uploads["up-1"].importedLayout, undefined);
        assert.equal(uploads["up-1"].configRevision, 1);

        // 4. Reader B completes and invokes its callback
        readerBCallback();
        // Commit transition must be safe when React re-evaluates the updater
        // against the same prior state (development Strict Mode / concurrent render).
        const priorToCommit = uploads;
        assert.equal(pendingBCommit.token, tokenB);
        assert.deepEqual(priorToCommit["up-1"].activeLayoutImport, {
            token: tokenB,
            expectedRevision: priorToCommit["up-1"].configRevision,
        });
        const firstAttempt = coordinator.commitImport(
            priorToCommit,
            "up-1",
            pendingBCommit.token,
            pendingBCommit.layout,
            pendingBCommit.expectedRevision,
            pendingBCommit.startedAt
        );
        const replayedAttempt = coordinator.commitImport(
            priorToCommit,
            "up-1",
            pendingBCommit.token,
            pendingBCommit.layout,
            pendingBCommit.expectedRevision,
            pendingBCommit.startedAt
        );
        assert.equal(firstAttempt.committed, true, "First pure updater evaluation should be accepted");
        assert.equal(replayedAttempt.committed, true, "Replayed updater evaluation must remain accepted");
        assert.deepEqual(replayedAttempt.nextState, firstAttempt.nextState, "Replayed updater must produce the same state");
        assert.equal(coordinator.isTokenActive("up-1", tokenB), true, "Pure state calculation must not consume the token");
        const cancelledRequestState = clearRegionLayoutImport(priorToCommit, "up-1", tokenB);
        const staleAttempt = coordinator.commitImport(
            cancelledRequestState,
            "up-1",
            tokenB,
            pendingBCommit.layout,
            pendingBCommit.expectedRevision,
            pendingBCommit.startedAt
        );
        assert.equal(staleAttempt.committed, false, "State-ordered cancellation must reject an already queued late commit");
        uploads = firstAttempt.nextState;
        assert.equal(uploads["up-1"].activeLayoutImport, null, "Successful import consumes its snapshot request identity");

        // Finalize effects only after the committed state is observable.
        assert.equal(coordinator.finalizeCommittedImport(uploads["up-1"]), true);
        assert.equal(coordinator.isTokenActive("up-1", tokenB), false, "Effect finalization consumes token");

        // State must commit Layout B
        assert.ok(uploads["up-1"].importedLayout);
        assert.equal(uploads["up-1"].importedLayout.name, "Layout B (Fast)");
        assert.equal(uploads["up-1"].configRevision, 2);
        assert.equal(uploads["up-1"].rois[0].roi_id, "site-b");

        testsPassed++;
        console.log("✓ Test 15 Passed: A/B out-of-order completion coordination rejects superseded reads.");
    }

    // --- 16. Asynchronous Import Coordination: Edit During File Read ---
    {
        let uploads = { "up-1": createMockUpload("up-1") };
        const coordinator = new ImportCoordinator();

        let readerAborted = false;
        let readerCallback = null;

        const mockLayout = {
            format: "dispense-region-layout",
            version: 1,
            name: "Late Layout",
            source_image: { width: 800, height: 600 },
            rois: [{ roi_id: "late-site", x: 0.1, y: 0.1, width: 0.2, height: 0.2 }],
        };

        // Technician selects layout file
        const token = startCoordinatedImport(
            coordinator,
            "up-1",
            uploads["up-1"].configRevision,
            (onSuccess) => {
                readerCallback = () => onSuccess(JSON.stringify(mockLayout));
                return () => { readerAborted = true; };
            },
            {
                getCurrentUpload: () => uploads["up-1"],
                onStart: (token, expectedRevision) => {
                    uploads = beginRegionLayoutImport(uploads, "up-1", token, expectedRevision);
                },
                onCommit: (token, layout, expectedRevision, startedAt) => {
                    const res = coordinator.commitImport(uploads, "up-1", token, layout, expectedRevision, startedAt);
                    if (res.committed) {
                        uploads = res.nextState;
                    }
                },
                onError: () => {},
                parseLayout: parseRegionLayout,
            }
        );

        assert.equal(coordinator.isTokenActive("up-1", token), true);

        // While file is reading, technician modifies ROIs manually (bumps revision, cancels pending import)
        coordinator.cancelImport("up-1");
        uploads = handleReconfigure(uploads, "up-1", {
            rois: [{ roi_id: "manual-edit-site", x: 0.5, y: 0.5, width: 0.1, height: 0.1 }],
        });

        assert.equal(readerAborted, true, "Reader must be aborted on manual reconfiguration");
        assert.equal(uploads["up-1"].configRevision, 2);
        assert.equal(uploads["up-1"].rois[0].roi_id, "manual-edit-site");

        // Stale reader completes after edit
        readerCallback();

        // Stale layout must NOT overwrite manual edits
        assert.equal(uploads["up-1"].importedLayout, null);
        assert.equal(uploads["up-1"].configRevision, 2);
        assert.equal(uploads["up-1"].rois[0].roi_id, "manual-edit-site");

        testsPassed++;
        console.log("✓ Test 16 Passed: Manual edits during file read abort reader and reject late layout commit.");
    }

    // --- 17. Asynchronous Import Coordination: Abandonment and Deletion During Read ---
    {
        let uploads = {
            "up-1": createMockUpload("up-1"),
            "up-2": createMockUpload("up-2"),
        };
        const coordinator = new ImportCoordinator();

        let reader1Callback = null;
        let reader2Callback = null;

        const mockLayout = {
            format: "dispense-region-layout",
            version: 1,
            name: "Test Layout",
            source_image: { width: 800, height: 600 },
            rois: [{ roi_id: "test-site", x: 0.2, y: 0.2, width: 0.3, height: 0.3 }],
        };

        // Case A: Read on up-1, user abandons layout
        startCoordinatedImport(
            coordinator,
            "up-1",
            uploads["up-1"].configRevision,
            (onSuccess) => {
                reader1Callback = () => onSuccess(JSON.stringify(mockLayout));
                return () => {};
            },
            {
                getCurrentUpload: () => uploads["up-1"],
                onStart: (token, expectedRevision) => {
                    uploads = beginRegionLayoutImport(uploads, "up-1", token, expectedRevision);
                },
                onCommit: (token, layout, expectedRevision, startedAt) => {
                    const res = coordinator.commitImport(uploads, "up-1", token, layout, expectedRevision, startedAt);
                    if (res.committed) {
                        uploads = res.nextState;
                    }
                },
                onError: () => {},
                parseLayout: parseRegionLayout,
            }
        );

        coordinator.cancelImport("up-1");
        uploads = handleAbandonLayout(uploads, "up-1");
        assert.equal(uploads["up-1"].importedLayout, null);

        reader1Callback();
        assert.equal(uploads["up-1"].importedLayout, null, "Late read cannot restore abandoned layout");

        // Case B: Read on up-2, user deletes up-2
        startCoordinatedImport(
            coordinator,
            "up-2",
            uploads["up-2"].configRevision,
            (onSuccess) => {
                reader2Callback = () => onSuccess(JSON.stringify(mockLayout));
                return () => {};
            },
            {
                getCurrentUpload: () => uploads["up-2"],
                onStart: (token, expectedRevision) => {
                    uploads = beginRegionLayoutImport(uploads, "up-2", token, expectedRevision);
                },
                onCommit: (token, layout, expectedRevision, startedAt) => {
                    const res = coordinator.commitImport(uploads, "up-2", token, layout, expectedRevision, startedAt);
                    if (res.committed) {
                        uploads = res.nextState;
                    }
                },
                onError: () => {},
                parseLayout: parseRegionLayout,
            }
        );

        coordinator.cancelImport("up-2");
        uploads = handleRemove(uploads, "up-2");
        assert.equal(uploads["up-2"], undefined);

        reader2Callback();
        assert.equal(uploads["up-2"], undefined, "Late read cannot resurrect deleted upload");

        testsPassed++;
        console.log("✓ Test 17 Passed: Abandonment and deletion during file read safely prevent state mutation.");
    }

    // --- 18. Cross-View Arbitration (Inline vs Studio) and Teardown Cleanup ---
    {
        let uploads = { "up-1": createMockUpload("up-1") };
        const coordinator = new ImportCoordinator();

        let inlineCallback = null;
        let studioCallback = null;

        const inlineLayout = {
            format: "dispense-region-layout",
            version: 1,
            name: "Inline Layout",
            source_image: { width: 800, height: 600 },
            rois: [{ roi_id: "inline-site", x: 0.1, y: 0.1, width: 0.2, height: 0.2 }],
        };
        const studioLayout = {
            format: "dispense-region-layout",
            version: 1,
            name: "Studio Layout",
            source_image: { width: 1024, height: 768 },
            rois: [{ roi_id: "studio-site", x: 0.4, y: 0.4, width: 0.3, height: 0.3 }],
        };

        // 1. Inline triggers import
        startCoordinatedImport(
            coordinator,
            "up-1",
            uploads["up-1"].configRevision,
            (onSuccess) => {
                inlineCallback = () => onSuccess(JSON.stringify(inlineLayout));
                return () => {};
            },
            {
                getCurrentUpload: () => uploads["up-1"],
                onStart: (token, expectedRevision) => {
                    uploads = beginRegionLayoutImport(uploads, "up-1", token, expectedRevision);
                },
                onCommit: (token, layout, expectedRevision, startedAt) => {
                    const res = coordinator.commitImport(uploads, "up-1", token, layout, expectedRevision, startedAt);
                    if (res.committed) uploads = res.nextState;
                },
                onError: () => {},
                parseLayout: parseRegionLayout,
            }
        );

        // 2. Studio triggers import on the same upload (supersedes inline)
        startCoordinatedImport(
            coordinator,
            "up-1",
            uploads["up-1"].configRevision,
            (onSuccess) => {
                studioCallback = () => onSuccess(JSON.stringify(studioLayout));
                return () => {};
            },
            {
                getCurrentUpload: () => uploads["up-1"],
                onStart: (token, expectedRevision) => {
                    uploads = beginRegionLayoutImport(uploads, "up-1", token, expectedRevision);
                },
                onCommit: (token, layout, expectedRevision, startedAt) => {
                    const res = coordinator.commitImport(uploads, "up-1", token, layout, expectedRevision, startedAt);
                    if (res.committed) uploads = res.nextState;
                },
                onError: () => {},
                parseLayout: parseRegionLayout,
            }
        );

        // Inline finishes late -> discarded
        inlineCallback();
        assert.equal(uploads["up-1"].importedLayout, undefined);

        // Studio finishes -> committed
        studioCallback();
        assert.equal(uploads["up-1"].importedLayout.name, "Studio Layout");

        // 3. Teardown / Unmount simulation
        let teardownCallback = null;
        let teardownAborted = false;
        startCoordinatedImport(
            coordinator,
            "up-1",
            uploads["up-1"].configRevision,
            (onSuccess) => {
                teardownCallback = () => onSuccess(JSON.stringify(inlineLayout));
                return () => { teardownAborted = true; };
            },
            {
                getCurrentUpload: () => uploads["up-1"],
                onStart: (token, expectedRevision) => {
                    uploads = beginRegionLayoutImport(uploads, "up-1", token, expectedRevision);
                },
                onCommit: (token, layout, expectedRevision, startedAt) => {
                    const res = coordinator.commitImport(uploads, "up-1", token, layout, expectedRevision, startedAt);
                    if (res.committed) uploads = res.nextState;
                },
                onError: () => {},
                parseLayout: parseRegionLayout,
            }
        );

        coordinator.cancelAll();
        assert.equal(teardownAborted, true, "cancelAll must abort active readers on unmount");
        teardownCallback();
        assert.equal(uploads["up-1"].importedLayout.name, "Studio Layout", "Teardown prevents late commit");

        testsPassed++;
        console.log("✓ Test 18 Passed: Cross-view (Inline vs Studio) arbitration and teardown cleanup verified.");
    }

    // --- 19. Obsolete Error Callback Suppression & Invalid Input Safety ---
    {
        let uploads = { "up-1": createMockUpload("up-1") };
        const coordinator = new ImportCoordinator();

        let errorCallback = null;
        let reportedError = null;

        // Start import
        startCoordinatedImport(
            coordinator,
            "up-1",
            uploads["up-1"].configRevision,
            (_onSuccess, onError) => {
                errorCallback = () => onError(new Error("Disk read error"));
                return () => {};
            },
            {
                getCurrentUpload: () => uploads["up-1"],
                onStart: (token, expectedRevision) => {
                    uploads = beginRegionLayoutImport(uploads, "up-1", token, expectedRevision);
                },
                onCommit: () => {},
                onError: (err, token) => {
                    uploads = clearRegionLayoutImport(uploads, "up-1", token);
                    reportedError = err;
                },
                parseLayout: parseRegionLayout,
            }
        );

        // User edits upload before disk error fires
        coordinator.cancelImport("up-1");
        errorCallback();

        // Stale error must be suppressed
        assert.equal(reportedError, null, "Stale error callback must not be reported to UI");

        // Valid session with invalid schema content
        let invalidSchemaError = null;
        startCoordinatedImport(
            coordinator,
            "up-1",
            uploads["up-1"].configRevision,
            () => {
                return () => {};
            },
            {
                getCurrentUpload: () => uploads["up-1"],
                onStart: (token, expectedRevision) => {
                    uploads = beginRegionLayoutImport(uploads, "up-1", token, expectedRevision);
                },
                onCommit: () => {},
                onError: (err, token) => {
                    uploads = clearRegionLayoutImport(uploads, "up-1", token);
                    invalidSchemaError = err;
                },
                parseLayout: parseRegionLayout,
            }
        );

        // Test parser failure within active session
        startCoordinatedImport(
            coordinator,
            "up-1",
            uploads["up-1"].configRevision,
            (onSuccess) => {
                onSuccess("{ invalid json content");
                return () => {};
            },
            {
                getCurrentUpload: () => uploads["up-1"],
                onStart: (token, expectedRevision) => {
                    uploads = beginRegionLayoutImport(uploads, "up-1", token, expectedRevision);
                },
                onCommit: () => {},
                onError: (err, token) => {
                    uploads = clearRegionLayoutImport(uploads, "up-1", token);
                    invalidSchemaError = err;
                },
                parseLayout: parseRegionLayout,
            }
        );
        assert.ok(invalidSchemaError, "Invalid JSON must report error through onError handler");
        assert.equal(uploads["up-1"].importedLayout, undefined, "Invalid JSON must not mutate upload state");

        testsPassed++;
        console.log("✓ Test 19 Passed: Obsolete error callback suppression and invalid input safety verified.");
    }

    // --- 20. Delayed Valid Import A Followed by Oversized File B Rejection ---
    {
        let uploads = { "up-1": createMockUpload("up-1") };
        // Simulate existing analyzed state with results
        uploads["up-1"].status = "analyzed";
        uploads["up-1"].result = { status: "CALIBRATED", observations: [{ id: "obs-1" }] };
        const initialRevision = uploads["up-1"].configRevision;

        const coordinator = new ImportCoordinator();
        let reportedError = null;
        let readerAAborted = false;
        let readerACallback = null;

        const mockLayoutA = {
            format: "dispense-region-layout",
            version: 1,
            name: "Layout A",
            source_image: { width: 800, height: 600 },
            rois: [{ roi_id: "site-a", x: 0.1, y: 0.1, width: 0.2, height: 0.2 }],
        };

        // Helper representing the parent component's handleSelectLayoutFile logic
        const simulateParentSelectFile = (uploadId, file, customReadFn) => {
            // Must invalidate prior session BEFORE any validation!
            const isWithinSizeLimit = beginRegionLayoutFileSelection(coordinator, uploadId, file.size, MAX_LAYOUT_FILE_BYTES);
            uploads = clearRegionLayoutImport(uploads, uploadId);
            if (!isWithinSizeLimit) {
                reportedError = `File "${file.name}" rejected: payload (${(file.size / 1024).toFixed(1)} KiB) exceeds maximum 256 KiB limit.`;
                return;
            }

            const current = uploads[uploadId];
            if (!current) return;
            reportedError = null;

            startCoordinatedImport(
                coordinator,
                uploadId,
                current.configRevision,
                customReadFn,
                {
                    getCurrentUpload: () => uploads[uploadId],
                    onStart: (token, expectedRevision) => {
                        uploads = beginRegionLayoutImport(uploads, uploadId, token, expectedRevision);
                    },
                    onCommit: (token, layout, expectedRevision, startedAt) => {
                        const res = coordinator.commitImport(uploads, uploadId, token, layout, expectedRevision, startedAt);
                        if (res.committed) {
                            uploads = res.nextState;
                        }
                    },
                    onError: (err, token) => {
                        uploads = clearRegionLayoutImport(uploads, uploadId, token);
                        reportedError = err;
                    },
                    parseLayout: parseRegionLayout,
                }
            );
        };

        // 1. Technician selects valid file A, which starts a delayed read
        const fileA = { name: "valid_layout_a.json", size: 1024 };
        simulateParentSelectFile("up-1", fileA, (onSuccess) => {
            readerACallback = () => onSuccess(JSON.stringify(mockLayoutA));
            return () => { readerAAborted = true; };
        });

        assert.equal(coordinator.isTokenActive("up-1", 1), true, "Import A session is active");
        assert.equal(readerAAborted, false);
        assert.equal(reportedError, null);

        // 2. While read A is pending, technician selects oversized file B (300 KiB > 256 KiB)
        const fileB = { name: "oversized_layout_b.json", size: 300 * 1024 };
        simulateParentSelectFile("up-1", fileB, () => {
            throw new Error("Reader B should never be invoked for rejected file");
        });

        // Verifications on file B selection:
        // - Import A session must be cancelled immediately
        assert.equal(readerAAborted, true, "Reader A must be aborted upon selecting File B");
        assert.equal(coordinator.isTokenActive("up-1", 1), false, "Token A must be invalidated");
        // - Error must be recorded for file B rejection
        assert.ok(reportedError && reportedError.includes("exceeds maximum 256 KiB limit"));
        // - Upload state and existing results must be completely preserved
        assert.equal(uploads["up-1"].status, "analyzed");
        assert.ok(uploads["up-1"].result);
        assert.equal(uploads["up-1"].configRevision, initialRevision);
        assert.equal(uploads["up-1"].importedLayout, undefined);

        // 3. Delayed read A completes late after File B was rejected
        readerACallback();

        // Late read A MUST NOT commit or mutate state
        assert.equal(uploads["up-1"].status, "analyzed", "Late read A must not overwrite status");
        assert.ok(uploads["up-1"].result, "Late read A must not wipe prior analysis results");
        assert.equal(uploads["up-1"].configRevision, initialRevision, "Late read A must not bump revision");
        assert.equal(uploads["up-1"].importedLayout, undefined, "Late read A must not apply layout");

        testsPassed++;
        console.log("✓ Test 20 Passed: Delayed valid import A followed by oversized B rejection preserves state and cancels A.");
    }

    // --- 21. Synchronous Read Completion Before React Publishes the Start Snapshot ---
    {
        let uploads = { "up-1": createMockUpload("up-1") };
        const initialRevision = uploads["up-1"].configRevision;
        const coordinator = new ImportCoordinator();
        const queuedUpdates = [];
        let importError = null;
        const layout = {
            format: "dispense-region-layout",
            version: 1,
            name: "Fast Read Layout",
            source_image: { width: 800, height: 600 },
            rois: [{ roi_id: "fast-site", x: 0.1, y: 0.1, width: 0.2, height: 0.2 }],
        };

        startCoordinatedImport(
            coordinator,
            "up-1",
            uploads["up-1"].configRevision,
            (onSuccess) => {
                // Simulate a read finishing before React has rendered onStart's queued update.
                onSuccess(JSON.stringify(layout));
                return () => {};
            },
            {
                getCurrentUpload: () => uploads["up-1"],
                onStart: (token, expectedRevision) => {
                    queuedUpdates.push((prev) => beginRegionLayoutImport(prev, "up-1", token, expectedRevision));
                },
                onCommit: (token, parsedLayout, expectedRevision, startedAt) => {
                    queuedUpdates.push((prev) => coordinator.commitImport(
                        prev, "up-1", token, parsedLayout, expectedRevision, startedAt
                    ).nextState);
                },
                onError: (error) => { importError = error; },
                parseLayout: parseRegionLayout,
            }
        );

        assert.equal(importError, null, "A synchronous valid read must not be treated as stale");
        assert.equal(queuedUpdates.length, 2, "Start and commit transitions should both be queued");
        const stateAfterStart = queuedUpdates[0](uploads);
        const stateAfterCommit = queuedUpdates[1](stateAfterStart);
        const replayedCommit = queuedUpdates[1](stateAfterStart);
        assert.deepEqual(replayedCommit, stateAfterCommit, "React may replay the commit updater deterministically");
        uploads = stateAfterCommit;
        assert.equal(uploads["up-1"].importedLayout.name, "Fast Read Layout");
        assert.equal(uploads["up-1"].configRevision, initialRevision + 1);

        testsPassed++;
        console.log("✓ Test 21 Passed: Synchronous file-read completion queues and replays the import transition safely.");
    }

    console.log(`\nAll ${testsPassed} regression tests passed successfully.`);
}

runTests();
