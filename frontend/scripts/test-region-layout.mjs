/**
 * Deterministic regression suite for Portable Region Layout Contract & Validation (DLK-M3-046).
 *
 * Verifies:
 * 1. Valid minimal layout parsing and validation.
 * 2. Region count boundary enforcement (0, 1, 100, 101 regions).
 * 3. File size boundary enforcement (exact 256 KiB vs oversized 256 KiB + 1 byte).
 * 4. Schema strictness and unknown key rejection at root, source_image, and ROI levels.
 * 5. String safety: name and roi_id whitespace trimming, leading/trailing space rejection, control chars, max length.
 * 6. Numeric and coordinate boundaries: positive safe integers for dimensions, finite numbers, [0, 1] bounds, tolerance.
 * 7. Duplicate ROI ID rejection.
 * 8. Round-trip fidelity and allowlisted serialization without extraneous field leakage.
 * 9. JSON syntax error handling.
 */

import assert from "node:assert/strict";
import {
    REGION_LAYOUT_FORMAT,
    REGION_LAYOUT_VERSION,
    MAX_LAYOUT_FILE_BYTES,
    MAX_LAYOUT_ROIS,
    validateRegionLayout,
    parseRegionLayout,
    createRegionLayout,
    serializeRegionLayout,
} from "../lib/region-layout.ts";

function createValidLayoutObject(roiCount = 1) {
    const rois = [];
    for (let i = 0; i < roiCount; i++) {
        rois.push({
            roi_id: `dot-${i + 1}`,
            x: 0.1,
            y: 0.1,
            width: 0.2,
            height: 0.2,
        });
    }
    return {
        format: REGION_LAYOUT_FORMAT,
        version: REGION_LAYOUT_VERSION,
        name: "Test Layout",
        source_image: {
            width: 800,
            height: 600,
        },
        rois,
    };
}

function runTests() {
    let testsPassed = 0;

    // --- 1. Valid Minimal Layout ---
    {
        const validObj = createValidLayoutObject(1);
        const result = validateRegionLayout(validObj);
        assert.equal(result.ok, true);
        if (result.ok) {
            assert.equal(result.layout.name, "Test Layout");
            assert.equal(result.layout.rois.length, 1);
            assert.equal(result.layout.source_image.width, 800);
            assert.equal(result.layout.source_image.height, 600);
        }
        testsPassed++;
        console.log("✓ Test 1 Passed: Valid minimal layout validates successfully.");
    }

    // --- 2. Region Count Boundaries (0, 1, 100, 101) ---
    {
        // 0 ROIs -> rejected
        const zeroObj = createValidLayoutObject(0);
        const resZero = validateRegionLayout(zeroObj);
        assert.equal(resZero.ok, false);
        assert.match(resZero.error, /at least 1 region/i);

        // 100 ROIs -> accepted (at MAX_LAYOUT_ROIS)
        assert.equal(MAX_LAYOUT_ROIS, 100);
        const hundredObj = createValidLayoutObject(MAX_LAYOUT_ROIS);
        const resHundred = validateRegionLayout(hundredObj);
        assert.equal(resHundred.ok, true);

        // 101 ROIs -> rejected (MAX_LAYOUT_ROIS + 1)
        const hundredOneObj = createValidLayoutObject(MAX_LAYOUT_ROIS + 1);
        const resHundredOne = validateRegionLayout(hundredOneObj);
        assert.equal(resHundredOne.ok, false);
        assert.match(resHundredOne.error, /exceeds maximum of 100 regions/i);

        testsPassed++;
        console.log("✓ Test 2 Passed: Region count boundaries (0, 1, 100, 101) strictly enforced.");
    }

    // --- 3. File Payload Size Boundaries (Exact 256 KiB vs Oversized) ---
    {
        // Construct string with exact 256 KiB (262,144 bytes)
        const base = createValidLayoutObject(1);
        const baseJson = JSON.stringify(base);
        // We pad whitespace inside JSON string to reach exact MAX_LAYOUT_FILE_BYTES
        const currentBytes = new TextEncoder().encode(baseJson).length;
        const paddingNeeded = MAX_LAYOUT_FILE_BYTES - currentBytes;
        assert.ok(paddingNeeded > 0, "Base JSON must be smaller than 256 KiB");

        const exact256kStr = baseJson + " ".repeat(paddingNeeded);
        assert.equal(new TextEncoder().encode(exact256kStr).length, MAX_LAYOUT_FILE_BYTES);

        const resExact = parseRegionLayout(exact256kStr);
        assert.equal(resExact.ok, true, "Exact 256 KiB file must be accepted");

        // 256 KiB + 1 byte -> rejected before parsing
        const oversizedStr = exact256kStr + " ";
        assert.equal(new TextEncoder().encode(oversizedStr).length, MAX_LAYOUT_FILE_BYTES + 1);

        const resOversized = parseRegionLayout(oversizedStr);
        assert.equal(resOversized.ok, false);
        assert.match(resOversized.error, /exceeds maximum allowed size of 256 KiB/i);

        testsPassed++;
        console.log("✓ Test 3 Passed: Exact 256 KiB and oversized payload boundaries enforced.");
    }

    // --- 4. Schema Strictness and Unknown Key Rejection ---
    {
        // Root unknown key
        const rootUnknown = { ...createValidLayoutObject(1), unexpected_field: true };
        const resRootUnknown = validateRegionLayout(rootUnknown);
        assert.equal(resRootUnknown.ok, false);
        assert.match(resRootUnknown.error, /Unrecognized root property 'unexpected_field'/);

        // Root missing key
        const missingName = createValidLayoutObject(1);
        delete missingName.name;
        const resMissingName = validateRegionLayout(missingName);
        assert.equal(resMissingName.ok, false);
        assert.match(resMissingName.error, /Missing required root property 'name'/);

        // Invalid format
        const wrongFormat = { ...createValidLayoutObject(1), format: "other-format" };
        const resWrongFormat = validateRegionLayout(wrongFormat);
        assert.equal(resWrongFormat.ok, false);
        assert.match(resWrongFormat.error, /Invalid layout format/);

        // Unsupported version (e.g. 2 or string "1")
        const wrongVersion = { ...createValidLayoutObject(1), version: 2 };
        const resWrongVersion = validateRegionLayout(wrongVersion);
        assert.equal(resWrongVersion.ok, false);
        assert.match(resWrongVersion.error, /Unsupported layout version/);

        const stringVersion = { ...createValidLayoutObject(1), version: "1" };
        const resStringVersion = validateRegionLayout(stringVersion);
        assert.equal(resStringVersion.ok, false);
        assert.match(resStringVersion.error, /Unsupported layout version/);

        // source_image unknown key
        const srcUnknown = {
            ...createValidLayoutObject(1),
            source_image: { width: 800, height: 600, extra: "not-allowed" },
        };
        const resSrcUnknown = validateRegionLayout(srcUnknown);
        assert.equal(resSrcUnknown.ok, false);
        assert.match(resSrcUnknown.error, /must contain only 'width' and 'height'/);

        // ROI unknown key
        const roiUnknown = createValidLayoutObject(1);
        roiUnknown.rois[0].confidence = 0.99;
        const resRoiUnknown = validateRegionLayout(roiUnknown);
        assert.equal(resRoiUnknown.ok, false);
        assert.match(resRoiUnknown.error, /invalid or unrecognized properties/);

        testsPassed++;
        console.log("✓ Test 4 Passed: Schema strictness and unknown key rejection at all levels.");
    }

    // --- 5. String Safety: Name and roi_id Rules ---
    {
        // Blank or whitespace name
        const blankName = { ...createValidLayoutObject(1), name: "   " };
        const resBlankName = validateRegionLayout(blankName);
        assert.equal(resBlankName.ok, false);
        assert.match(resBlankName.error, /cannot be empty or blank/);

        // Name exceeding 100 characters
        const longName = { ...createValidLayoutObject(1), name: "a".repeat(101) };
        const resLongName = validateRegionLayout(longName);
        assert.equal(resLongName.ok, false);
        assert.match(resLongName.error, /exceeds maximum length of 100/);

        // Name with control characters
        const controlCharName = { ...createValidLayoutObject(1), name: "Test\nLayout" };
        const resControlName = validateRegionLayout(controlCharName);
        assert.equal(resControlName.ok, false);
        assert.match(resControlName.error, /disallowed control characters/);

        // roi_id with leading/trailing whitespace
        const whitespaceRoiId = createValidLayoutObject(1);
        whitespaceRoiId.rois[0].roi_id = " dot-1 ";
        const resWhitespaceRoi = validateRegionLayout(whitespaceRoiId);
        assert.equal(resWhitespaceRoi.ok, false);
        assert.match(resWhitespaceRoi.error, /has leading or trailing whitespace/);

        // roi_id exceeding 100 characters
        const longRoiId = createValidLayoutObject(1);
        longRoiId.rois[0].roi_id = "r".repeat(101);
        const resLongRoi = validateRegionLayout(longRoiId);
        assert.equal(resLongRoi.ok, false);
        assert.match(resLongRoi.error, /exceeds maximum length of 100/);

        // roi_id with control characters
        const ctrlRoiId = createValidLayoutObject(1);
        ctrlRoiId.rois[0].roi_id = "dot\x001";
        const resCtrlRoi = validateRegionLayout(ctrlRoiId);
        assert.equal(resCtrlRoi.ok, false);
        assert.match(resCtrlRoi.error, /disallowed control characters/);

        testsPassed++;
        console.log("✓ Test 5 Passed: String constraints (whitespace, length, control chars) verified.");
    }

    // --- 6. Numeric and Coordinate Validation ---
    {
        // Negative / zero / float dimensions
        const zeroWidth = {
            ...createValidLayoutObject(1),
            source_image: { width: 0, height: 600 },
        };
        assert.equal(validateRegionLayout(zeroWidth).ok, false);

        const floatHeight = {
            ...createValidLayoutObject(1),
            source_image: { width: 800, height: 599.5 },
        };
        assert.equal(validateRegionLayout(floatHeight).ok, false);

        // Nonfinite coordinates
        const nanCoord = createValidLayoutObject(1);
        nanCoord.rois[0].x = NaN;
        assert.equal(validateRegionLayout(nanCoord).ok, false);

        const infCoord = createValidLayoutObject(1);
        infCoord.rois[0].width = Infinity;
        assert.equal(validateRegionLayout(infCoord).ok, false);

        // Out of [0, 1] bounds
        const outOfBoundsX = createValidLayoutObject(1);
        outOfBoundsX.rois[0].x = -0.01;
        assert.equal(validateRegionLayout(outOfBoundsX).ok, false);

        const zeroWidthRoi = createValidLayoutObject(1);
        zeroWidthRoi.rois[0].width = 0;
        assert.equal(validateRegionLayout(zeroWidthRoi).ok, false);

        // Extent boundary check (x + width > 1.00001)
        const extentExceeded = createValidLayoutObject(1);
        extentExceeded.rois[0].x = 0.9;
        extentExceeded.rois[0].width = 0.10002;
        assert.equal(validateRegionLayout(extentExceeded).ok, false);

        const extentWithinTolerance = createValidLayoutObject(1);
        extentWithinTolerance.rois[0].x = 0.9;
        extentWithinTolerance.rois[0].width = 0.100005;
        assert.equal(validateRegionLayout(extentWithinTolerance).ok, true);

        testsPassed++;
        console.log("✓ Test 6 Passed: Numeric constraints and coordinate bounds verified.");
    }

    // --- 7. Duplicate ROI IDs ---
    {
        const dupObj = createValidLayoutObject(2);
        dupObj.rois[0].roi_id = "duplicate-id";
        dupObj.rois[1].roi_id = "duplicate-id";

        const resDup = validateRegionLayout(dupObj);
        assert.equal(resDup.ok, false);
        assert.match(resDup.error, /Duplicate ROI ID 'duplicate-id'/);

        testsPassed++;
        console.log("✓ Test 7 Passed: Duplicate ROI IDs detected and rejected.");
    }

    // --- 8. Round-trip Fidelity and Allowlisted Serialization ---
    {
        const rois = [
            { roi_id: "site-alpha", x: 0.12345, y: 0.23456, width: 0.34567, height: 0.45678 },
            { roi_id: "site-beta", x: 0.5, y: 0.6, width: 0.25, height: 0.35 },
        ];
        const createdRes = createRegionLayout(
            " Two-site Calibration Layout ",
            { width: 1920, height: 1080 },
            rois
        );
        assert.equal(createdRes.ok, true);
        if (!createdRes.ok) return;

        const serialized = serializeRegionLayout(createdRes.layout);
        const parsedRes = parseRegionLayout(serialized);
        assert.equal(parsedRes.ok, true);
        if (!parsedRes.ok) return;

        // Verify name was trimmed
        assert.equal(parsedRes.layout.name, "Two-site Calibration Layout");
        // Verify dimensions preserved exactly
        assert.equal(parsedRes.layout.source_image.width, 1920);
        assert.equal(parsedRes.layout.source_image.height, 1080);
        // Verify ROI order, IDs and numbers preserved exactly
        assert.equal(parsedRes.layout.rois.length, 2);
        assert.equal(parsedRes.layout.rois[0].roi_id, "site-alpha");
        assert.equal(parsedRes.layout.rois[0].x, 0.12345);
        assert.equal(parsedRes.layout.rois[0].y, 0.23456);
        assert.equal(parsedRes.layout.rois[0].width, 0.34567);
        assert.equal(parsedRes.layout.rois[0].height, 0.45678);

        assert.equal(parsedRes.layout.rois[1].roi_id, "site-beta");
        assert.equal(parsedRes.layout.rois[1].x, 0.5);
        assert.equal(parsedRes.layout.rois[1].y, 0.6);
        assert.equal(parsedRes.layout.rois[1].width, 0.25);
        assert.equal(parsedRes.layout.rois[1].height, 0.35);

        // Verify allowlisted serialization does not output forbidden fields
        const rawJsonObj = JSON.parse(serialized);
        const serializedKeys = Object.keys(rawJsonObj).sort();
        assert.deepEqual(serializedKeys, ["format", "name", "rois", "source_image", "version"]);

        testsPassed++;
        console.log("✓ Test 8 Passed: Round-trip fidelity and exact allowlisted serialization verified.");
    }

    // --- 9. JSON Syntax Error Handling ---
    {
        const badSyntax = "{ invalid json content ...";
        const resBad = parseRegionLayout(badSyntax);
        assert.equal(resBad.ok, false);
        assert.match(resBad.error, /invalid JSON syntax/i);

        testsPassed++;
        console.log("✓ Test 9 Passed: Invalid JSON syntax fails cleanly with safe error message.");
    }

    console.log(`\nAll ${testsPassed} region layout contract tests passed successfully.`);
}

runTests();
