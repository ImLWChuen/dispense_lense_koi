/**
 * Deterministic regression suite for Reports view state transitions and truthful failure handling (DLK-M3-028 / R11).
 *
 * Verifies:
 * 1. Initial loading state: shows dedicated loader, no error, no stale banner, no empty state.
 * 2. Initial load failure: shows dedicated error card with retry button; never renders table, empty banner, or stale banner.
 * 3. Initial load success: renders reports table, clears loading/error.
 * 4. Refresh in-flight: maintains existing data view while background loading flag is set.
 * 5. Refresh failure (R4 & R11): PRESERVES previously loaded reports; renders stale warning banner; does NOT wipe data to dedicated error.
 * 6. Refresh recovery: successfully updating after a failure clears error and removes stale banner.
 * 7. Truthful empty database: only renders "No reports found" when request succeeded and database actually returned 0 cases.
 * 8. Case response mapping: cleanly derives report title, formatted dates, and resolved status.
 */

import assert from "node:assert/strict";
import {
    createInitialReportsState,
    startReportsLoading,
    reportsLoadSuccess,
    reportsLoadFailure,
    deriveReportsView,
    mapCasesToReports,
} from "../lib/reports-state.ts";

const mockReports = [
    {
        id: "case-001",
        displayId: "RPT-CASE001",
        caseRef: "DSP-CASE001",
        title: "Bridging Defect",
        date: "Sep 20, 2026",
        type: "Diagnostic Report",
        status: "Complete",
        isResolved: true,
    },
    {
        id: "case-002",
        displayId: "RPT-CASE002",
        caseRef: "DSP-CASE002",
        title: "Tailing Defect",
        date: "Sep 19, 2026",
        type: "Diagnostic Report",
        status: "UNRESOLVED",
        isResolved: false,
    },
];

function runTests() {
    let testsPassed = 0;

    // --- 1. Initial Loading State ---
    {
        const state = createInitialReportsState();
        const view = deriveReportsView(state);

        assert.equal(state.isLoading, true);
        assert.equal(state.error, null);
        assert.equal(state.reports.length, 0);

        assert.equal(view.showInitialLoading, true);
        assert.equal(view.showDedicatedError, false);
        assert.equal(view.showStaleBanner, false);
        assert.equal(view.showTable, false);
        assert.equal(view.showEmpty, false);

        testsPassed++;
        console.log("✓ Test 1 Passed: Initial state shows dedicated loading view exclusively.");
    }

    // --- 2. Initial Load Failure ---
    {
        const state0 = createInitialReportsState();
        const stateFail = reportsLoadFailure(state0, "Network connection error");
        const view = deriveReportsView(stateFail);

        assert.equal(stateFail.isLoading, false);
        assert.equal(stateFail.error, "Network connection error");
        assert.equal(stateFail.reports.length, 0);

        assert.equal(view.showInitialLoading, false);
        assert.equal(view.showDedicatedError, true);
        assert.equal(view.showStaleBanner, false);
        assert.equal(view.showTable, false);
        assert.equal(view.showEmpty, false);

        testsPassed++;
        console.log("✓ Test 2 Passed: Initial load failure renders dedicated error card and never shows empty or stale state.");
    }

    // --- 3. Initial Load Success ---
    {
        const state0 = createInitialReportsState();
        const stateSuccess = reportsLoadSuccess(state0, mockReports);
        const view = deriveReportsView(stateSuccess);

        assert.equal(stateSuccess.isLoading, false);
        assert.equal(stateSuccess.error, null);
        assert.equal(stateSuccess.reports.length, 2);

        assert.equal(view.showInitialLoading, false);
        assert.equal(view.showDedicatedError, false);
        assert.equal(view.showStaleBanner, false);
        assert.equal(view.showTable, true);
        assert.equal(view.showEmpty, false);

        testsPassed++;
        console.log("✓ Test 3 Passed: Initial load success populates reports and renders table.");
    }

    // --- 4. Refresh In-Flight ---
    {
        const stateSuccess = reportsLoadSuccess(createInitialReportsState(), mockReports);
        const stateRefreshing = startReportsLoading(stateSuccess);
        const view = deriveReportsView(stateRefreshing);

        assert.equal(stateRefreshing.isLoading, true);
        assert.equal(stateRefreshing.error, null);
        assert.equal(stateRefreshing.reports.length, 2);

        assert.equal(view.showInitialLoading, false);
        assert.equal(view.showDedicatedError, false);
        assert.equal(view.showStaleBanner, false);
        assert.equal(view.showTable, true);

        testsPassed++;
        console.log("✓ Test 4 Passed: In-flight refresh preserves previous reports view.");
    }

    // --- 5. Refresh Failure Preserves Previous Data with Stale Banner (R4 & R11) ---
    {
        const stateSuccess = reportsLoadSuccess(createInitialReportsState(), mockReports);
        const stateRefreshing = startReportsLoading(stateSuccess);
        const stateRefreshFailed = reportsLoadFailure(stateRefreshing, "503 Service Unavailable");
        const view = deriveReportsView(stateRefreshFailed);

        assert.equal(stateRefreshFailed.isLoading, false);
        assert.equal(stateRefreshFailed.error, "503 Service Unavailable");
        // CRUCIAL: Reports must NOT be wiped to []!
        assert.equal(stateRefreshFailed.reports.length, 2);
        assert.deepEqual(stateRefreshFailed.reports, mockReports);

        // View flags:
        assert.equal(view.showDedicatedError, false, "Must NOT flip to dedicated error when stale reports exist");
        assert.equal(view.showStaleBanner, true, "Must render stale warning banner");
        assert.equal(view.showTable, true, "Must keep previously loaded reports table visible");
        assert.equal(view.showEmpty, false);

        testsPassed++;
        console.log("✓ Test 5 Passed: Refresh failure preserves previously loaded reports and renders stale warning banner.");
    }

    // --- 6. Refresh Recovery ---
    {
        const stateSuccess = reportsLoadSuccess(createInitialReportsState(), mockReports);
        const stateRefreshFailed = reportsLoadFailure(stateSuccess, "503 Service Unavailable");
        const updatedReports = [
            ...mockReports,
            {
                id: "case-003",
                displayId: "RPT-CASE003",
                caseRef: "DSP-CASE003",
                title: "Satellite Defect",
                date: "Sep 20, 2026",
                type: "Diagnostic Report",
                status: "Complete",
                isResolved: true,
            },
        ];

        const stateRecovered = reportsLoadSuccess(stateRefreshFailed, updatedReports);
        const view = deriveReportsView(stateRecovered);

        assert.equal(stateRecovered.isLoading, false);
        assert.equal(stateRecovered.error, null);
        assert.equal(stateRecovered.reports.length, 3);

        assert.equal(view.showDedicatedError, false);
        assert.equal(view.showStaleBanner, false);
        assert.equal(view.showTable, true);

        testsPassed++;
        console.log("✓ Test 6 Passed: Subsequent successful refresh clears stale banner and updates table.");
    }

    // --- 7. Truthful Empty Database Load ---
    {
        const stateEmpty = reportsLoadSuccess(createInitialReportsState(), []);
        const view = deriveReportsView(stateEmpty);

        assert.equal(stateEmpty.isLoading, false);
        assert.equal(stateEmpty.error, null);
        assert.equal(stateEmpty.reports.length, 0);

        assert.equal(view.showEmpty, true);
        assert.equal(view.showTable, false);
        assert.equal(view.showDedicatedError, false);
        assert.equal(view.showStaleBanner, false);

        testsPassed++;
        console.log("✓ Test 7 Passed: Empty database renders empty state without error or stale banners.");
    }

    // --- 8. Case Response Mapping ---
    {
        const rawCases = [
            {
                case_id: "12345678-abcd-ef01-2345-6789abcdef01",
                defect_name: "Bridging",
                description: "Fallback desc",
                issue_condition: "RESOLVED",
                created_at: "2026-09-20T10:00:00Z",
            },
            {
                case_id: "87654321-dcba-10fe-5432-10fedcba9876",
                defect_name: null,
                description: "Description when no defect name",
                issue_condition: "IssueCondition.INVESTIGATING",
                created_at: null,
            },
        ];

        const mapped = mapCasesToReports(rawCases);
        assert.equal(mapped.length, 2);
        assert.equal(mapped[0].displayId, "RPT-12345678");
        assert.equal(mapped[0].caseRef, "DSP-12345678");
        assert.equal(mapped[0].title, "Bridging");
        assert.equal(mapped[0].status, "Complete");
        assert.equal(mapped[0].isResolved, true);

        assert.equal(mapped[1].displayId, "RPT-87654321");
        assert.equal(mapped[1].title, "Description when no defect name");
        assert.equal(mapped[1].status, "INVESTIGATING");
        assert.equal(mapped[1].isResolved, false);
        assert.equal(mapped[1].date, "Recent");

        testsPassed++;
        console.log("✓ Test 8 Passed: mapCasesToReports correctly maps raw API cases to ReportItem view models.");
    }

    console.log(`\nAll ${testsPassed} reports state regression tests passed successfully.`);
}

runTests();
